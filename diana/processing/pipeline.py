import asyncio
import logging
import shutil
from pathlib import Path

from diana.config import DianaConfig
from diana.database import (
    get_job,
    increment_completed_chunks,
    update_job_status,
)
from diana.models import JobStatus, parse_page_range
from diana.parsers.registry import get_parser
from diana.processing.chunker import chunk_text
from diana.llm.registry import get_llm_config
from diana.processing.cleaner import clean_text
from diana.processing.llm_cleaner import llm_clean_text
from diana.processing.merger import merge_chunks
from diana.processing.synthesizer import synthesize_chunk
from diana.tts.registry import create_engine

logger = logging.getLogger(__name__)


async def process_job(job_id: str, config: DianaConfig) -> None:
    """Run the full processing pipeline for a single job."""
    db_path = config.storage.database_path
    job = get_job(db_path, job_id)
    if job is None:
        raise ValueError(f"Job {job_id} not found")

    engine = None
    try:
        # 1. Extract text
        update_job_status(db_path, job_id, JobStatus.EXTRACTING)

        if job.file_type == "web":
            from diana.news.scraper import scrape_source
            _, text = scrape_source(job.upload_path)
        else:
            parser = get_parser(job.upload_path)
            # Resolve page/chapter range if specified
            page_indices = None
            if job.page_range:
                if hasattr(parser, "page_count"):
                    total = parser.page_count(job.upload_path)
                elif hasattr(parser, "chapter_count"):
                    total = parser.chapter_count(job.upload_path)
                else:
                    total = 0
                if total > 0:
                    page_indices = parse_page_range(job.page_range, total)
            text = parser.extract_text(job.upload_path, page_indices=page_indices)

        # Clean text for TTS compatibility
        llm_cfg = get_llm_config(config)
        if llm_cfg is not None:
            text = await llm_clean_text(text, llm_cfg)
        else:
            text = clean_text(text)

        if not text.strip():
            raise ValueError("No text could be extracted from the uploaded file")

        # 2. Chunk
        update_job_status(db_path, job_id, JobStatus.CHUNKING)
        chunks = chunk_text(text, max_chars=config.processing.chunk_max_chars)

        if not chunks:
            raise ValueError("Text chunking produced no chunks")

        update_job_status(
            db_path, job_id, JobStatus.SYNTHESIZING,
            total_chunks=len(chunks),
        )

        # 3. Synthesize each chunk — use the job's engine, not the config default
        engine = create_engine(config, engine_name=job.tts_engine)
        chunk_dir = Path(config.storage.chunk_dir) / job_id
        chunk_dir.mkdir(parents=True, exist_ok=True)

        semaphore = asyncio.Semaphore(config.processing.max_concurrent_chunks)

        async def _synth(i: int, chunk_text: str) -> str:
            async with semaphore:
                path = await synthesize_chunk(
                    engine, chunk_text, job.tts_voice,
                    config.tts.speed, i, str(chunk_dir),
                )
                increment_completed_chunks(db_path, job_id)
                return path

        chunk_paths = await asyncio.gather(
            *[_synth(i, c) for i, c in enumerate(chunks)]
        )

        # 4. Merge into final MP3
        update_job_status(db_path, job_id, JobStatus.MERGING)
        output_dir = Path(config.storage.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"{job_id}.mp3")

        merge_chunks(
            list(chunk_paths),
            output_path,
            bitrate=config.processing.output_bitrate,
            gap_ms=config.processing.gap_ms,
        )

        # 5. Complete
        update_job_status(
            db_path, job_id, JobStatus.COMPLETED,
            output_path=output_path,
        )
        logger.info("Job %s completed: %s", job_id, output_path)

        # 6. Cleanup intermediate chunks
        shutil.rmtree(chunk_dir, ignore_errors=True)

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        update_job_status(
            db_path, job_id, JobStatus.FAILED,
            error_message=str(e),
        )
    finally:
        if engine is not None:
            engine.shutdown()
