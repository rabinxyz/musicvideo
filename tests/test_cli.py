"""Tests for the CLI entry point."""

import json
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from click.testing import CliRunner

from musicvid.musicvid import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCLI:
    """Tests for the Click CLI."""

    def test_help_shows_usage(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "audio_file" in result.output.lower() or "AUDIO_FILE" in result.output

    def test_missing_audio_file(self, runner):
        result = runner.invoke(cli, [])
        assert result.exit_code != 0

    def test_invalid_audio_file(self, runner, tmp_path):
        result = runner.invoke(cli, [str(tmp_path / "nonexistent.mp3")])
        assert result.exit_code != 0

    def test_font_flag_accepted(self, runner, tmp_path):
        """The --font flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--font", "/some/font.ttf", "--help"])
        assert result.exit_code == 0

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_full_pipeline_integration(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--mode", "stock",
            "--preset", "full",
            "--style", "auto",
            "--resolution", "1080p",
        ])

        assert result.exit_code == 0
        mock_analyze.assert_called_once()
        mock_direct.assert_called_once()
        mock_fetch.assert_called_once()
        mock_assemble.assert_called_once()

    def test_mode_option_values(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake")
        for mode in ["stock", "ai", "hybrid"]:
            result = runner.invoke(cli, [str(audio_file), "--mode", mode, "--help"])
            assert result.exit_code == 0

    def test_new_flag_accepted(self, runner, tmp_path):
        """The --new flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--new", "--help"])
        assert result.exit_code == 0

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_cache_skips_stages_when_cached(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """When cached JSON files exist, stages 1-3 should be skipped."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        from musicvid.pipeline.cache import get_audio_hash
        audio_hash = get_audio_hash(str(audio_file))

        output_dir = tmp_path / "output"
        cache_dir = output_dir / "tmp" / audio_hash
        cache_dir.mkdir(parents=True)

        analysis_data = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        scene_plan_data = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        manifest_data = [
            {"scene_index": 0, "video_path": str(cache_dir / "videos" / "scene_000.mp4"),
             "search_query": "test"},
        ]

        # Create cached JSON files
        (cache_dir / "audio_analysis.json").write_text(json.dumps(analysis_data))
        (cache_dir / "scene_plan.json").write_text(json.dumps(scene_plan_data))
        (cache_dir / "video_manifest.json").write_text(json.dumps(manifest_data))

        # Create the referenced video file so stage 3 cache is valid
        (cache_dir / "videos").mkdir()
        (cache_dir / "videos" / "scene_000.mp4").write_bytes(b"fake video")

        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--mode", "stock", "--preset", "full",
        ])

        assert result.exit_code == 0
        # Stages 1-3 should NOT have been called
        mock_analyze.assert_not_called()
        mock_direct.assert_not_called()
        mock_fetch.assert_not_called()
        # Stage 4 always runs
        mock_assemble.assert_called_once()
        # Output should show CACHED
        assert "CACHED" in result.output

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_new_flag_forces_recalculation(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """The --new flag should ignore cache and run all stages."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        from musicvid.pipeline.cache import get_audio_hash
        audio_hash = get_audio_hash(str(audio_file))

        output_dir = tmp_path / "output"
        cache_dir = output_dir / "tmp" / audio_hash
        cache_dir.mkdir(parents=True)

        # Create cached files
        analysis_data = {
            "lyrics": [], "beats": [0.0], "bpm": 100.0,
            "duration": 5.0, "sections": [{"label": "verse", "start": 0.0, "end": 5.0}],
            "mood_energy": "worship", "language": "en",
        }
        (cache_dir / "audio_analysis.json").write_text(json.dumps(analysis_data))

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir), "--new",
            "--mode", "stock", "--preset", "full",
        ])

        assert result.exit_code == 0
        # All stages should have been called despite cache
        mock_analyze.assert_called_once()
        mock_direct.assert_called_once()
        mock_fetch.assert_called_once()
        mock_assemble.assert_called_once()

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_stage3_cache_invalid_when_video_files_missing(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """Stage 3 cache should be invalidated if video files no longer exist on disk."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        from musicvid.pipeline.cache import get_audio_hash
        audio_hash = get_audio_hash(str(audio_file))

        output_dir = tmp_path / "output"
        cache_dir = output_dir / "tmp" / audio_hash
        cache_dir.mkdir(parents=True)

        analysis_data = {
            "lyrics": [], "beats": [0.0], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        scene_plan_data = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        manifest_data = [
            {"scene_index": 0, "video_path": str(cache_dir / "videos" / "scene_000.mp4"),
             "search_query": "test"},
        ]

        (cache_dir / "audio_analysis.json").write_text(json.dumps(analysis_data))
        (cache_dir / "scene_plan.json").write_text(json.dumps(scene_plan_data))
        (cache_dir / "video_manifest.json").write_text(json.dumps(manifest_data))
        # NOTE: video file intentionally NOT created — cache should be invalid

        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--mode", "stock", "--preset", "full",
        ])

        assert result.exit_code == 0
        # Stages 1-2 should be skipped (cached)
        mock_analyze.assert_not_called()
        mock_direct.assert_not_called()
        # Stage 3 should run because video file is missing
        mock_fetch.assert_called_once()
        mock_assemble.assert_called_once()

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.generate_images")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_mode_ai_calls_image_generator(
        self, mock_analyze, mock_direct, mock_gen_images, mock_assemble, mock_font, runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_gen_images.return_value = [str(tmp_path / "scene_000.png")]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--mode", "ai",
            "--preset", "full",
        ])

        assert result.exit_code == 0
        mock_gen_images.assert_called_once()
        mock_assemble.assert_called_once()

        # Check that fetch_manifest passed to assembler uses image paths
        call_kwargs = mock_assemble.call_args[1]
        manifest = call_kwargs["fetch_manifest"]
        assert manifest[0]["video_path"].endswith(".png")

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.generate_images")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_mode_ai_cache_skips_generation(
        self, mock_analyze, mock_direct, mock_gen_images, mock_assemble, mock_font, runner, tmp_path
    ):
        """When cached image_manifest.json exists with valid files, skip generation."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        from musicvid.pipeline.cache import get_audio_hash
        audio_hash = get_audio_hash(str(audio_file))

        output_dir = tmp_path / "output"
        cache_dir = output_dir / "tmp" / audio_hash
        cache_dir.mkdir(parents=True)

        analysis_data = {
            "lyrics": [], "beats": [0.0], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        scene_plan_data = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }

        # Create the cached image file
        image_path = cache_dir / "scene_000.png"
        image_path.write_bytes(b"fake png")

        manifest_data = [
            {"scene_index": 0, "video_path": str(image_path), "search_query": "test"},
        ]

        (cache_dir / "audio_analysis.json").write_text(json.dumps(analysis_data))
        (cache_dir / "scene_plan.json").write_text(json.dumps(scene_plan_data))
        (cache_dir / "image_manifest.json").write_text(json.dumps(manifest_data))

        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir), "--mode", "ai",
            "--preset", "full",
        ])

        assert result.exit_code == 0
        mock_gen_images.assert_not_called()
        mock_assemble.assert_called_once()
        assert "CACHED" in result.output

    @patch("musicvid.musicvid.get_font_path")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_font_flag_passed_to_assembler(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_font.return_value = "/resolved/font.ttf"
        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 58, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--font", "/custom/font.ttf",
        ])

        assert result.exit_code == 0
        mock_font.assert_called_once_with(custom_path="/custom/font.ttf")
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["font_path"] == "/resolved/font.ttf"

    def test_clip_flag_accepted(self, runner, tmp_path):
        """The --clip flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--clip", "15", "--help"])
        assert result.exit_code == 0

    def test_platform_flag_accepted(self, runner, tmp_path):
        """The --platform flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--platform", "reels", "--help"])
        assert result.exit_code == 0

    def test_title_card_flag_accepted(self, runner, tmp_path):
        """The --title-card flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--title-card", "--help"])
        assert result.exit_code == 0

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_clip")
    def test_clip_mode_calls_select_clip(
        self, mock_select, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 45.0, "end": 60.0, "text": "Amazing grace"}],
            "beats": [45.0, 46.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "chorus", "start": 45.0, "end": 75.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_select.return_value = {"start": 45.0, "end": 60.0, "reason": "chorus"}
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "chorus", "start": 0.0, "end": 15.0,
                        "visual_prompt": "test", "motion": "static",
                        "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--clip", "15",
        ])

        assert result.exit_code == 0, result.output
        mock_select.assert_called_once()
        select_args = mock_select.call_args
        assert select_args[0][1] == 15

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_clip")
    def test_clip_mode_output_filename_has_duration_suffix(
        self, mock_select, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 45.0, "end": 60.0, "text": "Amazing grace"}],
            "beats": [45.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "chorus", "start": 45.0, "end": 75.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_select.return_value = {"start": 45.0, "end": 75.0, "reason": "chorus"}
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "chorus", "start": 0.0, "end": 15.0,
                        "visual_prompt": "test", "motion": "static",
                        "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--clip", "30",
            "--mode", "stock",
            "--preset", "full",
        ])

        assert result.exit_code == 0, result.output
        # With --preset full, clip selection runs and select_clip is called with duration 30
        mock_select.assert_called_once()
        assert mock_select.call_args[0][1] == 30

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_clip")
    def test_clip_mode_with_platform_uses_portrait_resolution(
        self, mock_select, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 45.0, "end": 60.0, "text": "Amazing grace"}],
            "beats": [45.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "chorus", "start": 45.0, "end": 75.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_select.return_value = {"start": 45.0, "end": 60.0, "reason": "chorus"}
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "chorus", "start": 0.0, "end": 15.0,
                        "visual_prompt": "test", "motion": "static",
                        "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--clip", "30",
            "--platform", "reels",
            "--mode", "stock",
            "--preset", "full",
        ])

        assert result.exit_code == 0, result.output
        # With --preset full, clip selection runs; verify it was called with duration 30
        mock_select.assert_called_once()
        assert mock_select.call_args[0][1] == 30
        # Assemble was called (preset full generates one video)
        mock_assemble.assert_called_once()

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_clip")
    def test_clip_mode_filters_analysis_to_clip_window(
        self, mock_select, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        import pytest
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 10.0, "end": 15.0, "text": "Before clip"},
                {"start": 45.0, "end": 55.0, "text": "In clip"},
                {"start": 80.0, "end": 90.0, "text": "After clip"},
            ],
            "beats": [10.0, 45.0, 50.0, 80.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "chorus", "start": 45.0, "end": 75.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_select.return_value = {"start": 45.0, "end": 60.0, "reason": "chorus"}
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "chorus", "start": 0.0, "end": 15.0,
                        "visual_prompt": "test", "motion": "static",
                        "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--clip", "15",
        ])

        assert result.exit_code == 0, result.output
        # Director receives filtered analysis: only "In clip" segment, offset by clip_start
        director_analysis = mock_direct.call_args[0][0]
        assert director_analysis["duration"] == pytest.approx(15.0, abs=0.5)
        filtered_lyrics = director_analysis["lyrics"]
        assert len(filtered_lyrics) == 1
        assert filtered_lyrics[0]["text"] == "In clip"
        # Times should be offset relative to clip_start=45.0
        assert filtered_lyrics[0]["start"] == pytest.approx(0.0, abs=0.5)


class TestLyricsFlag:
    """Tests for --lyrics CLI option and auto-detection."""

    def test_lyrics_flag_accepted(self, runner, tmp_path):
        """The --lyrics flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--lyrics", str(tmp_path / "lyrics.txt"), "--help"])
        assert result.exit_code == 0

    @patch("musicvid.musicvid.align_with_claude")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_lyrics_flag_skips_whisper(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, mock_align, runner, tmp_path
    ):
        """When --lyrics is provided, lyrics from file replace Whisper output."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\nLine two\n")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 0.0, "end": 5.0, "text": "whisper text 1", "words": []},
                {"start": 5.0, "end": 10.0, "text": "whisper text 2", "words": []},
            ], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_align.return_value = [
            {"start": 0.0, "end": 5.0, "text": "Line one"},
            {"start": 5.0, "end": 10.0, "text": "Line two"},
        ]
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])

        assert result.exit_code == 0
        mock_align.assert_called_once()
        call_kwargs = mock_assemble.call_args[1]
        analysis_used = call_kwargs["analysis"]
        assert len(analysis_used["lyrics"]) == 2
        assert analysis_used["lyrics"][0]["text"] == "Line one"

    @patch("musicvid.musicvid.align_with_claude")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_auto_detect_single_txt(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, mock_align, runner, tmp_path
    ):
        """When exactly one .txt exists in audio dir, use it automatically."""
        audio_dir = tmp_path / "music"
        audio_dir.mkdir()
        audio_file = audio_dir / "song.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = audio_dir / "lyrics.txt"
        lyrics_file.write_text("Auto line one\nAuto line two\n")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 0.0, "end": 5.0, "text": "whisper 1", "words": []},
                {"start": 5.0, "end": 10.0, "text": "whisper 2", "words": []},
            ], "beats": [0.0], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_align.return_value = [
            {"start": 0.0, "end": 5.0, "text": "Auto line one"},
            {"start": 5.0, "end": 10.0, "text": "Auto line two"},
        ]
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [str(audio_file), "--output", str(output_dir)])

        assert result.exit_code == 0
        mock_align.assert_called_once()
        call_kwargs = mock_assemble.call_args[1]
        analysis_used = call_kwargs["analysis"]
        assert len(analysis_used["lyrics"]) == 2
        assert analysis_used["lyrics"][0]["text"] == "Auto line one"

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_auto_detect_multiple_txt_uses_whisper(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """When multiple .txt files exist, ignore auto-detection and use Whisper."""
        audio_dir = tmp_path / "music"
        audio_dir.mkdir()
        audio_file = audio_dir / "song.mp3"
        audio_file.write_bytes(b"fake audio")
        (audio_dir / "a.txt").write_text("A")
        (audio_dir / "b.txt").write_text("B")

        mock_analyze.return_value = {
            "lyrics": [{"start": 0.0, "end": 5.0, "text": "Whisper text", "words": []}],
            "beats": [0.0], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [str(audio_file), "--output", str(output_dir)])

        assert result.exit_code == 0
        assert "--lyrics" in result.output
        call_kwargs = mock_assemble.call_args[1]
        analysis_used = call_kwargs["analysis"]
        assert analysis_used["lyrics"][0]["text"] == "Whisper text"

    @patch("musicvid.musicvid.align_with_claude")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_lyrics_hash_invalidates_cache(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, mock_align, runner, tmp_path
    ):
        """Changing lyrics file content should invalidate the audio_analysis cache."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\nLine two\n")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 0.0, "end": 5.0, "text": "w1", "words": []},
                {"start": 5.0, "end": 10.0, "text": "w2", "words": []},
            ], "beats": [0.0], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_align.return_value = [
            {"start": 0.0, "end": 5.0, "text": "Line one"},
            {"start": 5.0, "end": 10.0, "text": "Line two"},
        ]
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        # First run
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])
        assert result.exit_code == 0

        # Modify lyrics file content
        lyrics_file.write_text("Changed line\n")
        mock_analyze.reset_mock()
        mock_align.reset_mock()

        # Second run — lyrics hash changed, so analyze_audio should be called again
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])
        assert result.exit_code == 0
        mock_analyze.assert_called_once()
        # align_with_claude should also be called again (new lyrics hash = no cached alignment)
        mock_align.assert_called_once()

    def test_lyrics_flag_missing_file(self, runner, tmp_path):
        """--lyrics with a nonexistent file should give a clear error."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        result = runner.invoke(cli, [
            str(audio_file), "--lyrics", str(tmp_path / "nonexistent.txt"),
        ])

        assert result.exit_code != 0


class TestEffectsFlag:
    """Tests for --effects CLI option."""

    def test_effects_flag_accepted(self, runner, tmp_path):
        """The --effects flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--effects", "full", "--help"])
        assert result.exit_code == 0

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_effects_flag_passes_to_assembler(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir), "--effects", "full",
        ])

        assert result.exit_code == 0
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["effects_level"] == "full"

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_effects_defaults_to_minimal(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [str(audio_file), "--output", str(output_dir)])

        assert result.exit_code == 0
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["effects_level"] == "minimal"


