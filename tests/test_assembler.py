"""Tests for assembler module."""

import json
import unittest
from unittest.mock import patch, MagicMock, call
from pathlib import Path

import pytest
import numpy as np

from musicvid.pipeline.assembler import (
    assemble_video,
    _create_ken_burns_clip,
    _create_subtitle_clips,
    _get_resolution,
)


class TestGetResolution:
    """Tests for resolution mapping."""

    def test_720p(self):
        assert _get_resolution("720p") == (1280, 720)

    def test_1080p(self):
        assert _get_resolution("1080p") == (1920, 1080)

    def test_4k(self):
        assert _get_resolution("4k") == (3840, 2160)

    def test_default(self):
        assert _get_resolution("unknown") == (1920, 1080)


class TestCreateSubtitleClips:
    """Tests for subtitle clip generation."""

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_creates_clips_for_lyrics(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        subtitle_style = sample_scene_plan["subtitle_style"]
        clips = _create_subtitle_clips(
            sample_analysis["lyrics"],
            subtitle_style,
            (1920, 1080),
        )
        assert len(clips) == len(sample_analysis["lyrics"])

    @patch("musicvid.pipeline.assembler.TextClip")
    def test_empty_lyrics(self, mock_text_clip, sample_scene_plan):
        subtitle_style = sample_scene_plan["subtitle_style"]
        clips = _create_subtitle_clips([], subtitle_style, (1920, 1080))
        assert len(clips) == 0

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_uses_provided_font_path(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        subtitle_style = sample_scene_plan["subtitle_style"]
        _create_subtitle_clips(
            sample_analysis["lyrics"],
            subtitle_style,
            (1920, 1080),
            font_path="/custom/font.ttf",
        )

        call_kwargs = mock_text_clip.call_args[1]
        assert call_kwargs["font"] == "/custom/font.ttf"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_subtitle_predisplay_offset(self, mock_text_clip, mock_vfx):
        """Subtitle clips start 0.1s before segment start, duration extended."""
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        lyrics = [{"start": 5.0, "end": 6.5, "text": "Hello"}]
        subtitle_style = {"font_size": 48, "color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, subtitle_style, (1920, 1080))

        # Should start 0.1s earlier: 5.0 - 0.1 = 4.9
        mock_clip.with_start.assert_called_once_with(4.9)
        # Duration: 1.5 + 0.1 = 1.6s
        mock_clip.with_duration.assert_called_once_with(pytest.approx(1.6, abs=0.001))


class TestAssembleVideo:
    """Tests for the main assemble_video function."""

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_produces_output_file(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip, mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
            {"scene_index": 1, "video_path": "/fake/scene_001.mp4", "search_query": "test"},
            {"scene_index": 2, "video_path": "/fake/scene_002.png", "search_query": "test"},
        ]

        output_file = str(tmp_output / "output.mp4")

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            resolution="1080p",
        )

        mock_clip.write_videofile.assert_called_once()
        call_args = mock_clip.write_videofile.call_args
        assert output_file in str(call_args)

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_passes_font_path_to_subtitles(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip, mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
            {"scene_index": 1, "video_path": "/fake/scene_001.mp4", "search_query": "test"},
            {"scene_index": 2, "video_path": "/fake/scene_002.png", "search_query": "test"},
        ]

        output_file = str(tmp_output / "output.mp4")

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            resolution="1080p",
            font_path="/custom/font.ttf",
        )

        call_kwargs = mock_text.call_args[1]
        assert call_kwargs["font"] == "/custom/font.ttf"


class TestAssembleVideoEffects:
    """Tests for visual effects integration in assembler."""

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_minimal_effects_applied(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip, mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
            {"scene_index": 1, "video_path": "/fake/scene_001.mp4", "search_query": "test"},
            {"scene_index": 2, "video_path": "/fake/scene_002.png", "search_query": "test"},
        ]

        output_file = str(tmp_output / "output.mp4")

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            resolution="1080p",
            effects_level="minimal",
        )

        mock_apply_effects.assert_called()
        mock_bars.assert_not_called()

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_none_effects_skip_all(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
            {"scene_index": 1, "video_path": "/fake/scene_001.mp4", "search_query": "test"},
            {"scene_index": 2, "video_path": "/fake/scene_002.png", "search_query": "test"},
        ]

        output_file = str(tmp_output / "output.mp4")

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            resolution="1080p",
            effects_level="none",
        )

        mock_apply_effects.assert_called()
        # Verify "none" was passed
        first_call_args = mock_apply_effects.call_args_list[0]
        assert first_call_args[1]["level"] == "none"
        mock_bars.assert_not_called()
        mock_light_leak.assert_not_called()

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_cinematic_bars_enabled_when_flag_true(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip
        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip, mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=str(tmp_output / "output.mp4"),
            resolution="1080p",
            effects_level="full",
            cinematic_bars=True,
        )

        mock_bars.assert_called_once()


