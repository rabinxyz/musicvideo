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


# ------------------------------------------------------------------ #
# Task 2: VisualRouter integration tests
# ------------------------------------------------------------------ #

from musicvid.pipeline.visual_router import VisualRouter


def _make_scene(source, query, idx=0, start=0.0, end=10.0, visual_prompt="fallback prompt"):
    return {
        "index": idx,
        "section": "verse",
        "start": start,
        "end": end,
        "visual_source": source,
        "search_query": query,
        "visual_prompt": visual_prompt,
        "motion_prompt": "",
        "animate": False,
    }


class TestVideoStockSanitization:
    """_route_video_stock respects sanitize_query."""

    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch("musicvid.pipeline.visual_router.fetch_video_by_query")
    def test_blocked_query_skips_pexels_falls_back_bfl(self, mock_fetch, mock_bfl, tmp_path):
        mock_bfl.return_value = str(tmp_path / "scene_000.jpg")
        router = VisualRouter(str(tmp_path))
        scene = _make_scene("TYPE_VIDEO_STOCK", "mosque at sunset", visual_prompt="nature scene")

        result = router.route(scene)

        mock_fetch.assert_not_called()
        mock_bfl.assert_called_once()
        assert result == str(tmp_path / "scene_000.jpg")

    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch("musicvid.pipeline.visual_router.fetch_video_by_query")
    def test_safe_replacement_passed_to_fetch(self, mock_fetch, mock_bfl, tmp_path):
        mock_fetch.return_value = str(tmp_path / "scene_000.mp4")
        router = VisualRouter(str(tmp_path))
        scene = _make_scene("TYPE_VIDEO_STOCK", "prayer hands close up")

        result = router.route(scene)

        # Should have been replaced
        call_query = mock_fetch.call_args_list[0][0][0]
        assert call_query == SAFE_QUERY_MAP["prayer hands"]

    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch("musicvid.pipeline.visual_router.fetch_video_by_query")
    def test_safe_query_passes_through(self, mock_fetch, mock_bfl, tmp_path):
        mock_fetch.return_value = str(tmp_path / "scene_000.mp4")
        router = VisualRouter(str(tmp_path))
        scene = _make_scene("TYPE_VIDEO_STOCK", "mountain valley peaceful morning")

        router.route(scene)

        call_query = mock_fetch.call_args_list[0][0][0]
        assert call_query == "mountain valley peaceful morning"


class TestPhotoStockSanitization:
    """_route_photo_stock respects sanitize_query."""

    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch("musicvid.pipeline.visual_router.fetch_video_by_query")
    @patch("musicvid.pipeline.visual_router.requests.get")
    @patch.dict(os.environ, {"UNSPLASH_ACCESS_KEY": "fake", "PEXELS_API_KEY": "fake"})
    def test_blocked_query_skips_unsplash_pexels_falls_back_bfl(
        self, mock_get, mock_fetch, mock_bfl, tmp_path
    ):
        mock_bfl.return_value = str(tmp_path / "scene_001.jpg")
        router = VisualRouter(str(tmp_path))
        scene = _make_scene("TYPE_PHOTO_STOCK", "hindu temple sunrise", idx=1,
                            visual_prompt="peaceful morning")

        result = router.route(scene)

        mock_get.assert_not_called()
        mock_fetch.assert_not_called()
        mock_bfl.assert_called_once()

    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch("musicvid.pipeline.visual_router.fetch_video_by_query")
    @patch("musicvid.pipeline.visual_router.requests.get")
    @patch.dict(os.environ, {"UNSPLASH_ACCESS_KEY": "fake", "PEXELS_API_KEY": ""})
    def test_safe_replacement_passed_to_unsplash(
        self, mock_get, mock_fetch, mock_bfl, tmp_path
    ):
        # Simulate successful Unsplash response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"urls": {"regular": "https://example.com/photo.jpg"}}
        mock_img_resp = MagicMock()
        mock_img_resp.content = b"fake image bytes"
        mock_get.side_effect = [mock_resp, mock_img_resp]

        router = VisualRouter(str(tmp_path))
        scene = _make_scene("TYPE_PHOTO_STOCK", "worship hands raised", idx=1)

        router.route(scene)

        # First call is the Unsplash API call — check query param
        call_params = mock_get.call_args_list[0][1]["params"]
        assert call_params["query"] == SAFE_QUERY_MAP["worship hands raised"]

    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch("musicvid.pipeline.visual_router.fetch_video_by_query")
    @patch("musicvid.pipeline.visual_router.requests.get")
    @patch.dict(os.environ, {"UNSPLASH_ACCESS_KEY": "fake", "PEXELS_API_KEY": ""})
    def test_safe_query_passes_through_to_unsplash(
        self, mock_get, mock_fetch, mock_bfl, tmp_path
    ):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"urls": {"regular": "https://example.com/photo.jpg"}}
        mock_img_resp = MagicMock()
        mock_img_resp.content = b"fake image bytes"
        mock_get.side_effect = [mock_resp, mock_img_resp]

        router = VisualRouter(str(tmp_path))
        scene = _make_scene("TYPE_PHOTO_STOCK", "open bible morning light", idx=1)

        router.route(scene)

        call_params = mock_get.call_args_list[0][1]["params"]
        assert call_params["query"] == "open bible morning light"
