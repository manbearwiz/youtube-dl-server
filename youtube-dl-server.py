import logging
import os
import sys
import subprocess
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
# gains timestamps/levels. Configure via YDL_LOG_LEVEL (see .env.example).
logging.basicConfig(
    level=config("YDL_LOG_LEVEL", default="INFO"),
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("youtube-dl-server")

templates = Jinja2Templates(directory="templates")

app_defaults = {
    "YDL_PROXY": config("YDL_PROXY", default=None) or None,
    "YDL_FORMAT": config("YDL_FORMAT", cast=str, default="bestvideo+bestaudio/best"),
    "YDL_EXTRACT_AUDIO_FORMAT": config("YDL_EXTRACT_AUDIO_FORMAT", default=None),
    "YDL_EXTRACT_AUDIO_QUALITY": config(
        "YDL_EXTRACT_AUDIO_QUALITY", cast=str, default="192"
    ),
    "YDL_RECODE_VIDEO_FORMAT": config("YDL_RECODE_VIDEO_FORMAT", default=None),
    "YDL_OUTPUT_TEMPLATE": config(
        "YDL_OUTPUT_TEMPLATE",
        cast=str,
        default="/youtube-dl/%(title).200s [%(id)s].%(ext)s",
    ),
    "YDL_ARCHIVE_FILE": config("YDL_ARCHIVE_FILE", default=None),
    "YDL_UPDATE_TIME": config("YDL_UPDATE_TIME", cast=bool, default=True),
}


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
            {"status": "unhealthy", "error": f"output directory not writable: {output_dir}"},
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

    task = BackgroundTask(download, url, options)

    logger.info("Added url %s to the download queue", url)

    if not ui:
        return JSONResponse(
            {"success": True, "url": url, "options": options}, background=task
        )
    # quote() percent-encodes the url so the added= query param parses correctly
    # on the UI page (previously raw concatenation).
    return RedirectResponse(
        url="/youtube-dl?added=" + quote(url),
        status_code=HTTP_303_SEE_OTHER,
        background=task,
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


def get_ydl_options(request_options):
    request_vars = {
        "YDL_EXTRACT_AUDIO_FORMAT": None,
        "YDL_RECODE_VIDEO_FORMAT": None,
    }

    requested_format = request_options.get("format", "bestvideo")

    if requested_format in ["aac", "flac", "mp3", "m4a", "opus", "vorbis", "wav"]:
        request_vars["YDL_EXTRACT_AUDIO_FORMAT"] = requested_format
    elif requested_format == "bestaudio":
        request_vars["YDL_EXTRACT_AUDIO_FORMAT"] = "best"
    elif requested_format in ["mp4", "flv", "webm", "ogg", "mkv", "avi"]:
        request_vars["YDL_RECODE_VIDEO_FORMAT"] = requested_format

    ydl_vars = app_defaults | request_vars

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

    return {
        "proxy": ydl_vars["YDL_PROXY"],
        "format": ydl_vars["YDL_FORMAT"],
        "postprocessors": postprocessors,
        "outtmpl": ydl_vars["YDL_OUTPUT_TEMPLATE"],
        "download_archive": ydl_vars["YDL_ARCHIVE_FILE"],
        "updatetime": ydl_vars["YDL_UPDATE_TIME"],
    }


def download(url, request_options):
    with YoutubeDL(get_ydl_options(request_options)) as ydl:
        ydl.download([url])


routes = [
    Route("/", endpoint=redirect),
    Route("/healthz", endpoint=healthz),
    Route("/youtube-dl", endpoint=dl_queue_list),
    Route("/youtube-dl/q", endpoint=q_put, methods=["POST"]),
    Route("/youtube-dl/update", endpoint=update_route, methods=["PUT"]),
]

app = Starlette(debug=False, routes=routes)
