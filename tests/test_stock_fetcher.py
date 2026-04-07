"""Tests for stock_fetcher module."""

import json
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from musicvid.pipeline.stock_fetcher import (
    fetch_videos, fetch_video_by_query, _build_search_query,
    reset_download_registry, _downloaded_urls,
)


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


class TestFetchVideoByQuery:
    """Tests for fetch_video_by_query() single-video helper."""

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_downloads_video_matching_min_duration(self, mock_requests, tmp_path):
        mock_search = MagicMock()
        mock_search.json.return_value = {
            "videos": [
                {
                    "duration": 10,
                    "video_files": [
                        {"id": 1, "width": 1920, "height": 1080,
                         "link": "https://example.com/video.mp4"},
                    ],
                }
            ]
        }
        mock_search.raise_for_status = MagicMock()
        mock_download = MagicMock()
        mock_download.raise_for_status = MagicMock()
        mock_download.iter_content = MagicMock(return_value=[b"video-data"])
        mock_requests.get.side_effect = [mock_search, mock_download]

        from musicvid.pipeline.stock_fetcher import fetch_video_by_query
        output = str(tmp_path / "scene_000.mp4")
        result = fetch_video_by_query("mountain sunrise", min_duration=5.0, output_path=output)

        assert result == output
        assert Path(output).exists()

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_returns_none_when_no_videos_found(self, mock_requests, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"videos": []}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        from musicvid.pipeline.stock_fetcher import fetch_video_by_query
        output = str(tmp_path / "scene_001.mp4")
        result = fetch_video_by_query("nothing matches", min_duration=5.0, output_path=output)

        assert result is None

    def test_returns_none_when_no_api_key(self, tmp_path):
        from musicvid.pipeline.stock_fetcher import fetch_video_by_query
        with patch.dict(os.environ, {}, clear=True):
            result = fetch_video_by_query("query", min_duration=5.0,
                                          output_path=str(tmp_path / "out.mp4"))
        assert result is None

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    def test_returns_cached_path_without_api_call(self, tmp_path):
        output = tmp_path / "scene_002.mp4"
        output.write_bytes(b"cached-video")

        from musicvid.pipeline.stock_fetcher import fetch_video_by_query
        with patch("musicvid.pipeline.stock_fetcher.requests") as mock_req:
            result = fetch_video_by_query("any query", 5.0, str(output))
        assert result == str(output)
        mock_req.get.assert_not_called()


class TestStockDeduplication:
    """Tests for the URL deduplication registry."""

    def setup_method(self):
        reset_download_registry()

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_fetch_video_by_query_skips_already_downloaded(self, mock_requests, tmp_path):
        """Two calls with same results should pick different videos."""
        def make_mock_response(videos_json):
            mock_search = MagicMock()
            mock_search.json.return_value = videos_json
            mock_search.raise_for_status = MagicMock()
            mock_download = MagicMock()
            mock_download.raise_for_status = MagicMock()
            mock_download.iter_content = MagicMock(return_value=[b"video-data"])
            return [mock_search, mock_download]

        videos_payload = {
            "videos": [
                {
                    "url": "https://pexels.com/video/1",
                    "duration": 10,
                    "video_files": [
                        {"id": 1, "width": 1920, "height": 1080,
                         "link": "https://example.com/video1.mp4"},
                    ],
                },
                {
                    "url": "https://pexels.com/video/2",
                    "duration": 10,
                    "video_files": [
                        {"id": 2, "width": 1920, "height": 1080,
                         "link": "https://example.com/video2.mp4"},
                    ],
                },
            ]
        }

        mock_requests.get.side_effect = (
            make_mock_response(videos_payload)
            + make_mock_response(videos_payload)
        )

        output1 = str(tmp_path / "scene_000.mp4")
        output2 = str(tmp_path / "scene_001.mp4")

        fetch_video_by_query("mountain sunrise", min_duration=5.0, output_path=output1)
        fetch_video_by_query("mountain sunrise", min_duration=5.0, output_path=output2)

        assert len(_downloaded_urls) == 2

    def test_reset_clears_registry(self):
        """reset_download_registry() empties the set."""
        _downloaded_urls.add("https://pexels.com/video/999")
        assert len(_downloaded_urls) == 1
        reset_download_registry()
        assert len(_downloaded_urls) == 0

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_fallback_when_all_downloaded(self, mock_requests, tmp_path):
        """When only video is already registered, still returns a result (fallback)."""
        _downloaded_urls.add("https://pexels.com/video/1")

        mock_search = MagicMock()
        mock_search.json.return_value = {
            "videos": [
                {
                    "url": "https://pexels.com/video/1",
                    "duration": 10,
                    "video_files": [
                        {"id": 1, "width": 1920, "height": 1080,
                         "link": "https://example.com/video1.mp4"},
                    ],
                },
            ]
        }
        mock_search.raise_for_status = MagicMock()
        mock_download = MagicMock()
        mock_download.raise_for_status = MagicMock()
        mock_download.iter_content = MagicMock(return_value=[b"video-data"])
        mock_requests.get.side_effect = [mock_search, mock_download]

        output = str(tmp_path / "scene_000.mp4")
        result = fetch_video_by_query("mountain sunrise", min_duration=5.0, output_path=output)

        assert result is not None
