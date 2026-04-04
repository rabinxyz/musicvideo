"""Tests for the AI image generator pipeline stage."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from tenacity import wait_none


class TestGenerateImages:
    """Tests for generate_images()."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_returns_correct_number_of_paths(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "mountain sunrise golden light", "start": 0.0, "end": 5.0},
                {"visual_prompt": "calm water reflection", "start": 5.0, "end": 10.0},
            ]
        }

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_response = MagicMock()
        mock_response.data = [mock_image]
        mock_client.images.generate.return_value = mock_response

        mock_http_response = MagicMock()
        mock_http_response.content = b"fake png data"
        mock_requests.get.return_value = mock_http_response

        result = generate_images(scene_plan, str(tmp_path))

        assert len(result) == 2
        assert all(p.endswith(".png") for p in result)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_every_prompt_contains_protestant_disclaimer(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, PROTESTANT_DISCLAIMER

        scene_plan = {
            "scenes": [
                {"visual_prompt": "mountain sunrise", "start": 0.0, "end": 5.0},
                {"visual_prompt": "calm water", "start": 5.0, "end": 10.0},
                {"visual_prompt": "sunset horizon", "start": 10.0, "end": 15.0},
            ]
        }

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_response = MagicMock()
        mock_response.data = [mock_image]
        mock_client.images.generate.return_value = mock_response

        mock_http_response = MagicMock()
        mock_http_response.content = b"fake png data"
        mock_requests.get.return_value = mock_http_response

        generate_images(scene_plan, str(tmp_path))

        calls = mock_client.images.generate.call_args_list
        assert len(calls) == 3
        for call in calls:
            prompt = call[1]["prompt"] if "prompt" in call[1] else call[0][0]
            assert PROTESTANT_DISCLAIMER in prompt

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_error_when_api_key_missing(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            generate_images(scene_plan, str(tmp_path))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_retry_on_api_error(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, _generate_image

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = type("APIError", (Exception,), {})

        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_success = MagicMock()
        mock_success.data = [mock_image]

        # Fail twice, succeed on third attempt
        mock_client.images.generate.side_effect = [
            mock_openai.APIError("rate limit"),
            mock_openai.APIError("server error"),
            mock_success,
        ]

        mock_http_response = MagicMock()
        mock_http_response.content = b"fake png"
        mock_requests.get.return_value = mock_http_response

        # Disable tenacity wait to avoid slow test
        original_wait = _generate_image.retry.wait
        _generate_image.retry.wait = wait_none()
        try:
            result = generate_images(scene_plan, str(tmp_path))
        finally:
            _generate_image.retry.wait = original_wait

        assert len(result) == 1
        assert mock_client.images.generate.call_count == 3
