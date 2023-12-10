from pathlib import Path

from ydl_server import views
from ydl_server.config import get_finished_path

from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

static = StaticFiles(directory=str(Path(__file__).parent / "static"), html=True)

finished_files = StaticFiles(directory=get_finished_path())

routes = [
    Route("/api/extractors", views.api_list_extractors, name="api_list_extractors"),
    Route("/api/formats", views.api_list_formats, name="api_list_formats"),
    Route("/api/info", views.api_server_info, name="api_server_info"),
    Route("/api/downloads/stats", views.api_queue_size, name="api_queue_size"),
    Route("/api/downloads", views.api_logs, name="api_logs"),
    Route("/api/downloads/clean", views.api_logs_clean, name="api_logs_clean"),
    Route(
        "/api/downloads",
        views.api_logs_purge,
        name="api_logs_purge",
        methods=["DELETE"],
    ),
    Route(
        "/api/downloads",
        views.api_queue_download,
        name="api_queue_download",
        methods=["POST"],
    ),
    Route(
        "/api/metadata",
        views.api_metadata_fetch,
        name="api_metadata_fetch",
        methods=["POST"],
    ),
    Route("/api/finished", views.api_finished, name="api_finished", methods=["GET"]),
    Route(
        "/api/finished/{fname:path}",
        views.api_delete_file,
        name="api_delete_file",
        methods=["DELETE"],
    ),
    Route(
        "/api/jobs/{job_id:str}/stop",
        views.api_jobs_stop,
        name="api_jobs_stop",
        methods=["POST"],
    ),
    Route(
        "/api/jobs/{job_id:str}/retry",
        views.api_jobs_retry,
        name="api_jobs_retry",
        methods=["POST"],
    ),
    Mount("/api/finished/", finished_files, name="api_finished"),
    Mount("/", static, name="static"),
]
