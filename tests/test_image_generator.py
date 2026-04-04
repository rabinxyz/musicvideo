"""Tests for the multi-provider AI image generator pipeline stage."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from tenacity import wait_none


BANNED_WORDS = [
    "catholic", "rosary", "madonna", "saint", "cross with figure",
    "stained glass", "church interior", "religious", "icon", "byzantine",
    "papal", "crucifix", "prayer beads", "maria", "monastery", "monk",
    "nun", "cathedral", "chapel", "shrine", "altar", "candle altar",
    "sacred heart", "ihs",
]


class TestFluxProvider:
    """Tests for Flux providers (flux-dev, flux-pro, schnell)."""

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_flux_dev_returns_correct_paths(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "mountain sunrise golden light", "start": 0.0, "end": 5.0},
                {"visual_prompt": "calm water reflection", "start": 5.0, "end": 10.0},
            ]
        }

        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg data"
        mock_requests.get.return_value = mock_http

        result = generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        assert len(result) == 2
        assert all(p.endswith(".jpg") for p in result)

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_flux_dev_uses_correct_model_id(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        mock_fal.run.assert_called_once()
        assert mock_fal.run.call_args[0][0] == "fal-ai/flux/dev"

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_flux_pro_uses_correct_model_id(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="flux-pro")

        assert mock_fal.run.call_args[0][0] == "fal-ai/flux-pro"

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_schnell_uses_correct_model_and_steps(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="schnell")

        assert mock_fal.run.call_args[0][0] == "fal-ai/flux/schnell"
        assert mock_fal.run.call_args[1]["arguments"]["num_inference_steps"] == 4

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_negative_prompt_is_separate_parameter(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, NEGATIVE_PROMPT

        scene_plan = {"scenes": [{"visual_prompt": "mountain sunrise", "start": 0.0, "end": 5.0}]}
        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        args = mock_fal.run.call_args[1]["arguments"]
        assert args["negative_prompt"] == NEGATIVE_PROMPT
        assert NEGATIVE_PROMPT not in args["prompt"]

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_flux_retry_on_api_error(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, _generate_flux

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        mock_fal.run.side_effect = [
            Exception("rate limit"),
            Exception("server error"),
            {"images": [{"url": "https://example.com/image.jpg"}]},
        ]
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        original_wait = _generate_flux.retry.wait
        _generate_flux.retry.wait = wait_none()
        try:
            result = generate_images(scene_plan, str(tmp_path), provider="flux-dev")
        finally:
            _generate_flux.retry.wait = original_wait

        assert len(result) == 1
        assert mock_fal.run.call_count == 3


class TestDalleProvider:
    """Tests for legacy DALL-E provider."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_dalle_returns_correct_paths(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "mountain sunrise", "start": 0.0, "end": 5.0},
                {"visual_prompt": "calm water", "start": 5.0, "end": 10.0},
            ]
        }

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_response = MagicMock()
        mock_response.data = [mock_image]
        mock_client.images.generate.return_value = mock_response

        mock_http = MagicMock()
        mock_http.content = b"fake png data"
        mock_requests.get.return_value = mock_http

        result = generate_images(scene_plan, str(tmp_path), provider="dalle")

        assert len(result) == 2
        assert all(p.endswith(".jpg") for p in result)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_dalle_prompt_has_no_negative_content(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, NEGATIVE_PROMPT

        scene_plan = {"scenes": [{"visual_prompt": "mountain sunrise", "start": 0.0, "end": 5.0}]}

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_response = MagicMock()
        mock_response.data = [mock_image]
        mock_client.images.generate.return_value = mock_response

        mock_http = MagicMock()
        mock_http.content = b"fake png"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="dalle")

        prompt = mock_client.images.generate.call_args[1]["prompt"]
        assert NEGATIVE_PROMPT not in prompt
        assert "no " not in prompt.lower()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_dalle_retry_on_api_error(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, _generate_dalle

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_success = MagicMock()
        mock_success.data = [mock_image]

        mock_client.images.generate.side_effect = [
            Exception("rate limit"),
            Exception("server error"),
            mock_success,
        ]

        mock_http = MagicMock()
        mock_http.content = b"fake png"
        mock_requests.get.return_value = mock_http

        original_wait = _generate_dalle.retry.wait
        _generate_dalle.retry.wait = wait_none()
        try:
            result = generate_images(scene_plan, str(tmp_path), provider="dalle")
        finally:
            _generate_dalle.retry.wait = original_wait

        assert len(result) == 1
        assert mock_client.images.generate.call_count == 3


class TestProviderDetection:
    """Tests for provider validation and error messages."""

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_error_when_fal_key_missing(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        with pytest.raises(EnvironmentError, match="FAL_KEY"):
            generate_images(scene_plan, str(tmp_path), provider="flux-dev")

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_error_when_openai_key_missing(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            generate_images(scene_plan, str(tmp_path), provider="dalle")

    def test_raises_error_for_unknown_provider(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        with pytest.raises(ValueError, match="Unknown provider"):
            generate_images(scene_plan, str(tmp_path), provider="midjourney")

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_default_provider_is_flux_dev(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path))

        assert mock_fal.run.call_args[0][0] == "fal-ai/flux/dev"


class TestBannedWords:
    """Tests that banned words never appear in prompts."""

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_flux_prompt_has_no_banned_words(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "golden wheat fields, warm light, peaceful", "start": 0.0, "end": 5.0},
                {"visual_prompt": "mountain peaks, morning mist, majestic", "start": 5.0, "end": 10.0},
            ]
        }

        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        for call in mock_fal.run.call_args_list:
            prompt = call[1]["arguments"]["prompt"].lower()
            for word in BANNED_WORDS:
                assert word not in prompt, f"Banned word '{word}' found in prompt: {prompt}"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_dalle_prompt_has_no_banned_words(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "golden wheat fields, warm light, peaceful", "start": 0.0, "end": 5.0},
                {"visual_prompt": "mountain peaks, morning mist, majestic", "start": 5.0, "end": 10.0},
            ]
        }

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_response = MagicMock()
        mock_response.data = [mock_image]
        mock_client.images.generate.return_value = mock_response

        mock_http = MagicMock()
        mock_http.content = b"fake png"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="dalle")

        for call in mock_client.images.generate.call_args_list:
            prompt = call[1]["prompt"].lower()
            for word in BANNED_WORDS:
                assert word not in prompt, f"Banned word '{word}' found in DALL-E prompt: {prompt}"
