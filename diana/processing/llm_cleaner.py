import asyncio
import logging

from diana.config import LLMConfig
from diana.llm.client import llm_complete
from diana.processing.cleaner import clean_text, strip_non_speakable

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a text editor preparing a document for audio narration. \
Clean the following text so it reads naturally when spoken aloud.

Rules:
1. REMOVE completely: tables, data grids, figure/chart text, inline citations \
([1] or (Smith, 2020)), footnotes, reference list entries, DOI/URL/arXiv lines, \
page numbers, journal/copyright footers, LaTeX commands.
2. CONVERT math to spoken form where clear \
(e.g. x^2 -> "x squared", E=mc2 -> "E equals m c squared"). \
Remove formulas too complex to speak naturally.
3. PRESERVE all narrative prose, headings, and arguments.
4. Do NOT summarise or compress prose — keep all original sentences that are speakable.
5. Output ONLY the cleaned text. No preamble, no markdown fencing.\
"""

_TRANSLATE_SUFFIX = "\n6. Translate the cleaned text to {language}."


def _split_for_llm(text: str, chunk_size: int) -> list[str]:
    """Split text into chunks of at most chunk_size chars, respecting paragraph breaks."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    current: list[str] = []
    current_len = 0
    for para in text.split("\n\n"):
        para_len = len(para) + 2  # +2 for the separator
        if current_len + para_len > chunk_size and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += para_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks


async def _clean_chunk(chunk: str, llm_cfg: LLMConfig) -> str:
    system = _SYSTEM_PROMPT
    if llm_cfg.target_language:
        system += _TRANSLATE_SUFFIX.format(language=llm_cfg.target_language)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"<text>\n{chunk}\n</text>"},
    ]
    return await llm_complete(
        provider=llm_cfg.provider,
        api_key=llm_cfg.api_key,
        model=llm_cfg.model,
        messages=messages,
        max_tokens=4096,
    )


async def _clean_chunk_with_fallback(
    i: int, chunk: str, llm_cfg: LLMConfig, semaphore: asyncio.Semaphore,
) -> str:
    """Clean a single chunk with concurrency limiting and fallback."""
    async with semaphore:
        try:
            result = await _clean_chunk(chunk, llm_cfg)
            if result and len(result.strip()) >= len(chunk.strip()) * 0.1:
                return result
            logger.warning(
                "LLM cleaning produced unexpectedly short output for chunk %d "
                "(%d chars → %d chars). Using rule-based fallback.",
                i, len(chunk), len(result),
            )
            return clean_text(chunk)
        except Exception as exc:
            logger.warning(
                "LLM cleaning failed for chunk %d, using rule-based fallback: %s", i, exc
            )
            return clean_text(chunk)


async def llm_clean_text(text: str, llm_cfg: LLMConfig) -> str:
    """Clean text using an LLM. Falls back to rule-based clean_text() on any error.

    Chunks are processed concurrently (up to _MAX_CONCURRENT_LLM_CALLS at a time)
    to speed up large documents. After LLM cleaning, still applies
    strip_non_speakable() as a safety net to ensure no characters outside
    printable ASCII reach the TTS tokenizer.
    """
    chunks = _split_for_llm(text, llm_cfg.chunk_size)
    semaphore = asyncio.Semaphore(llm_cfg.max_concurrent_calls)

    cleaned = await asyncio.gather(*(
        _clean_chunk_with_fallback(i, chunk, llm_cfg, semaphore)
        for i, chunk in enumerate(chunks)
    ))

    combined = "\n\n".join(cleaned)
    return strip_non_speakable(combined)
