from pathlib import Path

from ydl_server import views
from ydl_server.config import app_config, get_finished_path

from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

static = StaticFiles(directory=str(Path(__file__).parent / "static"))

finished_files = StaticFiles(directory=get_finished_path())

routes = [
    Route("/", views.front_index, name="index"),
    Route("/index", views.front_index, name="index"),
    Route("/logs", views.front_logs, name="logs"),
    Route("/finished", views.front_finished, name="finished"),
    Route("/api/finished", views.api_list_finished, name="api_list_finished"),
    Route("/api/extractors",
          views.api_list_extractors,
          name="api_list_extractors"),
    Route("/api/youtube-dl/update", views.ydl_update, name="api_update"),
    Route("/api/downloads/stats", views.api_queue_size, name="api_queue_size"),
    Route("/api/downloads", views.api_logs, name="api_logs"),
    Route("/api/downloads/clean", views.api_logs_clean, name="api_logs_clean"),
    Route("/api/downloads",
          views.api_logs_purge,
          name="api_logs_purge",
          methods=['DELETE']),
    Route("/api/downloads",
          views.api_queue_download,
          name="api_queue_download",
          methods=['POST']),
    Route("/api/metadata",
          views.api_metadata_fetch,
          name="api_metadata_fetch",
          methods=['POST']),
    Mount("/static", static, name="static"),
    Mount("/api/finished/", finished_files, name="api_finished"),
]