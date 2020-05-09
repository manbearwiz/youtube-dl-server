from __future__ import unicode_literals
import json
import os
from collections import ChainMap
from queue import Queue
from bottle import route, run, Bottle, request, static_file, template
from threading import Thread
from pathlib import Path
from ydl_server.logdb import JobsDB, Job, Actions
from ydl_server import jobshandler, ydlhandler
from ydl_server.config import app_defaults

app = Bottle()


@app.route(['/', '/index'])
def front_index():
    return template('./ydl_server/templates/index.html',
            ydl_version=ydlhandler.get_ydl_version())

@app.route('/logs')
def front_logs():
    return template('./ydl_server/templates/logs.html',
            ydl_version=ydlhandler.get_ydl_version())

@app.route('/static/:filename#.*#')
def server_static(filename):
    return static_file(filename, root='./ydl_server/static')

@app.route('/api/downloads/stats', method='GET')
def api_queue_size():
    db = JobsDB(readonly=True)
    jobs = db.get_all()
    return {
        "success": True,
        "stats": {
            "queue": ydlhandler.queue.qsize(),
            "pending": len([job for job in jobs if job['status'] == "Pending"]),
            "running": len([job for job in jobs if job['status'] == "Running"]),
            "completed": len([job for job in jobs if job['status'] == "Completed"]),
            "failed": len([job for job in jobs if job['status'] == "Failed"])
        }
    }

@app.route('/api/downloads', method='GET')
def api_logs():
    db = JobsDB(readonly=True)
    return json.dumps(db.get_all())

@app.route('/api/downloads', method='DELETE')
def api_logs_purge():
    jobshandler.put((Actions.PURGE_LOGS, None))
    return {"success": True}


@app.route('/api/downloads', method='POST')
def api_queue_download():
    url = request.forms.get("url")
    options = {'format': request.forms.get("format")}

    if not url:
        return {"success": False, "error": "'url' query parameter omitted"}

    job = Job(url, Job.PENDING, "", request.forms.get("format"))
    jobshandler.put((Actions.INSERT, job))

    print("Added url " + url + " to the download queue")
    return {"success": True, "url": url, "options": options}

@app.route('/api/youtube-dl/version')
def ydl_version():
    return {'version': youtube_dl.version.__version__}

@app.route("/youtube-dl/update", method="GET")
def ydl_update():
    return ydlhandler.update()

JobsDB.init_db()

ydlhandler.start()
print("Started download thread")
jobshandler.start(ydlhandler.queue)
print("Started jobs manager thread")

ydlhandler.resume_pending()

print("Updating youtube-dl to the newest version")
updateResult = ydlhandler.update()
print(updateResult["output"])
print(updateResult["error"])

app_vars = ChainMap(os.environ, app_defaults)

app.run(host=app_vars['YDL_SERVER_HOST'],
        port=app_vars['YDL_SERVER_PORT'],
        debug=app_vars['YDL_DEBUG'])
ydlhandler.finish()
jobshandler.finish()
ydlhandler.thread.join()
jobshandler.thread.join()
