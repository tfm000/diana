import pytest

from diana.database import (
    count_jobs,
    create_job,
    delete_folder,
    delete_job,
    get_job,
    get_next_pending_job,
    increment_completed_chunks,
    init_db,
    list_folders,
    list_jobs,
    move_job_to_folder,
    rename_job,
    update_job_status,
)
from diana.models import Job, JobStatus


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def _make_job(id="job1", filename="test.pdf", **kwargs):
    defaults = dict(
        id=id,
        filename=filename,
        file_type="pdf",
        upload_path=f"/tmp/{id}.pdf",
        status=JobStatus.PENDING,
        tts_engine="kokoro",
        tts_voice="af_heart",
    )
    defaults.update(kwargs)
    return Job(**defaults)


class TestInitDb:
    def test_creates_table(self, db_path):
        # Should not raise
        init_db(db_path)

    def test_idempotent(self, db_path):
        init_db(db_path)
        init_db(db_path)


class TestCreateAndGetJob:
    def test_round_trip(self, db_path):
        job = _make_job()
        create_job(db_path, job)
        fetched = get_job(db_path, "job1")
        assert fetched is not None
        assert fetched.id == "job1"
        assert fetched.filename == "test.pdf"
        assert fetched.status == JobStatus.PENDING

    def test_get_nonexistent(self, db_path):
        assert get_job(db_path, "nope") is None


class TestListJobs:
    def test_returns_descending_order(self, db_path):
        import time
        for i in range(3):
            create_job(db_path, _make_job(id=f"job{i}", filename=f"file{i}.pdf"))
            time.sleep(0.01)  # ensure different timestamps
        jobs = list_jobs(db_path)
        assert jobs[0].id == "job2"
        assert jobs[-1].id == "job0"

    def test_limit_and_offset(self, db_path):
        for i in range(5):
            create_job(db_path, _make_job(id=f"job{i}"))
        assert len(list_jobs(db_path, limit=2)) == 2
        assert len(list_jobs(db_path, limit=2, offset=4)) == 1


class TestUpdateJobStatus:
    def test_updates_status(self, db_path):
        create_job(db_path, _make_job())
        update_job_status(db_path, "job1", JobStatus.COMPLETED, output_path="/out.mp3")
        job = get_job(db_path, "job1")
        assert job.status == JobStatus.COMPLETED
        assert job.output_path == "/out.mp3"


class TestRenameJob:
    def test_renames(self, db_path):
        create_job(db_path, _make_job())
        rename_job(db_path, "job1", "new_name.pdf")
        job = get_job(db_path, "job1")
        assert job.filename == "new_name.pdf"


class TestDeleteJob:
    def test_deletes_row(self, db_path):
        create_job(db_path, _make_job())
        delete_job(db_path, "job1")
        assert get_job(db_path, "job1") is None

    def test_delete_nonexistent_no_error(self, db_path):
        delete_job(db_path, "nope")


class TestIncrementCompletedChunks:
    def test_increments(self, db_path):
        create_job(db_path, _make_job(total_chunks=5))
        increment_completed_chunks(db_path, "job1")
        increment_completed_chunks(db_path, "job1")
        job = get_job(db_path, "job1")
        assert job.completed_chunks == 2


class TestGetNextPendingJob:
    def test_returns_oldest_pending(self, db_path):
        import time
        create_job(db_path, _make_job(id="old"))
        time.sleep(0.01)
        create_job(db_path, _make_job(id="new"))
        job = get_next_pending_job(db_path)
        assert job.id == "old"

    def test_returns_none_when_empty(self, db_path):
        assert get_next_pending_job(db_path) is None


class TestCountJobs:
    def test_counts(self, db_path):
        assert count_jobs(db_path) == 0
        create_job(db_path, _make_job(id="j1"))
        create_job(db_path, _make_job(id="j2"))
        assert count_jobs(db_path) == 2


class TestFolders:
    def test_list_folders_empty(self, db_path):
        assert list_folders(db_path) == []

    def test_move_and_list(self, db_path):
        create_job(db_path, _make_job())
        move_job_to_folder(db_path, "job1", "Audiobooks")
        assert list_folders(db_path) == ["Audiobooks"]
        job = get_job(db_path, "job1")
        assert job.folder == "Audiobooks"

    def test_delete_folder_moves_to_ungrouped(self, db_path):
        create_job(db_path, _make_job())
        move_job_to_folder(db_path, "job1", "MyFolder")
        delete_folder(db_path, "MyFolder")
        job = get_job(db_path, "job1")
        assert job.folder == ""
        assert list_folders(db_path) == []

    def test_multiple_folders(self, db_path):
        create_job(db_path, _make_job(id="j1"))
        create_job(db_path, _make_job(id="j2"))
        move_job_to_folder(db_path, "j1", "A")
        move_job_to_folder(db_path, "j2", "B")
        assert list_folders(db_path) == ["A", "B"]
