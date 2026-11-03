import asyncio
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.config import Config
from starlette.concurrency import run_in_threadpool
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
    # Four. Previously a burst of requests ran up to anyio's 40-token thread pool,
    # because each request spawned its own task. A single download is unaffected;
    # concurrent bursts serialize. 40 restores the previous ceiling.
    "YDL_MAX_CONCURRENT_DOWNLOADS": (int, 4),
    "YDL_JOB_HISTORY": (int, 200),
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
        request, "index.html", {"ytdlp_version": version.__version__}
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
        # Status intentionally stays 200 to preserve the existing API contract;
        # this branch previously crashed with AttributeError instead (pinned by
        # the baseline tests).
        return JSONResponse(
            {"success": False, "error": "/q called without a 'url' in form data"}
        )

    job = store.add(url, options)
    queue.put_nowait(job)

    logger.info("Added url %s to the download queue", url)

    if not ui:
        # job_id is additive: success/url/options are what consumers already read.
        return JSONResponse(
            {"success": True, "url": url, "options": options, "job_id": job["id"]}
        )
    # quote() percent-encodes the url so the added= query param parses correctly
    # on the UI page (previously raw concatenation).
    return RedirectResponse(
        url="/youtube-dl?added=" + quote(url),
        status_code=HTTP_303_SEE_OTHER,
    )


async def update_route(request):
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


class JobStore:
    """Live job record. The durable record is the yt-dlp archive file
    (YDL_ARCHIVE_FILE); this is a bounded in-memory view that a restart clears."""

    def __init__(self, history_limit):
        self.history_limit = history_limit
        self.order = []
        self.counter = 0

    def add(self, url, request_options):
        self.counter += 1
        job = {
            "id": str(self.counter),
            "url": url,
            "options": dict(request_options),
            "status": "queued",
            "error": None,
        }
        self.order.append(job)
        while self.history_limit and len(self.order) > self.history_limit:
            self.order.pop(0)
        return job

    def snapshot(self):
        return [dict(job) for job in self.order]


store = JobStore(app_defaults["YDL_JOB_HISTORY"])
queue = asyncio.Queue()


async def process(job):
    # A failure used to be invisible to the caller: the response had already been sent
    # as success, so a raising download produced a traceback at best and nothing was
    # recorded.
    job["status"] = "running"
    try:
        await run_in_threadpool(download, job["url"], job["options"])
        job["status"] = "done"
    except Exception as exc:
        logger.exception("Download failed for %s", job["url"])
        job["status"] = "failed"
        job["error"] = str(exc)


async def worker():
    while True:
        job = await queue.get()
        await process(job)
        queue.task_done()


@asynccontextmanager
async def lifespan(app):
    # The worker count is the limit. 0 creates no workers, which the test harness uses
    # so queue state is observable without a running loop.
    workers = [
        asyncio.create_task(worker())
        for _ in range(app_defaults["YDL_MAX_CONCURRENT_DOWNLOADS"])
    ]
    yield
    for task in workers:
        task.cancel()


routes = [
    Route("/", endpoint=redirect),
    Route("/healthz", endpoint=healthz),
    Route("/youtube-dl", endpoint=dl_queue_list),
    Route("/youtube-dl/q", endpoint=q_put, methods=["POST"]),
    Route("/youtube-dl/update", endpoint=update_route, methods=["PUT"]),
]

app = Starlette(debug=False, routes=routes, lifespan=lifespan)