class TestAssembleVideoClipMode:
    """Tests for clip mode (clip_start/clip_end, fades, title card, portrait resolution)."""

    def _make_mock_clip(self):
        mock_clip = MagicMock()
        mock_clip.duration = 15.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_end.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip
        return mock_clip

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_clip_mode_trims_audio(
        self, mock_concat, mock_composite, mock_text, mock_audio_cls,
        mock_image, mock_video, mock_vfx, mock_afx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = self._make_mock_clip()
        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio_cls.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=str(tmp_output / "output.mp4"),
            resolution="1080p",
            clip_start=45.0,
            clip_end=60.0,
        )

        mock_clip.subclipped.assert_called_with(45.0, 60.0)

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_clip_mode_applies_audio_fades(
        self, mock_concat, mock_composite, mock_text, mock_audio_cls,
        mock_image, mock_video, mock_vfx, mock_afx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = self._make_mock_clip()
        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio_cls.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=str(tmp_output / "output.mp4"),
            resolution="1080p",
            clip_start=45.0,
            clip_end=60.0,
        )

        mock_afx.AudioFadeIn.assert_called_with(0.5)
        mock_afx.AudioFadeOut.assert_called_with(1.0)

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_clip_mode_applies_video_fades(
        self, mock_concat, mock_composite, mock_text, mock_audio_cls,
        mock_image, mock_video, mock_vfx, mock_afx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = self._make_mock_clip()
        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio_cls.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=str(tmp_output / "output.mp4"),
            resolution="1080p",
            clip_start=45.0,
            clip_end=60.0,
        )

        mock_vfx.FadeIn.assert_called_with(0.5)
        mock_vfx.FadeOut.assert_called_with(1.0)

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    @patch("musicvid.pipeline.assembler.ColorClip")
    def test_clip_mode_title_card_prepended(
        self, mock_color_clip, mock_concat, mock_composite, mock_text, mock_audio_cls,
        mock_image, mock_video, mock_vfx, mock_afx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = self._make_mock_clip()
        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio_cls.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_color_clip.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=str(tmp_output / "output.mp4"),
            resolution="1080p",
            clip_start=45.0,
            clip_end=60.0,
            title_card_text="My Song",
        )

        # Title card text should appear in a TextClip call
        text_calls = [str(c) for c in mock_text.call_args_list]
        assert any("My Song" in c for c in text_calls)

    def test_portrait_resolution_maps_correctly(self):
        from musicvid.pipeline.assembler import _get_resolution
        w, h = _get_resolution("portrait")
        assert w == 1080
        assert h == 1920


class TestLoadSceneClipAnimated:
    """Tests that animated scenes skip Ken Burns and use VideoFileClip resized."""

    @patch("musicvid.pipeline.assembler.VideoFileClip")
    def test_animated_scene_skips_ken_burns(self, mock_vfc, tmp_path):
        from musicvid.pipeline.assembler import _load_scene_clip

        # Create a fake .mp4 file
        fake_mp4 = tmp_path / "animated.mp4"
        fake_mp4.write_bytes(b"fake video")

        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_vfc.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in", "animate": True}
        result = _load_scene_clip(str(fake_mp4), scene, (1920, 1080))

        # resized should be called to fit target_size
        mock_clip.resized.assert_called_once_with(new_size=(1920, 1080))
        # transform (Ken Burns) should NOT be called
        mock_clip.transform.assert_not_called()

    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_non_animated_image_uses_ken_burns(self, mock_ic, tmp_path):
        from musicvid.pipeline.assembler import _load_scene_clip

        fake_jpg = tmp_path / "scene.jpg"
        fake_jpg.write_bytes(b"fake jpeg")

        mock_clip = MagicMock()
        mock_clip.duration = None
        mock_ic.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.cropped.return_value = mock_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in", "animate": False}
        _load_scene_clip(str(fake_jpg), scene, (1920, 1080))

        # transform (Ken Burns) SHOULD be called
        mock_clip.transform.assert_called()

    @patch("musicvid.pipeline.assembler.VideoFileClip")
    def test_non_animated_mp4_skips_ken_burns(self, mock_vfc, tmp_path):
        """Non-animated .mp4 (stock video) should skip Ken Burns — video already has motion."""
        from musicvid.pipeline.assembler import _load_scene_clip

        fake_mp4 = tmp_path / "stock.mp4"
        fake_mp4.write_bytes(b"fake video")

        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_vfc.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.cropped.return_value = mock_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in", "animate": False}
        _load_scene_clip(str(fake_mp4), scene, (1920, 1080))

        # Ken Burns (transform) should NOT be called — .mp4 already has motion
        mock_clip.transform.assert_not_called()
        # Should just resize
        mock_clip.resized.assert_called()


