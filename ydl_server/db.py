import sqlite3
import re
import datetime

from ydl_server.config import app_config

STATUS_NAME = ["Running", "Completed", "Failed", "Pending", "Aborted"]

SCHEMA_VERSION = 1

class Actions:
    DOWNLOAD = 1
    PURGE_LOGS = 2
    INSERT = 3
    UPDATE = 4
    RESUME = 5
    SET_NAME = 6
    SET_STATUS = 7
    SET_LOG = 8
    CLEAN_LOGS = 9
    SET_PID = 10
    DELETE_LOG = 11
    DELETE_LOG_SAFE = 12


class JobType:
    YDL_DOWNLOAD = 0
    YDL_UPDATE = 1


class Job:
    RUNNING = 0
    COMPLETED = 1
    FAILED = 2
    PENDING = 3
    ABORTED = 4

    def __init__(self, name, status, log, jobtype, format=None, url=None, id=-1, pid=0):
        self.id = id
        self.name = name
        self.status = status
        self.log = log
        self.last_update = ""
        self.format = format
        self.type = jobtype
        self.url = url
        self.pid = pid

    @staticmethod
    def clean_logs(logs):
        if not logs:
            return logs
        clean = ""
        for line in logs.split("\n"):
            line = re.sub(".*\r", "", line)
            if len(line) > 0:
                clean = "%s%s\n" % (clean, line)
        return clean


