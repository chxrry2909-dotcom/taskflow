
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

PRIORITY_RANK = {"low": 1, "medium": 2, "high": 3}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_db(path):
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


@contextmanager
def db_connection(path):
    conn = get_db(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path):
    with db_connection(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                priority_rank INTEGER NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 2,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_queue
            ON tasks(status, priority_rank DESC, created_at ASC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status
            ON tasks(status)
        """)

        # Add execution tracking columns to existing databases.
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(tasks)"
            ).fetchall()
        }

        if "picked_order" not in columns:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN picked_order INTEGER"
            )

        if "worker_name" not in columns:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN worker_name TEXT"
            )


def row_to_dict(row):
    if row is None:
        return None

    item = dict(row)
    item["payload"] = json.loads(item["payload"])
    item["result"] = (
        json.loads(item["result"]) if item["result"] else None
    )

    return item


def create_task(path, task_type, priority, payload, max_retries=2):
    task_id = str(uuid.uuid4())
    now = utc_now()

    with db_connection(path) as conn:
        conn.execute("""
            INSERT INTO tasks
            (
                id, task_type, priority, priority_rank,
                payload, status, max_retries,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        """, (
            task_id,
            task_type,
            priority,
            PRIORITY_RANK[priority],
            json.dumps(payload),
            max_retries,
            now,
            now
        ))

    return get_task(path, task_id)


def get_task(path, task_id):
    with db_connection(path) as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

    return row_to_dict(row)


def list_tasks(path, status=None, limit=100):
    with db_connection(path) as conn:
        if status:
            rows = conn.execute("""
                SELECT * FROM tasks
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (status, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM tasks
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

    return [row_to_dict(row) for row in rows]


def get_stats(path, worker_count):
    with db_connection(path) as conn:
        rows = conn.execute("""
            SELECT status, COUNT(*) AS count
            FROM tasks
            GROUP BY status
        """).fetchall()

    counts = {
        row["status"]: row["count"]
        for row in rows
    }

    return {
        "pending": counts.get("pending", 0),
        "processing": counts.get("processing", 0),
        "completed": counts.get("completed", 0),
        "failed": counts.get("failed", 0),
        "workers": worker_count
    }