class TestLoadSceneClipSmartCrop(unittest.TestCase):
    """Tests that _load_scene_clip uses smart crop for portrait images."""

    def setUp(self):
        self.scene = {
            "start": 0.0,
            "end": 5.0,
            "motion": "pan_up",
            "animate": False,
            "transition": "crossfade",
        }
        self.portrait_size = (1080, 1920)

    @patch("musicvid.pipeline.assembler.convert_for_platform")
    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_portrait_image_calls_convert_for_platform(self, mock_ImageClip, mock_convert):
        mock_convert.return_value = "/fake/smart_scene.jpg"
        mock_clip = MagicMock()
        mock_clip.size = (1080, 1920)
        mock_clip.w = 1080
        mock_clip.h = 1920
        mock_clip.cropped.return_value = mock_clip
        mock_ImageClip.return_value = mock_clip

        from musicvid.pipeline.assembler import _load_scene_clip
        _load_scene_clip("/fake/scene.jpg", self.scene, self.portrait_size, reels_style="blur-bg")

        mock_convert.assert_called_once_with("/fake/scene.jpg", "reels", style="blur-bg")
        mock_ImageClip.assert_called_once_with("/fake/smart_scene.jpg")

    @patch("musicvid.pipeline.assembler.convert_for_platform")
    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_portrait_image_uses_crop_style_when_specified(self, mock_ImageClip, mock_convert):
        mock_convert.return_value = "/fake/smart_scene.jpg"
        mock_clip = MagicMock()
        mock_clip.size = (1080, 1920)
        mock_clip.w = 1080
        mock_clip.h = 1920
        mock_clip.cropped.return_value = mock_clip
        mock_ImageClip.return_value = mock_clip

        from musicvid.pipeline.assembler import _load_scene_clip
        _load_scene_clip("/fake/scene.jpg", self.scene, self.portrait_size, reels_style="crop")

        mock_convert.assert_called_once_with("/fake/scene.jpg", "reels", style="crop")

    @patch("musicvid.pipeline.assembler.convert_for_platform")
    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_landscape_image_does_not_call_convert_for_platform(self, mock_ImageClip, mock_convert):
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.cropped.return_value = mock_clip
        mock_ImageClip.return_value = mock_clip

        from musicvid.pipeline.assembler import _load_scene_clip
        _load_scene_clip("/fake/scene.jpg", self.scene, (1920, 1080), reels_style="blur-bg")

        mock_convert.assert_not_called()


class TestPortraitKenBurns:
    """Tests for portrait-mode Ken Burns restrictions."""

    def test_pan_up_calls_transform(self):
        from musicvid.pipeline.assembler import _create_ken_burns_clip
        from unittest.mock import MagicMock

        mock_clip = MagicMock()
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.size = (1080, 1920)
        mock_clip.w = 1080
        mock_clip.h = 1920
        mock_clip.cropped.return_value = mock_clip

        result = _create_ken_burns_clip(mock_clip, 5.0, "pan_up", (1080, 1920))

        mock_clip.transform.assert_called_once()

    def test_pan_down_calls_transform(self):
        from musicvid.pipeline.assembler import _create_ken_burns_clip
        from unittest.mock import MagicMock

        mock_clip = MagicMock()
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.size = (1080, 1920)
        mock_clip.w = 1080
        mock_clip.h = 1920
        mock_clip.cropped.return_value = mock_clip

        result = _create_ken_burns_clip(mock_clip, 5.0, "pan_down", (1080, 1920))

        mock_clip.transform.assert_called_once()

    def test_remap_motion_for_portrait_replaces_horizontal(self):
        from musicvid.pipeline.assembler import _remap_motion_for_portrait

        assert _remap_motion_for_portrait("pan_left") == "pan_up"
        assert _remap_motion_for_portrait("pan_right") == "pan_down"
        assert _remap_motion_for_portrait("slow_zoom_in") == "slow_zoom_in"
        assert _remap_motion_for_portrait("slow_zoom_out") == "slow_zoom_out"
        assert _remap_motion_for_portrait("static") == "static"


class TestAssembleVideoLogo:
    """Tests for logo overlay integration in assembler."""

    @patch("musicvid.pipeline.assembler.apply_logo")
    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_logo_overlay_added_as_last_layer(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars, mock_apply_logo,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip, mock_clip]

        mock_logo_clip = MagicMock()
        mock_apply_logo.return_value = mock_logo_clip

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]
        output_file = str(tmp_output / "output.mp4")

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            logo_path="/fake/logo.png",
            logo_position="top-left",
            logo_size=None,
            logo_opacity=0.85,
        )

        mock_apply_logo.assert_called_once_with(
            mock_clip, "/fake/logo.png", "top-left", None, 0.85
        )
        # Logo should be in layers passed to CompositeVideoClip
        composite_call = mock_composite.call_args
        layers = composite_call[0][0]
        assert mock_logo_clip in layers

    @patch("musicvid.pipeline.assembler.apply_logo")
    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_no_logo_when_path_is_none(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars, mock_apply_logo,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip, mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]
        output_file = str(tmp_output / "output.mp4")

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
        )

        mock_apply_logo.assert_not_called()