class TestAILyricsAlignment:
    """Tests for AI lyrics alignment integration in CLI."""

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.align_with_claude")
    def test_lyrics_file_triggers_alignment(
        self, mock_align, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """When --lyrics is provided, align_with_claude should be called."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Correct line one\nCorrect line two\n")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 0.5, "end": 2.0, "text": "whisper text 1", "words": []},
                {"start": 2.5, "end": 4.0, "text": "whisper text 2", "words": []},
            ],
            "beats": [0.0], "bpm": 120.0, "duration": 10.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_align.return_value = [
            {"start": 0.5, "end": 2.0, "text": "Correct line one"},
            {"start": 2.5, "end": 4.0, "text": "Correct line two"},
        ]
        mock_direct.return_value = {
            "overall_style": "contemplative", "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])

        assert result.exit_code == 0
        mock_align.assert_called_once()
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["analysis"]["lyrics"][0]["text"] == "Correct line one"

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.align_with_claude")
    def test_alignment_result_cached(
        self, mock_align, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """Second run with same lyrics should use cached alignment."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\nLine two\n")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 0.5, "end": 2.0, "text": "w1", "words": []},
                {"start": 2.5, "end": 4.0, "text": "w2", "words": []},
            ],
            "beats": [0.0], "bpm": 120.0, "duration": 10.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_align.return_value = [
            {"start": 0.5, "end": 2.0, "text": "Line one"},
            {"start": 2.5, "end": 4.0, "text": "Line two"},
        ]
        mock_direct.return_value = {
            "overall_style": "contemplative", "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        # First run
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])
        assert result.exit_code == 0

        # Second run — alignment should be cached
        mock_align.reset_mock()
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])
        assert result.exit_code == 0
        mock_align.assert_not_called()
        assert "AI dopasowanie" in result.output

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_no_lyrics_file_uses_whisper(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """Without lyrics file, Whisper lyrics should be used as-is."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 0.0, "end": 5.0, "text": "Whisper text", "words": []}],
            "beats": [0.0], "bpm": 120.0, "duration": 10.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative", "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [str(audio_file), "--output", str(output_dir)])

        assert result.exit_code == 0
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["analysis"]["lyrics"][0]["text"] == "Whisper text"

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.align_with_claude")
    def test_alignment_log_message(
        self, mock_align, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """CLI should display alignment log message with line count."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\nLine two\nLine three\n")

        mock_analyze.return_value = {
            "lyrics": [{"start": 0.0, "end": 3.0, "text": "w", "words": []}],
            "beats": [0.0], "bpm": 120.0, "duration": 10.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_align.return_value = [
            {"start": 0.0, "end": 1.0, "text": "Line one"},
            {"start": 1.0, "end": 2.0, "text": "Line two"},
            {"start": 2.0, "end": 3.0, "text": "Line three"},
        ]
        mock_direct.return_value = {
            "overall_style": "contemplative", "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])

        assert result.exit_code == 0
        assert "Whisper timing + AI dopasowanie" in result.output
        assert "3 linii" in result.output


class TestAnimateCLI:
    """Tests for the --animate CLI flag."""

    def _make_scene_plan_with_animated(self):
        return {
            "overall_style": "contemplative",
            "master_style": "Warm grade",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF",
                               "outline_color": "#000", "position": "center-bottom",
                               "animation": "fade"},
            "scenes": [
                {"section": "verse", "start": 0.0, "end": 4.0,
                 "visual_prompt": "meadow", "motion": "slow_zoom_in",
                 "transition": "crossfade", "overlay": "none",
                 "animate": True, "motion_prompt": "Camera rises slowly"},
                {"section": "chorus", "start": 4.0, "end": 7.0,
                 "visual_prompt": "mountain", "motion": "static",
                 "transition": "cut", "overlay": "none",
                 "animate": False, "motion_prompt": ""},
                {"section": "outro", "start": 7.0, "end": 10.0,
                 "visual_prompt": "sunset", "motion": "pan_left",
                 "transition": "fade_black", "overlay": "none",
                 "animate": False, "motion_prompt": ""},
            ],
        }

    def _make_analysis(self):
        return {
            "lyrics": [], "beats": [], "bpm": 120.0, "duration": 10.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }

    @patch("musicvid.musicvid.animate_image")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.generate_images", return_value=["/fake/s0.jpg", "/fake/s1.jpg", "/fake/s2.jpg"])
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_animate_never_does_not_call_animate_image(
        self, mock_analyze, mock_plan, mock_gen, mock_assemble, mock_font, mock_animate, tmp_path
    ):
        from musicvid.musicvid import cli

        mock_analyze.return_value = self._make_analysis()
        mock_plan.return_value = self._make_scene_plan_with_animated()

        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake audio")

        runner = CliRunner()
        result = runner.invoke(cli, [str(audio), "--mode", "ai", "--animate", "never"])

        mock_animate.assert_not_called()
        assert result.exit_code == 0

    @patch("musicvid.musicvid.animate_image", return_value="/fake/animated.mp4")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.generate_images", return_value=["/fake/s0.jpg", "/fake/s1.jpg", "/fake/s2.jpg"])
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_animate_auto_with_runway_key_calls_animator(
        self, mock_analyze, mock_plan, mock_gen, mock_assemble, mock_font, mock_animate, tmp_path
    ):
        from musicvid.musicvid import cli

        mock_analyze.return_value = self._make_analysis()
        mock_plan.return_value = self._make_scene_plan_with_animated()

        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake audio")

        runner = CliRunner()
        with patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key", "BFL_API_KEY": "test-bfl"}):
            result = runner.invoke(cli, [str(audio), "--mode", "ai", "--animate", "auto"])

        # Should be called once (only scene 0 has animate=True)
        mock_animate.assert_called_once()
        assert result.exit_code == 0

    @patch("musicvid.musicvid.animate_image")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.generate_images", return_value=["/fake/s0.jpg", "/fake/s1.jpg", "/fake/s2.jpg"])
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_animate_fallback_when_no_runway_key(
        self, mock_analyze, mock_plan, mock_gen, mock_assemble, mock_font, mock_animate, tmp_path
    ):
        from musicvid.musicvid import cli

        mock_analyze.return_value = self._make_analysis()
        mock_plan.return_value = self._make_scene_plan_with_animated()

        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake audio")

        runner = CliRunner()
        # Remove RUNWAY_API_KEY so the fallback path is triggered
        env = {k: v for k, v in os.environ.items() if k != "RUNWAY_API_KEY"}
        env["BFL_API_KEY"] = "test-bfl"
        with patch.dict(os.environ, env, clear=True):
            result = runner.invoke(cli, [str(audio), "--mode", "ai", "--animate", "auto"])

        mock_animate.assert_not_called()
        assert result.exit_code == 0


class TestFilterScenePlanToClip:
    """Tests for _filter_scene_plan_to_clip helper."""

    def test_returns_only_overlapping_scenes(self):
        from musicvid.musicvid import _filter_scene_plan_to_clip

        scene_plan = {
            "overall_style": "contemplative",
            "master_style": "warm tones",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48},
            "scenes": [
                {"section": "intro", "start": 0.0, "end": 15.0, "visual_prompt": "sunrise",
                 "motion": "slow_zoom_in", "transition": "cut", "overlay": "none"},
                {"section": "verse", "start": 15.0, "end": 45.0, "visual_prompt": "lake",
                 "motion": "pan_left", "transition": "crossfade", "overlay": "none"},
                {"section": "chorus", "start": 45.0, "end": 75.0, "visual_prompt": "mountain",
                 "motion": "slow_zoom_out", "transition": "cut", "overlay": "none"},
                {"section": "outro", "start": 75.0, "end": 100.0, "visual_prompt": "sunset",
                 "motion": "static", "transition": "fade_black", "overlay": "none"},
            ],
        }

        result = _filter_scene_plan_to_clip(scene_plan, 45.0, 60.0)

        assert len(result["scenes"]) == 1
        assert result["scenes"][0]["section"] == "chorus"

    def test_offsets_scene_times_to_zero(self):
        from musicvid.musicvid import _filter_scene_plan_to_clip

        scene_plan = {
            "overall_style": "contemplative",
            "master_style": "",
            "color_palette": [],
            "subtitle_style": {},
            "scenes": [
                {"section": "chorus", "start": 45.0, "end": 75.0, "visual_prompt": "mountain",
                 "motion": "slow_zoom_out", "transition": "cut", "overlay": "none"},
            ],
        }

        result = _filter_scene_plan_to_clip(scene_plan, 45.0, 60.0)

        assert result["scenes"][0]["start"] == 0.0
        assert result["scenes"][0]["end"] == 15.0

    def test_trims_partially_overlapping_scenes(self):
        from musicvid.musicvid import _filter_scene_plan_to_clip

        scene_plan = {
            "overall_style": "contemplative",
            "master_style": "",
            "color_palette": [],
            "subtitle_style": {},
            "scenes": [
                {"section": "verse", "start": 10.0, "end": 30.0, "visual_prompt": "lake",
                 "motion": "pan_left", "transition": "cut", "overlay": "none"},
                {"section": "chorus", "start": 30.0, "end": 50.0, "visual_prompt": "mountain",
                 "motion": "slow_zoom_out", "transition": "cut", "overlay": "none"},
            ],
        }

        result = _filter_scene_plan_to_clip(scene_plan, 25.0, 40.0)

        assert len(result["scenes"]) == 2
        assert result["scenes"][0]["start"] == 0.0
        assert result["scenes"][0]["end"] == 5.0
        assert result["scenes"][1]["start"] == 5.0
        assert result["scenes"][1]["end"] == 15.0

    def test_preserves_non_scene_fields(self):
        from musicvid.musicvid import _filter_scene_plan_to_clip

        scene_plan = {
            "overall_style": "joyful",
            "master_style": "golden tones",
            "color_palette": ["#fff"],
            "subtitle_style": {"font_size": 48},
            "scenes": [
                {"section": "chorus", "start": 0.0, "end": 30.0, "visual_prompt": "test",
                 "motion": "static", "transition": "cut", "overlay": "none"},
            ],
        }

        result = _filter_scene_plan_to_clip(scene_plan, 0.0, 15.0)

        assert result["overall_style"] == "joyful"
        assert result["master_style"] == "golden tones"
        assert result["color_palette"] == ["#fff"]
        assert result["subtitle_style"] == {"font_size": 48}


