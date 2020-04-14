import os
import sqlite3

STATUS_NAME =["Running",
        "Completed",
        "Failed"]
class Job:
    def __init__(self, name, status, log):
        self.id = -1
        self.name = name
        self.status = status
        self.log = log
        self.last_update = ""

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
        cursor.execute("INSERT INTO jobs (name, status, log) VALUES (?,\
                ?, ?);", (job.name, str(job.status), job.log))
        job.id = cursor.lastrowid
        self.conn.commit()

    def update_job(self, job):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE jobs SET status = ?, log = ?, last_update = datetime() \
                where id = ?;", (str(job.status), job.log, str(job.id)))
        self.conn.commit()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY \
                AUTOINCREMENT, name TEXT NOT NULL, \
                status INTEGER NOT NULL, log TEXT, \
                last_update DATETIME DEFAULT CURRENT_TIMESTAMP);")
        self.conn.commit()

    def get_all(self, limit=50):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, status, log, last_update from jobs ORDER BY last_update DESC LIMIT ?;", (str(limit),))
        rows = []
        for job_id, name, status, log, last_update in cursor.fetchall():
            rows.append({'id': job_id,
                        'name': name,
                        'status': STATUS_NAME[status],
                        'log': log,
                        'last_update': last_update})
        return rows
