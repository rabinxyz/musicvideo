"""Tests for visual effects module."""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from musicvid.pipeline.effects import apply_warm_grade
from musicvid.pipeline.effects import apply_vignette
from musicvid.pipeline.effects import create_cinematic_bars
from musicvid.pipeline.effects import apply_film_grain
from musicvid.pipeline.effects import create_light_leak
from musicvid.pipeline.effects import apply_effects
from musicvid.pipeline.effects import apply_subtle_film_look


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


class TestApplyFilmGrain:
    """Tests for film grain (animated noise) effect."""

    def test_adds_noise_to_frame(self):
        """Frame should differ from original after grain is applied."""
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_film_grain(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame.copy()

        np.random.seed(42)
        output = transform_fn(get_frame, 0)

        # Grain adds noise, so output should not be identical to input
        assert not np.array_equal(output, frame)

    def test_grain_is_subtle(self):
        """Mean pixel difference should be small (opacity 0.15, sigma 8)."""
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_film_grain(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame.copy()

        np.random.seed(42)
        output = transform_fn(get_frame, 0)

        diff = np.abs(output.astype(int) - frame.astype(int))
        assert diff.mean() < 5, f"Grain too strong: mean diff {diff.mean()}"


class TestCreateLightLeak:
    """Tests for light leak effect."""

    @patch("musicvid.pipeline.effects.ImageClip")
    def test_returns_clip_with_correct_duration(self, mock_image_clip):
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_end.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_image_clip.return_value = mock_clip

        result = create_light_leak(10.0, (1920, 1080))

        mock_clip.with_duration.assert_called_once()
        assert result is not None

    @patch("musicvid.pipeline.effects.ImageClip")
    def test_leak_appears_between_20_and_60_percent(self, mock_image_clip):
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_end.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_image_clip.return_value = mock_clip

        np.random.seed(42)
        create_light_leak(10.0, (1920, 1080))

        start_call = mock_clip.with_start.call_args[0][0]
        assert 2.0 <= start_call <= 6.0, f"Start {start_call} not in 20-60% of 10s"


class TestApplyEffects:
    """Tests for the apply_effects orchestrator."""

    def test_none_returns_clip_unchanged(self):
        """Level 'none' should not apply any effects."""
        mock_clip = MagicMock()
        result = apply_effects(mock_clip, level="none")
        assert result is mock_clip
        mock_clip.transform.assert_not_called()

    @patch("musicvid.pipeline.effects.apply_subtle_film_look")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_minimal_applies_warm_and_vignette(self, mock_warm, mock_vignette, mock_film):
        """Level 'minimal' should apply warm grade, vignette, and subtle film look."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip
        mock_film.return_value = mock_clip

        apply_effects(mock_clip, level="minimal")

        mock_warm.assert_called_once_with(mock_clip)
        mock_vignette.assert_called_once()
        mock_film.assert_called_once()

    @patch("musicvid.pipeline.effects.apply_film_grain")
    @patch("musicvid.pipeline.effects.apply_subtle_film_look")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_full_applies_all_frame_effects(self, mock_warm, mock_vignette, mock_film, mock_grain):
        """Level 'full' should apply warm grade, vignette, subtle film look, and film grain."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip
        mock_film.return_value = mock_clip
        mock_grain.return_value = mock_clip

        apply_effects(mock_clip, level="full")

        mock_warm.assert_called_once()
        mock_vignette.assert_called_once()
        mock_film.assert_called_once()
        mock_grain.assert_called_once()

    def test_default_level_is_minimal(self):
        """Default level should be 'minimal'."""
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        with patch("musicvid.pipeline.effects.apply_warm_grade", return_value=mock_clip) as mock_warm, \
             patch("musicvid.pipeline.effects.apply_vignette", return_value=mock_clip), \
             patch("musicvid.pipeline.effects.apply_subtle_film_look", return_value=mock_clip):
            apply_effects(mock_clip)
            mock_warm.assert_called_once()


class TestApplySubtleFilmLook:
    """Tests for subtle film look (desaturation + grain)."""

    def test_reduces_saturation(self):
        """Output should have lower saturation than fully saturated input."""
        # Create a purely red frame (max saturation)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[:, :, 0] = 200  # R
        frame[:, :, 1] = 50   # G
        frame[:, :, 2] = 50   # B

        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_subtle_film_look(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame.copy()

        np.random.seed(42)
        output = transform_fn(get_frame, 0)

        # Saturation = chroma / max. After desaturation, R-G gap should shrink
        orig_chroma = int(frame[0, 0, 0]) - int(frame[0, 0, 1])  # 150
        out_chroma = int(output[0, 0, 0]) - int(output[0, 0, 1])
        assert out_chroma < orig_chroma, (
            f"Output chroma {out_chroma} should be less than input chroma {orig_chroma}"
        )

    def test_desaturation_is_subtle(self):
        """Only ~8% saturation reduction — channels should stay close to original."""
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        frame[:, :, 0] = 200  # skew red channel

        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_subtle_film_look(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame.copy()

        np.random.seed(42)
        output = transform_fn(get_frame, 0)

        # Mean pixel value should be close to original (within 15 per channel)
        diff = np.abs(output.astype(int) - frame.astype(int))
        assert diff.mean() < 15, f"Film look too aggressive: mean diff {diff.mean()}"

    def test_returns_clip(self):
        """apply_subtle_film_look returns a clip (result of clip.transform)."""
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        result = apply_subtle_film_look(mock_clip)

        assert result is mock_clip
        mock_clip.transform.assert_called_once()


class TestApplyEffectsWithFilmLook:
    """Tests that apply_effects includes subtle_film_look for minimal and full."""

    @patch("musicvid.pipeline.effects.apply_subtle_film_look")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_minimal_applies_film_look(self, mock_warm, mock_vignette, mock_film):
        """Level 'minimal' applies warm grade, vignette, and subtle film look."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip
        mock_film.return_value = mock_clip

        apply_effects(mock_clip, level="minimal")

        mock_warm.assert_called_once()
        mock_vignette.assert_called_once()
        mock_film.assert_called_once()

    @patch("musicvid.pipeline.effects.apply_film_grain")
    @patch("musicvid.pipeline.effects.apply_subtle_film_look")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_full_applies_film_look_and_grain(self, mock_warm, mock_vignette, mock_film, mock_grain):
        """Level 'full' applies all including subtle film look and film grain."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip
        mock_film.return_value = mock_clip
        mock_grain.return_value = mock_clip

        apply_effects(mock_clip, level="full")

        mock_warm.assert_called_once()
        mock_vignette.assert_called_once()
        mock_film.assert_called_once()
        mock_grain.assert_called_once()

    @patch("musicvid.pipeline.effects.apply_subtle_film_look")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_none_skips_film_look(self, mock_warm, mock_vignette, mock_film):
        """Level 'none' does not apply subtle film look."""
        mock_clip = MagicMock()

        apply_effects(mock_clip, level="none")

        mock_film.assert_not_called()
        mock_warm.assert_not_called()
