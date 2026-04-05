"""Tests for assembler module."""

import json
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

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in", "animate": False}
        _load_scene_clip(str(fake_jpg), scene, (1920, 1080))

        # transform (Ken Burns) SHOULD be called
        mock_clip.transform.assert_called()

    @patch("musicvid.pipeline.assembler.VideoFileClip")
    def test_non_animated_mp4_uses_ken_burns(self, mock_vfc, tmp_path):
        """Non-animated .mp4 (stock video) should still get Ken Burns."""
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

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in", "animate": False}
        _load_scene_clip(str(fake_mp4), scene, (1920, 1080))

        # transform (Ken Burns) SHOULD be called for non-animated video
        mock_clip.transform.assert_called()


class TestPortraitKenBurns:
    """Tests for portrait-mode Ken Burns restrictions."""

    def test_pan_up_calls_transform(self):
        from musicvid.pipeline.assembler import _create_ken_burns_clip
        from unittest.mock import MagicMock

        mock_clip = MagicMock()
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        result = _create_ken_burns_clip(mock_clip, 5.0, "pan_up", (1080, 1920))

        mock_clip.transform.assert_called_once()

    def test_pan_down_calls_transform(self):
        from musicvid.pipeline.assembler import _create_ken_burns_clip
        from unittest.mock import MagicMock

        mock_clip = MagicMock()
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

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
        mock_clip.resized.return_value = mock_clip
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
        mock_clip.resized.return_value = mock_clip
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