class TestFilterManifestToClip:
    """Tests for _filter_manifest_to_clip helper."""

    def test_returns_only_matching_entries(self):
        from musicvid.musicvid import _filter_manifest_to_clip

        scenes = [
            {"section": "intro", "start": 0.0, "end": 15.0},
            {"section": "verse", "start": 15.0, "end": 45.0},
            {"section": "chorus", "start": 45.0, "end": 75.0},
        ]
        manifest = [
            {"scene_index": 0, "video_path": "/a.jpg", "search_query": "intro"},
            {"scene_index": 1, "video_path": "/b.jpg", "search_query": "verse"},
            {"scene_index": 2, "video_path": "/c.jpg", "search_query": "chorus"},
        ]

        result = _filter_manifest_to_clip(manifest, scenes, 45.0, 60.0)

        assert len(result) == 1
        assert result[0]["video_path"] == "/c.jpg"

    def test_reindexes_scene_indices(self):
        from musicvid.musicvid import _filter_manifest_to_clip

        scenes = [
            {"section": "verse", "start": 15.0, "end": 45.0},
            {"section": "chorus", "start": 45.0, "end": 75.0},
        ]
        manifest = [
            {"scene_index": 0, "video_path": "/a.jpg", "search_query": "verse"},
            {"scene_index": 1, "video_path": "/b.jpg", "search_query": "chorus"},
        ]

        result = _filter_manifest_to_clip(manifest, scenes, 40.0, 55.0)

        assert len(result) == 2
        assert result[0]["scene_index"] == 0
        assert result[1]["scene_index"] == 1


