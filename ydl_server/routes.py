from bottle import route, run, request, static_file, template, response
import json
from datetime import datetime
from operator import itemgetter
from pathlib import Path

from ydl_server import jobshandler, ydlhandler, app
from ydl_server.config import app_config
from ydl_server.logdb import JobsDB, Job, Actions, JobType

@app.route(['/', '/index'])
def front_index():
    return template('./ydl_server/templates/index.html',
            ydl_version=ydlhandler.get_ydl_version(),
            ydl_name=ydlhandler.ydl_module_name,
            ydl_website=ydlhandler.get_ydl_website())

@app.route('/logs')
def front_logs():
    return template('./ydl_server/templates/logs.html',
            ydl_version=ydlhandler.get_ydl_version(),
            ydl_name=ydlhandler.ydl_module_name,
            ydl_website=ydlhandler.get_ydl_website())

@app.route('/finished')
def front_finished():
    return template('./ydl_server/templates/finished.html',
            ydl_version=ydlhandler.get_ydl_version(),
            ydl_name=ydlhandler.ydl_module_name,
            ydl_website=ydlhandler.get_ydl_website())


@app.route('/api/finished')
def api_list_finished():
    root_dir = Path(app_config['ydl_options'].get('output')).parent
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
    root_dir = Path(app_config['ydl_options'].get('output')).parent
    return static_file(filename, root=root_dir)

@app.route('/static/:filename#.*#')
def server_static(filename):
    return static_file(filename, root='./ydl_server/static')

@app.route('/api/extractors')
def api_list_extractors():
    return json.dumps(ydlhandler.get_ydl_extractors())

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
    if (app_config['ydl_server'].get('update_poll_delay_min') and
            (datetime.now() - ydlhandler.ydl_last_update).seconds >
            app_config['ydl_server'].get('update_poll_delay_min') * 60):
        job = Job("Youtube-dl Update", Job.PENDING, "", JobType.YDL_UPDATE, None, None)
        jobshandler.put((Actions.INSERT, job))

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
    rc, stdout = ydlhandler.fetch_metadata(url)
    if rc == 0:
        return stdout
    response.status = 404

@app.route("/api/youtube-dl/update", method="GET")
def ydl_update():
    job = Job("Youtube-dl Update", Job.PENDING, "", JobType.YDL_UPDATE, None, None)
    jobshandler.put((Actions.INSERT, job))
    return {"success": True}