class TestAssembleVideoLut:
    @patch("musicvid.pipeline.assembler.apply_logo")
    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    @patch("musicvid.pipeline.assembler.prepare_lut_ffmpeg_params")
    def test_lut_params_passed_to_write_videofile(
        self, mock_prepare_lut, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars, mock_apply_logo,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_end.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_video.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = []
        mock_prepare_lut.return_value = ["-vf", "lut3d='/tmp/test.cube':interp=trilinear"]

        output_file = str(tmp_output / "test_lut.mp4")
        manifest = [{"scene_index": 0, "video_path": "/fake/vid.mp4", "search_query": "test"}]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            lut_style="warm",
            lut_intensity=0.85,
        )

        mock_prepare_lut.assert_called_once_with(
            lut_path=None, lut_style="warm", intensity=0.85
        )
        call_kwargs = mock_clip.write_videofile.call_args[1]
        assert "ffmpeg_params" in call_kwargs
        assert "lut3d" in str(call_kwargs["ffmpeg_params"])

    @patch("musicvid.pipeline.assembler.apply_logo")
    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    @patch("musicvid.pipeline.assembler.prepare_lut_ffmpeg_params")
    def test_no_lut_means_no_ffmpeg_params(
        self, mock_prepare_lut, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars, mock_apply_logo,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_end.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_video.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = []
        mock_prepare_lut.return_value = []

        output_file = str(tmp_output / "test_no_lut.mp4")
        manifest = [{"scene_index": 0, "video_path": "/fake/vid.mp4", "search_query": "test"}]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
        )

        call_kwargs = mock_clip.write_videofile.call_args[1]
        if "ffmpeg_params" in call_kwargs:
            assert "lut3d" not in str(call_kwargs["ffmpeg_params"])


class TestKenBurnsCoverScale:
    """Tests that _create_ken_burns_clip uses cover scaling (not stretch)."""

    def test_cover_scale_fills_frame_preserving_aspect_ratio(self):
        """4:3 image into 16:9 frame: must scale up and crop, not stretch."""
        from musicvid.pipeline.assembler import _create_ken_burns_clip
        from unittest.mock import MagicMock

        # Simulate a 1024x768 BFL image (4:3 ratio)
        mock_clip = MagicMock()
        mock_clip.size = (1024, 768)
        mock_clip.w = 1024
        mock_clip.h = 768
        mock_clip.resized.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        target_size = (1920, 1080)
        _create_ken_burns_clip(mock_clip, 5.0, "slow_zoom_in", target_size)

        # Cover scale: resized() must be called with a scalar float, not a tuple
        resized_call = mock_clip.resized.call_args
        assert resized_call is not None
        args, kwargs = resized_call
        if args:
            scale_arg = args[0]
        else:
            scale_arg = kwargs.get("new_size", None)
        assert not isinstance(scale_arg, tuple), (
            f"resized() was called with tuple {scale_arg!r} (stretch), "
            "expected scalar (cover scale)"
        )

        # cropped must be called to trim the overflow
        mock_clip.cropped.assert_called_once()


class TestCreateKenBurnsClip:
    """Tests for new motion types in _create_ken_burns_clip."""

    def test_diagonal_drift_returns_clip(self):
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        result = _create_ken_burns_clip(mock_clip, 10.0, motion="diagonal_drift")
        mock_clip.transform.assert_called_once()

    def test_cut_zoom_returns_clip(self):
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        result = _create_ken_burns_clip(mock_clip, 5.0, motion="cut_zoom")
        mock_clip.transform.assert_called_once()


