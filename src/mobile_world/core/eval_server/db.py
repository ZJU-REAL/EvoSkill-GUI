"""SQLite database for eval job persistence."""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = None  # Set by app.py at startup


def _get_db_path() -> str:
    if DB_PATH is None:
        raise RuntimeError("DB_PATH not initialized — call init_db() first")
    return DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_dir: str = ".") -> None:
    global DB_PATH
    path = Path(db_dir) / "eval_jobs.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH = str(path)
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id                TEXT PRIMARY KEY,
            label             TEXT DEFAULT '',
            status            TEXT NOT NULL DEFAULT 'queued',
            agent_type        TEXT NOT NULL,
            model_name        TEXT NOT NULL,
            llm_base_url      TEXT NOT NULL,
            api_key           TEXT DEFAULT '',
            env_count         INTEGER NOT NULL,
            max_round         INTEGER DEFAULT 50,
            step_wait_time    REAL DEFAULT 1.0,
            auto_retry          INTEGER DEFAULT 0,
            enable_user_interaction INTEGER DEFAULT 0,
            env_image         TEXT DEFAULT '',
            container_prefix  TEXT NOT NULL,
            log_dir           TEXT DEFAULT '',
            tmux_session      TEXT DEFAULT '',
            log_file          TEXT DEFAULT '',
            total_tasks       INTEGER,
            successful_tasks  INTEGER,
            success_rate      REAL,
            scores_json       TEXT DEFAULT '',
            created_at        REAL DEFAULT (strftime('%s', 'now')),
            started_at        TEXT,
            finished_at       TEXT
        )
    """)
    conn.commit()
    # Migration: add auto_retry column if missing (for existing databases)
    try:
        conn.execute("SELECT auto_retry FROM jobs LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE jobs ADD COLUMN auto_retry INTEGER DEFAULT 0")
        conn.commit()
    # Migration: add env_image column if missing
    try:
        conn.execute("SELECT env_image FROM jobs LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE jobs ADD COLUMN env_image TEXT DEFAULT ''")
        conn.commit()
    conn.close()


def create_job(
    agent_type: str,
    model_name: str,
    llm_base_url: str,
    env_count: int,
    api_key: str = "",
    label: str = "",
    max_round: int = 50,
    step_wait_time: float = 1.0,
    auto_retry: int = 0,
    enable_user_interaction: bool = False,
    env_image: str = "",
) -> dict:
    job_id = uuid.uuid4().hex[:12]
    prefix = f"eval_{job_id}"
    conn = get_connection()
    conn.execute(
        """INSERT INTO jobs (id, label, agent_type, model_name, llm_base_url,
           api_key, env_count, max_round, step_wait_time,
           auto_retry, enable_user_interaction, env_image, container_prefix)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, label, agent_type, model_name, llm_base_url,
         api_key, env_count, max_round, step_wait_time,
         auto_retry, int(enable_user_interaction), env_image, prefix),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row)


def get_job(job_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_jobs(
    status: str | None = None,
    agent_type: str | None = None,
    label: str | None = None,
    model_name: str | None = None,
) -> list[dict]:
    conn = get_connection()
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if agent_type:
        clauses.append("agent_type = ?")
        params.append(agent_type)
    if label:
        clauses.append("label LIKE ?")
        params.append(f"%{label}%")
    if model_name:
        clauses.append("model_name LIKE ?")
        params.append(f"%{model_name}%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM jobs{where} ORDER BY created_at DESC", params
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_job(job_id: str, **fields) -> None:
    conn = get_connection()
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [job_id]
    conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


def count_running_envs() -> int:
    """Count total env_count across all running jobs."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(env_count), 0) as total FROM jobs WHERE status = 'running'"
    ).fetchone()
    conn.close()
    return row["total"]
