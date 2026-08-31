import importlib
import io
import json
import os
import re
import shlex
import time
from datetime import datetime, timezone
from importlib import metadata
from queue import Empty, Queue
from subprocess import PIPE, STDOUT, Popen
from threading import Thread
from time import sleep

from ydl_server.config import resolve_finished_file
from ydl_server.db import Actions, Job, JobsDB, JobType

YDL_MODULES = ["youtube_dl", "youtube_dlc", "yt_dlp"]


class OptionsError(Exception):
    pass


class DownloadError(Exception):
    pass


class CutError(Exception):
    pass

# Fallback when an extractor announces an upcoming event without a release timestamp
UPCOMING_DELAY_RE = re.compile(
    r"(?:will begin in|begins in|premieres in|starts in)\s+(\d+)\s+(second|minute|hour|day)s?",
    re.IGNORECASE,
)

DELAY_UNIT_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}

SCHEDULE_MIN_DELAY = 300
SCHEDULE_RELEASE_BUFFER = 60

SENSITIVE_OPTS = {
    "--username",
    "--password",
    "--video-password",
    "--ap-username",
    "--ap-password",
    "--client-secret",
    "--add-header",
}


def get_ydl_website(ydl_module_name):
    try:
        meta = metadata.metadata(ydl_module_name)
    except metadata.PackageNotFoundError:
        print(f"Package {ydl_module_name} not found, skipping get_ydl_website")
        return ""

    url = meta.get("Home-page")
    if not url:
        urls = {
            entry.split(",", 1)[0].strip(): entry.split(",", 1)[1].strip()
            for entry in meta.get_all("Project-URL") or []
            if "," in entry
        }
        url = urls.get("Homepage") or urls.get("Documentation") or urls.get("Repository")
    return url


def parse_upcoming_delay(output):
    """Seconds since epoch derived from a 'will begin in X hours' message, or None."""
    match = UPCOMING_DELAY_RE.search(output or "")
    if not match:
        return None
    return int(time.time()) + int(match.group(1)) * DELAY_UNIT_SECONDS[match.group(2).lower()]


def read_proc_stdout(proc, strio):
    strio.write(proc.stdout.read1().decode())


