"""Tests for Runway Gen-4 video animation module."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def _make_post_response(task_id="task-abc"):
    resp = MagicMock()
    resp.json.return_value = {"id": task_id}
    return resp


def _make_poll_response(status, video_url=None):
    resp = MagicMock()
    if status == "SUCCEEDED":
        resp.json.return_value = {"status": "SUCCEEDED", "output": [{"url": video_url}]}
    elif status == "FAILED":
        resp.json.return_value = {"status": "FAILED"}
    else:
        resp.json.return_value = {"status": status}
    return resp


def _make_poll_response_str(status, video_url=None):
    """Runway response where output is a list of URL strings, not dicts."""
    resp = MagicMock()
    if status == "SUCCEEDED":
        resp.json.return_value = {"status": "SUCCEEDED", "output": [video_url]}
    else:
        resp.json.return_value = {"status": status}
    return resp


def _make_download_response():
    resp = MagicMock()
    resp.iter_content.return_value = [b"fake", b"video", b"data"]
    return resp


class TestAnimateImage:
    """Tests for animate_image() function."""

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_returns_output_path(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        mock_time.monotonic.side_effect = [0.0, 1.0, 2.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-1")
        mock_requests.get.side_effect = [
            _make_poll_response("SUCCEEDED", "https://runway.ai/video.mp4"),
            _make_download_response(),
        ]

        img = tmp_path / "scene_000.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "animated_scene_000.mp4"

        result = animate_image(str(img), "Slow camera push forward", output_path=str(out))

        assert result == str(out)
        assert out.exists()

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_cache_hit_skips_api(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        img = tmp_path / "scene_000.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "animated_scene_000.mp4"
        out.write_bytes(b"existing video")  # simulate cached file

        result = animate_image(str(img), "Slow zoom", output_path=str(out))

        assert result == str(out)
        mock_requests.post.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_when_no_api_key(self, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        img = tmp_path / "scene_000.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "animated.mp4"

        with pytest.raises(RuntimeError, match="RUNWAY_API_KEY"):
            animate_image(str(img), "Slow zoom", output_path=str(out))

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_polling_pending_then_succeeded(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        mock_time.monotonic.side_effect = [0.0, 1.0, 2.0, 3.0, 4.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-pending")
        mock_requests.get.side_effect = [
            _make_poll_response("PENDING"),
            _make_poll_response("PENDING"),
            _make_poll_response("SUCCEEDED", "https://runway.ai/video.mp4"),
            _make_download_response(),
        ]

        img = tmp_path / "scene.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "out.mp4"

        result = animate_image(str(img), "Camera rises", output_path=str(out))
        assert result == str(out)

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_timeout_raises_timeout_error(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        # monotonic returns > POLL_TIMEOUT after first call
        mock_time.monotonic.side_effect = [0.0, 301.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-slow")
        mock_requests.get.return_value = _make_poll_response("PENDING")

        img = tmp_path / "scene.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "out.mp4"

        with pytest.raises(TimeoutError):
            animate_image(str(img), "Slow zoom", output_path=str(out))

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_failed_status_raises_runtime_error(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        mock_time.monotonic.side_effect = [0.0, 1.0, 2.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-fail")
        mock_requests.get.side_effect = [
            _make_poll_response("FAILED"),
        ]

        img = tmp_path / "scene.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "out.mp4"

        with pytest.raises(RuntimeError, match="FAILED"):
            animate_image(str(img), "Slow zoom", output_path=str(out))

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_submit_called_with_correct_payload(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        mock_time.monotonic.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-1")
        mock_requests.get.side_effect = [
            _make_poll_response("SUCCEEDED", "https://runway.ai/video.mp4"),
            _make_download_response(),
        ]

        img = tmp_path / "scene.jpg"
        img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)  # minimal jpeg bytes
        out = tmp_path / "out.mp4"

        animate_image(str(img), "Camera rises slowly", duration=5, output_path=str(out))

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["model"] == "gen4.5"
        assert payload["duration"] == 5
        assert payload["ratio"] == "1280:720"
        assert payload["promptText"] == "Camera rises slowly"
        assert payload["promptImage"].startswith("data:image/jpeg;base64,")


class TestPollAnimationOutputFormats:
    """Tests that _poll_animation handles both output formats from Runway API."""

    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_string_list_output(self, mock_time, mock_requests):
        from musicvid.pipeline.video_animator import _poll_animation

        mock_time.monotonic.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()
        mock_requests.get.return_value = _make_poll_response_str(
            "SUCCEEDED", "https://runway.ai/video.mp4"
        )

        url = _poll_animation("task-xyz")
        assert url == "https://runway.ai/video.mp4"

    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_dict_list_output(self, mock_time, mock_requests):
        from musicvid.pipeline.video_animator import _poll_animation

        mock_time.monotonic.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()
        mock_requests.get.return_value = _make_poll_response(
            "SUCCEEDED", "https://runway.ai/video.mp4"
        )

        url = _poll_animation("task-xyz")
        assert url == "https://runway.ai/video.mp4"

    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_unexpected_output_raises(self, mock_time, mock_requests):
        from musicvid.pipeline.video_animator import _poll_animation

        mock_time.monotonic.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()
        resp = MagicMock()
        resp.json.return_value = {"status": "SUCCEEDED", "output": []}
        mock_requests.get.return_value = resp

        with pytest.raises(RuntimeError, match="Unexpected output structure"):
            _poll_animation("task-xyz")