class TestPresetMode:
    """Tests for --preset and --reel-duration CLI flags."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_preset_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--preset", "all", "--help"])
        assert result.exit_code == 0

    def test_reel_duration_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--reel-duration", "30", "--help"])
        assert result.exit_code == 0

    def test_preset_invalid_value_rejected(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--preset", "invalid"])
        assert result.exit_code != 0

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_preset_full_assembles_one_video(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 0.5, "end": 2.0, "text": "Test"}],
            "beats": [0.0, 0.5, 1.0],
            "bpm": 120.0,
            "duration": 60.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 60.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 60.0,
                        "visual_prompt": "test", "motion": "static",
                        "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--preset", "full",
        ])

        assert result.exit_code == 0, result.output
        assert mock_assemble.call_count == 1
        call_kwargs = mock_assemble.call_args[1]
        assert "pelny" in call_kwargs["output_path"]
        assert call_kwargs["output_path"].endswith("_youtube.mp4")

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_preset_social_assembles_three_reels(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 20.0, "end": 24.0, "text": "Verse line"},
                {"start": 60.0, "end": 64.0, "text": "Chorus line"},
                {"start": 90.0, "end": 94.0, "text": "Bridge line"},
            ],
            "beats": [0.0, 0.5, 1.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [
                {"label": "verse", "start": 0.0, "end": 60.0},
                {"label": "chorus", "start": 60.0, "end": 90.0},
                {"label": "bridge", "start": 90.0, "end": 120.0},
            ],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
                {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Opening"},
                {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Peak"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [
                {"section": "verse", "start": 0.0, "end": 60.0,
                 "visual_prompt": "test1", "motion": "static", "transition": "cut", "overlay": "none"},
                {"section": "chorus", "start": 60.0, "end": 90.0,
                 "visual_prompt": "test2", "motion": "slow_zoom_in", "transition": "cut", "overlay": "none"},
                {"section": "bridge", "start": 90.0, "end": 120.0,
                 "visual_prompt": "test3", "motion": "pan_left", "transition": "cut", "overlay": "none"},
            ],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v1.mp4", "search_query": "test1"},
            {"scene_index": 1, "video_path": "/fake/v2.mp4", "search_query": "test2"},
            {"scene_index": 2, "video_path": "/fake/v3.mp4", "search_query": "test3"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--preset", "social",
        ])

        assert result.exit_code == 0, result.output
        assert mock_assemble.call_count == 3
        mock_social.assert_called_once()

        # All 3 calls should use portrait resolution
        for call in mock_assemble.call_args_list:
            assert call[1]["resolution"] == "portrait"

        # Check output paths are in social/ subfolder
        paths = [call[1]["output_path"] for call in mock_assemble.call_args_list]
        assert all("social" in p for p in paths)
        assert any("rolka_A" in p for p in paths)
        assert any("rolka_B" in p for p in paths)
        assert any("rolka_C" in p for p in paths)

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_preset_all_assembles_four_videos(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 20.0, "end": 24.0, "text": "Test"}],
            "beats": [0.0, 0.5],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [
                {"label": "verse", "start": 0.0, "end": 60.0},
                {"label": "chorus", "start": 60.0, "end": 90.0},
                {"label": "bridge", "start": 90.0, "end": 120.0},
            ],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
                {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Opening"},
                {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Peak"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [
                {"section": "verse", "start": 0.0, "end": 60.0,
                 "visual_prompt": "test", "motion": "static", "transition": "cut", "overlay": "none"},
                {"section": "chorus", "start": 60.0, "end": 90.0,
                 "visual_prompt": "test", "motion": "static", "transition": "cut", "overlay": "none"},
                {"section": "bridge", "start": 90.0, "end": 120.0,
                 "visual_prompt": "test", "motion": "static", "transition": "cut", "overlay": "none"},
            ],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v1.mp4", "search_query": "test"},
            {"scene_index": 1, "video_path": "/fake/v2.mp4", "search_query": "test"},
            {"scene_index": 2, "video_path": "/fake/v3.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--preset", "all",
        ])

        assert result.exit_code == 0, result.output
        assert mock_assemble.call_count == 4

        # First call is full YouTube video
        first_call = mock_assemble.call_args_list[0][1]
        assert "pelny" in first_call["output_path"]

        # Remaining 3 calls are social reels
        for call in mock_assemble.call_args_list[1:]:
            assert call[1]["resolution"] == "portrait"
            assert "social" in call[1]["output_path"]

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_preset_all_stages_1_to_3_run_once(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 20.0, "end": 24.0, "text": "Test"}],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [
                {"label": "verse", "start": 0.0, "end": 60.0},
                {"label": "chorus", "start": 60.0, "end": 90.0},
                {"label": "bridge", "start": 90.0, "end": 120.0},
            ],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
                {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Opening"},
                {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Peak"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [
                {"section": "verse", "start": 0.0, "end": 60.0,
                 "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"},
            ],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--preset", "all",
            "--mode", "stock",
        ])

        assert result.exit_code == 0, result.output
        mock_analyze.assert_called_once()
        mock_direct.assert_called_once()
        mock_fetch.assert_called_once()
        assert mock_assemble.call_count == 4

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_reel_duration_changes_clip_length(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 180.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 10.0, "end": 40.0, "section": "verse", "reason": "A"},
                {"id": "B", "start": 60.0, "end": 90.0, "section": "verse", "reason": "B"},
                {"id": "C", "start": 120.0, "end": 150.0, "section": "verse", "reason": "C"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 180.0,
                        "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--preset", "social",
            "--reel-duration", "30",
        ])

        assert result.exit_code == 0, result.output
        mock_social.assert_called_once()
        assert mock_social.call_args[0][1] == 30

        paths = [call[1]["output_path"] for call in mock_assemble.call_args_list]
        assert all("30s" in p for p in paths)

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_social_reels_use_correct_assembler_params(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 180.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 10.0, "end": 25.0, "section": "verse", "reason": "A"},
                {"id": "B", "start": 60.0, "end": 75.0, "section": "verse", "reason": "B"},
                {"id": "C", "start": 120.0, "end": 135.0, "section": "verse", "reason": "C"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 180.0,
                        "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir), "--preset", "social",
        ])

        assert result.exit_code == 0, result.output
        for call in mock_assemble.call_args_list:
            kwargs = call[1]
            assert kwargs["resolution"] == "portrait"
            assert kwargs["audio_fade_out"] == 1.5
            assert kwargs["subtitle_margin_bottom"] == 200
            assert kwargs["cinematic_bars"] == False
            assert kwargs["clip_start"] is not None
            assert kwargs["clip_end"] is not None

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_no_preset_flag_unchanged_behavior(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        """Without --preset, existing behavior is preserved exactly."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 60.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 60.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 60.0,
                        "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--mode", "stock", "--preset", "full",
        ])

        assert result.exit_code == 0, result.output
        assert mock_assemble.call_count == 1
        call_kwargs = mock_assemble.call_args[1]
        # With --preset full, output goes to pelny/ directory as a YouTube video
        assert "_youtube.mp4" in call_kwargs["output_path"]
        assert "pelny" in call_kwargs["output_path"]
        assert "social" not in call_kwargs["output_path"]

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_social_clips_cached_on_second_run(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        base_analysis = {
            "lyrics": [],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 180.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_analyze.return_value = base_analysis
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 10.0, "end": 25.0, "section": "verse", "reason": "A"},
                {"id": "B", "start": 60.0, "end": 75.0, "section": "verse", "reason": "B"},
                {"id": "C", "start": 120.0, "end": 135.0, "section": "verse", "reason": "C"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 180.0,
                        "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"
        args = [str(audio_file), "--output", str(output_dir), "--preset", "social"]

        # First run
        runner.invoke(cli, args)
        assert mock_social.call_count == 1

        # Second run — social clips should be cached
        runner.invoke(cli, args)
        assert mock_social.call_count == 1  # not called again

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_different_reel_duration_invalidates_cache(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        base_analysis = {
            "lyrics": [],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 180.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_analyze.return_value = base_analysis
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 10.0, "end": 25.0, "section": "verse", "reason": "A"},
                {"id": "B", "start": 60.0, "end": 75.0, "section": "verse", "reason": "B"},
                {"id": "C", "start": 120.0, "end": 135.0, "section": "verse", "reason": "C"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 180.0,
                        "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"

        # Run with 15s
        runner.invoke(cli, [str(audio_file), "--output", str(output_dir), "--preset", "social"])
        assert mock_social.call_count == 1

        # Run with 30s — different cache key
        runner.invoke(cli, [str(audio_file), "--output", str(output_dir), "--preset", "social", "--reel-duration", "30"])
        assert mock_social.call_count == 2  # called again because different duration


class TestLogoFlag:
    """Tests for --logo CLI flag."""

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_logo_passed_to_assembler(self, mock_analyze, mock_director, mock_fetch, mock_assemble, mock_font, runner, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"fake_png")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_director.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"}]

        result = runner.invoke(cli, [str(audio), "--logo", str(logo), "--output", str(tmp_path / "out")])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["logo_path"] == str(logo)
        assert call_kwargs["logo_position"] == "top-left"
        assert call_kwargs["logo_opacity"] == 0.85
        assert call_kwargs["logo_size"] is None

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_logo_all_options(self, mock_analyze, mock_director, mock_fetch, mock_assemble, mock_font, runner, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")
        logo = tmp_path / "logo.svg"
        logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_director.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"}]

        result = runner.invoke(cli, [
            str(audio), "--logo", str(logo),
            "--logo-position", "bottom-right",
            "--logo-size", "200",
            "--logo-opacity", "0.5",
            "--output", str(tmp_path / "out"),
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["logo_path"] == str(logo)
        assert call_kwargs["logo_position"] == "bottom-right"
        assert call_kwargs["logo_size"] == 200
        assert call_kwargs["logo_opacity"] == 0.5

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_no_logo_by_default(self, mock_analyze, mock_director, mock_fetch, mock_assemble, mock_font, runner, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_director.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"}]

        result = runner.invoke(cli, [str(audio), "--output", str(tmp_path / "out")])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["logo_path"] is None


class TestLogoWithPreset:
    """Tests that logo params are passed through preset mode."""

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.select_social_clips")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_preset_all_passes_logo_to_all_assemblies(
        self, mock_analyze, mock_director, mock_fetch, mock_social, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"fake_png")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 100.0, "sections": [{"label": "verse", "start": 0.0, "end": 100.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_director.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 100.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]
        mock_social.return_value = {
            "clips": [
                {"id": 1, "start": 0.0, "end": 15.0, "section": "intro", "reason": "test"},
                {"id": 2, "start": 30.0, "end": 45.0, "section": "chorus", "reason": "test"},
                {"id": 3, "start": 60.0, "end": 75.0, "section": "outro", "reason": "test"},
            ]
        }

        result = runner.invoke(cli, [
            str(audio), "--preset", "all",
            "--logo", str(logo), "--logo-position", "top-right",
            "--output", str(tmp_path / "out"),
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
        # 1 full + 3 social = 4 assemble calls
        assert mock_assemble.call_count == 4
        for call_obj in mock_assemble.call_args_list:
            kwargs = call_obj[1]
            assert kwargs["logo_path"] == str(logo)
            assert kwargs["logo_position"] == "top-right"

    def test_lut_style_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake")
        result = runner.invoke(cli, [str(audio_file), "--lut-style", "warm", "--help"])
        assert result.exit_code == 0

    def test_subtitle_style_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake")
        result = runner.invoke(cli, [str(audio_file), "--subtitle-style", "karaoke", "--help"])
        assert result.exit_code == 0

    def test_transitions_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake")
        result = runner.invoke(cli, [str(audio_file), "--transitions", "cut", "--help"])
        assert result.exit_code == 0

    def test_beat_sync_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake")
        result = runner.invoke(cli, [str(audio_file), "--beat-sync", "auto", "--help"])
        assert result.exit_code == 0

    def test_yes_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake")
        result = runner.invoke(cli, [str(audio_file), "--yes", "--help"])
        assert result.exit_code == 0

    def test_quick_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake")
        result = runner.invoke(cli, [str(audio_file), "--quick", "--help"])
        assert result.exit_code == 0

    def test_economy_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake")
        result = runner.invoke(cli, [str(audio_file), "--economy", "--help"])
        assert result.exit_code == 0
