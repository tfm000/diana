"""Tests for diana.news.summarizer parsing and prompt logic."""

import json

import pytest

from diana.news.summarizer import (
    CATEGORIES,
    Story,
    _build_system_prompt,
    _parse_stories,
    _parse_stories_multi,
    _strip_fences,
)


class TestStripFences:
    def test_plain_json(self):
        text = '[{"headline": "test"}]'
        assert _strip_fences(text) == text

    def test_json_code_fence(self):
        text = '```json\n[{"headline": "test"}]\n```'
        result = _strip_fences(text)
        assert result == '[{"headline": "test"}]'

    def test_plain_code_fence(self):
        text = '```\n[{"headline": "test"}]\n```'
        result = _strip_fences(text)
        assert result == '[{"headline": "test"}]'

    def test_no_fence(self):
        text = "  [1, 2, 3]  "
        assert _strip_fences(text) == "[1, 2, 3]"

    def test_whitespace_stripped(self):
        text = "  \n[1]\n  "
        assert _strip_fences(text) == "[1]"


class TestParseStoriesMulti:
    def test_valid_json(self):
        data = [
            {
                "headline": "Test Story",
                "summary": "A summary.",
                "category": "Finance",
                "importance": 8,
                "url": "https://example.com",
                "source_name": "TestSource",
            }
        ]
        stories = _parse_stories_multi(json.dumps(data))
        assert len(stories) == 1
        assert stories[0].headline == "Test Story"
        assert stories[0].source_name == "TestSource"
        assert stories[0].importance == 8

    def test_malformed_json(self):
        stories = _parse_stories_multi("not json at all")
        assert stories == []

    def test_non_array_json(self):
        stories = _parse_stories_multi('{"headline": "test"}')
        assert stories == []

    def test_missing_headline_skipped(self):
        data = [
            {"headline": "", "summary": "Has summary", "category": "Other", "importance": 5, "url": "", "source_name": "X"},
            {"headline": "Valid", "summary": "Also valid", "category": "Other", "importance": 5, "url": "", "source_name": "Y"},
        ]
        stories = _parse_stories_multi(json.dumps(data))
        assert len(stories) == 1
        assert stories[0].headline == "Valid"

    def test_missing_summary_skipped(self):
        data = [
            {"headline": "Has headline", "summary": "", "category": "Other", "importance": 5, "url": "", "source_name": "X"},
        ]
        stories = _parse_stories_multi(json.dumps(data))
        assert stories == []

    def test_non_dict_items_skipped(self):
        data = [42, "string", {"headline": "Valid", "summary": "OK", "category": "Other", "importance": 5, "url": "", "source_name": "S"}]
        stories = _parse_stories_multi(json.dumps(data))
        assert len(stories) == 1

    def test_defaults_for_missing_fields(self):
        data = [{"headline": "H", "summary": "S"}]
        stories = _parse_stories_multi(json.dumps(data))
        assert len(stories) == 1
        assert stories[0].category == "Other"
        assert stories[0].importance == 5
        assert stories[0].url == ""
        assert stories[0].source_name == ""

    def test_with_markdown_fences(self):
        data = [{"headline": "H", "summary": "S", "category": "Finance", "importance": 7, "url": "", "source_name": "X"}]
        raw = f"```json\n{json.dumps(data)}\n```"
        stories = _parse_stories_multi(raw)
        assert len(stories) == 1


class TestParseStories:
    def test_source_name_injected(self):
        data = [
            {"headline": "Story", "summary": "Summary", "category": "World", "importance": 6, "url": ""},
        ]
        stories = _parse_stories(json.dumps(data), "MySource")
        assert len(stories) == 1
        assert stories[0].source_name == "MySource"

    def test_malformed_json(self):
        assert _parse_stories("{bad", "src") == []

    def test_non_array(self):
        assert _parse_stories('"just a string"', "src") == []


class TestBuildSystemPrompt:
    def test_contains_categories(self):
        prompt = _build_system_prompt(5)
        for cat in CATEGORIES:
            assert cat in prompt

    def test_contains_max_count(self):
        prompt = _build_system_prompt(10)
        assert "10" in prompt

    def test_requests_json_output(self):
        prompt = _build_system_prompt(5)
        assert "JSON" in prompt


class TestStoryDataclass:
    def test_creation(self):
        story = Story(
            headline="Test",
            summary="Sum",
            category="Finance",
            importance=7,
            url="https://example.com",
            source_name="Source",
        )
        assert story.headline == "Test"
        assert story.importance == 7