class TestSubtitleErrorHandling:
    """Tests for subtitle creation error handling."""

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_textclip_error_skips_segment_without_crash(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
        """If TextClip raises, the segment is skipped and other segments still render."""
        mock_good_clip = MagicMock()
        mock_good_clip.with_duration.return_value = mock_good_clip
        mock_good_clip.with_start.return_value = mock_good_clip
        mock_good_clip.with_position.return_value = mock_good_clip
        mock_good_clip.with_effects.return_value = mock_good_clip

        # First segment raises, second succeeds
        mock_text_clip.side_effect = [Exception("ImageMagick failed"), mock_good_clip]

        subtitle_style = sample_scene_plan["subtitle_style"]
        clips = _create_subtitle_clips(
            sample_analysis["lyrics"],
            subtitle_style,
            (1920, 1080),
        )
        # Should get 1 clip (second segment), not crash
        assert len(clips) == 1

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_empty_lyrics_returns_no_clips(self, mock_text_clip, mock_vfx, sample_scene_plan):
        """Empty lyrics list produces no clips and does not crash."""
        subtitle_style = sample_scene_plan["subtitle_style"]
        clips = _create_subtitle_clips([], subtitle_style, (1920, 1080))
        assert len(clips) == 0
        mock_text_clip.assert_not_called()

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_subtitle_position_within_frame(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
        """Subtitle y-position must be less than frame height."""
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        subtitle_style = sample_scene_plan["subtitle_style"]
        frame_h = 1080
        margin_bottom = 80
        font_size = subtitle_style.get("font_size", 58)
        _create_subtitle_clips(
            sample_analysis["lyrics"],
            subtitle_style,
            (1920, frame_h),
            subtitle_margin_bottom=margin_bottom,
        )

        # Check with_position was called with y < frame_h
        pos_call = mock_clip.with_position.call_args
        assert pos_call is not None
        args, kwargs = pos_call
        # Position is ("center", y_value)
        y_value = args[0][1]
        assert y_value < frame_h, f"Subtitle y={y_value} is outside frame height={frame_h}"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_textclip_height_includes_descender_padding(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
        """TextClip height must be font_size + 35% to accommodate descenders."""
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        subtitle_style = {"font_size": 58, "color": "#FFFFFF", "outline_color": "#000000"}
        _create_subtitle_clips(
            sample_analysis["lyrics"],
            subtitle_style,
            (1920, 1080),
        )

        call_kwargs = mock_text_clip.call_args_list[0][1]
        w, h = call_kwargs["size"]
        font_size = 58
        expected_h = font_size + int(font_size * 0.35)
        assert h == expected_h, f"Expected TextClip height={expected_h}, got {h}"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_subtitle_y_pos_accounts_for_descender_padding(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
        """Subtitle bottom edge (y_pos + padded_height) equals frame_h - margin_bottom."""
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        font_size = 58
        frame_h = 1080
        margin_bottom = 80
        subtitle_style = {"font_size": font_size, "color": "#FFFFFF", "outline_color": "#000000"}
        _create_subtitle_clips(
            sample_analysis["lyrics"],
            subtitle_style,
            (1920, frame_h),
            subtitle_margin_bottom=margin_bottom,
        )

        pos_call = mock_clip.with_position.call_args_list[0]
        args, _ = pos_call
        y_pos = args[0][1]
        padded_h = font_size + int(font_size * 0.35)
        assert y_pos + padded_h == frame_h - margin_bottom, (
            f"Expected y_pos + padded_h = {frame_h - margin_bottom}, got {y_pos + padded_h}"
        )


from musicvid.pipeline.assembler import _concatenate_with_transitions


class TestConcatenateWithTransitions:
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_all_cuts_uses_concatenate_videoclips(self, mock_concat):
        mock_concat.return_value = MagicMock()
        mock_clip = MagicMock()
        mock_clip.duration = 10.0
        scenes = [
            {"section": "verse", "transition_to_next": "cut"},
            {"section": "chorus"},
        ]
        _concatenate_with_transitions([mock_clip, mock_clip], scenes, bpm=84.0, target_size=(1920, 1080))
        mock_concat.assert_called_once()

    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_cross_dissolve_uses_composite(self, mock_vfx, mock_composite):
        mock_clip = MagicMock()
        mock_clip.duration = 10.0
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_composite.return_value = MagicMock()
        scenes = [
            {"section": "intro", "transition_to_next": "cross_dissolve"},
            {"section": "verse"},
        ]
        _concatenate_with_transitions([mock_clip, mock_clip], scenes, bpm=84.0, target_size=(1920, 1080))
        mock_composite.assert_called_once()

    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.ColorClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_dip_white_flash_position_accounts_for_dissolve_overlap(self, mock_vfx, mock_colorclip, mock_composite):
        """dip_white flash cursor must subtract cross_dissolve overlap from preceding clip."""
        mock_clip = MagicMock()
        mock_clip.duration = 10.0
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_colorclip_instance = MagicMock()
        mock_colorclip_instance.with_start.return_value = mock_colorclip_instance
        mock_colorclip_instance.with_effects.return_value = mock_colorclip_instance
        mock_colorclip.return_value = mock_colorclip_instance
        mock_composite.return_value = MagicMock()

        # clip 0 -> cross_dissolve (d≈0.36s at 84bpm) -> clip 1 -> dip_white -> clip 2
        scenes = [
            {"section": "intro", "transition_to_next": "cross_dissolve"},
            {"section": "chorus", "transition_to_next": "dip_white"},
            {"section": "verse"},
        ]
        _concatenate_with_transitions([mock_clip, mock_clip, mock_clip], scenes, bpm=84.0, target_size=(1920, 1080))

        # flash should be created (dip_white triggered)
        mock_colorclip.assert_called_once()
        # The with_start position should be approximately: (10 - dissolve_d) + 10 - dip_d/2
        # which is LESS than the naive 20.0 - dip_d/2
        call_args = mock_colorclip_instance.with_start.call_args
        actual_start = call_args[0][0]
        # dissolve_d = max(0.2, min(0.8, round(60/84/2, 2))) ≈ 0.36
        # naive start = 20.0 - dip_d/2; corrected start = (10-0.36+10) - dip_d/2 = 19.64 - dip_d/2
        assert actual_start < 19.5, f"Flash start {actual_start} should be < 19.5 (naive would be ~19.6, with overlap correction < that)"


class TestConvert16To9_16:
    """Tests for convert_16_9_to_9_16."""

    def test_output_dimensions(self):
        from musicvid.pipeline.assembler import convert_16_9_to_9_16

        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        resized_clip = MagicMock()
        resized_clip.size = (3413, 1920)
        mock_clip.resized.return_value = resized_clip
        cropped_clip = MagicMock()
        resized_clip.cropped.return_value = cropped_clip

        result = convert_16_9_to_9_16(mock_clip, target_w=1080, target_h=1920)

        mock_clip.resized.assert_called_once()
        args = mock_clip.resized.call_args[0]
        new_w, new_h = args[0]
        assert new_h == 1920
        assert new_w == int(1920 * 1920 / 1080)  # 3413

        resized_clip.cropped.assert_called_once()
        ckwargs = resized_clip.cropped.call_args[1]
        assert ckwargs["x1"] == (3413 - 1080) // 2
        assert ckwargs["x2"] == (3413 - 1080) // 2 + 1080
        assert ckwargs["y1"] == 0
        assert ckwargs["y2"] == 1920

    def test_does_not_stretch(self):
        """Result must not resize directly to target dimensions (that stretches)."""
        from musicvid.pipeline.assembler import convert_16_9_to_9_16

        mock_clip = MagicMock()
        mock_clip.size = (1280, 720)
        scale = 1920 / 720
        new_w = int(1280 * scale)
        resized_clip = MagicMock()
        resized_clip.size = (new_w, 1920)
        mock_clip.resized.return_value = resized_clip
        cropped_clip = MagicMock()
        resized_clip.cropped.return_value = cropped_clip

        convert_16_9_to_9_16(mock_clip, target_w=1080, target_h=1920)

        call_args = mock_clip.resized.call_args[0]
        w, h = call_args[0]
        assert not (w == 1080 and h == 1920), "Should not resize directly to 1080x1920"


class TestLoadSceneClipNonePath:
    """Tests that _load_scene_clip raises for None path."""

    def test_none_path_raises(self):
        from musicvid.pipeline.assembler import _load_scene_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in"}
        with pytest.raises((ValueError, TypeError)):
            _load_scene_clip(None, scene, (1080, 1920))


class TestLoadSceneClipPortraitMp4:
    """Tests that _load_scene_clip uses crop (not stretch) for portrait .mp4."""

    @patch("musicvid.pipeline.assembler.VideoFileClip")
    def test_portrait_mp4_uses_convert_not_resize(self, mock_vfc, tmp_path):
        from musicvid.pipeline.assembler import _load_scene_clip

        fake_mp4 = tmp_path / "scene.mp4"
        fake_mp4.write_bytes(b"fake video")

        mock_clip = MagicMock()
        mock_clip.duration = 10.0
        mock_clip.size = (1920, 1080)
        mock_clip.subclipped.return_value = mock_clip
        resized_clip = MagicMock()
        resized_clip.size = (3413, 1920)
        mock_clip.resized.return_value = resized_clip
        cropped_clip = MagicMock()
        resized_clip.cropped.return_value = cropped_clip
        mock_vfc.return_value = mock_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in"}
        _load_scene_clip(str(fake_mp4), scene, (1080, 1920))

        # resized must NOT be called with new_size=(1080, 1920) — that stretches
        for call in mock_clip.resized.call_args_list:
            kw = call[1]
            if "new_size" in kw:
                assert kw["new_size"] != (1080, 1920), \
                    "resized(new_size=(1080,1920)) stretches video — use convert_16_9_to_9_16"


class TestAssembleVideoWowConfig(unittest.TestCase):
    """Tests for wow_config integration in assemble_video."""

    def _make_scene_plan(self):
        return {
            "overall_style": "worship",
            "subtitle_style": {"font_size": 54, "color": "#FFFFFF",
                               "outline_color": "#000000",
                               "position": "bottom", "animation": "fade"},
            "scenes": [
                {
                    "section": "chorus", "start": 0.0, "end": 5.0,
                    "visual_source": "TYPE_VIDEO_STOCK",
                    "motion": "slow_zoom_in", "transition": "cut",
                    "transition_to_next": "cut", "lyrics_in_scene": [],
                    "search_query": "nature", "visual_prompt": "",
                    "motion_prompt": "", "animate": False, "overlay": "none",
                }
            ],
        }

    def _make_analysis(self):
        return {
            "lyrics": [], "beats": [1.0, 2.0], "bpm": 120.0,
            "duration": 5.0,
            "sections": [{"label": "chorus", "start": 0.0, "end": 5.0}],
            "energy_peaks": [],
        }

    def _make_manifest(self):
        return [{"scene_index": 0, "video_path": "/fake/scene.mp4",
                 "start": 0.0, "end": 5.0, "source": "stock"}]

    @patch("pathlib.Path.mkdir")
    @patch("musicvid.pipeline.assembler.apply_wow_effects")
    @patch("musicvid.pipeline.assembler.prepare_lut_ffmpeg_params", return_value=[])
    @patch("musicvid.pipeline.assembler._create_subtitle_clips", return_value=[])
    @patch("musicvid.pipeline.assembler._concatenate_with_transitions")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    def test_wow_effects_called_when_wow_config_provided(
        self, mock_vfc, mock_afc, mock_comp, mock_effects,
        mock_concat, mock_subtitles, mock_lut, mock_wow, mock_mkdir
    ):
        from musicvid.pipeline.assembler import assemble_video

        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.duration = 5.0
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_vfc.return_value = mock_clip
        mock_effects.return_value = mock_clip
        mock_concat.return_value = mock_clip

        mock_final = MagicMock()
        mock_final.duration = 5.0
        mock_final.with_audio.return_value = mock_final
        mock_final.with_duration.return_value = mock_final
        mock_comp.return_value = mock_final

        mock_audio = MagicMock()
        mock_audio.duration = 5.0
        mock_afc.return_value = mock_audio

        wow_config = {
            "enabled": True, "zoom_punch": True, "light_flash": True,
            "dynamic_grade": True, "dynamic_vignette": True,
            "motion_blur": False, "particles": False,
        }

        assemble_video(
            analysis=self._make_analysis(),
            scene_plan=self._make_scene_plan(),
            fetch_manifest=self._make_manifest(),
            audio_path="/fake/audio.mp3",
            output_path="/fake/output.mp4",
            wow_config=wow_config,
        )

        mock_wow.assert_called_once()
        call_kwargs = mock_wow.call_args[1]
        self.assertEqual(call_kwargs["video_path"], "/fake/output.mp4")
        self.assertEqual(call_kwargs["video_width"], 1920)
        self.assertEqual(call_kwargs["video_height"], 1080)

    @patch("pathlib.Path.mkdir")
    @patch("musicvid.pipeline.assembler.apply_wow_effects")
    @patch("musicvid.pipeline.assembler.prepare_lut_ffmpeg_params", return_value=[])
    @patch("musicvid.pipeline.assembler._create_subtitle_clips", return_value=[])
    @patch("musicvid.pipeline.assembler._concatenate_with_transitions")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    def test_wow_effects_not_called_when_wow_config_is_none(
        self, mock_vfc, mock_afc, mock_comp, mock_effects,
        mock_concat, mock_subtitles, mock_lut, mock_wow, mock_mkdir
    ):
        from musicvid.pipeline.assembler import assemble_video

        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.duration = 5.0
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_vfc.return_value = mock_clip
        mock_effects.return_value = mock_clip
        mock_concat.return_value = mock_clip

        mock_final = MagicMock()
        mock_final.duration = 5.0
        mock_final.with_audio.return_value = mock_final
        mock_final.with_duration.return_value = mock_final
        mock_comp.return_value = mock_final

        mock_audio = MagicMock()
        mock_audio.duration = 5.0
        mock_afc.return_value = mock_audio

        assemble_video(
            analysis=self._make_analysis(),
            scene_plan=self._make_scene_plan(),
            fetch_manifest=self._make_manifest(),
            audio_path="/fake/audio.mp3",
            output_path="/fake/output.mp4",
            wow_config=None,
        )

        mock_wow.assert_not_called()


class TestScalePopSubtitles(unittest.TestCase):
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_chorus_subtitle_gets_transform(self, mock_vfx, mock_textclip):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.duration = 2.0
        mock_clip.w = 400
        mock_clip.h = 80
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 10.0, "end": 12.0, "text": "Chwała", "words": []}]
        subtitle_style = {"font_size": 64, "color": "#FFFFFF",
                          "outline_color": "#000000",
                          "position": "bottom", "animation": "fade"}
        sections = [{"label": "chorus", "start": 8.0, "end": 20.0}]

        _create_subtitle_clips(lyrics, subtitle_style, (1920, 1080),
                               sections=sections)

        mock_clip.transform.assert_called_once()

    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_verse_subtitle_has_no_scale_pop(self, mock_vfx, mock_textclip):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.duration = 2.0
        mock_clip.w = 400
        mock_clip.h = 80
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 5.0, "end": 7.0, "text": "Bóg jest dobry", "words": []}]
        subtitle_style = {"font_size": 54, "color": "#FFFFFF",
                          "outline_color": "#000000",
                          "position": "bottom", "animation": "fade"}
        sections = [{"label": "verse", "start": 0.0, "end": 20.0}]

        _create_subtitle_clips(lyrics, subtitle_style, (1920, 1080),
                               sections=sections)

        mock_clip.transform.assert_not_called()


