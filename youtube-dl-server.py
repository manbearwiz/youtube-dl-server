import asyncio
import json
import logging
import os
import sys
import subprocess
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.config import Config
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette.background import BackgroundTask
from starlette.status import HTTP_303_SEE_OTHER

from yt_dlp import YoutubeDL, version

config = Config(".env")

# Logging stays on stdout so existing log scrapers keep working; the format
# gains timestamps/levels. Configure via YDL_LOG_LEVEL (see .env.example). The
# logger's own level is the one option resolved before the table below, because
# handlers must be configured before resolving can log a warning.
logging.basicConfig(
    level=config("YDL_LOG_LEVEL", default="INFO"),
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("youtube-dl-server")


def split_langs(value):
    # yt-dlp expects subtitleslangs as a list; a comma-separated env value is the
    # natural spelling here (and "all" is yt-dlp's own special value).
    return [lang.strip() for lang in value.split(",") if lang.strip()]


# Options are data, not per-option code: name -> (cast, default). Resolution
# order is the process environment, then the .env file, then the default.
OPTIONS = {
    "YDL_FORMAT": (str, "bestvideo+bestaudio/best"),
    "YDL_EXTRACT_AUDIO_FORMAT": (str, None),
    "YDL_EXTRACT_AUDIO_QUALITY": (str, "192"),
    "YDL_RECODE_VIDEO_FORMAT": (str, None),
    "YDL_OUTPUT_TEMPLATE": (str, "/youtube-dl/%(title).200s [%(id)s].%(ext)s"),
    "YDL_ARCHIVE_FILE": (str, None),
    "YDL_UPDATE_TIME": (bool, True),
    "YDL_PROXY": (str, None),
    "YDL_COOKIE_FILE": (str, None),
    "YDL_WRITE_SUBTITLES": (bool, False),
    "YDL_SUBTITLES_LANGS": (split_langs, None),
    "YDL_WRITE_THUMBNAIL": (bool, False),
    "YDL_EMBED_METADATA": (bool, False),
    "YDL_UPDATE_CHECK": (bool, False),
    "YDL_UPDATE_CHECK_INTERVAL": (int, 86400),
}


def resolve(key, cast, default):
    # An empty value means "not set": an env file cannot distinguish absent from
    # empty, and yt-dlp checks these options with `is not None` (an empty
    # cookiefile would be a file literally named "").
    #
    # An unparseable value warns and falls back to the documented default instead
    # of raising -- starlette's cast=bool accepts only true/1/false/0 and raises
    # ValueError for anything else, including an empty value, which crashed the
    # app at import time (a container restart loop with no clear message).
    try:
        value = config(key, cast=cast, default=default)
    except ValueError as exc:
        logger.warning("Ignoring %s: %s (using default %r)", key, exc, default)
        return default
    return default if value == "" else value


app_defaults = {
    key: resolve(key, cast, default) for key, (cast, default) in OPTIONS.items()
}

templates = Jinja2Templates(directory="templates")


async def dl_queue_list(request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"ytdlp_version": version.__version__, "update": update_status},
    )


async def redirect(request):
    return RedirectResponse(url="/youtube-dl")


async def healthz(request):
    # Readiness probe: the app responds and the output volume is writable,
    # which is the most common operational failure for this service. No
    # external network calls -- health checks should stay local and cheap.
    output_dir = os.path.dirname(app_defaults["YDL_OUTPUT_TEMPLATE"]) or "."
    if not os.path.isdir(output_dir) or not os.access(output_dir, os.W_OK):
        return JSONResponse(
            {
                "status": "unhealthy",
                "error": f"output directory not writable: {output_dir}",
            },
            status_code=503,
        )
    return JSONResponse({"status": "ok"})


async def q_put(request):
    form = await request.form()
    url = (form.get("url") or "").strip()
    ui = form.get("ui")
    options = {"format": form.get("format")}

    if not url:
        # Status stays 200: the API contract for a missing url is a JSON error
        # body.
        return JSONResponse(
            {"success": False, "error": "/q called without a 'url' in form data"}
        )

    task = BackgroundTask(download, url, options)

    logger.info("Added url %s to the download queue", url)

    if not ui:
        return JSONResponse(
            {"success": True, "url": url, "options": options}, background=task
        )
    # percent-encoding makes the added= query param parse correctly on the UI
    # page.
    return RedirectResponse(
        url="/youtube-dl?added=" + quote(url),
        status_code=HTTP_303_SEE_OTHER,
        background=task,
    )


async def update_route(request):
    if request.method == "GET":
        return JSONResponse(dict(update_status))

    task = BackgroundTask(update)

    return JSONResponse({"output": "Initiated package update"}, background=task)


def update():
    try:
        output = subprocess.check_output(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
        )

        logger.info("yt-dlp update: %s", output.decode("utf-8"))
    except subprocess.CalledProcessError as e:
        logger.error("yt-dlp update failed: %s", e.output)


PYPI_JSON_URL = "https://pypi.org/pypi/yt-dlp/json"
MIN_CHECK_INTERVAL = 60

# What the last check found. This never installs anything: the record is read by
# GET /youtube-dl/update and by the queue page, and an upgrade happens only through
# the explicit PUT /youtube-dl/update.
update_status = {
    "current": version.__version__,
    "latest": None,
    "checked_at": None,
    "update_available": False,
}


