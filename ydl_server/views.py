from starlette.responses import JSONResponse

from operator import itemgetter
from pathlib import Path
from ydl_server.config import app_config, get_finished_path, get_ydl_formats
from ydl_server.db import JobsDB, Job, Actions, JobType
from datetime import datetime
import os
import signal
import shutil


async def api_finished(request):
    root_dir = Path(get_finished_path())
    matches = root_dir.glob("*")

    files = [
        {
            "name": f1.name,
            "modified": datetime.fromtimestamp(f1.stat().st_mtime).strftime("%H:%m %D"),
            "created": datetime.fromtimestamp(f1.stat().st_ctime).strftime("%H:%m %D"),
            "size": f1.stat().st_size if not f1.is_dir() else None,
            "directory": f1.is_dir(),
            "children": sorted(
                [
                    {
                        "name": f2.name,
                        "size": f2.stat().st_size,
                        "modified": datetime.fromtimestamp(f2.stat().st_mtime).strftime(
                            "%H:%m %D"
                        ),
                        "created": datetime.fromtimestamp(f2.stat().st_ctime).strftime(
                            "%H:%m %D"
                        ),
                    }
                    for f2 in f1.iterdir()
                    if not f2.name.startswith(".")
                ],
                key=itemgetter("modified"),
                reverse=True,
            )
            if f1.is_dir()
            else None,
        }
        for f1 in matches
        if not f1.name.startswith(".")
    ]
    return JSONResponse(files)


async def api_delete_file(request):
    fname = request.path_params["fname"]
    if not fname:
        return JSONResponse({"success": False, "message": "No filename specified"})
    fname = os.path.realpath(os.path.join(get_finished_path(), fname))
    if os.path.commonprefix((fname, get_finished_path())) != get_finished_path():
        return JSONResponse({"success": False, "message": "Invalid filename"})
    fname = Path(fname)
    try:
        if fname.is_dir():
            shutil.rmtree(fname)
        else:
            fname.unlink()
    except OSError as e:
        print(e)
        return JSONResponse(
            {"success": False, "message": "Could not delete the specified file"}
        )

    return JSONResponse({"success": True, "message": "File deleted"})


async def api_list_extractors(request):
    return JSONResponse(request.app.state.ydlhandler.ydl_extractors)


async def api_server_info(request):
    return JSONResponse(
        {
            "ydl_module_name": request.app.state.ydlhandler.ydl_module_name,
            "ydl_module_version": request.app.state.ydlhandler.ydl_version,
            "ydl_module_website": request.app.state.ydlhandler.ydl_website,
            "ydls_version": request.app.state.ydlhandler.ydls_version,
            "ydls_release_date": request.app.state.ydlhandler.ydls_release_date,
            "download_workers_count": request.app.state.ydlhandler.download_workers_count,
        }
    )


async def api_list_formats(request):
    return JSONResponse(
        {
            "ydl_formats": get_ydl_formats(app_config),
            "ydl_default_format": app_config["ydl_server"].get(
                "default_format", "video/best"
            ),
        }
    )


async def api_queue_size(request):
    db = JobsDB(readonly=True)
    jobs = db.get_jobs(app_config["ydl_server"].get("max_log_entries", 100))
    return JSONResponse(
        {
            "success": True,
            "stats": {
                "queue": request.app.state.ydlhandler.queue.qsize(),
                "pending": len([job for job in jobs if job["status"] == "Pending"]),
                "running": len([job for job in jobs if job["status"] == "Running"]),
                "completed": len([job for job in jobs if job["status"] == "Completed"]),
                "failed": len([job for job in jobs if job["status"] == "Failed"]),
                "aborted": len([job for job in jobs if job["status"] == "Aborted"]),
            },
        }
    )