class TestReelsSubtitleFontSize(unittest.TestCase):
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_chorus_font_size_72_in_reels_mode(self, mock_vfx, mock_textclip):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.duration = 2.0
        mock_clip.w = 400
        mock_clip.h = 80
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 10.0, "end": 12.0, "text": "Alleluja", "words": []}]
        subtitle_style = {"font_size": 54, "color": "#FFFFFF",
                          "outline_color": "#000000",
                          "position": "bottom", "animation": "fade"}
        sections = [{"label": "chorus", "start": 8.0, "end": 20.0}]

        _create_subtitle_clips(lyrics, subtitle_style, (1080, 1920),
                               sections=sections, reels_mode=True)

        call_kwargs = mock_textclip.call_args[1]
        self.assertEqual(call_kwargs.get("font_size"), 72)

    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_chorus_font_size_unchanged_when_not_reels(self, mock_vfx, mock_textclip):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.duration = 2.0
        mock_clip.w = 400
        mock_clip.h = 80
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 10.0, "end": 12.0, "text": "Alleluja", "words": []}]
        subtitle_style = {"font_size": 54, "color": "#FFFFFF",
                          "outline_color": "#000000",
                          "position": "bottom", "animation": "fade"}
        sections = [{"label": "chorus", "start": 8.0, "end": 20.0}]

        _create_subtitle_clips(lyrics, subtitle_style, (1920, 1080),
                               sections=sections, reels_mode=False)

        call_kwargs = mock_textclip.call_args[1]
        # Should be 64 (chorus size from _SECTION_FONT_SIZES), not 72
        self.assertEqual(call_kwargs.get("font_size"), 64)