def version_tuple(value):
    # Dotted numeric segments as an int tuple, so 2026.10.26.1 orders after
    # 2026.10.26. A segment that is not numeric is not comparable.
    parts = value.split(".")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def check_interval():
    # The floor keeps a mis-set interval from turning the check into a loop against
    # the index.
    return max(app_defaults["YDL_UPDATE_CHECK_INTERVAL"], MIN_CHECK_INTERVAL)


def fetch_latest():
    with urllib.request.urlopen(PYPI_JSON_URL, timeout=10) as response:
        return json.load(response)["info"]["version"]


async def check_update():
    try:
        latest = await asyncio.to_thread(fetch_latest)
    except Exception as exc:
        # Logged, not reported: a deployment without outbound access, or a failed
        # request, looks to a client exactly like an up-to-date one.
        logger.warning("yt-dlp update check failed: %s", exc)
        return

    current = version.__version__
    current_tuple, latest_tuple = version_tuple(current), version_tuple(latest)
    if current_tuple is None or latest_tuple is None:
        logger.warning("Cannot compare yt-dlp versions %s and %s", current, latest)
        return

    update_status["current"] = current
    update_status["latest"] = latest
    update_status["checked_at"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    update_status["update_available"] = latest_tuple > current_tuple
    if update_status["update_available"]:
        logger.info("yt-dlp update available: %s (running %s)", latest, current)


async def update_check_loop():
    interval = check_interval()
    while True:
        await asyncio.sleep(interval)
        await check_update()


# A request's `format` field names a postprocessor, not yt-dlp's format selector
# (that is the YDL_FORMAT option). Values outside these lists select nothing.
REQUEST_AUDIO_FORMATS = {
    "aac": "aac",
    "flac": "flac",
    "mp3": "mp3",
    "m4a": "m4a",
    "opus": "opus",
    "vorbis": "vorbis",
    "wav": "wav",
    # yt-dlp's own "keep the best audio codec, do not convert" spelling
    "bestaudio": "best",
}
REQUEST_RECODE_FORMATS = {"mp4", "flv", "webm", "ogg", "mkv", "avi"}


def get_ydl_options(request_options):
    # The env values are defaults: they apply when the request names no codec or
    # container. A request that names one selects a single pipeline, so it wins over
    # the env default for both kinds (ffmpeg would otherwise recode an extracted
    # audio file into a video container).
    ydl_vars = dict(app_defaults)
    requested_format = request_options.get("format")

    if requested_format in REQUEST_AUDIO_FORMATS:
        ydl_vars["YDL_EXTRACT_AUDIO_FORMAT"] = REQUEST_AUDIO_FORMATS[requested_format]
        ydl_vars["YDL_RECODE_VIDEO_FORMAT"] = None
    elif requested_format in REQUEST_RECODE_FORMATS:
        ydl_vars["YDL_RECODE_VIDEO_FORMAT"] = requested_format
        ydl_vars["YDL_EXTRACT_AUDIO_FORMAT"] = None

    postprocessors = []

    if ydl_vars["YDL_EXTRACT_AUDIO_FORMAT"]:
        postprocessors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": ydl_vars["YDL_EXTRACT_AUDIO_FORMAT"],
                "preferredquality": ydl_vars["YDL_EXTRACT_AUDIO_QUALITY"],
            }
        )

    if ydl_vars["YDL_RECODE_VIDEO_FORMAT"]:
        postprocessors.append(
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": ydl_vars["YDL_RECODE_VIDEO_FORMAT"],
            }
        )

    if ydl_vars["YDL_EMBED_METADATA"]:
        # After the converters, the same order yt-dlp uses: containers before
        # conversion may not carry metadata (3gp, webm).
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})

    options = {
        "format": ydl_vars["YDL_FORMAT"],
        "postprocessors": postprocessors,
        "outtmpl": ydl_vars["YDL_OUTPUT_TEMPLATE"],
        "download_archive": ydl_vars["YDL_ARCHIVE_FILE"],
        "cookiefile": ydl_vars["YDL_COOKIE_FILE"],
        "proxy": ydl_vars["YDL_PROXY"],
        "updatetime": ydl_vars["YDL_UPDATE_TIME"],
        "writesubtitles": ydl_vars["YDL_WRITE_SUBTITLES"],
        "writethumbnail": ydl_vars["YDL_WRITE_THUMBNAIL"],
    }

    # Only pass languages the operator asked for. Passing None would override
    # yt-dlp's own default language selection, and the value must be a list.
    if ydl_vars["YDL_SUBTITLES_LANGS"]:
        options["subtitleslangs"] = ydl_vars["YDL_SUBTITLES_LANGS"]

    return options


def download(url, request_options):
    with YoutubeDL(get_ydl_options(request_options)) as ydl:
        ydl.download([url])


routes = [
    Route("/", endpoint=redirect),
    Route("/healthz", endpoint=healthz),
    Route("/youtube-dl", endpoint=dl_queue_list),
    Route("/youtube-dl/q", endpoint=q_put, methods=["POST"]),
    Route("/youtube-dl/update", endpoint=update_route, methods=["GET", "PUT"]),
]


@asynccontextmanager
async def lifespan(app):
    task = None
    if app_defaults["YDL_UPDATE_CHECK"]:
        # The first check is awaited, so the record is populated before the first
        # request. Startup makes no network call while the check is off, which is the
        # default.
        await check_update()
        task = asyncio.create_task(update_check_loop())
    yield
    if task is not None:
        task.cancel()


app = Starlette(debug=False, routes=routes, lifespan=lifespan)
