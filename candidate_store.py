"""SQLite persistence for screened candidates and notification history."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.getenv("CANDIDATE_DB_PATH", Path(__file__).parent / "data" / "talentlens.sqlite3"))
STATUSES = (
    "Applied", "Under Review", "Shortlisted", "Interview Scheduled", "Rejected", "Hired"
)
NOTIFY_STATUSES = {"Shortlisted", "Interview Scheduled", "Rejected"}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_db():
    with connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                job_title TEXT NOT NULL,
                resume_file TEXT NOT NULL,
                score INTEGER NOT NULL,
                result_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Applied'
                    CHECK (status IN ('Applied','Under Review','Shortlisted','Interview Scheduled','Rejected','Hired')),
                status_updated_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                success INTEGER NOT NULL,
                failure TEXT,
                recipient TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_notification_history_candidate
                ON notification_history(candidate_id, timestamp DESC);
        """)


def create_candidate(*, name, email, job_title, resume_file, score, result):
    now = utc_now()
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO candidates
               (name,email,job_title,resume_file,score,result_json,status,status_updated_at,created_at)
               VALUES (?,?,?,?,?,?,'Applied',?,?)""",
            (name, email, job_title, resume_file, score,
             json.dumps(result, ensure_ascii=False), now, now),
        )
        return {"candidate_id": cursor.lastrowid, "status": "Applied", "status_updated_at": now}


def get_candidate(candidate_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        return dict(row) if row else None


def update_status(candidate_id, status):
    timestamp = utc_now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if current is None:
            return None
        if current["status"] == status:
            result = dict(current)
            result["unchanged"] = True
            return result
        conn.execute(
            "UPDATE candidates SET status=?, status_updated_at=? WHERE id=?",
            (status, timestamp, candidate_id),
        )
        result = dict(conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone())
        result["unchanged"] = False
        return result


def log_notification(candidate_id, status, timestamp, success, failure=None, recipient=None):
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO notification_history
               (candidate_id,status,timestamp,success,failure,recipient) VALUES (?,?,?,?,?,?)""",
            (candidate_id, status, timestamp, int(success), failure, recipient),
        )
        return cursor.lastrowid


def list_notifications(limit=50, candidate_id=None):
    limit = max(1, min(int(limit), 200))
    query = """SELECT n.id,n.candidate_id,c.name,c.job_title,n.status,n.timestamp,
                  n.success,n.failure
           FROM notification_history n JOIN candidates c ON c.id=n.candidate_id"""
    params = []
    if candidate_id is not None:
        query += " WHERE n.candidate_id=?"
        params.append(candidate_id)
    query += " ORDER BY n.timestamp DESC,n.id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def list_candidates(limit=200):
    limit = max(1, min(int(limit), 500))
    with connect() as conn:
        rows = conn.execute(
            "SELECT id,name,job_title,resume_file,score,status,status_updated_at,created_at,result_json FROM candidates ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["result"] = json.loads(item.pop("result_json"))
            output.append(item)
        return output
