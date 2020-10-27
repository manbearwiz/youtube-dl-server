import os
from queue import Queue
from threading import Thread
import subprocess
from collections import ChainMap
import io
import importlib
import youtube_dlc
import json
from time import sleep
import sys

from ydl_server.logdb import JobsDB, Job, Actions, JobType
from ydl_server import jobshandler
from ydl_server.config import app_defaults

queue = Queue()
thread = None
done = False

def start():
    thread = Thread(target=worker)
    thread.start()

def put(obj):
    queue.put(obj)

def finish():
    done = True

def worker():
    while not done:
        job = queue.get()
        job.status = Job.RUNNING
        jobshandler.put((Actions.SET_STATUS, (job.id, job.status)))
        if job.type == JobType.YDL_DOWNLOAD:
            output = io.StringIO()
            stdout_thread = Thread(target=download_log_update,
                    args=(job, output))
            stdout_thread.start()
            try:
                job.log = Job.clean_logs(download(job.url, {'format':  job.format}, output, job.id))
                job.status = Job.COMPLETED
            except Exception as e:
                job.status = Job.FAILED
                job.log += str(e)
                print("Exception during download task:\n" + str(e))
            stdout_thread.join()
        elif job.type == JobType.YDL_UPDATE:
            rc, log = update()
            job.log = Job.clean_logs(log)
            job.status = Job.COMPLETED if rc == 0 else Job.FAILED
        jobshandler.put((Actions.UPDATE, job))
        queue.task_done()

def reload_youtube_dl():
    for module in list(sys.modules.keys()):
        if 'youtube' in module:
            importlib.reload(sys.modules[module])

def update():
    if os.environ.get('YDL_PYTHONPATH'):
        command = ["pip", "install", "--no-cache-dir", "-t", os.environ.get('YDL_PYTHONPATH'), "--upgrade", "youtube-dlc"]
    else:
        command = ["pip", "install", "--no-cache-dir", "--upgrade", "youtube-dlc"]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = proc.communicate()
    if proc.returncode == 0:
        reload_youtube_dl()
    return proc.returncode, str(out.decode('utf-8'))

def get_ydl_options(request_options):
    request_vars = {
        'YDL_EXTRACT_AUDIO_FORMAT': None,
        'YDL_RECODE_VIDEO_FORMAT': None,
    }

    requested_format = request_options.get('format', 'bestvideo')

    if requested_format in ['aac', 'flac', 'mp3', 'm4a', 'opus', 'vorbis', 'wav']:
        request_vars['YDL_EXTRACT_AUDIO_FORMAT'] = requested_format
    elif requested_format == 'bestaudio':
        request_vars['YDL_EXTRACT_AUDIO_FORMAT'] = 'best'
    elif requested_format in ['mp4', 'flv', 'webm', 'ogg', 'mkv', 'avi']:
        request_vars['YDL_RECODE_VIDEO_FORMAT'] = requested_format

    ydl_vars = ChainMap(request_vars, os.environ, app_defaults)

    postprocessors = []

    if(ydl_vars['YDL_EXTRACT_AUDIO_FORMAT']):
        postprocessors.append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': ydl_vars['YDL_EXTRACT_AUDIO_FORMAT'],
            'preferredquality': ydl_vars['YDL_EXTRACT_AUDIO_QUALITY'],
        })

    if(ydl_vars['YDL_RECODE_VIDEO_FORMAT']):
        postprocessors.append({
            'key': 'FFmpegVideoConvertor',
            'preferedformat': ydl_vars['YDL_RECODE_VIDEO_FORMAT'],
        })

    ydl_options = {
        'format': ydl_vars['YDL_FORMAT'],
        'postprocessors': postprocessors,
        'outtmpl': ydl_vars['YDL_OUTPUT_TEMPLATE'],
        'download_archive': ydl_vars['YDL_ARCHIVE_FILE'],
        'cachedir': ydl_vars['YDL_CACHE_DIR']
    }

    ydl_options = {**ydl_vars['YDL_RAW_OPTIONS'], **ydl_options}

    if ydl_vars['YDL_SUBTITLES_LANGUAGES']:
        ydl_options['writesubtitles'] = True
        if ydl_vars['YDL_SUBTITLES_LANGUAGES'] != 'all':
            ydl_options['subtitleslangs'] = \
                    ydl_vars['YDL_SUBTITLES_LANGUAGES'].split(',')
        else:
            ydl_options['allsubtitles'] = True

    return ydl_options

def download_log_update(job, stringio):
    while job.status == Job.RUNNING:
        job.log = Job.clean_logs(stringio.getvalue())
        jobshandler.put((Actions.SET_LOG, (job.id, job.log)))
        sleep(5)

def fetch_metadata(url):
    stdout = io.StringIO()
    stderr = io.StringIO()
    info = None
    with youtube_dlc.YoutubeDL({'extract_flat': 'in_playlist'}) as ydl:
        ydl.params['extract_flat'] = 'in_playlist'
        return ydl.extract_info(url, download=False)

def download(url, request_options, output, job_id):
    with youtube_dlc.YoutubeDL(get_ydl_options(request_options)) as ydl:
        ydl.params['extract_flat'] = 'in_playlist'
        ydl_opts = ChainMap(os.environ, app_defaults)
        info = ydl.extract_info(url, download=False)
        if 'title' in info and info['title']:
            jobshandler.put((Actions.SET_NAME, (job_id, info['title'])))
        if '_type' in info and info['_type'] == 'playlist' \
                and 'YDL_OUTPUT_TEMPLATE_PLAYLIST' in ydl_opts:
            ydl.params['outtmpl'] = ydl_opts['YDL_OUTPUT_TEMPLATE_PLAYLIST']
        ydl.params['extract_flat']= False

        # Swap out sys.stdout as ydl's output so we can capture it
        ydl._screen_file = output
        ydl._err_file = ydl._screen_file
        ydl.download([url])
        return ydl._screen_file.getvalue()

def resume_pending():
    db = JobsDB(readonly=False)
    jobs = db.get_all()
    not_endeds = [job for job in jobs if job['status'] == "Pending" or job['status'] == 'Running']
    for pending in not_endeds:
        if int(pending["type"]) == JobType.YDL_UPDATE:
            jobshandler.put((Actions.SET_STATUS, (pending["id"], Job.FAILED)))
        else:
            job = Job(pending["name"], Job.PENDING, "Queue stopped",
                    int(pending["type"]), pending["format"], pending["url"])
            job.id = pending["id"]
            jobshandler.put((Actions.RESUME, job))

def join():
    if thread is not None:
        return thread.join()

def get_ydl_version():
    return youtube_dlc.version.__version__
