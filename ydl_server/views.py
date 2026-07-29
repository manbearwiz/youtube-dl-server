from starlette.responses import JSONResponse

from pathlib import Path
from ydl_server.config import (
    app_config,
    get_finished_path,
    get_ydl_formats,
    get_ui_aliases,
    resolve_finished_file,
)
from ydl_server.db import JobsDB, Job, Actions, JobType
import os
import re
import signal
import shutil


TIMESTAMP_RE = re.compile(r"^(\d+(\.\d+)?|(\d+:)?[0-5]?\d:[0-5]?\d(\.\d+)?)$")


def parse_timestamp(ts):
    seconds = 0.0
    for part in ts.split(":"):
        seconds = seconds * 60 + float(part)
    return seconds


MAX_TREE_DEPTH = 32


def build_finished_tree(root_dir, seen=None, depth=0):
    try:
        entries = list(os.scandir(root_dir))
    except OSError as e:
        print(f"Error scanning {root_dir} - {e}")
        return []
    if seen is None:
        seen = set()
    files = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        stat, is_dir = None, False
        try:
            stat = entry.stat()
            is_dir = entry.is_dir()
        except Exception as e:
            print(f"Error accessing {entry.path} - {e}")
        children = None
        if is_dir:
            children = []
            key = (stat.st_dev, stat.st_ino) if stat else None
            if (
                depth < MAX_TREE_DEPTH
                and key not in seen
                and resolve_finished_file(entry.path) is not None
            ):
                seen.add(key)
                children = build_finished_tree(entry.path, seen, depth + 1)
        file_info = {
            "name": entry.name,
            "modified": stat.st_mtime if stat else None,
            "created": stat.st_ctime if stat else None,
            "size": stat.st_size if stat and not is_dir else None,
            "directory": is_dir,
            "children": children,
        }
        files.append(file_info)
    return files


async def api_finished(request):
    return JSONResponse(build_finished_tree(Path(get_finished_path())))


async def api_delete_file(request):
    fname = request.path_params["fname"]
    if not fname:
        return JSONResponse({"success": False, "message": "No filename specified"})
    fname = resolve_finished_file(fname)
    if fname is None:
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
            {"success": False, "message": f"Could not delete the specified file (Err {e.errno or 'unknown'})"}
        )

    return JSONResponse({"success": True, "message": "File deleted"})


async def api_cut_file(request):
    fname = request.path_params["fname"]
    data = await request.json()
    start = str(data.get("start") or "0")
    end = data.get("end") or None
    mode = data.get("mode", "fast")
    output = (data.get("output") or "").strip()

    src = resolve_finished_file(fname)
    if src is None:
        return JSONResponse({"success": False, "message": "Invalid filename"})
    if not os.path.isfile(src):
        return JSONResponse({"success": False, "message": "File not found"})

    if not output or "/" in output or output.startswith("."):
        return JSONResponse({"success": False, "message": "Invalid output filename"})
    dst = os.path.join(os.path.dirname(src), output)
    if os.path.exists(dst):
        return JSONResponse({"success": False, "message": "Output file already exists"})

    if not TIMESTAMP_RE.match(start) or (end and not TIMESTAMP_RE.match(str(end))):
        return JSONResponse({"success": False, "message": "Invalid timestamp"})
    if end and parse_timestamp(str(end)) <= parse_timestamp(start):
        return JSONResponse({"success": False, "message": "End time must be after start time"})
    if mode not in ("fast", "precise"):
        return JSONResponse({"success": False, "message": "Invalid mode"})

    job = Job(
        "Cut {} [{} - {}]".format(fname, start, end or "end"),
        Job.PENDING,
        "",
        JobType.FFMPEG_CUT,
        None,
        [fname],
        extra_params={"start": start, "end": end, "mode": mode, "output": output},
    )
    request.app.state.jobshandler.put((Actions.INSERT, job))

    return JSONResponse({"success": True, "output": output})


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
            "ydl_aliases": get_ui_aliases(app_config),
            "ydl_default_format": app_config["ydl_server"].get(
                "default_format", "video/best"
            ),
        }
    )


async def api_queue_size(request):
    db = JobsDB(readonly=True)
    counts = db.get_job_counts()
    db.close()
    return JSONResponse(
        {
            "success": True,
            "stats": {
                "queue": request.app.state.ydlhandler.queue.qsize(),
                **counts,
            },
        }
    )


async def api_logs(request):
    db = JobsDB(readonly=True)
    limit = app_config["ydl_server"].get("max_log_entries", 100)
    status = request.query_params.get("status", None)
    if request.query_params.get("show_logs", "1") in ["1", "true"]:
        result = db.get_jobs_with_logs(limit, status)
    else:
        result = db.get_jobs(limit, status)
    db.close()
    return JSONResponse(result)


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
    db.close()

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
    db.close()
    if not job:
        return JSONResponse({"success": False}, status_code=404)

    new_job = Job(
        job["name"], Job.PENDING, "", int(job["type"]), job["format"], job["urls"], extra_params=job.get("extra_params", {})
    )
    new_job.force_generic_extractor = job.get("force_generic_extractor", False)

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
    aliases = data.get("aliases", [])
    audio_format = data.get("audio_format")
    format_str = data.get("format")
    force_generic_extractor = data.get("force_generic_extractor", False)

    if isinstance(aliases, str):
        aliases = [a for a in aliases.split(",") if a]

    if profile:
        format_str = ','.join([format_str, profile])
    if aliases:
        format_str = ','.join([format_str] + ["alias/{}".format(a) for a in aliases])
    if audio_format:
        format_str = ',audio/'.join([format_str, audio_format])
    options = {"format": format_str, "force_generic_extractor": force_generic_extractor}

    if url:
        urls.append(url)

    if len(urls) == 0:
        return JSONResponse(
            {"success": False, "error": "'url' and 'urls' query parameters omitted"}
        )

    extra_params = data.get("extra_params", {})

    job = Job(
        ", ".join(urls), Job.PENDING, "", JobType.YDL_DOWNLOAD, format_str, urls, extra_params=extra_params
    )
    job.force_generic_extractor = force_generic_extractor
    request.app.state.jobshandler.insert_and_wait(job)

    print("Added url " + ",".join(urls) + " to the download queue")
    return JSONResponse({"success": True, "urls": urls, "options": options, "job_id": job.id})


async def api_metadata_fetch(request):
    if request.headers.get("Content-Type") == "application/x-www-form-urlencoded":
        data = await request.form()
    else:
        data = await request.json()
    url = data.get("url")
    urls = data.get("urls", [])
    force_generic_extractor = data.get("force_generic_extractor", False)
    if url:
        urls.append(url)
    rc, stdout = request.app.state.ydlhandler.fetch_metadata(urls, force_generic_extractor=force_generic_extractor)
    if rc == 0:
        return JSONResponse(stdout)
    return JSONResponse({"success": False}, status_code=404)