class JobsDB:

    @staticmethod
    def init():
        conn = sqlite3.connect(
            "file://%s" % app_config["ydl_server"].get("metadata_db_path"), uri=True
        )
        version = JobsDB.db_version(conn)
        JobsDB.migrate(conn, version)
        conn.close()
        

    @staticmethod
    def db_version(conn):
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        table_exists = cursor.fetchone()
        if not table_exists:
            return -1
        cursor.execute("PRAGMA user_version;")
        version = int(cursor.fetchone()[0])
        return version

    @staticmethod
    def migrate(conn, version):
        print("Migrating database from version %d" % version)
        match version:
            case -1:
                print("No jobs table found, creating")
                JobsDB.create(conn)
                return
            case 0:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info('jobs')")
                columns = [row[1] for row in cursor.fetchall()]
                if set(columns) != set(
                    [
                        "id",
                        "name",
                        "status",
                        "format",
                        "log",
                        "last_update",
                        "type",
                        "url",
                        "pid",
                    ]
                ):
                    print("Outdated jobs table, cleaning up and recreating")
                    cursor.execute("DROP TABLE if exists jobs;")
                    conn.commit()
                    JobsDB.create(conn)
                    return
            case SCHEMA_VERSION:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    PRAGMA user_version = """ + str(SCHEMA_VERSION) + """;
                    """
                )
                conn.commit()
                return
        return JobsDB.migrate(conn, version + 1)


    @staticmethod
    def create(conn):
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE if not exists jobs
                (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    log TEXT,
                    format TEXT,
                    last_update DATETIME DEFAULT CURRENT_TIMESTAMP,
                    type INTEGER NOT NULL,
                    url TEXT,
                    pid INTEGER
                );
            """
        )
        cursor.execute(
            """
            PRAGMA user_version = """ + str(SCHEMA_VERSION) + """;
            """
        )
        conn.commit()

    @staticmethod
    def convert_datetime_to_tz(dt):
        dt = datetime.datetime.strptime("{} +0000".format(dt), "%Y-%m-%d %H:%M:%S %z")
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")

    def __init__(self, readonly=True):
        self.conn = sqlite3.connect(
            "file://%s%s"
            % (
                app_config["ydl_server"].get("metadata_db_path"),
                "?mode=ro" if readonly else "",
            ),
            uri=True,
        )

    def close(self):
        self.conn.close()

    def insert_job(self, job):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO jobs
                (name, status, log, format, type, url, pid)
            VALUES
                (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                job.name,
                str(job.status),
                job.log,
                job.format,
                str(job.type),
                "\n".join(job.url),
                job.pid,
            ),
        )
        job.id = cursor.lastrowid
        self.conn.commit()

    def update_job(self, job):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE jobs
            SET status = ?, log = ?, last_update = datetime() \
            WHERE id = ?;
            """,
            (str(job.status), job.log, str(job.id)),
        )
        self.conn.commit()

    def set_job_status(self, job_id, status):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE jobs
            SET status = ?, last_update = datetime() \
            WHERE id = ?;
            """,
            (str(status), str(job_id)),
        )
        self.conn.commit()

    def set_job_pid(self, job_id, pid):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE jobs
            SET pid = ?, last_update = datetime() \
            WHERE id = ?;
            """,
            (str(pid), str(job_id)),
        )
        self.conn.commit()

    def set_job_log(self, job_id, log):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE jobs
            SET log = ?, last_update = datetime() \
            WHERE id = ?;
            """,
            (log, str(job_id)),
        )
        self.conn.commit()

    def set_job_name(self, job_id, name):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE jobs
            SET name = ?, last_update = datetime() \
            WHERE id = ?;
            """,
            (name, str(job_id)),
        )
        self.conn.commit()

    def purge_jobs(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM jobs;")
        self.conn.commit()
        self.conn.execute("VACUUM")

    def delete_job_safe(self, job_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM jobs WHERE id = ? AND ( status = ? OR status = ? );",
            (str(job_id), Job.ABORTED, Job.FAILED),
        )
        self.conn.commit()
        self.conn.execute("VACUUM")

    def delete_job(self, job_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM jobs WHERE id = ?;",
            (str(job_id),),
        )
        self.conn.commit()
        self.conn.execute("VACUUM")

    def clean_old_jobs(self, limit=10):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT last_update
            FROM jobs
            ORDER BY last_update DESC
            LIMIT ?;
            """,
            (str(limit),),
        )
        rows = list(cursor.fetchall())
        if len(rows) > 0:
            cursor.execute(
                "DELETE FROM jobs WHERE last_update < ? AND status != ? and status != ?;",
                (rows[-1][0], Job.PENDING, Job.RUNNING),
            )
        self.conn.commit()
        self.conn.execute("VACUUM")

    def get_job_by_id(self, job_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                id, name, status, log, last_update, format, type, url, pid
            FROM
                jobs
            WHERE id = ?;
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if not row:
            return
        (
            job_id,
            name,
            status,
            log,
            last_update,
            format,
            jobtype,
            url,
            pid,
        ) = row
        return {
            "id": job_id,
            "name": name,
            "status": STATUS_NAME[status],
            "log": log,
            "format": format,
            "last_update": JobsDB.convert_datetime_to_tz(last_update),
            "type": jobtype,
            "urls": url.split("\n"),
            "pid": pid,
        }

    def get_jobs_with_logs(self, limit=50, status=None):
        cursor = self.conn.cursor()
        status = STATUS_NAME.index(status.capitalize()) if status and status.capitalize() in STATUS_NAME else -1
        if status >= 0:
            cursor.execute(
                """
                SELECT
                    id, name, status, log, last_update, format, type, url, pid
                FROM
                    jobs
                WHERE
                    status = ?
                ORDER BY last_update DESC LIMIT ?;
                """,
                (status, str(limit),),
            )
        else:
            cursor.execute(
                """
                SELECT
                    id, name, status, log, last_update, format, type, url, pid
                FROM
                    jobs
                ORDER BY last_update DESC LIMIT ?;
                """,
                (str(limit),),
            )
        rows = []
        for (
            job_id,
            name,
            status,
            log,
            last_update,
            format,
            jobtype,
            url,
            pid,
        ) in cursor.fetchall():
            rows.append(
                {
                    "id": job_id,
                    "name": name,
                    "status": STATUS_NAME[status],
                    "log": log,
                    "format": format,
                    "last_update": JobsDB.convert_datetime_to_tz(last_update),
                    "type": jobtype,
                    "urls": url.split("\n"),
                    "pid": pid,
                }
            )
        return rows

    def get_jobs(self, limit=50, status=None):
        cursor = self.conn.cursor()
        status = STATUS_NAME.index(status.capitalize()) if status and status.capitalize() in STATUS_NAME else -1
        if status >= 0:
            cursor.execute(
                """
                SELECT
                    id, name, status, last_update, format, type, url, pid
                FROM
                    jobs
                WHERE
                    status = ?
                ORDER BY last_update DESC LIMIT ?;
                """,
                (status, str(limit),),
            )
        else:
            cursor.execute(
                """
                SELECT
                    id, name, status, last_update, format, type, url, pid
                FROM
                    jobs
                ORDER BY last_update DESC LIMIT ?;
                """,
                (str(limit),),
            )
        rows = []
        for (
            job_id,
            name,
            status,
            last_update,
            format,
            jobtype,
            url,
            pid,
        ) in cursor.fetchall():
            rows.append(
                {
                    "id": job_id,
                    "name": name,
                    "status": STATUS_NAME[status],
                    "format": format,
                    "last_update": JobsDB.convert_datetime_to_tz(last_update),
                    "type": jobtype,
                    "urls": url.split("\n"),
                    "pid": pid,
                }
            )
        return rows
