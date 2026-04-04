"""Tests for stock_fetcher module."""

import json
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from musicvid.pipeline.stock_fetcher import fetch_videos, _build_search_query


class TestBuildSearchQuery:
    """Tests for search query building."""

    def test_uses_visual_prompt(self):
        scene = {
            "visual_prompt": "mountain sunrise golden light peaceful morning",
            "section": "intro",
        }
        query = _build_search_query(scene, "contemplative")
        assert "mountain" in query or "sunrise" in query

    def test_style_mapping_contemplative(self):
        scene = {"visual_prompt": "", "section": "verse"}
        query = _build_search_query(scene, "contemplative")
        assert len(query) > 0

    def test_style_mapping_joyful(self):
        scene = {"visual_prompt": "", "section": "verse"}
        query = _build_search_query(scene, "joyful")
        assert len(query) > 0


class TestFetchVideos:
    """Tests for the fetch_videos function."""

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_returns_video_paths_per_scene(self, mock_requests, sample_scene_plan, tmp_output):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "videos": [
                {
                    "id": 123,
                    "video_files": [
                        {"id": 1, "quality": "hd", "width": 1920, "height": 1080,
                         "link": "https://example.com/video.mp4"},
                    ],
                },
            ],
        }
        mock_response.content = b"fake video data"
        mock_response.iter_content = MagicMock(return_value=[b"fake video data"])
        mock_requests.get.return_value = mock_response

        output_dir = str(tmp_output / "tmp")
        result = fetch_videos(sample_scene_plan, output_dir=output_dir)

        assert len(result) == len(sample_scene_plan["scenes"])
        for entry in result:
            assert "scene_index" in entry
            assert "video_path" in entry
            assert "search_query" in entry

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_saves_manifest(self, mock_requests, sample_scene_plan, tmp_output):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "videos": [
                {
                    "id": 456,
                    "video_files": [
                        {"id": 2, "quality": "hd", "width": 1920, "height": 1080,
                         "link": "https://example.com/v2.mp4"},
                    ],
                },
            ],
        }
        mock_response.content = b"fake video data"
        mock_response.iter_content = MagicMock(return_value=[b"fake video data"])
        mock_requests.get.return_value = mock_response

        output_dir = str(tmp_output / "tmp")
        result = fetch_videos(sample_scene_plan, output_dir=output_dir)

        manifest_path = tmp_output / "tmp" / "fetch_manifest.json"
        assert manifest_path.exists()

    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_handles_api_failure_gracefully(self, mock_requests, sample_scene_plan, tmp_output):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_requests.get.return_value = mock_response

        output_dir = str(tmp_output / "tmp")
        result = fetch_videos(sample_scene_plan, output_dir=output_dir)

        assert len(result) == len(sample_scene_plan["scenes"])
        for entry in result:
            assert "video_path" in entry
