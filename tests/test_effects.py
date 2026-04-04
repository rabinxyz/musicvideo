"""Tests for visual effects module."""

import numpy as np
import pytest
from unittest.mock import MagicMock

from musicvid.pipeline.effects import apply_warm_grade


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
