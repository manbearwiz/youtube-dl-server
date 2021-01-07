import os
from queue import Queue
from threading import Thread
import subprocess
import io
import importlib
import json
from time import sleep
from datetime import datetime
import sys
from subprocess import Popen, PIPE, STDOUT

from ydl_server.logdb import JobsDB, Job, Actions, JobType
from ydl_server import jobshandler
from ydl_server.config import app_config


def get_ydl_website():
    import pip._internal.commands.show as pipshow
    info = list(pipshow.search_packages_info([ydl_module_name]))
    if len(info) < 1 or 'home-page' not in info[0]:
        return ''
    return info[0]['home-page']


ydl_module = None
ydl_module_name = None
app_config['ydl_last_update'] = datetime.now()

modules = ['youtube-dl', 'youtube-dlc']

if os.environ.get('YOUTUBE_DL') in modules:
    ydl_module = importlib.import_module(os.environ.get('YOUTUBE_DL').replace('-','_'))
else:
    for module in modules:
        try:
            ydl_module = importlib.import_module(module.replace('-', '_'))
            break
        except ImportError:
            pass
if ydl_module is None:
    raise ImportError('No youtube_dl implementation found')
ydl_module_name = ydl_module.__name__.replace('_', '-')

ydl_website = get_ydl_website()

print('Using {} module'.format(ydl_module_name))

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


def read_proc_stdout(proc, strio):
    strio.write(proc.stdout.read1().decode())


def worker():
    while not done:
        job = queue.get()
        job.status = Job.RUNNING
        jobshandler.put((Actions.SET_STATUS, (job.id, job.status)))
        if job.type == JobType.YDL_DOWNLOAD:
            output = io.StringIO()
            try:
                download(job, {'format': job.format}, output)
            except Exception as e:
                job.status = Job.FAILED
                job.log = "Error during download task"
                print("Error during download task:\n{}\n{}".format(type(e).__name__, str(e)))
        elif job.type == JobType.YDL_UPDATE:
            rc, log = update()
            job.log = Job.clean_logs(log)
            job.status = Job.COMPLETED if rc == 0 else Job.FAILED
        jobshandler.put((Actions.UPDATE, job))
        queue.task_done()


def reload_youtube_dl():
    for module in list(sys.modules.keys()):
        if 'youtube' in module:
            try:
                importlib.reload(sys.modules[module])
            except ModuleNotFoundError:
                print("ModuleNotFoundError:\n" + module)


def update():
    if os.environ.get('YDL_PYTHONPATH'):
        command = ["pip", "install", "--no-cache-dir", "-t", os.environ.get('YDL_PYTHONPATH'), "--upgrade", ydl_module_name]
    else:
        command = ["pip", "install", "--no-cache-dir", "--upgrade", ydl_module_name]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = proc.communicate()
    if proc.wait() == 0:
        app_config['ydl_last_update'] = datetime.now()
        reload_youtube_dl()
    return proc.returncode, str(out.decode('utf-8'))


def get_ydl_options(app_config, request_options):
    req_format = request_options.get('format', 'best')
    if req_format.startswith('audio/'):
        app_config.update({'extract-audio': None})
        app_config.update({'audio-format': req_format.split('/')[-1]})
    elif req_format.startswith('video/'):
        # youtube-dl downloads BEST video and audio by default
        if req_format != 'video/best':
            app_config.update({'format': req_format.split('/')[-1]})
    else:
        app_config.update({'format': req_format})
    return app_config


def download_log_update(job, proc, strio):
    while job.status == Job.RUNNING:
        read_proc_stdout(proc, strio)
        job.log = Job.clean_logs(strio.getvalue())
        jobshandler.put((Actions.SET_LOG, (job.id, job.log)))
        sleep(3)


def fetch_metadata(url):
    ydl_opts = app_config.get('ydl_options', {})
    cmd = get_ydl_full_cmd(ydl_opts, url)
    cmd.extend(['-J', '--flat-playlist'])

    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()

    if proc.wait() != 0:
        return -1, stderr.decode()

    return 0, json.loads(stdout)


def get_ydl_full_cmd(opt_dict, url):
    cmd = [ydl_module_name]
    if opt_dict is not None:
        for key, val in opt_dict.items():
            if isinstance(val, bool) and not val:
                continue
            cmd.append('--{}'.format(key))
            if val is not None and not isinstance(val, bool):
                cmd.append(str(val))
    cmd.append(url)
    return cmd


def download(job, request_options, output):
    ydl_opts = get_ydl_options(app_config.get('ydl_options', {}),
                               request_options)
    cmd = get_ydl_full_cmd(ydl_opts, job.url)

    rc, metadata = fetch_metadata(job.url)
    if rc != 0:
        job.log = Job.clean_logs(metadata)
        job.status = Job.FAILED
        print("Error during download task:\n" + job.log)
        return

    jobshandler.put((Actions.SET_NAME, (job.id, metadata.get('title', job.url))))

    if metadata.get('_type') == 'playlist':
        ydl_opts.update({'output': app_config['ydl_server'].get('output_playlist', ydl_opts.get('output'))})

    cmd = get_ydl_full_cmd(ydl_opts, job.url)
    proc = Popen(cmd, stdout=PIPE, stderr=STDOUT)
    stdout_thread = Thread(target=download_log_update,
                           args=(job, proc, output))
    stdout_thread.start()

    if proc.wait() == 0:
        read_proc_stdout(proc, output)
        job.log = Job.clean_logs(output.getvalue())
        job.status = Job.COMPLETED
    else:
        read_proc_stdout(proc, output)
        job.log = Job.clean_logs(output.getvalue())
        job.status = Job.FAILED
        print("Error during download task:\n" + output.getvalue())
    stdout_thread.join()


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
    return ydl_module.version.__version__


def get_ydl_extractors():
    return [ie.IE_NAME for ie in ydl_module.extractor.list_extractors(app_config['ydl_options'].get('age-limit')) if ie._WORKING]
