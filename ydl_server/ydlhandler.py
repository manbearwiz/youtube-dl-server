import os
from queue import Queue, Empty
from threading import Thread
import io
import importlib
import json
from time import sleep
from datetime import datetime
from subprocess import Popen, PIPE, STDOUT

from ydl_server.db import JobsDB, Job, Actions, JobType


YDL_MODULES = ["youtube_dl", "youtube_dlc", "yt_dlp"]


def get_ydl_website(ydl_module_name):
    try:
        import pip._internal.commands.show as pipshow
    except ModuleNotFoundError:
        print("Module not found, skipping get_ydl_website")
        return None

    info = list(pipshow.search_packages_info([ydl_module_name]))
    if len(info) < 1:
        return ""
    info = info[0]
    url = getattr(info, "home-page", None) or  getattr(info, "homepage", None)
    if not url:
        urls = getattr(info, "project_urls", None)
        if urls:
            urls = {v.split(",")[0].strip(): v.split(",")[1].strip() for v in urls if "," in v}
            url = urls.get("Homepage") or urls.get("Documentation") or urls.get("Repository")
    return url


def read_proc_stdout(proc, strio):
    strio.write(proc.stdout.read1().decode())


class YdlHandler:
    def import_ydl_module(self):
        ydl_module = None
        if os.environ.get("YOUTUBE_DL").replace("-", "_") in YDL_MODULES:
            ydl_module = importlib.import_module(
                os.environ.get("YOUTUBE_DL").replace("-", "_")
            )
        else:
            for module in YDL_MODULES:
                try:
                    ydl_module = importlib.import_module(module)
                    break
                except ImportError:
                    pass
        if ydl_module is None:
            raise ImportError("No youtube_dl implementation found")

        self.ydl_module_name = ydl_module.__name__.replace("_", "-")
        self.ydl_website = get_ydl_website(self.ydl_module_name)

        self.ydls_version = os.environ.get("YDLS_VERSION", "")
        self.ydls_release_date = os.environ.get("YDLS_RELEASE_DATE", "")

        importlib.reload(ydl_module.version)
        importlib.reload(ydl_module.extractor)

        self.ydl_version = ydl_module.version.__version__
        self.ydl_extractors = [
            ie.IE_NAME
            for ie in ydl_module.extractor.list_extractors(
                self.app_config["ydl_options"].get("age-limit")
            )
            if ie._WORKING
        ]

    def __init__(self, app_config, jobshandler):
        self.queue = Queue()
        self.threads = []
        self.done = False
        self.ydl_module_name = None
        self.ydl_version = None
        self.ydl_extractors = []
        self.app_config = app_config
        self.jobshandler = jobshandler

        self.app_config["ydl_last_update"] = datetime.now()

        self.import_ydl_module()

        print("Using {} module".format(self.ydl_module_name))

    def start(self):
        self.download_workers_count = self.app_config["ydl_server"].get(
            "download_workers_count", 2
        )
        for i in range(self.download_workers_count):
            thread = Thread(target=self.worker, args=(i,))
            self.threads.append(thread)
            thread.start()
            print("Started dl worker %i" % i)

    def put(self, obj):
        self.queue.put(obj)

    def finish(self):
        self.done = True

    def worker(self, thread_id):
        db = JobsDB(readonly=True)
        while not self.done:
            try:
                job = self.queue.get(timeout=1)
            except Empty:
                continue
            job_detail = db.get_job_by_id(job.id)
            if not job_detail or job_detail["status"] == "Aborted":
                self.queue.task_done()
                continue
            job.status = Job.RUNNING
            self.jobshandler.put((Actions.SET_STATUS, (job.id, job.status)))
            self.queue.task_done()
            if job.type == JobType.YDL_DOWNLOAD:
                output = io.StringIO()
                try:
                    self.download(job, {"format": job.format}, output)
                except Exception as e:
                    job.status = Job.FAILED
                    job.log = "Error during download task:\n{}:\n\t{}".format(
                        type(e).__name__, str(e)
                    )
                    print(
                        "Error during download task:\n{}:\n\t{}".format(
                            type(e).__name__, str(e)
                        )
                    )
            self.jobshandler.put((Actions.UPDATE, job))

    def get_format_and_profile(self, format_string):
        fmt, audio, profile = None, None, None
        for s in format_string.split(","):
            if s.startswith("profile/"):
                profile = s
            elif s.startswith("audio/") or s.startswith("bestaudio/"):
                audio = s
            else:
                fmt = s
        return fmt, audio, profile

    def get_profile(self, profile_str):
        if not profile_str:
            return {}
        profile_name = "/".join(profile_str.split("/")[1:])
        profile = self.app_config.get("profiles", {}).get(profile_name, {}).get('ydl_options')
        if not profile:
            raise Exception("Unknown profile ", profile_str)
        return profile

    def get_ydl_options(self, ydl_config, request_options):
        ydl_config = ydl_config.copy()
        req_format, req_audio, req_profile = self.get_format_and_profile(request_options.get("format"))

        profile = self.get_profile(req_profile)
        if profile:
            req_format = profile.get("format") if req_format is None else req_format

        if req_audio is not None and req_format is None:
            ydl_config.update({"extract-audio": None})
            ydl_config.update({"audio-format": req_audio.split("/")[-1]})

        if req_format is not None:
            if req_format == "video/best":
                req_format = "video/bestvideo"
            if req_format.startswith("video/"):
                # youtube-dl downloads BEST video and audio by default
                if req_format != "video/best":
                    req_format = req_format.split("/")[-1]
            if req_audio is not None:
                req_format = req_format + "+" + req_audio.split("/")[-1]
            else:
                req_format = req_format + "+bestaudio/best"
            ydl_config.update({"format": req_format})

        if req_format is None and req_audio is None:
            ydl_config.update({"format": "video/best"})

        if profile:
            profile = {k: v for k, v in profile.items() if k != "format"}
            ydl_config.update(profile)
        return ydl_config

    def download_log_update(self, job, proc, strio):
        while job.status == Job.RUNNING:
            read_proc_stdout(proc, strio)
            job.log = Job.clean_logs(strio.getvalue())
            self.jobshandler.put((Actions.SET_LOG, (job.id, job.log)))
            sleep(3)

    def fetch_metadata(self, url, force_generic_extractor=False):
        ydl_opts = self.app_config.get("ydl_options", {})
        extra_opts = ["-J", "--flat-playlist"]
        if force_generic_extractor:
            extra_opts.append("--force-generic-extractor")
        cmd = self.get_ydl_full_cmd(ydl_opts, url, extra_opts)

        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        if proc.wait() != 0:
            return -1, stderr.decode()

        return 0, [json.loads(s) for s in stdout.decode().strip().split("\n")]

    def get_ydl_full_cmd(self, opt_dict, url, extra_opts=None):
        cmd = [self.ydl_module_name]
        if opt_dict is not None:
            for key, val in opt_dict.items():
                if isinstance(val, bool) and not val:
                    continue
                cmd.append("--{}".format(key))
                if val is not None and not isinstance(val, bool):
                    cmd.append(str(val))
        if extra_opts is not None and isinstance(extra_opts, list):
            cmd.extend(extra_opts)
        cmd.append("--")
        cmd.extend(url)
        return cmd

    def download(self, job, request_options, output):
        ydl_opts = self.get_ydl_options(
            self.app_config.get("ydl_options", {}), request_options
        )
        extra_opts = []
        force_generic = getattr(job, "force_generic_extractor", False)
        if force_generic:
            extra_opts.append("--force-generic-extractor")
        cmd = self.get_ydl_full_cmd(ydl_opts, job.url, extra_opts)

        rc, metadata = self.fetch_metadata(job.url, force_generic_extractor=force_generic)
        if rc != 0:
            job.log = Job.clean_logs(metadata)
            job.status = Job.FAILED
            print("Error in metadata fetching process:\n" + job.log)
            raise Exception(job.log)

        title = ", ".join(
            [md.get("title", job.url[i]) for i, md in enumerate(metadata)]
        )
        self.jobshandler.put((Actions.SET_NAME, (job.id, title)))

        if metadata[0].get("_type") == "playlist" or len(metadata) > 1:
            ydl_opts.update(
                {
                    "output": self.app_config["ydl_server"].get(
                        "output_playlist", ydl_opts.get("output")
                    )
                }
            )

        cmd = self.get_ydl_full_cmd(ydl_opts, job.url, extra_opts)

        proc = Popen(cmd, stdout=PIPE, stderr=STDOUT)
        self.jobshandler.put((Actions.SET_PID, (job.id, proc.pid)))
        stdout_thread = Thread(
            target=self.download_log_update, args=(job, proc, output)
        )
        stdout_thread.start()

        rc = proc.wait()
        if rc == 0:
            read_proc_stdout(proc, output)
            job.log = Job.clean_logs(output.getvalue())
            job.status = Job.COMPLETED
        else:
            read_proc_stdout(proc, output)
            job.log = Job.clean_logs(output.getvalue())
            job.status = Job.FAILED
            print(
                "Error in download process (RC=" + str(rc) + "):\n" + output.getvalue()
            )
        stdout_thread.join()

    def resume_pending(self):
        db = JobsDB(readonly=False)
        jobs = db.get_jobs_with_logs(self.app_config["ydl_server"].get("max_log_entries", 100))
        not_endeds = [
            job
            for job in jobs
            if job["status"] == "Pending" or job["status"] == "Running"
        ]
        for pending in not_endeds:
            job = Job(
                pending["name"],
                Job.PENDING,
                "Queue stopped",
                int(pending["type"]),
                pending["format"],
                pending["urls"],
            )
            job.id = pending["id"]
            self.jobshandler.put((Actions.RESUME, job))

    def join(self):
        for thread in self.threads:
            thread.join()
