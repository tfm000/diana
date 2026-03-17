"""Tests for diana.processing.pipeline."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from diana.models import Job, JobStatus


def _make_config():
    """Create a minimal mock DianaConfig."""
    config = MagicMock()
    config.storage.database_path = ":memory:"
    config.storage.chunk_dir = "/tmp/chunks"
    config.storage.output_dir = "/tmp/output"
    config.processing.chunk_max_chars = 5000
    config.processing.output_bitrate = "192k"
    config.processing.gap_ms = 500
    config.processing.max_concurrent_chunks = 2
    config.tts.speed = 1.0
    return config


def _make_job(file_type="txt", page_range=""):
    return Job(
        id="test-job-123",
        filename="test.txt",
        file_type=file_type,
        upload_path="/tmp/test.txt",
        status=JobStatus.PENDING,
        tts_engine="kokoro",
        tts_voice="af_heart",
        page_range=page_range,
    )


class TestProcessJobHappyPath:
    @patch("diana.processing.pipeline.shutil")
    @patch("diana.processing.pipeline.Path")
    @patch("diana.processing.pipeline.merge_chunks")
    @patch("diana.processing.pipeline.synthesize_chunk", new_callable=AsyncMock)
    @patch("diana.processing.pipeline.create_engine")
    @patch("diana.processing.pipeline.clean_text")
    @patch("diana.processing.pipeline.get_llm_config", return_value=None)
    @patch("diana.processing.pipeline.chunk_text")
    @patch("diana.processing.pipeline.get_parser")
    @patch("diana.processing.pipeline.update_job_status")
    @patch("diana.processing.pipeline.increment_completed_chunks")
    @patch("diana.processing.pipeline.get_job")
    def test_happy_path_completes(
        self, mock_get_job, mock_inc, mock_update, mock_get_parser,
        mock_chunk, mock_llm_cfg, mock_clean, mock_create_engine,
        mock_synth, mock_merge, mock_path, mock_shutil,
    ):
        job = _make_job()
        mock_get_job.return_value = job

        parser = MagicMock()
        parser.extract_text.return_value = "Extracted text content."
        mock_get_parser.return_value = parser

        mock_clean.return_value = "Cleaned text content."
        mock_chunk.return_value = ["chunk1", "chunk2"]

        engine = MagicMock()
        engine.shutdown = MagicMock()
        mock_create_engine.return_value = engine

        mock_synth.return_value = "/tmp/chunks/test-job-123/0.wav"

        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance

        config = _make_config()

        from diana.processing.pipeline import process_job
        asyncio.run(process_job("test-job-123", config))

        # Verify status transitions
        status_calls = [c[0][2] for c in mock_update.call_args_list]
        assert JobStatus.EXTRACTING in status_calls
        assert JobStatus.CHUNKING in status_calls
        assert JobStatus.SYNTHESIZING in status_calls
        assert JobStatus.MERGING in status_calls
        assert JobStatus.COMPLETED in status_calls

        # Verify engine was shut down
        engine.shutdown.assert_called_once()

    @patch("diana.processing.pipeline.shutil")
    @patch("diana.processing.pipeline.Path")
    @patch("diana.processing.pipeline.merge_chunks")
    @patch("diana.processing.pipeline.synthesize_chunk", new_callable=AsyncMock)
    @patch("diana.processing.pipeline.create_engine")
    @patch("diana.processing.pipeline.clean_text")
    @patch("diana.processing.pipeline.get_llm_config", return_value=None)
    @patch("diana.processing.pipeline.chunk_text")
    @patch("diana.processing.pipeline.get_parser")
    @patch("diana.processing.pipeline.update_job_status")
    @patch("diana.processing.pipeline.increment_completed_chunks")
    @patch("diana.processing.pipeline.get_job")
    def test_extraction_failure_sets_failed(
        self, mock_get_job, mock_inc, mock_update, mock_get_parser,
        mock_chunk, mock_llm_cfg, mock_clean, mock_create_engine,
        mock_synth, mock_merge, mock_path, mock_shutil,
    ):
        job = _make_job()
        mock_get_job.return_value = job

        parser = MagicMock()
        parser.extract_text.side_effect = RuntimeError("File corrupted")
        mock_get_parser.return_value = parser

        config = _make_config()

        from diana.processing.pipeline import process_job
        asyncio.run(process_job("test-job-123", config))

        # Should have set FAILED status
        status_calls = [c[0][2] for c in mock_update.call_args_list]
        assert JobStatus.FAILED in status_calls

    @patch("diana.processing.pipeline.shutil")
    @patch("diana.processing.pipeline.Path")
    @patch("diana.processing.pipeline.merge_chunks")
    @patch("diana.processing.pipeline.synthesize_chunk", new_callable=AsyncMock)
    @patch("diana.processing.pipeline.create_engine")
    @patch("diana.processing.pipeline.clean_text")
    @patch("diana.processing.pipeline.get_llm_config", return_value=None)
    @patch("diana.processing.pipeline.chunk_text")
    @patch("diana.processing.pipeline.update_job_status")
    @patch("diana.processing.pipeline.increment_completed_chunks")
    @patch("diana.processing.pipeline.get_job")
    def test_web_job_uses_scraper(
        self, mock_get_job, mock_inc, mock_update,
        mock_chunk, mock_llm_cfg, mock_clean, mock_create_engine,
        mock_synth, mock_merge, mock_path, mock_shutil,
    ):
        job = _make_job(file_type="web")
        mock_get_job.return_value = job

        mock_clean.return_value = "Cleaned web text."
        mock_chunk.return_value = ["chunk1"]

        engine = MagicMock()
        engine.shutdown = MagicMock()
        mock_create_engine.return_value = engine

        mock_synth.return_value = "/tmp/chunks/test-job-123/0.wav"
        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance

        config = _make_config()

        with patch("diana.news.scraper.scrape_source") as mock_scrape:
            mock_scrape.return_value = ([], "Scraped web content.")

            from diana.processing.pipeline import process_job
            asyncio.run(process_job("test-job-123", config))

            mock_scrape.assert_called_once_with(job.upload_path)


class TestProcessJobNotFound:
    @patch("diana.processing.pipeline.get_job", return_value=None)
    def test_raises_for_missing_job(self, mock_get_job):
        config = _make_config()
        from diana.processing.pipeline import process_job

        with pytest.raises(ValueError, match="not found"):
            asyncio.run(process_job("nonexistent", config))