async def api_logs(request):
    db = JobsDB(readonly=True)
    if request.query_params.get("show_logs", "1") in ["1", "true"]:
        return JSONResponse(
            db.get_jobs_with_logs(
                app_config["ydl_server"].get("max_log_entries", 100),
                request.query_params.get("status", None)
                )
        )
    return JSONResponse(
        db.get_jobs(app_config["ydl_server"].get("max_log_entries", 100))
    )


async def api_logs_purge(request):
    request.app.state.jobshandler.put((Actions.PURGE_LOGS, None))
    return JSONResponse({"success": True})


async def api_logs_clean(request):
    request.app.state.jobshandler.put((Actions.CLEAN_LOGS, None))
    return JSONResponse({"success": True})


async def api_jobs_stop(request):
    db = JobsDB(readonly=True)
    job_id = request.path_params["job_id"]
    job = db.get_job_by_id(job_id)

    if not job:
        return JSONResponse({"success": False}, status_code=404)
    if job["status"] == "Pending":
        print("Cancelling pending job")
        request.app.state.jobshandler.put(
            (Actions.SET_STATUS, (job["id"], Job.ABORTED))
        )
        return JSONResponse({"success": True})
    if job["status"] == "Running" and int(job["pid"]) != 0:
        print("Stopping running job", job["pid"])
        try:
            print(os.kill(job["pid"], signal.SIGINT))
        except ProcessLookupError:
            print("Process already dead")
        return JSONResponse({"success": True})
    if int(job["pid"]) == 0:
        request.app.state.jobshandler.put(
            (Actions.SET_STATUS, (job["id"], Job.ABORTED))
        )
        return JSONResponse({"success": True})
    return JSONResponse({"success": False})


async def api_jobs_retry(request):
    db = JobsDB(readonly=True)
    job_id = request.path_params["job_id"]
    job = db.get_job_by_id(job_id)
    if not job:
        return JSONResponse({"success": False}, status_code=404)

    new_job = Job(
        job["name"], Job.PENDING, "", JobType.YDL_DOWNLOAD, job["format"], job["urls"]
    )

    request.app.state.jobshandler.put((Actions.DELETE_LOG_SAFE, job))
    request.app.state.jobshandler.put((Actions.INSERT, new_job))

    return JSONResponse({"success": True})

async def api_jobs_delete(request):
    job_id = request.path_params["job_id"]
    if job_id is not None:
        request.app.state.jobshandler.put((Actions.DELETE_LOG, {'id': job_id}))
        return JSONResponse({"success": True})
    return JSONResponse({"success": False})

async def api_queue_download(request):
    if request.headers.get("Content-Type") == "application/x-www-form-urlencoded":
        data = await request.form()
    else:
        data = await request.json()
    url = data.get("url")
    urls = data.get("urls", [])
    profile = data.get("profile")
    audio_format = data.get("audio_format")
    format_str = data.get("format")

    if profile:
        format_str = ','.join([format_str, profile])
    if audio_format:
        format_str = ',audio/'.join([format_str, audio_format])
    options = {"format": format_str}

    if url:
        urls.append(url)

    if len(urls) == 0:
        return JSONResponse(
            {"success": False, "error": "'url' and 'urls' query parameters omitted"}
        )

    job = Job(
        ", ".join(urls), Job.PENDING, "", JobType.YDL_DOWNLOAD, format_str, urls
    )
    request.app.state.jobshandler.put((Actions.INSERT, job))

    print("Added url " + ",".join(urls) + " to the download queue")
    return JSONResponse({"success": True, "urls": urls, "options": options})


async def api_metadata_fetch(request):
    if request.headers.get("Content-Type") == "application/x-www-form-urlencoded":
        data = await request.form()
    else:
        data = await request.json()
    url = data.get("url")
    urls = data.get("urls", [])
    if url:
        urls.append(url)
    rc, stdout = request.app.state.ydlhandler.fetch_metadata(urls)
    if rc == 0:
        return JSONResponse(stdout)
    return JSONResponse({"success": False}, status_code=404)
