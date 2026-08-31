import time
from queue import Empty, Queue
from threading import Event, Thread

from ydl_server.db import Actions, Job, JobsDB


class JobsHandler:
    def __init__(self, app_config):
        self.queue = Queue()
        self.thread = None
        self.scheduler_thread = None
        self.done = False
        self.app_config = app_config

    def start(self, dl_queue):
        self.thread = Thread(target=self.worker, args=(dl_queue,))
        self.thread.start()
        self.scheduler_thread = Thread(target=self.scheduler_worker)
        self.scheduler_thread.start()

    def stop(self):
        self.done = True

    def put(self, obj):
        self.queue.put(obj)

    def insert_and_wait(self, job, timeout=5):
        event = Event()
        self.queue.put((Actions.INSERT, job, event))
        event.wait(timeout)

    def finish(self):
        self.done = True

    def worker(self, dl_queue):
        db = JobsDB(readonly=False)
        while not self.done:
            try:
                item = self.queue.get(timeout=1)
            except Empty:
                continue
            action, job = item[0], item[1]
            event = item[2] if len(item) > 2 else None
            if action == Actions.PURGE_LOGS:
                if db.purge_jobs():
                    db.vacuum()
            elif action == Actions.INSERT:
                if db.clean_old_jobs(
                        self.app_config["ydl_server"].get("max_log_entries", 100) - 1
                    ):
                    db.vacuum()
                db.insert_job(job)
                if event:
                    event.set()
                dl_queue.put(job)
            elif action == Actions.UPDATE:
                db.update_job(job)
            elif action == Actions.RESUME:
                db.update_job(job)
                dl_queue.put(job)
            elif action == Actions.SET_NAME:
                job_id, name = job
                db.set_job_name(job_id, name)
            elif action == Actions.SET_LOG:
                job_id, log = job
                db.set_job_log(job_id, log)
            elif action == Actions.SET_STATUS:
                job_id, status = job
                db.set_job_status(job_id, status)
            elif action == Actions.SET_PID:
                job_id, pid = job
                db.set_job_pid(job_id, pid)
            elif action == Actions.CLEAN_LOGS:
                if db.clean_old_jobs():
                    db.vacuum()
            elif action == Actions.DELETE_LOG_SAFE:
                deleted = db.delete_job_safe(job["id"])
                if deleted:
                    db.vacuum()
            elif action == Actions.DELETE_LOG:
                deleted = db.delete_job(job["id"])
                if deleted:
                    db.vacuum()
            self.queue.task_done()

    def scheduler_worker(self):
        """Re-queue scheduled jobs (upcoming live events) once their release time is reached."""
        db = JobsDB(readonly=True)
        interval = self.app_config["ydl_server"].get("schedule_check_interval", 60)
        elapsed = interval
        while not self.done:
            if elapsed < interval:
                time.sleep(1)
                elapsed += 1
                continue
            elapsed = 0
            for due in db.get_due_scheduled_jobs(int(time.time())):
                print(f"Scheduled time reached for job {due['id']}")
                job = Job(
                    due["name"],
                    Job.PENDING,
                    "Scheduled time reached",
                    int(due["type"]),
                    due["format"],
                    due["urls"],
                    id=due["id"],
                    force_generic_extractor=due["force_generic_extractor"],
                    extra_params=due["extra_params"],
                )
                self.put((Actions.RESUME, job))
        db.close()

    def join(self):
        if self.scheduler_thread is not None:
            self.scheduler_thread.join()
        if self.thread is not None:
            return self.thread.join()
