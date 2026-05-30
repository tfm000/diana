"""Tests for diana.news.summarizer.build_digest_text (PRIV-04 News digest).

These tests lock D-09: with LLM off, the News page concatenates cleaned
article prose with blank-line boundaries, with no spoken titles, no
"Source:" prefix, and no category labels. The helper must also be pure
(Streamlit-free) and perform zero LLM/summarizer egress.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from diana.news.scraper import RawArticle


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _article(headline: str, excerpt: str = "", url: str = "") -> RawArticle:
    return RawArticle(
        headline=headline,
        excerpt=excerpt,
        url=url,
        pub_date=datetime(2026, 5, 30, tzinfo=timezone.utc),
    )


def _sources_two_each() -> list[dict]:
    return [
        {
            "name": "Source Alpha",
            "url": "https://alpha.example.com",
            "articles": [
                _article(
                    "Alpha One Headline",
                    "Alpha one excerpt body — first article from source alpha.",
                ),
                _article(
                    "Alpha Two Headline",
                    "Alpha two excerpt body — second article from source alpha.",
                ),
            ],
        },
        {
            "name": "Source Beta",
            "url": "https://beta.example.com",
            "articles": [
                _article(
                    "Beta One Headline",
                    "Beta one excerpt body — first article from source beta.",
                ),
                _article(
                    "Beta Two Headline",
                    "Beta two excerpt body — second article from source beta.",
                ),
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Import / purity
# ---------------------------------------------------------------------------


class TestPurity:
    def test_helper_importable_without_streamlit(self):
        # If build_digest_text accidentally pulled in Streamlit at module scope
        # this would fail under pytest (which never imports st).
        from diana.news.summarizer import build_digest_text  # noqa: F401

    def test_helper_returns_str(self):
        from diana.news.summarizer import build_digest_text

        result = build_digest_text(_sources_two_each())
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# D-09 content shape
# ---------------------------------------------------------------------------


class TestDigestShape:
    def test_blank_line_joins_between_articles(self):
        from diana.news.summarizer import build_digest_text

        result = build_digest_text(_sources_two_each())
        # Four articles -> three "\n\n" separators (and no leading/trailing blank line).
        assert result.count("\n\n") == 3
        # No triple-newline runs (no empty segments leaking in).
        assert "\n\n\n" not in result
        assert not result.startswith("\n")
        assert not result.endswith("\n")

    def test_no_headlines_as_title_lines(self):
        from diana.news.summarizer import build_digest_text

        result = build_digest_text(_sources_two_each())
        # No headline should appear as a standalone line preceding its body.
        for headline in (
            "Alpha One Headline",
            "Alpha Two Headline",
            "Beta One Headline",
            "Beta Two Headline",
        ):
            assert f"{headline}\n" not in result
            assert f"\n{headline}" not in result
            # And the headline string must not appear anywhere when the excerpt
            # was non-empty (we never speak the title for sources with bodies).
            assert headline not in result

    def test_no_source_prefix(self):
        from diana.news.summarizer import build_digest_text

        result = build_digest_text(_sources_two_each())
        assert "Source:" not in result
        assert "Source Alpha" not in result
        assert "Source Beta" not in result

    def test_no_category_labels(self):
        from diana.news.summarizer import build_digest_text

        # Pass sources annotated with a category key the helper must ignore.
        sources = _sources_two_each()
        for src in sources:
            src["category"] = "Finance"  # extraneous, must not surface
        result = build_digest_text(sources)
        # None of the seven canonical categories may appear in the digest.
        for cat in (
            "Finance",
            "Politics",
            "Technology",
            "Science",
            "Sports",
            "Entertainment",
            "World",
            "Health",
            "Other",
        ):
            assert cat not in result


# ---------------------------------------------------------------------------
# Body selection & ordering
# ---------------------------------------------------------------------------


class TestBodySelection:
    def test_excerpt_used_when_present(self):
        from diana.news.summarizer import build_digest_text

        result = build_digest_text(_sources_two_each())
        # Excerpt prose appears, headlines do not (covered above).
        assert "Alpha one excerpt body" in result
        assert "Beta two excerpt body" in result

    def test_falls_back_to_headline_when_excerpt_empty(self):
        from diana.news.summarizer import build_digest_text

        sources = [
            {
                "name": "S",
                "url": "https://s.example.com",
                "articles": [
                    _article("Only Headline Available", excerpt=""),
                    _article(
                        "Has Excerpt Title", "Excerpt body here for the second article."
                    ),
                ],
            }
        ]
        result = build_digest_text(sources)
        # First article had no excerpt -> headline used as the body.
        assert "Only Headline Available" in result
        # Second article still uses the excerpt (its title should not appear).
        assert "Has Excerpt Title" not in result
        assert "Excerpt body here for the second article" in result

    def test_falls_back_to_headline_when_excerpt_whitespace(self):
        from diana.news.summarizer import build_digest_text

        sources = [
            {
                "name": "S",
                "url": "https://s.example.com",
                "articles": [
                    _article("Whitespace Excerpt Headline", excerpt="   \n  \t  "),
                ],
            }
        ]
        result = build_digest_text(sources)
        assert "Whitespace Excerpt Headline" in result

    def test_empty_body_articles_are_skipped(self):
        from diana.news.summarizer import build_digest_text

        sources = [
            {
                "name": "S",
                "url": "https://s.example.com",
                "articles": [
                    _article("Real Body One", "Real body number one."),
                    # Both empty -> body resolves to "" -> skipped.
                    _article("", excerpt=""),
                    _article("Real Body Two", "Real body number two."),
                ],
            }
        ]
        result = build_digest_text(sources)
        # Two segments (the skipped empty article does NOT inject a blank).
        assert result.count("\n\n") == 1
        assert "Real body number one" in result
        assert "Real body number two" in result

    def test_ordering_source_then_article(self):
        from diana.news.summarizer import build_digest_text

        result = build_digest_text(_sources_two_each())
        idx_a1 = result.find("Alpha one excerpt body")
        idx_a2 = result.find("Alpha two excerpt body")
        idx_b1 = result.find("Beta one excerpt body")
        idx_b2 = result.find("Beta two excerpt body")
        assert -1 < idx_a1 < idx_a2 < idx_b1 < idx_b2

    def test_empty_input_returns_empty_string(self):
        from diana.news.summarizer import build_digest_text

        assert build_digest_text([]) == ""

    def test_source_with_no_articles_does_not_break(self):
        from diana.news.summarizer import build_digest_text

        sources = [
            {"name": "Empty Source", "url": "https://e.example.com", "articles": []},
            {
                "name": "S",
                "url": "https://s.example.com",
                "articles": [_article("H", "Real body content."),],
            },
        ]
        result = build_digest_text(sources)
        assert result == "Real body content."


# ---------------------------------------------------------------------------
# T-04-01: zero LLM/summarizer egress on the digest path
# ---------------------------------------------------------------------------


class TestNoLLMEgress:
    def test_does_not_call_summarize_all_sources(self):
        from diana.news import summarizer

        with patch.object(
            summarizer, "summarize_all_sources", side_effect=AssertionError(
                "build_digest_text must not call summarize_all_sources"
            )
        ):
            summarizer.build_digest_text(_sources_two_each())

    def test_does_not_import_or_call_llm_complete(self):
        # llm_complete lives in diana.llm.client; patch it there and assert
        # build_digest_text does not trigger it (no LLM network call).
        import diana.llm.client as llm_client_mod
        from diana.news.summarizer import build_digest_text

        with patch.object(
            llm_client_mod, "llm_complete", side_effect=AssertionError(
                "build_digest_text must not call llm_complete"
            )
        ):
            build_digest_text(_sources_two_each())


# ---------------------------------------------------------------------------
# Cleaner is applied (smoke check)
# ---------------------------------------------------------------------------


class TestCleanerApplied:
    def test_strips_urls_via_clean_text(self):
        # URLs inside an excerpt are stripped by diana.processing.cleaner.clean_text.
        from diana.news.summarizer import build_digest_text

        sources = [
            {
                "name": "S",
                "url": "https://s.example.com",
                "articles": [
                    _article(
                        "H",
                        "Read more at https://news.example.com/story and back to prose.",
                    ),
                ],
            }
        ]
        result = build_digest_text(sources)
        assert "https://news.example.com" not in result
        assert "Read more at" in result
        assert "back to prose" in result


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
