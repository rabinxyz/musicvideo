"""Tests for stock content filtering — sanitize_query and VisualRouter integration."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from musicvid.pipeline.visual_router import sanitize_query, BLOCKED_WORDS, SAFE_QUERY_MAP


# ------------------------------------------------------------------ #
# Existing: director prompt filtering tests
# ------------------------------------------------------------------ #


class TestDirectorPromptFiltering:
    def test_director_prompt_bans_religious_keywords_in_search_query(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text()
        for word in ["muslim", "mosque", "islamic", "hindu", "buddha",
                     "church interior", "cathedral", "shrine", "altar",
                     "rosary", "meditation", "prayer rug", "hijab"]:
            assert word in prompt_text.lower(), f"Missing banned word: {word}"

    def test_director_prompt_has_safe_query_guidance(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text().lower()
        assert "person sitting" in prompt_text or "person walking" in prompt_text
        assert "nature" in prompt_text

    def test_director_prompt_restricts_video_stock_to_nature(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text()
        assert "TYPE_VIDEO_STOCK" in prompt_text
        assert "prayer" in prompt_text.lower() or "worship" in prompt_text.lower()


# ------------------------------------------------------------------ #
# Task 1: sanitize_query unit tests
# ------------------------------------------------------------------ #


class TestSanitizeQueryBlocked:
    """Blocked words must return 'BLOCKED'."""

    @pytest.mark.parametrize("word", BLOCKED_WORDS)
    def test_blocked_word_returns_blocked(self, word):
        assert sanitize_query(word) == "BLOCKED"

    @pytest.mark.parametrize("word", BLOCKED_WORDS)
    def test_blocked_word_case_insensitive(self, word):
        assert sanitize_query(word.upper()) == "BLOCKED"

    @pytest.mark.parametrize("word", BLOCKED_WORDS)
    def test_blocked_word_in_phrase(self, word):
        assert sanitize_query(f"beautiful {word} scenery") == "BLOCKED"


class TestSanitizeQuerySafeReplacement:
    """Unsafe queries get mapped to safe replacements."""

    @pytest.mark.parametrize("unsafe,safe", list(SAFE_QUERY_MAP.items()))
    def test_unsafe_replaced(self, unsafe, safe):
        assert sanitize_query(unsafe) == safe

    def test_unsafe_case_insensitive(self):
        assert sanitize_query("Prayer Hands") == SAFE_QUERY_MAP["prayer hands"]

    def test_unsafe_in_longer_phrase(self):
        result = sanitize_query("beautiful worship scene")
        assert result == SAFE_QUERY_MAP["worship"]


class TestSanitizeQuerySafePassthrough:
    """Safe queries pass through unchanged."""

    @pytest.mark.parametrize("query", [
        "mountain sunrise",
        "ocean waves",
        "person walking",
        "",
    ])
    def test_safe_passthrough(self, query):
        assert sanitize_query(query) == query

    def test_none_like_empty(self):
        assert sanitize_query("") == ""
