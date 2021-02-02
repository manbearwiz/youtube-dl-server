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


def reload_youtube_dl():
    for module in list(sys.modules.keys()):
        if 'youtube' in module:
            try:
                importlib.reload(sys.modules[module])
            except ModuleNotFoundError:
                print("ModuleNotFoundError:\n" + module)


def get_ydl_website(ydl_module_name):
    import pip._internal.commands.show as pipshow
    info = list(pipshow.search_packages_info([ydl_module_name]))
    if len(info) < 1 or 'home-page' not in info[0]:
        return ''
    return info[0]['home-page']


def read_proc_stdout(proc, strio):
    strio.write(proc.stdout.read1().decode())


class YdlHandler:
    def __init__(self, app_config, jobshandler):
        self.queue = Queue()
        self.thread = None
        self.done = False
        self.ydl_module = None
        self.ydl_module_name = None
        self.app_config = app_config
        self.jobshandler = jobshandler

        self.app_config['ydl_last_update'] = datetime.now()

        modules = ['youtube-dl', 'youtube-dlc']

        if os.environ.get('YOUTUBE_DL') in modules:
            self.ydl_module = importlib.import_module(
                os.environ.get('YOUTUBE_DL').replace('-', '_'))
        else:
            for module in modules:
                try:
                    self.ydl_module = importlib.import_module(
                        module.replace('-', '_'))
                    break
                except ImportError:
                    pass
        if self.ydl_module is None:
            raise ImportError('No youtube_dl implementation found')
        self.ydl_module_name = self.ydl_module.__name__.replace('_', '-')

        self.ydl_website = get_ydl_website(self.ydl_module_name)

        print('Using {} module'.format(self.ydl_module_name))

    def start(self):
        self.thread = Thread(target=self.worker)
        self.thread.start()

    def put(self, obj):
        self.queue.put(obj)

    def finish(self):
        self.done = True

    def worker(self):
        while not self.done:
            job = self.queue.get()
            job.status = Job.RUNNING
            self.jobshandler.put((Actions.SET_STATUS, (job.id, job.status)))
            if job.type == JobType.YDL_DOWNLOAD:
                output = io.StringIO()
                try:
                    self.download(job, {'format': job.format}, output)
                except Exception as e:
                    job.status = Job.FAILED
                    job.log = "Error during download task:\n{}:\n\t{}"\
                        .format(type(e).__name__, str(e))
                    print("Error during download task:\n{}:\n\t{}"\
                        .format(type(e).__name__, str(e)))
            elif job.type == JobType.YDL_UPDATE:
                rc, log = self.update()
                job.log = Job.clean_logs(log)
                job.status = Job.COMPLETED if rc == 0 else Job.FAILED
            self.jobshandler.put((Actions.UPDATE, job))
            self.queue.task_done()

    def update(self):
        if os.environ.get('YDL_PYTHONPATH'):
            command = [
                "pip", "install", "--no-cache-dir",
                "-t", os.environ.get('YDL_PYTHONPATH'),
                "--upgrade", self.ydl_module_name
                ]
        else:
            command = [
                "pip", "install", "--no-cache-dir",
                "--upgrade", self.ydl_module_name
                ]
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        out, err = proc.communicate()
        if proc.wait() == 0:
            self.app_config['ydl_last_update'] = datetime.now()
            reload_youtube_dl()
        return proc.returncode, str(out.decode('utf-8'))

    def get_ydl_options(self, ydl_config, request_options):
        ydl_config = ydl_config.copy()
        req_format = request_options.get('format')
        if req_format is None:
            req_format = 'best'
        if req_format.startswith('audio/'):
            ydl_config.update({'extract-audio': None})
            ydl_config.update({'audio-format': req_format.split('/')[-1]})
        elif req_format.startswith('video/'):
            # youtube-dl downloads BEST video and audio by default
            if req_format != 'video/best':
                ydl_config.update({'format': req_format.split('/')[-1]})
        else:
            ydl_config.update({'format': req_format})
        return ydl_config

    def download_log_update(self, job, proc, strio):
        while job.status == Job.RUNNING:
            read_proc_stdout(proc, strio)
            job.log = Job.clean_logs(strio.getvalue())
            self.jobshandler.put((Actions.SET_LOG, (job.id, job.log)))
            sleep(3)

    def fetch_metadata(self, url):
        ydl_opts = self.app_config.get('ydl_options', {})
        cmd = self.get_ydl_full_cmd(ydl_opts, url)
        cmd.extend(['-J', '--flat-playlist'])

        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        if proc.wait() != 0:
            return -1, stderr.decode()

        return 0, json.loads(stdout)

    def get_ydl_full_cmd(self, opt_dict, url):
        cmd = [self.ydl_module_name]
        if opt_dict is not None:
            for key, val in opt_dict.items():
                if isinstance(val, bool) and not val:
                    continue
                cmd.append('--{}'.format(key))
                if val is not None and not isinstance(val, bool):
                    cmd.append(str(val))
        cmd.append(url)
        return cmd

    def download(self, job, request_options, output):
        ydl_opts = self.get_ydl_options(self.app_config.get('ydl_options', {}),
                                        request_options)
        cmd = self.get_ydl_full_cmd(ydl_opts, job.url)

        rc, metadata = self.fetch_metadata(job.url)
        if rc != 0:
            job.log = Job.clean_logs(metadata)
            job.status = Job.FAILED
            raise Exception(job.log)

        self.jobshandler.put((Actions.SET_NAME,
                             (job.id, metadata.get('title', job.url))))

        if metadata.get('_type') == 'playlist':
            ydl_opts.update({
                'output': self.app_config['ydl_server']
                    .get('output_playlist', ydl_opts.get('output'))
                })

        cmd = self.get_ydl_full_cmd(ydl_opts, job.url)

        proc = Popen(cmd, stdout=PIPE, stderr=STDOUT)
        stdout_thread = Thread(target=self.download_log_update,
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

    def resume_pending(self):
        db = JobsDB(readonly=False)
        jobs = db.get_all()
        not_endeds = [job for job in jobs if job['status'] == "Pending"
                      or job['status'] == 'Running']
        for pending in not_endeds:
            if int(pending["type"]) == JobType.YDL_UPDATE:
                self.jobshandler.put((Actions.SET_STATUS,
                                     (pending["id"], Job.FAILED)))
            else:
                job = Job(pending["name"],
                          Job.PENDING, "Queue stopped",
                          int(pending["type"]),
                          pending["format"], pending["url"])
                job.id = pending["id"]
                self.jobshandler.put((Actions.RESUME, job))

    def join(self):
        if self.thread is not None:
            return self.thread.join()

    def get_ydl_version(self):
        return self.ydl_module.version.__version__

    def get_ydl_extractors(self):
        return [ie.IE_NAME for ie in self.ydl_module.extractor
                .list_extractors(
                    self.app_config['ydl_options'].get('age-limit')
                    ) if ie._WORKING]
