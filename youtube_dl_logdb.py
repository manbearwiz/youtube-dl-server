import os
import sqlite3
import re
from queue import Queue
from threading import Thread

STATUS_NAME =["Running",
        "Completed",
        "Failed",
        "Pending"]


class Actions:
    DOWNLOAD = 1
    PURGE_LOGS = 2
    INSERT = 3
    UPDATE = 4
    RESUME = 5

class Job:
    RUNNING = 0
    COMPLETED = 1
    FAILED = 2
    PENDING = 3

    def __init__(self, name, status, log, format):
        self.id = -1
        self.name = name
        self.status = status
        self.log = log
        self.last_update = ""
        self.format = format

    @staticmethod
    def clean_logs(logs):
        if not logs:
            return logs
        clean = ""
        for line in logs.split('\n'):
            line = re.sub('.*\r', '', line)
            if len(line) > 0:
                clean = '%s%s\n' % (clean, line)
        return clean

class JobsDB:
    def __init__(self, db_path, readonly=True):
        if not os.path.isfile(db_path):
            self.conn = sqlite3.connect("file://%s" % db_path)
            self.create_table()
            self.conn.close()
        self.conn = sqlite3.connect("file://%s%s" % (db_path,
                                            "?mode=ro" if readonly else ""),
                                    uri=True)

    def close(self):
        self.conn.close()

    def insert_job(self, job):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO jobs (name, status, log, format) VALUES (?,\
                ?, ?, ?);", (job.name, str(job.status), job.log, job.format))
        job.id = cursor.lastrowid
        self.conn.commit()

    def update_job(self, job):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE jobs SET status = ?, log = ?, last_update = datetime() \
                where id = ?;", (str(job.status), job.log, str(job.id)))
        self.conn.commit()

    def purge_jobs(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM jobs;")
        self.conn.commit()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY \
                AUTOINCREMENT, name TEXT NOT NULL, \
                status INTEGER NOT NULL, log TEXT, \
                format TEXT NOT NULL, \
                last_update DATETIME DEFAULT CURRENT_TIMESTAMP);")
        self.conn.commit()

    def get_all(self, limit=50):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, status, log, last_update, format from jobs ORDER BY last_update DESC LIMIT ?;", (str(limit),))
        rows = []
        for job_id, name, status, log, last_update, format in cursor.fetchall():
            rows.append({'id': job_id,
                        'name': name,
                        'status': STATUS_NAME[status],
                        'log': log,
                        'format': format,
                        'last_update': last_update})
        return rows

