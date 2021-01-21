from __future__ import unicode_literals
from starlette.applications import Starlette
from starlette.staticfiles import StaticFiles
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates
import uvicorn

from ydl_server.logdb import JobsDB, Job, Actions, JobType
from ydl_server import jobshandler, ydlhandler
from ydl_server.config import app_config

from ydl_server.routes import routes


if __name__ == "__main__":

    JobsDB.check_db_latest()
    JobsDB.init_db()

    ydlhandler.start()
    print("Started download thread")
    jobshandler.start(ydlhandler.queue)
    print("Started jobs manager thread")


    print("Updating youtube-dl to the newest version")
    job = Job("Youtube-dl Update", Job.PENDING, "", JobType.YDL_UPDATE, None, None)
    jobshandler.put((Actions.INSERT, job))

    ydlhandler.resume_pending()

    app = Starlette(routes=routes, debug=app_config['ydl_server'].get('debug', False))
    uvicorn.run(app,
                host=app_config['ydl_server'].get('host'),
                port=app_config['ydl_server'].get('port'),
                log_level=('debug' if app_config['ydl_server'].get(
                    'debug', False) else 'info'))

    ydlhandler.finish()
    jobshandler.finish()
    ydlhandler.join()
    jobshandler.join()
