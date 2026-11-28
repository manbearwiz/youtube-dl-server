import asyncio
import json
import logging
import optparse
import os
import subprocess
import sys
import urllib.request
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.config import Config
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route
from starlette.status import HTTP_303_SEE_OTHER
from starlette.templating import Jinja2Templates
from yt_dlp import YoutubeDL, parse_options, version

try:
    # yt-dlp's own config file reader and lookup. They are not part of its public
    # API, which reads config files only for its own command line, so if an upgrade
    # moves them the server runs without config files instead of failing to start.
    from yt_dlp.utils import Config as YtdlpConfig
    from yt_dlp.utils import get_system_config_dirs, get_user_config_dirs
except ImportError:
    YtdlpConfig = None

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
# order is the process environment, then the .env file, then a yt-dlp config file
# for the options yt-dlp has (YDL_ARGS below), then the default.
OPTIONS = {
    "YDL_FORMAT": (str, "bestvideo+bestaudio/best"),
    "YDL_EXTRACT_AUDIO_FORMAT": (str, None),
    "YDL_EXTRACT_AUDIO_QUALITY": (str, "192"),
    "YDL_RECODE_VIDEO_FORMAT": (str, None),
    "YDL_OUTPUT_TEMPLATE": (str, "/youtube-dl/%(title).200s [%(id)s].%(ext)s"),
    "YDL_ARCHIVE_FILE": (str, None),
    "YDL_UPDATE_TIME": (bool, True),
    "YDL_IGNORE_ERRORS": (bool, False),
    "YDL_PROXY": (str, None),
    "YDL_COOKIE_FILE": (str, None),
    "YDL_WRITE_SUBTITLES": (bool, False),
    "YDL_SUBTITLES_LANGS": (split_langs, None),
    "YDL_WRITE_THUMBNAIL": (bool, False),
    "YDL_EMBED_METADATA": (bool, False),
    "YDL_UPDATE_CHECK": (bool, False),
    "YDL_UPDATE_CHECK_INTERVAL": (int, 86400),
}


def flag(name):
    # A comma-separated list is yt-dlp's own spelling for list values (--sub-langs).
    return lambda value: [name, ",".join(value) if isinstance(value, list) else value]


def switch(on, off):
    return lambda value: [on if value else off]


# The yt-dlp command-line arguments for each option yt-dlp has. yt-dlp turns them
# into its params together with the config files, the way its own command line
# does, so a config file and these options combine by yt-dlp's rules.
YDL_ARGS = {
    "YDL_FORMAT": flag("-f"),
    "YDL_EXTRACT_AUDIO_FORMAT": lambda value: ["-x", "--audio-format", value],
    "YDL_EXTRACT_AUDIO_QUALITY": flag("--audio-quality"),
    "YDL_RECODE_VIDEO_FORMAT": flag("--recode-video"),
    "YDL_OUTPUT_TEMPLATE": flag("-o"),
    "YDL_ARCHIVE_FILE": flag("--download-archive"),
    "YDL_UPDATE_TIME": switch("--mtime", "--no-mtime"),
    "YDL_IGNORE_ERRORS": switch("--ignore-errors", "--abort-on-error"),
    "YDL_PROXY": flag("--proxy"),
    "YDL_COOKIE_FILE": flag("--cookies"),
    "YDL_WRITE_SUBTITLES": switch("--write-subs", "--no-write-subs"),
    "YDL_SUBTITLES_LANGS": flag("--sub-langs"),
    "YDL_WRITE_THUMBNAIL": switch("--write-thumbnail", "--no-write-thumbnail"),
    "YDL_EMBED_METADATA": switch("--embed-metadata", "--no-embed-metadata"),
}


def to_args(values):
    # None is unset, which leaves yt-dlp's own default (e.g. its proxy discovery).
    return [
        arg
        for key, value in values.items()
        if value is not None
        for arg in YDL_ARGS[key](value)
    ]


def parse_error(exc):
    # yt-dlp's message is the last line, after its usage text and the program name
    # ("uvicorn: error: no such option: ...").
    message = str(exc).strip().rpartition("\n")[2]
    return message.partition(": error: ")[2] or message


