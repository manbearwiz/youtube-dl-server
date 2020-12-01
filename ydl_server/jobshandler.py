from queue import Queue
from threading import Thread
from ydl_server.logdb import JobsDB, Job, Actions

queue = Queue()
thread = None
done = False

def start(dl_queue):
    thread = Thread(target=worker, args=(dl_queue,))
    thread.start()

def put(obj):
    queue.put(obj)

def finish():
    done = True

def worker(dl_queue):
    db = JobsDB(readonly=False)
    while not done:
        action, job = queue.get()
        if action == Actions.PURGE_LOGS:
            db.purge_jobs()
        elif action == Actions.INSERT:
            db.insert_job(job)
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
        queue.task_done()

def join():
    if thread is not None:
        return thread.join()
