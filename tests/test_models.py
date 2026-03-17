import pytest

from diana.models import Job, JobStatus, parse_page_range


class TestParsePageRange:
    def test_empty_string_returns_empty(self):
        assert parse_page_range("", 10) == []

    def test_none_returns_empty(self):
        assert parse_page_range(None, 10) == []

    def test_whitespace_returns_empty(self):
        assert parse_page_range("   ", 10) == []

    def test_single_page(self):
        assert parse_page_range("3", 10) == [2]

    def test_range(self):
        assert parse_page_range("1-3", 5) == [0, 1, 2]

    def test_mixed_ranges_and_pages(self):
        result = parse_page_range("1-3, 5, 8-10", 10)
        assert result == [0, 1, 2, 4, 7, 8, 9]

    def test_out_of_range_clamped(self):
        result = parse_page_range("1-100", 5)
        assert result == [0, 1, 2, 3, 4]

    def test_page_below_one_ignored(self):
        result = parse_page_range("0, 1", 5)
        assert result == [0]

    def test_page_above_total_ignored(self):
        result = parse_page_range("10", 5)
        assert result == []

    def test_duplicates_removed(self):
        result = parse_page_range("1, 1, 1-2", 5)
        assert result == [0, 1]

    def test_results_sorted(self):
        result = parse_page_range("5, 1, 3", 10)
        assert result == [0, 2, 4]

    def test_invalid_number_raises_valueerror(self):
        with pytest.raises(ValueError, match="Invalid"):
            parse_page_range("1-a", 10)

    def test_invalid_single_page_raises_valueerror(self):
        with pytest.raises(ValueError, match="Invalid page number"):
            parse_page_range("abc", 10)

    def test_spaces_tolerated(self):
        result = parse_page_range(" 1 - 3 , 5 ", 10)
        assert result == [0, 1, 2, 4]

    def test_trailing_comma_tolerated(self):
        result = parse_page_range("1,2,", 5)
        assert result == [0, 1]


class TestJob:
    def test_defaults(self):
        job = Job(
            id="abc",
            filename="test.txt",
            file_type="txt",
            upload_path="/tmp/test.txt",
            status=JobStatus.PENDING,
            tts_engine="kokoro",
            tts_voice="af_heart",
        )
        assert job.created_at is not None
        assert job.updated_at is not None
        assert job.folder == ""
        assert job.total_chunks == 0

    def test_status_coercion_from_string(self):
        job = Job(
            id="abc",
            filename="test.txt",
            file_type="txt",
            upload_path="/tmp/test.txt",
            status="pending",
            tts_engine="kokoro",
            tts_voice="af_heart",
        )
        assert job.status == JobStatus.PENDING

    def test_folder_none_coerced_to_empty(self):
        job = Job(
            id="abc",
            filename="test.txt",
            file_type="txt",
            upload_path="/tmp/test.txt",
            status=JobStatus.PENDING,
            tts_engine="kokoro",
            tts_voice="af_heart",
            folder=None,
        )
        assert job.folder == ""

    def test_progress_zero_chunks(self):
        job = Job(
            id="abc",
            filename="test.txt",
            file_type="txt",
            upload_path="/tmp/test.txt",
            status=JobStatus.PENDING,
            tts_engine="kokoro",
            tts_voice="af_heart",
        )
        assert job.progress == 0.0

    def test_progress_partial(self):
        job = Job(
            id="abc",
            filename="test.txt",
            file_type="txt",
            upload_path="/tmp/test.txt",
            status=JobStatus.SYNTHESIZING,
            tts_engine="kokoro",
            tts_voice="af_heart",
            total_chunks=10,
            completed_chunks=5,
        )
        assert job.progress == 0.5
