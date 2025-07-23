import sqlite3
import re
import datetime
import json
from functools import wraps

from ydl_server.config import app_config

STATUS_NAME = ["Running", "Completed", "Failed", "Pending", "Aborted"]

SCHEMA_VERSION = 3

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

    def __init__(self, name, status, log, jobtype, format=None, url=None, id=-1, pid=0, force_generic_extractor=False, extra_params={}):
        self.id = id
        self.name = name
        self.status = status
        self.log = log
        self.last_update = ""
        self.format = format
        self.type = jobtype
        self.url = url
        self.pid = pid
        self.force_generic_extractor = force_generic_extractor
        self.extra_params = extra_params

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


def with_cursor(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        cursor = self.conn.cursor()
        try:
            result = f(self, cursor, *args, **kwargs)
            self.conn.commit()
            return result
        finally:
            cursor.close()
    return wrapper

class JobsDB:
    SCHEMA_VERSION = SCHEMA_VERSION

    @staticmethod
    def init():
        conn = sqlite3.connect(
            "file://%s" % app_config["ydl_server"].get("metadata_db_path"), uri=True
        )
        try:
            version = JobsDB.db_version(conn)
            JobsDB.migrate(conn, version)
        finally:
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
        print(f"Migrating database from version {version}")
        match version:
            case -1:
                print("No jobs table found, creating")
                JobsDB.create(conn)
                return
            case 0:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info('jobs')")
                columns = [row[1] for row in cursor.fetchall()]
                if set(columns) != set([
                        "id",
                        "name",
                        "status",
                        "format",
                        "log",
                        "last_update",
                        "type",
                        "url",
                        "pid",
                    ]):
                    print("Outdated jobs table, cleaning up and recreating")
                    cursor.execute("DROP TABLE if exists jobs;")
                    conn.commit()
                    JobsDB.create(conn)
                    return
                if "force_generic_extractor" not in columns:
                    print("Adding force_generic_extractor column to jobs table")
                    cursor.execute("ALTER TABLE jobs ADD COLUMN force_generic_extractor INTEGER DEFAULT 0;")
                    conn.commit()
                cursor.execute(
                    f"PRAGMA user_version = {JobsDB.SCHEMA_VERSION};"
                )
                conn.commit()
                return
            case 1:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info('jobs')")
                columns = [row[1] for row in cursor.fetchall()]
                if "force_generic_extractor" not in columns:
                    print("Adding force_generic_extractor column to jobs table")
                    cursor.execute("ALTER TABLE jobs ADD COLUMN force_generic_extractor INTEGER DEFAULT 0;")
                    conn.commit()
                cursor.execute(
                    f"PRAGMA user_version = {JobsDB.SCHEMA_VERSION};"
                )
                conn.commit()
                return
            case 2:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info('jobs')")
                columns = [row[1] for row in cursor.fetchall()]
                if "extra_params" not in columns:
                    print("Adding extra_params column to jobs table")
                    cursor.execute("ALTER TABLE jobs ADD COLUMN extra_params TEXT DEFAULT '{}';") 
                    conn.commit()
                cursor.execute(
                    f"PRAGMA user_version = {JobsDB.SCHEMA_VERSION};"
                )
                conn.commit()
                return
            case JobsDB.SCHEMA_VERSION:
                cursor = conn.cursor()
                cursor.execute(
                    f"PRAGMA user_version = {JobsDB.SCHEMA_VERSION};"
                )
                conn.commit()
                return
        return JobsDB.migrate(conn, version + 1)

    @staticmethod
    def create(conn):
        cursor = conn.cursor()
        try:
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
                        pid INTEGER,
                        force_generic_extractor INTEGER DEFAULT 0,
                        extra_params TEXT DEFAULT '{}'
                    );
                """
            )
            cursor.execute(
                f"PRAGMA user_version = {SCHEMA_VERSION};"
            )
            conn.commit()
        finally:
            cursor.close()

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

    @with_cursor
    def insert_job(self, cursor, job):
        cursor.execute(
            """
            INSERT INTO jobs
                (name, status, log, format, type, url, pid, force_generic_extractor, extra_params)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                job.name,
                str(job.status),
                job.log,
                job.format,
                str(job.type),
                "\n".join(job.url),
                job.pid,
                int(getattr(job, "force_generic_extractor", False)),
                json.dumps(getattr(job, "extra_params", {})),
            ),
        )
        job.id = cursor.lastrowid

    @with_cursor
    def update_job(self, cursor, job):
        cursor.execute(
            """
            UPDATE jobs
            SET status = ?, log = ?, last_update = datetime(), force_generic_extractor = ?, extra_params = ? \
            WHERE id = ?;
            """,
            (str(job.status), job.log, int(getattr(job, "force_generic_extractor", False)), json.dumps(getattr(job, "extra_params", {})), str(job.id)),
        )

    @with_cursor
    def set_job_status(self, cursor, job_id, status):
        cursor.execute(
            """
            UPDATE jobs
            SET status = ?, last_update = datetime() \
            WHERE id = ?;
            """,
            (str(status), str(job_id)),
        )

    @with_cursor
    def set_job_pid(self, cursor, job_id, pid):
        cursor.execute(
            """
            UPDATE jobs
            SET pid = ?, last_update = datetime() \
            WHERE id = ?;
            """,
            (str(pid), str(job_id)),
        )

    @with_cursor
    def set_job_log(self, cursor, job_id, log):
        cursor.execute(
            """
            UPDATE jobs
            SET log = ?, last_update = datetime() \
            WHERE id = ?;
            """,
            (log, str(job_id)),
        )

    @with_cursor
    def set_job_name(self, cursor, job_id, name):
        cursor.execute(
            """
            UPDATE jobs
            SET name = ?, last_update = datetime() \
            WHERE id = ?;
            """,
            (name, str(job_id)),
        )

    def vacuum(self):
        print("Vacuuming database")
        self.conn.execute("VACUUM")

    @with_cursor
    def purge_jobs(self, cursor):
        cursor.execute("DELETE FROM jobs;")
        return cursor.rowcount

    @with_cursor
    def delete_job_safe(self, cursor, job_id):
        cursor.execute(
            "DELETE FROM jobs WHERE id = ? AND ( status = ? OR status = ? );",
            (str(job_id), Job.ABORTED, Job.FAILED),
        )
        return cursor.rowcount

    @with_cursor
    def delete_job(self, cursor, job_id):
        cursor.execute(
            "DELETE FROM jobs WHERE id = ?;",
            (str(job_id),),
        )
        return cursor.rowcount

    @with_cursor
    def clean_old_jobs(self, cursor, limit=10):
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
            return cursor.rowcount

    @with_cursor
    def get_job_by_id(self, cursor, job_id):
        cursor.execute(
            """
            SELECT
                id, name, status, log, last_update, format, type, url, pid, force_generic_extractor, extra_params
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
            force_generic_extractor,
            extra_params,
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
            "force_generic_extractor": bool(force_generic_extractor),
            "extra_params": json.loads(extra_params or '{}'),
        }

    @with_cursor
    def get_jobs_with_logs(self, cursor, limit=50, status=None):
        status = STATUS_NAME.index(status.capitalize()) if status and status.capitalize() in STATUS_NAME else -1
        if status >= 0:
            cursor.execute(
                """
                SELECT
                    id, name, status, log, last_update, format, type, url, pid, force_generic_extractor, extra_params
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
                    id, name, status, log, last_update, format, type, url, pid, force_generic_extractor, extra_params
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
            force_generic_extractor,
            extra_params,
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
                    "force_generic_extractor": bool(force_generic_extractor),
                    "extra_params": json.loads(extra_params or '{}'),
                }
            )
        return rows

    @with_cursor
    def get_jobs(self, cursor, limit=50, status=None):
        status = STATUS_NAME.index(status.capitalize()) if status and status.capitalize() in STATUS_NAME else -1
        if status >= 0:
            cursor.execute(
                """
                SELECT
                    id, name, status, last_update, format, type, url, pid, force_generic_extractor, extra_params
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
                    id, name, status, last_update, format, type, url, pid, force_generic_extractor, extra_params
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
            force_generic_extractor,
            extra_params,
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
                    "force_generic_extractor": bool(force_generic_extractor),
                    "extra_params": json.loads(extra_params or '{}'),
                }
            )
        return rows
