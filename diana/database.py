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

        CREATE TABLE IF NOT EXISTS news_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_news_sources_created ON news_sources(created_at);

        CREATE TABLE IF NOT EXISTS news_source_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
            rss_url TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(source_id, rss_url)
        );

        CREATE TABLE IF NOT EXISTS news_source_groups (
            source_id INTEGER NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
            group_name TEXT NOT NULL,
            PRIMARY KEY (source_id, group_name)
        );
        CREATE INDEX IF NOT EXISTS idx_news_source_groups_name ON news_source_groups(group_name);

        CREATE TABLE IF NOT EXISTS news_stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT NOT NULL,
            summary TEXT NOT NULL,
            category TEXT NOT NULL,
            importance INTEGER NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            source_name TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_news_stories_fetched ON news_stories(fetched_at);
    """)
    conn.execute("PRAGMA foreign_keys = ON")

    # Column migrations
    for migration in [
        "ALTER TABLE jobs ADD COLUMN page_range TEXT",
        "ALTER TABLE jobs ADD COLUMN folder TEXT DEFAULT ''",
        "ALTER TABLE news_sources ADD COLUMN rss_url TEXT DEFAULT ''",
        "ALTER TABLE news_sources ADD COLUMN source_group TEXT DEFAULT ''",
    ]:
        try:
            conn.execute(migration)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Deduplicate any duplicate feeds created before UNIQUE constraint was added
    try:
        conn.execute("""
            DELETE FROM news_source_feeds
            WHERE id NOT IN (
                SELECT MIN(id) FROM news_source_feeds GROUP BY source_id, rss_url
            )
        """)
        conn.commit()
    except Exception:
        pass

    # Data migration: promote old single rss_url / source_group columns to junction tables.
    # After migrating, clear the source columns so this block is a no-op on subsequent runs.
    try:
        rows = conn.execute(
            "SELECT id, rss_url, source_group FROM news_sources "
            "WHERE (rss_url IS NOT NULL AND rss_url != '') "
            "   OR (source_group IS NOT NULL AND source_group != '')"
        ).fetchall()
        now = datetime.now().isoformat()
        for row in rows:
            sid, old_rss, old_group = row[0], row[1] or "", row[2] or ""
            if old_rss:
                conn.execute(
                    "INSERT OR IGNORE INTO news_source_feeds (source_id, rss_url, label, created_at) "
                    "VALUES (?, ?, '', ?)",
                    (sid, old_rss, now),
                )
            if old_group:
                conn.execute(
                    "INSERT OR IGNORE INTO news_source_groups (source_id, group_name) VALUES (?, ?)",
                    (sid, old_group),
                )
            # Clear old columns so migration doesn't re-run next startup
            conn.execute(
                "UPDATE news_sources SET rss_url = '', source_group = '' WHERE id = ?",
                (sid,),
            )
        conn.commit()
    except Exception:
        pass  # Migration already done or columns don't exist yet

    conn.close()


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(**dict(row))


def create_job(db_path: str, job: Job) -> Job:
    conn = _get_connection(db_path)
    conn.execute(
        """INSERT INTO jobs
           (id, filename, file_type, upload_path, status, tts_engine, tts_voice,
            page_range, folder, output_path, total_chunks, completed_chunks,
            error_message, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job.id, job.filename, job.file_type, job.upload_path,
            job.status.value, job.tts_engine, job.tts_voice,
            job.page_range, job.folder, job.output_path, job.total_chunks,
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


def delete_job(db_path: str, job_id: str, chunk_base: str = "data/chunks") -> None:
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
    chunk_dir = Path(chunk_base) / job_id
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


def count_jobs(db_path: str) -> int:
    """Return total number of jobs."""
    conn = _get_connection(db_path)
    row = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()
    conn.close()
    return row[0]


def list_folders(db_path: str) -> list[str]:
    """Return distinct non-empty folder names."""
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT DISTINCT folder FROM jobs WHERE folder != '' ORDER BY folder"
    ).fetchall()
    conn.close()
    return [r["folder"] for r in rows]


def move_job_to_folder(db_path: str, job_id: str, folder: str) -> None:
    """Move a job into a folder (empty string = ungrouped)."""
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE jobs SET folder = ?, updated_at = ? WHERE id = ?",
        (folder, datetime.now().isoformat(), job_id),
    )
    conn.commit()
    conn.close()


def delete_folder(db_path: str, folder: str) -> None:
    """Remove a folder by moving all its jobs back to ungrouped."""
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE jobs SET folder = '', updated_at = ? WHERE folder = ?",
        (datetime.now().isoformat(), folder),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# News sources
# ---------------------------------------------------------------------------

