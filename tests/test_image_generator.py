"""Tests for the AI image generator pipeline stage."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


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
