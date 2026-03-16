import asyncio
import logging
import threading

from diana.config import DianaConfig
from diana.database import get_next_pending_job
from diana.processing.pipeline import process_job

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2.0


class JobWorker:
    """Background worker that polls for pending jobs and processes them."""

    def __init__(self, config: DianaConfig):
        self._config = config
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="diana-worker")
        self._thread.start()
        logger.info("Job worker started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
        logger.info("Job worker stopped")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._poll_loop())
        finally:
            loop.close()

    async def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job = get_next_pending_job(self._config.storage.database_path)
                if job:
                    logger.info("Processing job %s: %s", job.id, job.filename)
                    await process_job(job.id, self._config)
                else:
                    await asyncio.sleep(POLL_INTERVAL)
            except Exception as e:
                logger.error("Worker error: %s", e, exc_info=True)
                await asyncio.sleep(POLL_INTERVAL)