class TestReelsGradientOverlay(unittest.TestCase):
    def test_create_bottom_gradient_returns_clip(self):
        from musicvid.pipeline.assembler import _create_bottom_gradient

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_mask.return_value = mock_clip

        with patch("musicvid.pipeline.assembler.ImageClip", return_value=mock_clip):
            clip = _create_bottom_gradient(width=1080, height=1920, duration=5.0)

        self.assertIsNotNone(clip)
        mock_clip.with_duration.assert_called_with(5.0)

    def test_create_bottom_gradient_gradient_height(self):
        """Gradient height should be 30% of frame height by default."""
        import numpy as np
        from musicvid.pipeline.assembler import _create_bottom_gradient

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_mask.return_value = mock_clip

        captured_arrays = []

        def capture_imageclip(arr, **kwargs):
            captured_arrays.append(arr)
            return mock_clip

        with patch("musicvid.pipeline.assembler.ImageClip", side_effect=capture_imageclip):
            _create_bottom_gradient(width=1080, height=1920, duration=5.0)

        # First call is the black frame — height should be 30% of 1920 = 576
        self.assertTrue(len(captured_arrays) > 0)
        expected_grad_h = int(1920 * 0.3)
        self.assertEqual(captured_arrays[0].shape[0], expected_grad_h)

    def test_create_bottom_gradient_position(self):
        """Gradient should be positioned at the bottom of the frame."""
        from musicvid.pipeline.assembler import _create_bottom_gradient

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_mask.return_value = mock_clip

        with patch("musicvid.pipeline.assembler.ImageClip", return_value=mock_clip):
            _create_bottom_gradient(width=1080, height=1920, duration=5.0)

        grad_h = int(1920 * 0.3)
        mock_clip.with_position.assert_called_with(("center", 1920 - grad_h))

    def test_create_bottom_gradient_mask_applied(self):
        """Gradient should have a mask clip applied."""
        from musicvid.pipeline.assembler import _create_bottom_gradient

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_mask.return_value = mock_clip

        with patch("musicvid.pipeline.assembler.ImageClip", return_value=mock_clip):
            _create_bottom_gradient(width=1080, height=1920, duration=5.0)

        mock_clip.with_mask.assert_called_once()
