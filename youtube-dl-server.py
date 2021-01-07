from __future__ import unicode_literals

from ydl_server.logdb import JobsDB, Job, Actions, JobType
from ydl_server import jobshandler, ydlhandler, app
from ydl_server.config import app_config

from ydl_server import routes


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

app.run(host=app_config['ydl_server'].get('host'),
        port=app_config['ydl_server'].get('port'),
        debug=app_config['ydl_server'].get('debug', False))

ydlhandler.finish()
jobshandler.finish()
ydlhandler.join()
jobshandler.join()