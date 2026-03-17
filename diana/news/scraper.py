import html
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 12_000
_MAX_RSS_ITEMS = 30
_STALE_DAYS = 3

# Mimic a real browser so sites that only block obvious bot UAs will respond.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_RSS_CONTENT_TYPES = {
    "application/rss+xml",
    "application/atom+xml",
    "application/xml",
    "text/xml",
}

# Atom namespace
_ATOM_NS = "http://www.w3.org/2005/Atom"

_WS_RE = re.compile(r"\s+")


class ScraperError(Exception):
    pass


@dataclass
class RawArticle:
    headline: str
    excerpt: str
    url: str
    pub_date: datetime | None = field(default=None)  # UTC-aware when available


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scrape_source(url: str, timeout: int = 15) -> tuple[list[RawArticle], str]:
    """Fetch a URL and return (articles, scraped_text).

    Strategy (in order):
    1. If the URL itself is an RSS/Atom feed, parse it directly.
    2. Fetch the HTML page and look for <link rel="alternate"> RSS discovery.
    3. Fall back to HTML scraping.

    Raises ScraperError on unrecoverable failure.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ScraperError(
            f"Missing dependency: {exc}. Install with: pip install requests beautifulsoup4"
        )

    session = requests.Session()
    session.headers.update(_HEADERS)

    # --- Step 1: maybe it's already a feed URL ---
    if _looks_like_feed_url(url):
        try:
            return _fetch_and_parse_feed(url, session, timeout)
        except ScraperError:
            pass  # fall through to HTML

    # --- Step 2: fetch HTML, discover RSS ---
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        raise ScraperError(f"Failed to fetch {url}: {exc}")

    content_type = resp.headers.get("Content-Type", "")
    if any(ct in content_type for ct in _RSS_CONTENT_TYPES):
        # The URL itself returned XML/RSS
        try:
            return _parse_feed_bytes(resp.content, url)
        except Exception as exc:
            raise ScraperError(f"Failed to parse feed at {url}: {exc}")

    soup = BeautifulSoup(resp.text, "lxml" if _lxml_available() else "html.parser")

    feed_url = _discover_feed(soup, url)
    if feed_url:
        try:
            return _fetch_and_parse_feed(feed_url, session, timeout)
        except ScraperError as exc:
            logger.warning("RSS feed discovered at %s but failed: %s. Falling back to HTML.", feed_url, exc)

    # --- Step 3: HTML fallback ---
    return _parse_html(soup, url)


# ---------------------------------------------------------------------------
# Staleness helpers
# ---------------------------------------------------------------------------

def _to_utc(dt: datetime) -> datetime:
    """Ensure a datetime is UTC-aware; treat naive datetimes as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def all_articles_stale(articles: list[RawArticle], max_age_days: int = _STALE_DAYS) -> bool:
    """Return True only if every article has a known date AND all are older than max_age_days."""
    dated = [a for a in articles if a.pub_date is not None]
    if not dated:
        return False  # cannot determine age → assume fresh
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return all(_to_utc(a.pub_date) < cutoff for a in dated)


# ---------------------------------------------------------------------------
# LLM input formatting
# ---------------------------------------------------------------------------

