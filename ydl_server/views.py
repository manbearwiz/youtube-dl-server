from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates

from operator import itemgetter
from pathlib import Path
from ydl_server.config import app_config, get_finished_path
from ydl_server.logdb import JobsDB, Job, Actions, JobType
from datetime import datetime


templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


async def front_index(request):
    context = {
        'request': request,
        'ydl_version': request.app.state.ydlhandler.get_ydl_version(),
        'ydl_name': request.app.state.ydlhandler.ydl_module_name,
        'ydl_website': request.app.state.ydlhandler.ydl_website
    }
    return templates.TemplateResponse('index.html',
                                      context=context)


async def front_logs(request):
    context = {
        'request': request,
        'ydl_version': request.app.state.ydlhandler.get_ydl_version(),
        'ydl_name': request.app.state.ydlhandler.ydl_module_name,
        'ydl_website': request.app.state.ydlhandler.ydl_website
    }
    return templates.TemplateResponse('logs.html',
                                      context=context)


async def front_finished(request):
    context = {
        'request': request,
        'ydl_version': request.app.state.ydlhandler.get_ydl_version(),
        'ydl_name': request.app.state.ydlhandler.ydl_module_name,
        'ydl_website': request.app.state.ydlhandler.ydl_website
    }
    return templates.TemplateResponse('finished.html',
                                      context=context)


async def api_list_finished(request):
    root_dir = Path(get_finished_path())
    matches = root_dir.glob('*')

    files = [{'name': f1.name,
            'modified': f1.stat().st_mtime * 1000,
            'children': sorted([{
                'name': f2.name,
                'modified': f2.stat().st_mtime * 1000
                } for f2 in f1.iterdir() if not f2.name.startswith('.')], key=itemgetter('modified'), reverse=True) if f1.is_dir() else None
            } for f1 in matches if not f1.name.startswith('.')]

    files = sorted(files, key=itemgetter('modified'), reverse=True)
    return JSONResponse({
        "success": True,
        "files": files
        })


async def api_list_extractors(request):
    return JSONResponse(request.app.state.ydlhandler.get_ydl_extractors())


async def api_queue_size(request):
    db = JobsDB(readonly=True)
    jobs = db.get_all()
    return JSONResponse({
        "success": True,
        "stats": {
            "queue": request.app.state.ydlhandler.queue.qsize(),
            "pending": len([job for job in jobs if job['status'] == "Pending"]),
            "running": len([job for job in jobs if job['status'] == "Running"]),
            "completed": len([job for job in jobs if job['status'] == "Completed"]),
            "failed": len([job for job in jobs if job['status'] == "Failed"])
        }
    })


async def api_logs(request):
    db = JobsDB(readonly=True)
    return JSONResponse(db.get_all())


async def api_logs_purge(request):
    request.app.state.jobshandler.put((Actions.PURGE_LOGS, None))
    return JSONResponse({"success": True})


async def api_logs_clean(request):
    request.app.state.jobshandler.put((Actions.CLEAN_LOGS, None))
    return JSONResponse({"success": True})


async def api_queue_download(request):
    data = await request.form()
    if (app_config['ydl_server'].get('update_poll_delay_min') and
            (datetime.now() - app_config['ydl_last_update']).seconds >
            app_config['ydl_server'].get('update_poll_delay_min') * 60):
        job = Job("Youtube-dl Update", Job.PENDING, "", JobType.YDL_UPDATE, None, None)
        request.app.state.jobshandler.put((Actions.INSERT, job))

    url = data.get("url")
    options = {'format': data.get("format")}

    if not url:
        return JSONResponse({
            "success": False,
            "error": "'url' query parameter omitted"
            })

    job = Job(url, Job.PENDING, "", JobType.YDL_DOWNLOAD,
              data.get("format"), url)
    request.app.state.jobshandler.put((Actions.INSERT, job))

    print("Added url " + url + " to the download queue")
    return JSONResponse({"success": True, "url": url, "options": options})


async def api_metadata_fetch(request):
    data = await request.form()
    rc, stdout = request.app.state.ydlhandler.fetch_metadata(data.get("url"))
    if rc == 0:
        return JSONResponse(stdout)
    return JSONResponse({}, status_code=404)


async def ydl_update(request):
    job = Job("Youtube-dl Update", Job.PENDING, "", JobType.YDL_UPDATE, None,
              None)
    request.app.state.jobshandler.put((Actions.INSERT, job))
    return JSONResponse({
        "success": True,
        })
