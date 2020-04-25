from queue import Queue
from threading import Thread
from youtube_dl_logdb import JobsDB, Job, Actions

queue = Queue()
db_path = None
thread = None
done = False

def start(database_path, dl_queue):
    thread = Thread(target=worker, args=(database_path, dl_queue))
    thread.start()

def put(obj):
    queue.put(obj)

def finish():
    done = True

def worker(db_path, dl_queue):
    db = JobsDB(db_path, readonly=False)
    while not done:
        action, job = queue.get()
        if action == Actions.PURGE_LOGS:
            db.purge_jobs()
        elif action == Actions.INSERT:
            db.insert_job(job)
            dl_queue.put((Actions.DOWNLOAD, job))
        elif action == Actions.UPDATE:
            db.update_job(job)
        elif action == Actions.RESUME:
            db.update_job(job)
            dl_queue.put((Actions.DOWNLOAD, job))
        queue.task_done()

