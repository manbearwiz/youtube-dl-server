from contextlib import asynccontextmanager

import uvicorn
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from ydl_server.config import app_config
from ydl_server.db import JobsDB
from ydl_server.jobshandler import JobsHandler
from ydl_server.routes import routes
from ydl_server.ydlhandler import YdlHandler


def main():
    JobsDB.init()

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            await run_in_threadpool(shutdown)

    middleware = [Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])]

    app = Starlette(
        routes=routes,
        debug=app_config["ydl_server"].get("debug", False),
        middleware=middleware,
        lifespan=lifespan,
    )

    app.state.running = True
    app.state.jobshandler = JobsHandler(app_config)
    app.state.ydlhandler = YdlHandler(app_config, app.state.jobshandler)

    def shutdown():
        if not app.state.running:
            return
        print("Shutting down...")
        app.state.running = False
        app.state.ydlhandler.shutdown()
        print("Shutdown complete.")

    app.state.ydlhandler.start()
    print("Started download threads")
    app.state.jobshandler.start(app.state.ydlhandler.queue)
    print("Started jobs manager thread")

    app.state.ydlhandler.resume_pending()

    try:
        uvicorn.run(
            app,
            host=app_config["ydl_server"].get("host"),
            port=app_config["ydl_server"].get("port"),
            log_level=("debug" if app_config["ydl_server"].get("debug", False) else "info"),
            forwarded_allow_ips=app_config["ydl_server"].get("forwarded_allow_ips", None),
            proxy_headers=app_config["ydl_server"].get("proxy_headers", True),
            timeout_graceful_shutdown=app_config["ydl_server"].get("shutdown_timeout", 5),
        )
    finally:
        shutdown()


if __name__ == "__main__":
    main()
