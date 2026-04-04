"""Tests for the BFL (Black Forest Labs) AI image generator pipeline stage."""

import os
from unittest.mock import patch, MagicMock, call

import pytest
import requests
from tenacity import wait_none


BANNED_WORDS = [
    "catholic", "rosary", "madonna", "saint", "cross with figure",
    "stained glass", "church interior", "religious", "icon", "byzantine",
    "papal", "crucifix", "prayer beads", "maria", "monastery", "monk",
    "nun", "cathedral", "chapel", "shrine", "altar", "candle altar",
    "sacred heart", "ihs",
]

TWO_SCENE_PLAN = {
    "scenes": [
        {"visual_prompt": "mountain sunrise golden light", "start": 0.0, "end": 5.0},
        {"visual_prompt": "calm water reflection", "start": 5.0, "end": 10.0},
    ]
}

ONE_SCENE_PLAN = {
    "scenes": [{"visual_prompt": "test prompt", "start": 0.0, "end": 5.0}]
}


def _make_post_response(task_id="task-123"):
    """Create a mock POST response returning a task ID and polling URL."""
    resp = MagicMock()
    resp.json.return_value = {
        "id": task_id,
        "polling_url": f"https://api.bfl.ai/v1/get_result?id={task_id}",
    }
    return resp


def _make_poll_response(status="Ready", sample_url="https://bfl.ai/sample.jpg"):
    """Create a mock GET poll response."""
    resp = MagicMock()
    if status == "Ready":
        resp.json.return_value = {"status": "Ready", "result": {"sample": sample_url}}
    else:
        resp.json.return_value = {"status": status}
    return resp


def _make_download_response():
    """Create a mock GET download response."""
    resp = MagicMock()
    resp.content = b"fake jpeg data"
    return resp


class TestBFLFlowSubmitPollDownload:
    """Full flow tests: submit -> poll -> download."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_full_flow_returns_correct_paths(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        # For 2 scenes: POST, GET(poll), GET(download), POST, GET(poll), GET(download)
        mock_requests.post.side_effect = [
            _make_post_response("task-1"),
            _make_post_response("task-2"),
        ]
        mock_requests.get.side_effect = [
            _make_poll_response("Ready", "https://bfl.ai/img1.jpg"),
            _make_download_response(),
            _make_poll_response("Ready", "https://bfl.ai/img2.jpg"),
            _make_download_response(),
        ]

        result = generate_images(TWO_SCENE_PLAN, str(tmp_path))

        assert len(result) == 2
        assert all(p.endswith(".jpg") for p in result)
        assert "scene_000.jpg" in result[0]
        assert "scene_001.jpg" in result[1]

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_submit_uses_correct_model_and_params(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response()
        mock_requests.get.side_effect = [
            _make_poll_response(),
            _make_download_response(),
        ]

        generate_images(ONE_SCENE_PLAN, str(tmp_path), provider="flux-dev")

        post_call = mock_requests.post.call_args
        url = post_call[0][0] if post_call[0] else post_call[1].get("url", "")
        assert "/v1/flux-dev" in url

        payload = post_call[1]["json"]
        assert payload["width"] == 1280
        assert payload["height"] == 720
        assert "prompt" in payload
        assert "output_format" not in payload
        assert "safety_tolerance" not in payload
        assert "prompt_upsampling" not in payload

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_flux_pro_uses_correct_model(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response()
        mock_requests.get.side_effect = [
            _make_poll_response(),
            _make_download_response(),
        ]

        generate_images(ONE_SCENE_PLAN, str(tmp_path), provider="flux-pro")

        url = mock_requests.post.call_args[0][0]
        assert "/v1/flux-pro-1.1" in url

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_schnell_uses_correct_model(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response()
        mock_requests.get.side_effect = [
            _make_poll_response(),
            _make_download_response(),
        ]

        generate_images(ONE_SCENE_PLAN, str(tmp_path), provider="flux-schnell")

        url = mock_requests.post.call_args[0][0]
        assert "/v1/flux-2-klein-4b" in url

    @patch.dict(os.environ, {"BFL_API_KEY": "my-secret-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_auth_header_sent(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response()
        mock_requests.get.side_effect = [
            _make_poll_response(),
            _make_download_response(),
        ]

        generate_images(ONE_SCENE_PLAN, str(tmp_path))

        headers = mock_requests.post.call_args[1]["headers"]
        assert headers["X-Key"] == "my-secret-key"


class TestPolling:
    """Tests for polling behavior."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.time")
    @patch("musicvid.pipeline.image_generator.requests")
    def test_polling_with_pending_before_ready(self, mock_requests, mock_time, tmp_path):
        from musicvid.pipeline.image_generator import _poll_result

        # monotonic: start=0, then 1.5, 3.0, 4.5 (all within 120s)
        mock_time.monotonic.side_effect = [0, 1.5, 3.0, 4.5]
        mock_time.sleep = MagicMock()

        mock_requests.get.side_effect = [
            _make_poll_response("Pending"),
            _make_poll_response("Pending"),
            _make_poll_response("Ready", "https://bfl.ai/result.jpg"),
        ]

        result = _poll_result("https://api.bfl.ai/v1/get_result?id=task-abc")

        assert result == "https://bfl.ai/result.jpg"
        assert mock_requests.get.call_count == 3
        assert mock_time.sleep.call_count == 2

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.time")
    @patch("musicvid.pipeline.image_generator.requests")
    def test_polling_timeout_raises_error(self, mock_requests, mock_time, tmp_path):
        from musicvid.pipeline.image_generator import _poll_result

        # monotonic: start=0, then 121 (past 120s timeout)
        mock_time.monotonic.side_effect = [0, 121]
        mock_time.sleep = MagicMock()

        with pytest.raises(TimeoutError):
            _poll_result("https://api.bfl.ai/v1/get_result?id=task-timeout")


