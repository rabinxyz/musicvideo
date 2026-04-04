"""Tests for the CLI entry point."""

import json
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
