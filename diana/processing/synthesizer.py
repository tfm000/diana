import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2.0


async def synthesize_chunk(
    engine,
    chunk: str,
    voice: str,
    speed: float,
    chunk_index: int,
    output_dir: str,
) -> str:
    """Synthesize one text chunk to an audio file.

    Returns the path to the generated audio file.
    Retries up to MAX_RETRIES times on failure.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = output_dir / f"chunk_{chunk_index:05d}.wav"

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            audio_bytes = await engine.synthesize(chunk, voice=voice, speed=speed)
            chunk_path.write_bytes(audio_bytes)
            return str(chunk_path)
        except Exception as e:
            last_error = e
            logger.warning(
                "Chunk %d synthesis failed (attempt %d/%d): %s",
                chunk_index, attempt + 1, MAX_RETRIES, e,
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))

    raise RuntimeError(
        f"Failed to synthesize chunk {chunk_index} after {MAX_RETRIES} attempts: {last_error}"
    )