class TestProviderDetection:
    """Tests for provider validation and error messages."""

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_error_when_bfl_key_missing(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        with pytest.raises(EnvironmentError, match="BFL_API_KEY"):
            generate_images(ONE_SCENE_PLAN, str(tmp_path), provider="flux-dev")

    def test_raises_error_for_unknown_provider(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        with pytest.raises(ValueError, match="Unknown provider"):
            generate_images(ONE_SCENE_PLAN, str(tmp_path), provider="midjourney")

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_default_provider_is_flux_dev(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response()
        mock_requests.get.side_effect = [
            _make_poll_response(),
            _make_download_response(),
        ]

        generate_images(ONE_SCENE_PLAN, str(tmp_path))

        url = mock_requests.post.call_args[0][0]
        assert "/v1/flux-dev" in url


class TestRetryBehavior:
    """Tests for retry logic on _submit_task."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_retry_on_5xx_submit(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import _submit_task

        # Make isinstance checks work with the mock
        mock_requests.exceptions = requests.exceptions
        mock_requests.HTTPError = requests.HTTPError

        error_resp = MagicMock()
        error_resp.status_code = 500
        error = requests.HTTPError(response=error_resp)

        success_resp = _make_post_response("task-ok")

        mock_requests.post.side_effect = [error, error, success_resp]

        original_wait = _submit_task.retry.wait
        _submit_task.retry.wait = wait_none()
        try:
            task_id, polling_url = _submit_task("flux-dev", "test prompt")
        finally:
            _submit_task.retry.wait = original_wait

        assert task_id == "task-ok"
        assert "task-ok" in polling_url
        assert mock_requests.post.call_count == 3

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_no_retry_on_4xx(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import _submit_task

        mock_requests.exceptions = requests.exceptions
        mock_requests.HTTPError = requests.HTTPError

        error_resp = MagicMock()
        error_resp.status_code = 401

        success_resp = MagicMock()
        success_resp.raise_for_status.side_effect = requests.HTTPError(response=error_resp)

        mock_requests.post.return_value = success_resp

        original_wait = _submit_task.retry.wait
        _submit_task.retry.wait = wait_none()
        try:
            with pytest.raises(requests.HTTPError):
                _submit_task("flux-dev", "test prompt")
        finally:
            _submit_task.retry.wait = original_wait

        assert mock_requests.post.call_count == 1


class TestBannedWords:
    """Tests that banned words never appear in prompts."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_prompt_has_no_banned_words(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "golden wheat fields, warm light, peaceful", "start": 0.0, "end": 5.0},
                {"visual_prompt": "mountain peaks, morning mist, majestic", "start": 5.0, "end": 10.0},
            ]
        }

        mock_requests.post.side_effect = [
            _make_post_response("task-1"),
            _make_post_response("task-2"),
        ]
        mock_requests.get.side_effect = [
            _make_poll_response(),
            _make_download_response(),
            _make_poll_response(),
            _make_download_response(),
        ]

        generate_images(scene_plan, str(tmp_path))

        for post_call in mock_requests.post.call_args_list:
            prompt = post_call[1]["json"]["prompt"].lower()
            for word in BANNED_WORDS:
                assert word not in prompt, f"Banned word '{word}' found in prompt: {prompt}"
