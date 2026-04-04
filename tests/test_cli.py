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
        ])

        assert result.exit_code == 0, result.output
        assemble_call_kwargs = mock_assemble.call_args[1]
        assert "30s" in assemble_call_kwargs["output_path"]

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
        ])

        assert result.exit_code == 0, result.output
        assemble_call_kwargs = mock_assemble.call_args[1]
        assert assemble_call_kwargs["resolution"] == "portrait"
        assert "reels" in assemble_call_kwargs["output_path"]

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
