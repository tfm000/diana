import json
import logging
from dataclasses import dataclass

from diana.config import LLMConfig
from diana.llm.client import llm_complete
from diana.news.scraper import RawArticle, format_articles_for_llm

logger = logging.getLogger(__name__)

_MAX_COMBINED_CHARS = 60_000


class SummarizationError(Exception):
    pass


CATEGORIES = [
    "Finance", "Politics", "Technology & Science",
    "Sports & Entertainment", "World", "Health", "Other",
]

_CATEGORY_LIST = ", ".join(CATEGORIES)


def _build_system_prompt(max_per_category: int) -> str:
    return (
        f"You are a news editor. You will receive headlines and excerpts from multiple news sources.\n"
        f"For each of the following categories — {_CATEGORY_LIST} — identify the top "
        f"{max_per_category} most significant stories from the provided sources. "
        f"A category may have fewer than {max_per_category} stories if there are not enough "
        f"relevant articles — do not pad with low-quality stories. "
        f"Where the same story appears in multiple sources, merge into one entry — use the most "
        f"informative version and name the primary source.\n\n"
        f"Output a JSON array ONLY — no prose, no markdown fences. Each object must have:\n"
        f'- "headline": string — the story headline\n'
        f'- "summary": string — 2 to 3 sentence summary of the story\n'
        f'- "category": one of: {_CATEGORY_LIST}\n'
        f'- "importance": integer 1-10 where 10 is most globally significant\n'
        f'- "url": string — the article URL if identifiable, else empty string\n'
        f'- "source_name": string — the primary source name\n\n'
        f"Rules:\n"
        f"- Exclude advertisements and navigation links.\n"
        f"- Importance: breaking/major global news = 9-10; major policy = 7-8; regional = 4-6; minor = 1-3.\n"
        f"- Output valid JSON only. No trailing commas."
    )

# Kept for backwards-compatibility / single-source fallback use
_SINGLE_SYSTEM_PROMPT = """\
You are a news editor. You will receive raw scraped content from a news website.
Identify the 5 to 10 most significant news stories.

Output a JSON array ONLY — no prose, no markdown fences. Each object must have:
- "headline": string — the story headline
- "summary": string — 2 to 3 sentence summary of the story
- "category": one of: Finance, Politics, Technology, Science, Sports, Entertainment, World, Health, Other
- "importance": integer 1-10 where 10 is most globally significant
- "url": string — the article URL if identifiable, else empty string

Rules:
- Exclude duplicate stories, advertisements, and navigation links.
- Importance: breaking/major global news = 9-10; major policy = 7-8; regional = 4-6; minor = 1-3.
- Output valid JSON only. No trailing commas.\
"""


@dataclass
class Story:
    headline: str
    summary: str
    category: str
    importance: int
    url: str
    source_name: str


async def summarize_all_sources(
    sources_data: list[dict],
    llm_cfg: LLMConfig,
    max_per_category: int = 5,
) -> list[Story]:
    """Send all scraped articles to the LLM in a single call.

    sources_data: list of {"name": str, "url": str, "articles": list[RawArticle]}

    Returns a deduplicated Story list across all sources.
    Raises SummarizationError on failure.
    """
    # Build per-source text blocks
    blocks: list[tuple[str, str]] = []  # (source_name, formatted_text)
    for src in sources_data:
        articles: list[RawArticle] = src.get("articles", [])
        if not articles:
            continue
        text = format_articles_for_llm(articles)
        if text.strip():
            blocks.append((src["name"], text))

    if not blocks:
        return []

    # Cap total size — truncate proportionally if over limit
    total = sum(len(t) for _, t in blocks)
    combined_parts: list[str] = []
    for name, text in blocks:
        if total > _MAX_COMBINED_CHARS:
            allowed = max(500, int(len(text) / total * _MAX_COMBINED_CHARS))
            text = text[:allowed]
        combined_parts.append(f"=== {name.upper()} ===\n{text}")

    combined = "\n\n".join(combined_parts)

    messages = [
        {"role": "system", "content": _build_system_prompt(max_per_category)},
        {"role": "user", "content": combined},
    ]

    try:
        raw = await llm_complete(
            provider=llm_cfg.provider,
            api_key=llm_cfg.api_key,
            model=llm_cfg.model,
            messages=messages,
            max_tokens=4000,
        )
    except Exception as exc:
        raise SummarizationError(f"LLM call failed: {exc}") from exc

    stories = _parse_stories_multi(raw)
    if not stories:
        preview = raw.strip()[:200].replace("\n", " ")
        raise SummarizationError(f"LLM returned no parseable stories. Response preview: {preview!r}")
    return stories


async def summarize_source(
    source_name: str,
    source_url: str,
    scraped_text: str,
    llm_cfg: LLMConfig,
) -> list[Story]:
    """Single-source summarization (kept for backwards compatibility).

    Returns an empty list on any failure.
    """
    messages = [
        {"role": "system", "content": _SINGLE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Source name: {source_name}\n"
                f"Source URL: {source_url}\n\n"
                f"Scraped content:\n{scraped_text}"
            ),
        },
    ]

    try:
        raw = await llm_complete(
            provider=llm_cfg.provider,
            api_key=llm_cfg.api_key,
            model=llm_cfg.model,
            messages=messages,
            max_tokens=3000,
        )
    except Exception as exc:
        raise SummarizationError(f"LLM call failed: {exc}") from exc

    stories = _parse_stories(raw, source_name)
    if not stories:
        preview = raw.strip()[:200].replace("\n", " ")
        raise SummarizationError(f"LLM returned no parseable stories. Response preview: {preview!r}")
    return stories


def _parse_stories_multi(raw: str) -> list[Story]:
    """Parse LLM JSON output from a multi-source batch call."""
    text = _strip_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse LLM news JSON: %s\nRaw: %.200s", exc, raw)
        return []

    if not isinstance(data, list):
        logger.warning("LLM news response was not a JSON array")
        return []

    stories: list[Story] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            story = Story(
                headline=str(item.get("headline", "")).strip(),
                summary=str(item.get("summary", "")).strip(),
                category=str(item.get("category", "Other")).strip(),
                importance=int(item.get("importance", 5)),
                url=str(item.get("url", "")).strip(),
                source_name=str(item.get("source_name", "")).strip(),
            )
            if story.headline and story.summary:
                stories.append(story)
        except (TypeError, ValueError) as exc:
            logger.debug("Skipping malformed story entry: %s", exc)

    return stories


def _parse_stories(raw: str, source_name: str) -> list[Story]:
    """Parse LLM JSON output into Story objects, skipping malformed entries."""
    text = _strip_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse LLM news JSON: %s\nRaw: %.200s", exc, raw)
        return []

    if not isinstance(data, list):
        logger.warning("LLM news response was not a JSON array for %r", source_name)
        return []

    stories: list[Story] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            story = Story(
                headline=str(item.get("headline", "")).strip(),
                summary=str(item.get("summary", "")).strip(),
                category=str(item.get("category", "Other")).strip(),
                importance=int(item.get("importance", 5)),
                url=str(item.get("url", "")).strip(),
                source_name=source_name,
            )
            if story.headline and story.summary:
                stories.append(story)
        except (TypeError, ValueError) as exc:
            logger.debug("Skipping malformed story entry: %s", exc)

    return stories


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(line for line in lines if not line.startswith("```")).strip()
    return text
