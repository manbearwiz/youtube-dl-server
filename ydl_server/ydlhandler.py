import os
from queue import Queue
from threading import Thread
import subprocess
from collections import ChainMap
import io
import youtube_dl
from ydl_server.logdb import JobsDB, Job, Actions
from ydl_server import jobshandler
from ydl_server.config import app_defaults
from time import sleep

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
        jobshandler.put((Actions.UPDATE, job))
        output = io.StringIO() # FIXME intialize this ?
        stdout_thread = Thread(target=download_log_update,
                args=(job, output))
        stdout_thread.start()
        try:
            job.log = Job.clean_logs(download(job.name, {'format':  job.format}, output),)
            job.status = Job.COMPLETED
        except Exception as e:
            job.status = Job.FAILED
            job.log += str(e)
            print("Exception during download task:\n" + str(e))
        stdout_thread.join()
        jobshandler.put((Actions.UPDATE, job))
        queue.task_done()

def update():
    command = ["pip", "install", "--no-cache-dir", "--upgrade", "youtube-dl"]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    output, error = proc.communicate()
    return {
        "output": output.decode('ascii'),
        "error":  error.decode('ascii')
    }

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
        jobshandler.put((Actions.UPDATE, job))
        sleep(5)

def download(url, request_options, output):
    with youtube_dl.YoutubeDL(get_ydl_options(request_options)) as ydl:
        ydl.params['extract_flat']= 'in_playlist'
        info = ydl.extract_info(url, download=False)
        if '_type' in info and info['_type'] == 'playlist' \
                and 'YDL_OUTPUT_TEMPLATE_PLAYLIST' in app_defaults:
            ydl.params['outtmpl'] = app_defaults['YDL_OUTPUT_TEMPLATE_PLAYLIST']
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
        job = Job(pending["name"], Job.PENDING, "Queue stopped", pending["format"])
        job.id = pending["id"]
        jobshandler.put((Actions.RESUME, job))

def get_ydl_version():
    return youtube_dl.version.__version__
