import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from diana.models import Job, JobStatus


def _get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str) -> None:
    """Create the jobs table if it doesn't exist."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = _get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            upload_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            tts_engine TEXT NOT NULL,
            tts_voice TEXT NOT NULL,
            page_range TEXT,
            output_path TEXT,
            total_chunks INTEGER DEFAULT 0,
            completed_chunks INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
    """)
    # Migration: add page_range column to existing databases
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN page_range TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.close()


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(**dict(row))


def create_job(db_path: str, job: Job) -> Job:
    conn = _get_connection(db_path)
    conn.execute(
        """INSERT INTO jobs
           (id, filename, file_type, upload_path, status, tts_engine, tts_voice,
            page_range, output_path, total_chunks, completed_chunks, error_message,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job.id, job.filename, job.file_type, job.upload_path,
            job.status.value, job.tts_engine, job.tts_voice,
            job.page_range, job.output_path, job.total_chunks,
            job.completed_chunks, job.error_message,
            job.created_at.isoformat(), job.updated_at.isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return job


def get_job(db_path: str, job_id: str) -> Optional[Job]:
    conn = _get_connection(db_path)
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_job(row)


def list_jobs(db_path: str, limit: int = 50, offset: int = 0) -> list[Job]:
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [_row_to_job(r) for r in rows]


def rename_job(db_path: str, job_id: str, new_name: str) -> None:
    """Rename a job's display filename."""
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE jobs SET filename = ?, updated_at = ? WHERE id = ?",
        (new_name, datetime.now().isoformat(), job_id),
    )
    conn.commit()
    conn.close()


def update_job_status(db_path: str, job_id: str, status: JobStatus, **kwargs) -> None:
    """Update job status and any additional fields."""
    sets = ["status = ?", "updated_at = ?"]
    values = [status.value, datetime.now().isoformat()]

    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        values.append(val)

    values.append(job_id)
    conn = _get_connection(db_path)
    conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def increment_completed_chunks(db_path: str, job_id: str) -> None:
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE jobs SET completed_chunks = completed_chunks + 1, updated_at = ? WHERE id = ?",
        (datetime.now().isoformat(), job_id),
    )
    conn.commit()
    conn.close()


def delete_job(db_path: str, job_id: str) -> None:
    """Delete a job and clean up its associated files."""
    job = get_job(db_path, job_id)
    if job is None:
        return

    # Clean up files
    if job.upload_path:
        Path(job.upload_path).unlink(missing_ok=True)
    if job.output_path:
        Path(job.output_path).unlink(missing_ok=True)

    # Clean up chunk directory if it exists
    chunk_dir = Path("data/chunks") / job_id
    if chunk_dir.exists():
        shutil.rmtree(chunk_dir, ignore_errors=True)

    conn = _get_connection(db_path)
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


def get_next_pending_job(db_path: str) -> Optional[Job]:
    """Get the oldest pending job."""
    conn = _get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1",
        (JobStatus.PENDING.value,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_job(row)
