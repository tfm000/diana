"""Tests for diana.processing.pipeline."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import diana.processing.pipeline as pipeline_mod
from diana.models import Job, JobStatus
from diana.processing.pipeline import process_job


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


def _patch_pipeline(attr, **kwargs):
    """Shorthand for patch.object on the pipeline module."""
    return patch.object(pipeline_mod, attr, **kwargs)


class TestProcessJobHappyPath:
    def test_happy_path_completes(self):
        with (
            _patch_pipeline("shutil"),
            _patch_pipeline("Path"),
            _patch_pipeline("merge_chunks"),
            _patch_pipeline("synthesize_chunk", new_callable=AsyncMock) as mock_synth,
            _patch_pipeline("create_engine") as mock_create_engine,
            _patch_pipeline("clean_text") as mock_clean,
            _patch_pipeline("get_llm_config", return_value=None),
            _patch_pipeline("chunk_text") as mock_chunk,
            _patch_pipeline("get_parser") as mock_get_parser,
            _patch_pipeline("update_job_status") as mock_update,
            _patch_pipeline("increment_completed_chunks"),
            _patch_pipeline("get_job") as mock_get_job,
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

            config = _make_config()
            asyncio.run(process_job("test-job-123", config))

            status_calls = [c[0][2] for c in mock_update.call_args_list]
            assert JobStatus.EXTRACTING in status_calls
            assert JobStatus.CHUNKING in status_calls
            assert JobStatus.SYNTHESIZING in status_calls
            assert JobStatus.MERGING in status_calls
            assert JobStatus.COMPLETED in status_calls

            engine.shutdown.assert_called_once()

    def test_extraction_failure_sets_failed(self):
        with (
            _patch_pipeline("shutil"),
            _patch_pipeline("Path"),
            _patch_pipeline("merge_chunks"),
            _patch_pipeline("synthesize_chunk", new_callable=AsyncMock),
            _patch_pipeline("create_engine"),
            _patch_pipeline("clean_text"),
            _patch_pipeline("get_llm_config", return_value=None),
            _patch_pipeline("chunk_text"),
            _patch_pipeline("get_parser") as mock_get_parser,
            _patch_pipeline("update_job_status") as mock_update,
            _patch_pipeline("increment_completed_chunks"),
            _patch_pipeline("get_job") as mock_get_job,
        ):
            job = _make_job()
            mock_get_job.return_value = job

            parser = MagicMock()
            parser.extract_text.side_effect = RuntimeError("File corrupted")
            mock_get_parser.return_value = parser

            config = _make_config()
            asyncio.run(process_job("test-job-123", config))

            status_calls = [c[0][2] for c in mock_update.call_args_list]
            assert JobStatus.FAILED in status_calls

    def test_web_job_uses_scraper(self):
        with (
            _patch_pipeline("shutil"),
            _patch_pipeline("Path"),
            _patch_pipeline("merge_chunks"),
            _patch_pipeline("synthesize_chunk", new_callable=AsyncMock) as mock_synth,
            _patch_pipeline("create_engine") as mock_create_engine,
            _patch_pipeline("clean_text") as mock_clean,
            _patch_pipeline("get_llm_config", return_value=None),
            _patch_pipeline("chunk_text") as mock_chunk,
            _patch_pipeline("update_job_status"),
            _patch_pipeline("increment_completed_chunks"),
            _patch_pipeline("get_job") as mock_get_job,
            patch("diana.news.scraper.scrape_source") as mock_scrape,
        ):
            job = _make_job(file_type="web")
            mock_get_job.return_value = job

            mock_scrape.return_value = ([], "Scraped web content.")
            mock_clean.return_value = "Cleaned web text."
            mock_chunk.return_value = ["chunk1"]

            engine = MagicMock()
            engine.shutdown = MagicMock()
            mock_create_engine.return_value = engine

            mock_synth.return_value = "/tmp/chunks/test-job-123/0.wav"

            config = _make_config()
            asyncio.run(process_job("test-job-123", config))

            mock_scrape.assert_called_once_with(job.upload_path)


class TestProcessJobNotFound:
    def test_raises_for_missing_job(self):
        with _patch_pipeline("get_job", return_value=None):
            config = _make_config()
            with pytest.raises(ValueError, match="not found"):
                asyncio.run(process_job("nonexistent", config))