def setting(key, cast, default):
    # The value the environment or the .env file sets, or None when neither sets
    # one. An empty value means "not set": an env file cannot distinguish absent
    # from empty, and yt-dlp checks these options with `is not None` (an empty
    # cookiefile would be a file literally named "").
    #
    # An unparseable value warns and counts as not set instead of raising --
    # starlette's cast=bool accepts only true/1/false/0 and raises ValueError for
    # anything else, which crashed the app at import time (a container restart
    # loop with no clear message). yt-dlp checks the values it takes the same way
    # it checks its command line, so a bad one cannot fail every download.
    if config(key, default="") == "":
        return None
    try:
        value = config(key, cast=cast)
        if value == []:  # a list of nothing, e.g. YDL_SUBTITLES_LANGS=","
            return None
        if key in YDL_ARGS:
            parse_options(to_args({key: value}))
    except (ValueError, optparse.OptParseError) as exc:
        logger.warning(
            "Ignoring %s: %s (using default %r)", key, parse_error(exc), default
        )
        return None
    return value


def resolve(key, cast, default):
    value = setting(key, cast, default)
    return default if value is None else value


# The options the environment or the .env file sets. A yt-dlp config file cannot
# override these, only the defaults.
settings = {
    key: value
    for key, (cast, default) in OPTIONS.items()
    if (value := setting(key, cast, default)) is not None
}
app_defaults = {
    key: settings.get(key, default) for key, (_, default) in OPTIONS.items()
}


def read_config_files():
    # yt-dlp's own lookup for its system and user config files: in the image,
    # /etc/yt-dlp/config and the mounted /root/.config/yt-dlp/config. The first file
    # found in each is read, and the user's comes later, so it wins.
    if YtdlpConfig is None:
        logger.warning("This yt-dlp has no config file reader; ignoring config files")
        return []
    args = []
    for dirs in (get_system_config_dirs("yt-dlp"), get_user_config_dirs("yt-dlp")):
        paths = [
            path
            for d in dirs
            for path in (
                os.path.join(os.path.dirname(d), "yt-dlp.conf"),
                os.path.join(d, "config"),
                os.path.join(d, "config.txt"),
            )
        ]
        for path in paths:
            try:
                found = YtdlpConfig.read_file(path, default=None)
            except (OSError, ValueError) as exc:
                logger.warning("Ignoring yt-dlp config file %s: %s", path, exc)
                continue
            if found is not None:
                # The path only: a config file can hold credentials.
                logger.info("Using yt-dlp config file %s", path)
                args += found
                break

    # Checked once here, so a file yt-dlp cannot parse warns and is skipped, as a
    # bad option value is, instead of failing every download.
    try:
        parse_options(args)
    except optparse.OptParseError as exc:
        logger.warning("Ignoring yt-dlp config files: %s", parse_error(exc))
        return []
    except SystemExit:
        logger.warning("Ignoring yt-dlp config files: they make yt-dlp exit")
        return []
    return args


config_args = read_config_files()

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
    # external network calls -- health checks should stay local and cheap. The
    # output template is the one downloads use, so a config file's -o counts.
    outtmpl = get_ydl_options({})["outtmpl"]["default"]
    output_dir = os.path.dirname(outtmpl) or "."
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
    except Exception as exc:  # noqa: BLE001 - any failure here must not break the app
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
    update_status["checked_at"] = datetime.now(UTC).isoformat(timespec="seconds")
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

# The postprocessors that convert the downloaded file into another format.
CONVERTERS = {"FFmpegExtractAudio", "FFmpegVideoConvertor", "FFmpegVideoRemuxer"}


def request_args(requested_format):
    if requested_format in REQUEST_AUDIO_FORMATS:
        return ["-x", "--audio-format", REQUEST_AUDIO_FORMATS[requested_format]]
    if requested_format in REQUEST_RECODE_FORMATS:
        return ["--recode-video", requested_format]
    return []


def get_ydl_options(request_options):
    # One yt-dlp command line, lowest precedence first, as yt-dlp orders a config
    # file before its own arguments: the defaults, the config files, the options
    # the environment sets, then the request's format. yt-dlp builds the params
    # from it, postprocessors in its own order included.
    defaults = {key: app_defaults[key] for key in YDL_ARGS if key not in settings}
    chosen = {key: settings[key] for key in YDL_ARGS if key in settings}
    requested = request_args(request_options.get("format"))
    options = parse_options(
        [*to_args(defaults), *config_args, *to_args(chosen), *requested]
    ).ydl_opts

    if requested:
        # A request that names a codec or container selects the one pipeline, so it
        # replaces the other conversions (ffmpeg would otherwise recode an extracted
        # audio file into a video container). yt-dlp's -x has no negation, so they
        # are dropped here, and the final extension is the request's.
        own = "FFmpegExtractAudio" if requested[0] == "-x" else "FFmpegVideoConvertor"
        options["postprocessors"] = [
            pp
            for pp in options["postprocessors"]
            if pp["key"] not in CONVERTERS or pp["key"] == own
        ]
        options["final_ext"] = parse_options(requested).ydl_opts.get("final_ext")

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