def format_cmd(cmd):
    """Shell-quoted command line with credential values masked."""
    args, redact = [], False
    for arg in cmd:
        args.append("***" if redact else arg)
        redact = arg in SENSITIVE_OPTS
    return shlex.join(args)


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

        self.app_config["ydl_last_update"] = datetime.now(timezone.utc)

        self.import_ydl_module()

        print(f"Using {self.ydl_module_name} module")

    def start(self):
        self.download_workers_count = self.app_config["ydl_server"].get(
            "download_workers_count", 2
        )
        for i in range(self.download_workers_count):
            thread = Thread(target=self.worker, args=(i,))
            self.threads.append(thread)
            thread.start()
            print(f"Started dl worker {i}")

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
            output = io.StringIO()
            try:
                if job.type == JobType.YDL_DOWNLOAD:
                    self.download(job, {"format": job.format}, output)
                elif job.type == JobType.FFMPEG_CUT:
                    self.cut(job, output)
            except Exception as e:  # noqa: BLE001 - worker thread must survive any download failure
                job.status = Job.FAILED
                job.log = f"Error during download task:\n{type(e).__name__}:\n\t{e!s}"
                print(
                    f"Error during download task:\n{type(e).__name__}:\n\t{e!s}"
                )
            self.jobshandler.put((Actions.UPDATE, job))

    def get_format_and_profile(self, format_string):
        fmt, audio, profile, aliases = None, None, None, []
        for s in filter(None, (format_string or "").split(",")):
            if s.startswith("profile/"):
                profile = s
            elif s.startswith("alias/"):
                aliases.append(s)
            elif s.startswith(("audio/", "bestaudio/")):
                audio = s
            else:
                fmt = s
        return fmt, audio, profile, aliases

    def get_profile(self, profile_str):
        if not profile_str:
            return {}
        profile_name = "/".join(profile_str.split("/")[1:])
        profile = self.app_config.get("profiles", {}).get(profile_name, {}).get('ydl_options')
        if not profile:
            raise OptionsError(f"Unknown profile '{profile_str}'")
        return profile

    def get_aliases(self, alias_strs):
        options = {}
        for alias_str in alias_strs:
            alias_name = "/".join(alias_str.split("/")[1:])
            alias = self.app_config.get("aliases", {}).get(alias_name, {}).get("ydl_options")
            if not alias:
                raise OptionsError(f"Unknown alias '{alias_str}'")
            options.update(alias)
        return options

    def get_ydl_options(self, ydl_config, request_options):
        ydl_config = ydl_config.copy()
        req_format, req_audio, req_profile, req_aliases = self.get_format_and_profile(request_options.get("format"))

        profile = self.get_profile(req_profile)
        aliases = self.get_aliases(req_aliases)
        if profile:
            req_format = profile.get("format") if req_format is None else req_format
        if aliases:
            req_format = aliases.get("format") if req_format is None else req_format

        if req_audio is not None and req_format is None:
            ydl_config.update({"extract-audio": None})
            ydl_config.update({"audio-format": req_audio.split("/")[-1]})

        if req_format is not None:
            if req_format == "video/best":
                req_format = "video/bestvideo"
            # youtube-dl downloads BEST video and audio by default
            if req_format.startswith("video/") and req_format != "video/best":
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
        if aliases:
            aliases = {k: v for k, v in aliases.items() if k != "format"}
            ydl_config.update(aliases)
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

    def probe_upcoming(self, url, force_generic_extractor=False, error_output=None):
        """Release timestamp and title of an upcoming live event, or None.

        --ignore-no-formats-error turns the "This live event will begin in ..."
        extraction error into a warning, so the metadata is still returned.
        """
        if not self.app_config["ydl_server"].get("schedule_upcoming", True):
            return None
        ydl_opts = self.app_config.get("ydl_options", {})
        extra_opts = ["-J", "--flat-playlist", "--ignore-no-formats-error"]
        if force_generic_extractor:
            extra_opts.append("--force-generic-extractor")
        cmd = self.get_ydl_full_cmd(ydl_opts, url, extra_opts)

        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, _ = proc.communicate()
        if proc.wait() != 0:
            return None

        for line in stdout.decode().strip().split("\n"):
            try:
                metadata = json.loads(line)
            except json.JSONDecodeError:
                continue
            if metadata.get("live_status") != "is_upcoming":
                continue
            release = metadata.get("release_timestamp")
            if release is None:
                release = parse_upcoming_delay(error_output)
            if release is None:
                continue
            return int(release), metadata.get("title")
        return None

    def schedule_job(self, job, release_ts, title=None):
        """Park an upcoming live event until its release time instead of failing it."""
        attempts = job.extra_params.get("schedule_attempts", 0) + 1
        max_attempts = self.app_config["ydl_server"].get("schedule_max_attempts", 24)
        if attempts > max_attempts:
            job.log = Job.clean_logs(
                "{}\n[scheduled] giving up after {} attempts".format(job.log or "", max_attempts)
            )
            job.status = Job.FAILED
            return

        job.extra_params = {**job.extra_params, "schedule_attempts": attempts}
        job.scheduled_at = max(
            release_ts + SCHEDULE_RELEASE_BUFFER, int(time.time()) + SCHEDULE_MIN_DELAY
        )
        job.status = Job.SCHEDULED
        job.log = Job.clean_logs(
            "{}\n[scheduled] this event has not started yet, retrying at {} (attempt {}/{})".format(
                job.log or "",
                datetime.fromtimestamp(job.scheduled_at, tz=timezone.utc)
                .astimezone()
                .strftime("%Y-%m-%d %H:%M:%S"),
                attempts,
                max_attempts,
            )
        )
        if title:
            self.jobshandler.put((Actions.SET_NAME, (job.id, title)))
        # A pid left over from a previous attempt must not be signaled on abort
        self.jobshandler.put((Actions.SET_PID, (job.id, 0)))

    def get_ydl_full_cmd(self, opt_dict, url, extra_opts=None):
        cmd = [self.ydl_module_name]
        if opt_dict is not None:
            for key, val in opt_dict.items():
                if isinstance(val, bool) and not val:
                    continue
                cmd.append(f"--{key}")
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
            job.log = Job.clean_logs(f"[cmd] {format_cmd(cmd)}\n{metadata}")
            upcoming = self.probe_upcoming(
                job.url, force_generic_extractor=force_generic, error_output=metadata
            )
            if upcoming:
                self.schedule_job(job, *upcoming)
                return
            job.status = Job.FAILED
            print("Error in metadata fetching process:\n" + job.log)
            raise DownloadError(job.log)

        title = ", ".join(
            [md.get("title", job.url[i]) for i, md in enumerate(metadata)]
        )
        self.jobshandler.put((Actions.SET_NAME, (job.id, title)))

        upcoming = next(
            (md for md in metadata if md.get("live_status") == "is_upcoming"), None
        )
        if upcoming and self.app_config["ydl_server"].get("schedule_upcoming", True):
            release = upcoming.get("release_timestamp")
            if release is not None:
                job.log = Job.clean_logs(f"[cmd] {format_cmd(cmd)}")
                self.schedule_job(job, int(release))
                return

        if metadata[0].get("_type") == "playlist" or len(metadata) > 1:
            ydl_opts.update(
                {
                    "output": self.app_config["ydl_server"].get(
                        "output_playlist", ydl_opts.get("output")
                    )
                }
            )
        elif job.extra_params.get("title") and ydl_opts.get("output"):
            output_template_parts = ydl_opts.get("output").split("/")
            output_template = '/'.join(output_template_parts[:-1]) + f"/{job.extra_params.get("title")}.%(ext)s"
            ydl_opts.update(
                {
                    "output": output_template,
                }
            )

        cmd = self.get_ydl_full_cmd(ydl_opts, job.url, extra_opts)
        output.write(f"[cmd] {format_cmd(cmd)}\n")

        try:
            fmt_proc = Popen(
                self.get_ydl_full_cmd(ydl_opts, job.url, extra_opts + ["--simulate", "--print", "%(format)s"]),
                stdout=PIPE, stderr=PIPE
            )
            fmt_stdout, _ = fmt_proc.communicate()
            if fmt_proc.returncode == 0 and fmt_stdout.strip():
                output.write(f"[format] {fmt_stdout.decode().strip()}\n")
        except (OSError, UnicodeDecodeError) as e:
            print("Error looking up format", e)

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

    def cut(self, job, output):
        params = job.extra_params
        src = resolve_finished_file(job.url[0])
        if src is None:
            raise CutError("Invalid source file path")
        if not os.path.isfile(src):
            raise CutError(f"Source file not found: {job.url[0]}")
        dst = os.path.join(os.path.dirname(src), params["output"])

        cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-y", "-ss", str(params.get("start") or "0")]
        if params.get("end"):
            cmd.extend(["-to", str(params["end"])])
        cmd.extend(["-i", src])
        if params.get("mode", "fast") == "fast":
            cmd.extend(["-c", "copy", "-avoid_negative_ts", "make_zero"])
        cmd.append(dst)

        output.write(f"[cmd] {format_cmd(cmd)}\n")
        proc = Popen(cmd, stdout=PIPE, stderr=STDOUT)
        self.jobshandler.put((Actions.SET_PID, (job.id, proc.pid)))
        stdout_thread = Thread(
            target=self.download_log_update, args=(job, proc, output)
        )
        stdout_thread.start()

        rc = proc.wait()
        read_proc_stdout(proc, output)
        job.log = Job.clean_logs(output.getvalue())
        if rc == 0:
            job.status = Job.COMPLETED
        else:
            job.status = Job.FAILED
            if os.path.isfile(dst):
                os.remove(dst)
            print(
                "Error in cut process (RC=" + str(rc) + "):\n" + output.getvalue()
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
                extra_params=pending.get("extra_params", {})
            )
            job.id = pending["id"]
            job.force_generic_extractor = pending.get("force_generic_extractor", False)
            self.jobshandler.put((Actions.RESUME, job))

    def join(self):
        for thread in self.threads:
            thread.join()
