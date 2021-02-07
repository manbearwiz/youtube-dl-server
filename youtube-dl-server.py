from __future__ import unicode_literals
from starlette.applications import Starlette
from starlette.staticfiles import StaticFiles
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates
import uvicorn

from ydl_server.logdb import JobsDB, Job, Actions, JobType

from ydl_server.ydlhandler import YdlHandler
from ydl_server.jobshandler import JobsHandler
from ydl_server.config import app_config

from ydl_server.routes import routes


if __name__ == "__main__":

    JobsDB.check_db_latest()
    JobsDB.init_db()

    app = Starlette(routes=routes, debug=app_config['ydl_server'].get('debug', False))

    app.state.jobshandler = JobsHandler(app_config)
    app.state.ydlhandler = YdlHandler(app_config, app.state.jobshandler)

    app.state.ydlhandler.start()
    print("Started download thread")
    app.state.jobshandler.start(app.state.ydlhandler.queue)
    print("Started jobs manager thread")


    print("Updating youtube-dl to the newest version")
    job = Job("Youtube-dl Update", Job.PENDING, "", JobType.YDL_UPDATE, None, None)
    app.state.jobshandler.put((Actions.INSERT, job))

    app.state.ydlhandler.resume_pending()
    
    uvicorn.run(app,
                host=app_config['ydl_server'].get('host'),
                port=app_config['ydl_server'].get('port'),
                log_level=('debug' if app_config['ydl_server'].get(
                    'debug', False) else 'info'),
                forwarded_allow_ips=app_config['ydl_server'].get('forwarded_allow_ips', None),
                proxy_headers=app_config['ydl_server'].get('proxy_headers', True))

    app.state.ydlhandler.finish()
    app.state.jobshandler.finish()
    app.state.ydlhandler.join()
    app.state.jobshandler.join()
