import sys
import subprocess

from starlette.status import HTTP_303_SEE_OTHER
from starlette.applications import Starlette
from starlette.config import Config
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette.background import BackgroundTask

from yt_dlp import YoutubeDL, version

templates = Jinja2Templates(directory="templates")
config = Config(".env")

app_defaults = {
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
        "index.html", {"request": request, "ytdlp_version": version.__version__}
    )


async def redirect(request):
    return RedirectResponse(url="/youtube-dl")


async def q_put(request):
    form = await request.form()
    url = form.get("url").strip()
    ui = form.get("ui")
    options = {"format": form.get("format")}

    if not url:
        return JSONResponse(
            {"success": False, "error": "/q called without a 'url' in form data"}
        )

    task = BackgroundTask(download, url, options)

    print("Added url " + url + " to the download queue")

    if not ui:
        return JSONResponse(
            {"success": True, "url": url, "options": options}, background=task
        )
    return RedirectResponse(
        url="/youtube-dl?added=" + url, status_code=HTTP_303_SEE_OTHER, background=task
    )


async def update_route(scope, receive, send):
    task = BackgroundTask(update)

    return JSONResponse({"output": "Initiated package update"}, background=task)


def update():
    try:
        output = subprocess.check_output(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
        )

        print(output.decode("utf-8"))
    except subprocess.CalledProcessError as e:
        print(e.output)


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

    options = {
        "format": ydl_vars["YDL_FORMAT"],
        "postprocessors": postprocessors,
        "outtmpl": ydl_vars["YDL_OUTPUT_TEMPLATE"],
        "download_archive": ydl_vars["YDL_ARCHIVE_FILE"],
        "updatetime": ydl_vars["YDL_UPDATE_TIME"] == "True",
    }

    if ydl_vars["YDL_COOKIE_FILE"]:
        options["cookiefile"] = f"/youtube-dl/{ydl_vars['YDL_COOKIE_FILE']}"

    return options

def download(url, request_options):
    with YoutubeDL(get_ydl_options(request_options)) as ydl:
        ydl.download([url])


routes = [
    Route("/", endpoint=redirect),
    Route("/youtube-dl", endpoint=dl_queue_list),
    Route("/youtube-dl/q", endpoint=q_put, methods=["POST"]),
    Route("/youtube-dl/update", endpoint=update_route, methods=["PUT"]),
]

app = Starlette(debug=True, routes=routes)

print("Updating youtube-dl to the newest version")
update()
