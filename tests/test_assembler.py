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

    @patch("musicvid.pipeline.assembler.TextClip")
    def test_creates_clips_for_lyrics(self, mock_text_clip, sample_analysis, sample_scene_plan):
        mock_clip = MagicMock()
        mock_clip.set_duration.return_value = mock_clip
        mock_clip.set_start.return_value = mock_clip
        mock_clip.set_position.return_value = mock_clip
        mock_clip.crossfadein.return_value = mock_clip
        mock_clip.crossfadeout.return_value = mock_clip
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


class TestAssembleVideo:
    """Tests for the main assemble_video function."""

    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_produces_output_file(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resize.return_value = mock_clip
        mock_clip.subclip.return_value = mock_clip
        mock_clip.set_duration.return_value = mock_clip
        mock_clip.set_position.return_value = mock_clip
        mock_clip.set_start.return_value = mock_clip
        mock_clip.crossfadein.return_value = mock_clip
        mock_clip.crossfadeout.return_value = mock_clip
        mock_clip.fadein.return_value = mock_clip
        mock_clip.fadeout.return_value = mock_clip
        mock_clip.fl.return_value = mock_clip
        mock_clip.set_audio.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip

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
