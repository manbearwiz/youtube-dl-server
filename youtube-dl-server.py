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
    "YDL_MERGE_OUTPUT_FORMAT": config("YDL_MERGE_OUTPUT_FORMAT", default=None),
    "YDL_OUTPUT_TEMPLATE": config(
        "YDL_OUTPUT_TEMPLATE",
        cast=str,
        default="/youtube-dl/%(title).200s [%(id)s].%(ext)s",
    ),
    "YDL_NO_PLAYLIST": config("YDL_NO_PLAYLIST", cast=bool, default=True),
    "YDL_ARCHIVE_FILE": config("YDL_ARCHIVE_FILE", default=None),
    "YDL_COOKIES_FILE": config("YDL_COOKIES_FILE", default=None),
    "YDL_COOKIES_BROWSER": config("YDL_COOKIES_BROWSER", default=None),
    "YDL_UPDATE_TIME": config("YDL_UPDATE_TIME", cast=bool, default=True),
    "YDL_IGNORE_ERRORS": config("YDL_IGNORE_ERRORS", default=True),
    "YDL_RESTRICT_FILENAMES": config("YDL_RESTRICT_FILENAMES", cast=bool, default=False),
    "YDL_GEO_BYPASS": config("YDL_GEO_BYPASS", cast=bool, default=False),
    "YDL_WRITE_THUMBNAIL": config("YDL_WRITE_THUMBNAIL", cast=bool, default=True),
    "YDL_THUMBNAIL_FORMAT": config("YDL_THUMBNAIL_FORMAT", default=None),
    "YDL_WRITE_SUBTITLES": config("YDL_WRITE_SUBTITLES", cast=bool, default=False),
    "YDL_SUBTITLES_FORMAT": config("YDL_SUBTITLES_FORMAT", default=None),
    "YDL_CONVERT_SUBTITLES": config("YDL_CONVERT_SUBTITLES", default=None),
    "YDL_SUBTITLES_LANGS": config("YDL_SUBTITLES_LANGS", cast=str, default="all"),
    "YDL_EMBED_METADATA": config("YDL_EMBED_METADATA", cast=bool, default=False),
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

    if ydl_vars["YDL_WRITE_THUMBNAIL"] == True:
        postprocessors.append(
            {
                "key": "EmbedThumbnail",
                "already_have_thumbnail": False,
            }
        )

    if ydl_vars["YDL_THUMBNAIL_FORMAT"]:
        postprocessors.append(
            {
                "key": "FFmpegThumbnailsConvertor",
                "format": ydl_vars["YDL_THUMBNAIL_FORMAT"],
                "when": "before_dl",
            }
        )

    if ydl_vars["YDL_WRITE_SUBTITLES"] == True:
        postprocessors.append(
            {
                "key": "FFmpegEmbedSubtitle",
                "already_have_subtitle": False,
            }
        )

    if ydl_vars["YDL_CONVERT_SUBTITLES"]:
        postprocessors.append(
            {
                "key": "FFmpegSubtitlesConvertor",
                "format": ydl_vars["YDL_CONVERT_SUBTITLES"],
                "when": "post_process",
            }
        )

    if ydl_vars["YDL_EMBED_METADATA"] == True:
        postprocessors.append(
            {
                "key": "FFmpegMetadata",
                "add_infojson": "if_exists",
                "add_metadata": True,
                "add_chapters": True,
            }
        )

    return {
        "format": ydl_vars["YDL_FORMAT"],
        "merge_output_format": ydl_vars["YDL_MERGE_OUTPUT_FORMAT"],
        "postprocessors": postprocessors,
        "outtmpl": ydl_vars["YDL_OUTPUT_TEMPLATE"],
        "noplaylist": ydl_vars["YDL_NO_PLAYLIST"],
        "download_archive": ydl_vars["YDL_ARCHIVE_FILE"],
        "cookiefile": ydl_vars["YDL_COOKIES_FILE"],
        "cookiesfrombrowser": ydl_vars["YDL_COOKIES_BROWSER"],
        "updatetime": ydl_vars["YDL_UPDATE_TIME"] == "True",
        "ignoreerrors": ydl_vars["YDL_IGNORE_ERRORS"],
        "restrictfilenames": ydl_vars["YDL_RESTRICT_FILENAMES"],
        "geo_bypass": ydl_vars["YDL_GEO_BYPASS"],
        "writethumbnail": ydl_vars["YDL_WRITE_THUMBNAIL"],
        "writesubtitles": ydl_vars["YDL_WRITE_SUBTITLES"],
        "subtitlesformat": ydl_vars["YDL_SUBTITLES_FORMAT"],
        "subtitleslangs": list(ydl_vars["YDL_SUBTITLES_LANGS"].split(",")),
    }


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
