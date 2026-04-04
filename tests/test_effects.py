"""Tests for visual effects module."""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from musicvid.pipeline.effects import apply_warm_grade
from musicvid.pipeline.effects import apply_vignette
from musicvid.pipeline.effects import create_cinematic_bars


class TestApplyWarmGrade:
    """Tests for warm color grading effect."""

    def test_increases_red_decreases_blue(self):
        """Red channel increases by 15, blue decreases by 10 after warm grade."""
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        result = apply_warm_grade(mock_clip)

        # Extract the transform function passed to clip.transform()
        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame
        output = transform_fn(get_frame, 0)

        assert output[:, :, 0].mean() == 143  # R: 128 + 15
        assert output[:, :, 1].mean() == 133  # G: 128 + 5
        assert output[:, :, 2].mean() == 118  # B: 128 - 10

    def test_clamps_values(self):
        """Values clamp to 0-255 range."""
        frame = np.full((100, 100, 3), 250, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_warm_grade(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame
        output = transform_fn(get_frame, 0)

        assert output[:, :, 0].mean() == 255  # R: clamped at 255
        assert output[:, :, 2].mean() == 240  # B: 250 - 10


class TestApplyVignette:
    """Tests for vignette (edge darkening) effect."""

    def test_edges_darker_than_center(self):
        """Edge pixels should be darker than center pixels after vignette."""
        frame = np.full((200, 200, 3), 200, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_vignette(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame
        output = transform_fn(get_frame, 0)

        center_val = output[100, 100, 0]
        corner_val = output[0, 0, 0]
        assert center_val > corner_val, f"Center {center_val} should be brighter than corner {corner_val}"

    def test_center_mostly_unchanged(self):
        """Center pixel should retain most of its original brightness."""
        frame = np.full((200, 200, 3), 200, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_vignette(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame
        output = transform_fn(get_frame, 0)

        center_val = output[100, 100, 0]
        assert center_val >= 190, f"Center {center_val} should be close to original 200"


class TestCreateCinematicBars:
    """Tests for cinematic letterbox bars."""

    @patch("musicvid.pipeline.effects.ColorClip")
    def test_returns_two_bar_clips(self, mock_color_clip):
        mock_bar = MagicMock()
        mock_bar.with_duration.return_value = mock_bar
        mock_bar.with_position.return_value = mock_bar
        mock_color_clip.return_value = mock_bar

        bars = create_cinematic_bars(1920, 1080, 10.0)

        assert len(bars) == 2

    @patch("musicvid.pipeline.effects.ColorClip")
    def test_bar_height_is_12_percent(self, mock_color_clip):
        mock_bar = MagicMock()
        mock_bar.with_duration.return_value = mock_bar
        mock_bar.with_position.return_value = mock_bar
        mock_color_clip.return_value = mock_bar

        bars = create_cinematic_bars(1920, 1080, 10.0)

        # Bar height = 12% of 1080 = 129 (int)
        call_args_list = mock_color_clip.call_args_list
        size_arg = call_args_list[0][1]["size"]
        assert size_arg == (1920, 129)