def format_articles_for_llm(articles: list[RawArticle], max_age_days: int = _STALE_DAYS) -> str:
    """Convert a list of RawArticle into a clean, compact text block for the LLM.

    Filters out articles older than max_age_days (when date is known).
    Articles with unknown dates are always included.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    lines: list[str] = []
    for a in articles:
        if a.pub_date is not None and _to_utc(a.pub_date) < cutoff:
            continue
        headline = html.unescape(a.headline).strip()
        excerpt = html.unescape(a.excerpt or "").strip()
        excerpt = _WS_RE.sub(" ", excerpt)[:400]
        line = f"• {headline}"
        if excerpt:
            line += f"\n  {excerpt}"
        if a.url:
            line += f"\n  URL: {a.url}"
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# RSS / Atom helpers
# ---------------------------------------------------------------------------

def _looks_like_feed_url(url: str) -> bool:
    lower = url.lower()
    return any(kw in lower for kw in ("/rss", "/feed", "/atom", ".xml", "/rss.xml", ".rss"))


def _discover_feed(soup, page_url: str) -> str | None:
    """Find RSS/Atom link in HTML <head>."""
    for link in soup.find_all("link", rel="alternate"):
        link_type = link.get("type", "")
        if any(ct in link_type for ct in ("rss", "atom", "xml")):
            href = link.get("href", "")
            if href:
                return href if href.startswith("http") else urljoin(page_url, href)
    return None


def _fetch_and_parse_feed(feed_url: str, session, timeout: int) -> tuple[list[RawArticle], str]:
    try:
        resp = session.get(feed_url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        raise ScraperError(f"Failed to fetch feed {feed_url}: {exc}")
    return _parse_feed_bytes(resp.content, feed_url)


def _parse_pub_date(date_str: str) -> datetime | None:
    """Parse an RFC 2822 or ISO 8601 date string into a UTC-aware datetime."""
    if not date_str:
        return None
    # RFC 2822 (RSS 2.0 pubDate: "Mon, 15 Jan 2024 12:00:00 +0000")
    try:
        import email.utils
        return email.utils.parsedate_to_datetime(date_str)
    except Exception:
        pass
    # ISO 8601 (Atom: "2024-01-15T12:00:00Z")
    try:
        normalized = date_str.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:
        pass
    return None


def _parse_feed_bytes(content: bytes, source_url: str) -> tuple[list[RawArticle], str]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ScraperError(f"Invalid XML in feed: {exc}")

    articles: list[RawArticle] = []
    text_lines: list[str] = []

    # RSS 2.0
    for item in root.findall(".//item")[:_MAX_RSS_ITEMS]:
        headline = _xml_text(item, "title")
        excerpt = _xml_text(item, "description") or _xml_text(item, "summary")
        link = _xml_text(item, "link") or ""
        pub_date = _parse_pub_date(_xml_text(item, "pubDate"))
        if headline:
            excerpt = _strip_html(excerpt)
            articles.append(RawArticle(headline=headline, excerpt=excerpt, url=link, pub_date=pub_date))
            text_lines.append(f"{headline}\n{excerpt}")

    # Atom
    if not articles:
        ns = {"a": _ATOM_NS}
        for entry in root.findall("a:entry", ns)[:_MAX_RSS_ITEMS]:
            headline = _xml_text(entry, f"{{{_ATOM_NS}}}title")
            excerpt = _xml_text(entry, f"{{{_ATOM_NS}}}summary") or ""
            link_el = entry.find(f"{{{_ATOM_NS}}}link")
            link = link_el.get("href", "") if link_el is not None else ""
            pub_date_str = (
                _xml_text(entry, f"{{{_ATOM_NS}}}published")
                or _xml_text(entry, f"{{{_ATOM_NS}}}updated")
            )
            pub_date = _parse_pub_date(pub_date_str)
            if headline:
                excerpt = _strip_html(excerpt)
                articles.append(RawArticle(headline=headline, excerpt=excerpt, url=link, pub_date=pub_date))
                text_lines.append(f"{headline}\n{excerpt}")

    if not articles:
        raise ScraperError("Feed parsed but contained no items.")

    scraped_text = "\n\n".join(text_lines)[:_MAX_TEXT_CHARS]
    return articles, scraped_text


def _xml_text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    if child is None:
        return ""
    return (child.text or "").strip()


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string using BeautifulSoup if available."""
    if not text:
        return ""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", "", text).strip()


# ---------------------------------------------------------------------------
# HTML scraping fallback
# ---------------------------------------------------------------------------

def _parse_html(soup, page_url: str) -> tuple[list[RawArticle], str]:
    base = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"

    for tag in soup(["script", "style", "nav", "footer", "aside", "iframe"]):
        tag.decompose()

    articles: list[RawArticle] = []
    seen_headlines: set[str] = set()

    for a in soup.find_all("a", href=True):
        headline = a.get_text(strip=True)
        if len(headline) < 20 or len(headline) > 300:
            continue
        if headline in seen_headlines:
            continue
        seen_headlines.add(headline)

        href = a["href"]
        if href.startswith("http"):
            article_url = href
        elif href.startswith("/"):
            article_url = base + href
        else:
            article_url = urljoin(page_url, href)

        # Try to find a nearby <time datetime="..."> for the publication date
        pub_date: datetime | None = None
        parent = a.parent
        excerpt = ""
        if parent:
            time_el = parent.find("time") or a.find_next("time")
            if time_el is not None:
                pub_date = _parse_pub_date(time_el.get("datetime", ""))
            for sib in parent.find_next_siblings():
                text = sib.get_text(strip=True)
                if 30 < len(text) < 500:
                    excerpt = text
                    break

        articles.append(RawArticle(headline=headline, excerpt=excerpt, url=article_url, pub_date=pub_date))

    scraped_text = soup.get_text(separator="\n", strip=True)[:_MAX_TEXT_CHARS]
    return articles, scraped_text


def _lxml_available() -> bool:
    try:
        import lxml  # noqa: F401
        return True
    except ImportError:
        return False