def add_news_source(db_path: str, name: str, url: str) -> int:
    """Insert a news source. Returns the new source id.
    Raises sqlite3.IntegrityError if URL already exists.
    """
    conn = _get_connection(db_path)
    cur = conn.execute(
        "INSERT INTO news_sources (name, url, created_at) VALUES (?, ?, ?)",
        (name.strip(), url.strip(), datetime.now().isoformat()),
    )
    source_id = cur.lastrowid
    conn.commit()
    conn.close()
    return source_id


def update_news_source(db_path: str, source_id: int, name: str, url: str) -> None:
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE news_sources SET name = ?, url = ? WHERE id = ?",
        (name.strip(), url.strip(), source_id),
    )
    conn.commit()
    conn.close()


def remove_news_source(db_path: str, source_id: int) -> None:
    conn = _get_connection(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM news_sources WHERE id = ?", (source_id,))
    conn.commit()
    conn.close()


def list_news_sources(db_path: str) -> list[dict]:
    """Return all news sources enriched with their feeds and groups."""
    conn = _get_connection(db_path)
    sources = [dict(r) for r in conn.execute(
        "SELECT id, name, url, created_at FROM news_sources ORDER BY name ASC"
    ).fetchall()]

    for src in sources:
        sid = src["id"]
        src["feeds"] = [
            dict(r) for r in conn.execute(
                "SELECT id, rss_url, label FROM news_source_feeds WHERE source_id = ? ORDER BY id ASC",
                (sid,),
            ).fetchall()
        ]
        src["groups"] = [
            r[0] for r in conn.execute(
                "SELECT group_name FROM news_source_groups WHERE source_id = ? ORDER BY group_name ASC",
                (sid,),
            ).fetchall()
        ]

    conn.close()
    return sources


# --- Feeds ---

def add_news_feed(db_path: str, source_id: int, rss_url: str, label: str = "") -> None:
    conn = _get_connection(db_path)
    conn.execute(
        "INSERT INTO news_source_feeds (source_id, rss_url, label, created_at) VALUES (?, ?, ?, ?)",
        (source_id, rss_url.strip(), label.strip(), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def remove_news_feed(db_path: str, feed_id: int) -> None:
    conn = _get_connection(db_path)
    conn.execute("DELETE FROM news_source_feeds WHERE id = ?", (feed_id,))
    conn.commit()
    conn.close()


def clear_news_feeds(db_path: str, source_id: int) -> None:
    """Remove all RSS feeds for a source (used during import overwrite)."""
    conn = _get_connection(db_path)
    conn.execute("DELETE FROM news_source_feeds WHERE source_id = ?", (source_id,))
    conn.commit()
    conn.close()


def clear_source_groups(db_path: str, source_id: int) -> None:
    """Remove all group memberships for a source (used during import overwrite)."""
    conn = _get_connection(db_path)
    conn.execute("DELETE FROM news_source_groups WHERE source_id = ?", (source_id,))
    conn.commit()
    conn.close()


# --- Groups ---

def add_source_to_group(db_path: str, source_id: int, group_name: str) -> None:
    conn = _get_connection(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO news_source_groups (source_id, group_name) VALUES (?, ?)",
        (source_id, group_name.strip()),
    )
    conn.commit()
    conn.close()


def remove_source_from_group(db_path: str, source_id: int, group_name: str) -> None:
    conn = _get_connection(db_path)
    conn.execute(
        "DELETE FROM news_source_groups WHERE source_id = ? AND group_name = ?",
        (source_id, group_name),
    )
    conn.commit()
    conn.close()


def list_news_groups(db_path: str) -> list[str]:
    """Return all distinct group names sorted alphabetically."""
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT DISTINCT group_name FROM news_source_groups ORDER BY group_name ASC"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Persisted news stories
# ---------------------------------------------------------------------------

def save_news_stories(db_path: str, stories: list[dict], fetched_at: str) -> None:
    """Replace all stored stories with the new batch."""
    conn = _get_connection(db_path)
    conn.execute("DELETE FROM news_stories")
    conn.executemany(
        """INSERT INTO news_stories
           (headline, summary, category, importance, url, source_name, fetched_at)
           VALUES (:headline, :summary, :category, :importance, :url, :source_name, :fetched_at)""",
        [dict(s, fetched_at=fetched_at) for s in stories],
    )
    conn.commit()
    conn.close()


def load_latest_news(db_path: str) -> tuple[list[dict], str]:
    """Return (stories_as_dicts, fetched_at_str). Returns ([], '') if nothing stored."""
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT headline, summary, category, importance, url, source_name, fetched_at "
        "FROM news_stories ORDER BY importance DESC"
    ).fetchall()
    conn.close()
    if not rows:
        return [], ""
    stories = [dict(r) for r in rows]
    fetched_at = stories[0]["fetched_at"]
    return stories, fetched_at
