from __future__ import unicode_literals
import json
import os
from collections import ChainMap
from itertools import chain
from operator import itemgetter
from queue import Queue
from bottle import route, run, Bottle, request, static_file, template
from threading import Thread
from pathlib import Path
from ydl_server.logdb import JobsDB, Job, Actions, JobType
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

@app.route('/finished')
def front_finished():
    return template('./ydl_server/templates/finished.html',
            ydl_version=ydlhandler.get_ydl_version())


@app.route('/api/finished')
def api_list_finished():
    root_dir = Path(app_vars['YDL_OUTPUT_TEMPLATE']).parent
    matches = root_dir.glob('*')

    files = [{'name': f1.name,
            'modified': f1.stat().st_mtime * 1000,
            'children': sorted([{
                'name': f2.name,
                'modified': f2.stat().st_mtime * 1000
                } for f2 in f1.iterdir() if not f2.name.startswith('.')] if f1.is_dir() else [], key=itemgetter('modified'), reverse=True)
            } for f1 in matches if not f1.name.startswith('.')]

    files = sorted(files, key=itemgetter('modified'), reverse=True)
    return {
        "success": True,
        "files": files
        }

@app.route('/api/finished/:filename#.*#')
def api_serve_finished_file(filename):
    root_dir = Path(app_vars['YDL_OUTPUT_TEMPLATE']).parent
    return static_file(filename, root=root_dir)

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

    job = Job(url, Job.PENDING, "", JobType.YDL_DOWNLOAD, request.forms.get("format"), url)
    jobshandler.put((Actions.INSERT, job))

    print("Added url " + url + " to the download queue")
    return {"success": True, "url": url, "options": options}

@app.route('/api/metadata', method='POST')
def api_metadata_fetch():
    url = request.forms.get("url")
    return ydlhandler.fetch_metadata(url)

@app.route("/api/youtube-dl/update", method="GET")
def ydl_update():
    job = Job("Youtube-dl Update", Job.PENDING, "", JobType.YDL_UPDATE, None, None)
    jobshandler.put((Actions.INSERT, job))
    return {"success": True}

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

app_vars = ChainMap(os.environ, app_defaults)

app.run(host=app_vars['YDL_SERVER_HOST'],
        port=app_vars['YDL_SERVER_PORT'],
        debug=app_vars['YDL_DEBUG'])
ydlhandler.finish()
jobshandler.finish()
ydlhandler.join()
jobshandler.join()
