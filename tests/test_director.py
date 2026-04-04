"""Tests for director module."""

import json
from unittest.mock import patch, MagicMock

import pytest

from musicvid.pipeline.director import create_scene_plan


class TestCreateScenePlan:
    """Tests for the create_scene_plan function."""

    @patch("musicvid.pipeline.director.anthropic")
    def test_returns_valid_scene_plan(self, mock_anthropic, sample_analysis):
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "overall_style": "contemplative",
            "color_palette": ["#1a1a2e", "#16213e", "#e2e2e2"],
            "subtitle_style": {
                "font_size": 48,
                "color": "#FFFFFF",
                "outline_color": "#000000",
                "position": "center-bottom",
                "animation": "fade",
            },
            "scenes": [
                {
                    "section": "intro",
                    "start": 0.0,
                    "end": 2.0,
                    "visual_prompt": "mountain sunrise golden light",
                    "motion": "slow_zoom_in",
                    "transition": "fade_black",
                    "overlay": "none",
                },
                {
                    "section": "verse",
                    "start": 2.0,
                    "end": 6.0,
                    "visual_prompt": "calm water reflection",
                    "motion": "slow_zoom_out",
                    "transition": "crossfade",
                    "overlay": "none",
                },
                {
                    "section": "outro",
                    "start": 6.0,
                    "end": 10.0,
                    "visual_prompt": "sunset clouds golden",
                    "motion": "pan_left",
                    "transition": "fade_black",
                    "overlay": "none",
                },
            ],
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        result = create_scene_plan(sample_analysis)

        assert "overall_style" in result
        assert "color_palette" in result
        assert "subtitle_style" in result
        assert "scenes" in result
        assert len(result["scenes"]) > 0

    @patch("musicvid.pipeline.director.anthropic")
    def test_scenes_cover_full_duration(self, mock_anthropic, sample_analysis):
        scenes = [
            {
                "section": "intro", "start": 0.0, "end": 5.0,
                "visual_prompt": "test", "motion": "slow_zoom_in",
                "transition": "fade_black", "overlay": "none",
            },
            {
                "section": "verse", "start": 5.0, "end": 10.0,
                "visual_prompt": "test", "motion": "slow_zoom_out",
                "transition": "crossfade", "overlay": "none",
            },
        ]
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "overall_style": "contemplative",
            "color_palette": ["#aaa", "#bbb", "#ccc"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": scenes,
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        result = create_scene_plan(sample_analysis)

        assert result["scenes"][0]["start"] == 0.0
        assert result["scenes"][-1]["end"] == sample_analysis["duration"]

    @patch("musicvid.pipeline.director.anthropic")
    def test_respects_style_override(self, mock_anthropic, sample_analysis):
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "overall_style": "joyful",
            "color_palette": ["#aaa", "#bbb", "#ccc"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        result = create_scene_plan(sample_analysis, style_override="joyful")

        call_args = mock_client.messages.create.call_args
        user_message = call_args[1]["messages"][0]["content"]
        assert "joyful" in user_message

    @patch("musicvid.pipeline.director.anthropic")
    def test_saves_to_output_dir(self, mock_anthropic, sample_analysis, tmp_output):
        plan_data = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps(plan_data)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        output_dir = str(tmp_output / "tmp")
        result = create_scene_plan(sample_analysis, output_dir=output_dir)

        import json as json_mod
        saved = json_mod.loads((tmp_output / "tmp" / "scene_plan.json").read_text())
        assert saved["overall_style"] == "contemplative"
