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

    def _make_mock_client(self, mock_anthropic, plan_dict):
        """Helper: configure mock to return plan_dict as JSON."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps(plan_dict)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client
        return mock_client

    def _base_plan(self, scenes=None):
        """Helper: minimal valid plan dict with new fields."""
        return {
            "overall_style": "contemplative",
            "master_style": "Warm cinematic grade, golden tones",
            "color_palette": ["#aaa", "#bbb", "#ccc"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": scenes or [
                {"section": "verse", "start": 0.0, "end": 10.0,
                 "visual_prompt": "A lone figure stands on a cliff, warm amber light",
                 "motion": "slow_zoom_in", "transition": "crossfade", "overlay": "none",
                 "animate": False, "motion_prompt": ""},
            ],
        }

    @patch("musicvid.pipeline.director.anthropic")
    def test_returns_master_style(self, mock_anthropic, sample_analysis):
        mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
        result = create_scene_plan(sample_analysis)
        assert "master_style" in result
        assert isinstance(result["master_style"], str)
        assert len(result["master_style"]) > 0

    @patch("musicvid.pipeline.director.anthropic")
    def test_scenes_have_animate_field(self, mock_anthropic, sample_analysis):
        mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
        result = create_scene_plan(sample_analysis)
        for scene in result["scenes"]:
            assert "animate" in scene
            assert isinstance(scene["animate"], bool)

    @patch("musicvid.pipeline.director.anthropic")
    def test_animated_scenes_have_motion_prompt(self, mock_anthropic, sample_analysis):
        scenes = [
            {"section": "verse", "start": 0.0, "end": 5.0,
             "visual_prompt": "Mountain view", "motion": "slow_zoom_in",
             "transition": "crossfade", "overlay": "none",
             "animate": True, "motion_prompt": "Slow camera push forward"},
            {"section": "chorus", "start": 5.0, "end": 10.0,
             "visual_prompt": "Lake reflection", "motion": "static",
             "transition": "cut", "overlay": "none",
             "animate": False, "motion_prompt": ""},
        ]
        mock_client = self._make_mock_client(mock_anthropic, self._base_plan(scenes))
        result = create_scene_plan(sample_analysis)
        animated = [s for s in result["scenes"] if s["animate"]]
        for scene in animated:
            assert "motion_prompt" in scene
            assert len(scene["motion_prompt"]) > 0

    @patch("musicvid.pipeline.director.anthropic")
    def test_max_one_third_scenes_animated(self, mock_anthropic, sample_analysis):
        scenes = [
            {"section": "verse", "start": 0.0, "end": 4.0,
             "visual_prompt": "Meadow", "motion": "slow_zoom_in",
             "transition": "crossfade", "overlay": "none",
             "animate": True, "motion_prompt": "Camera rises slowly"},
            {"section": "chorus", "start": 4.0, "end": 7.0,
             "visual_prompt": "Mountain", "motion": "static",
             "transition": "cut", "overlay": "none",
             "animate": False, "motion_prompt": ""},
            {"section": "outro", "start": 7.0, "end": 10.0,
             "visual_prompt": "Sunset", "motion": "pan_left",
             "transition": "fade_black", "overlay": "none",
             "animate": False, "motion_prompt": ""},
        ]
        mock_client = self._make_mock_client(mock_anthropic, self._base_plan(scenes))
        result = create_scene_plan(sample_analysis)
        total = len(result["scenes"])
        animated = sum(1 for s in result["scenes"] if s["animate"])
        assert animated <= total / 3 + 0.01  # allow rounding up by 1

    @patch("musicvid.pipeline.director.anthropic")
    def test_master_style_default_when_missing(self, mock_anthropic, sample_analysis):
        """If Claude omits master_style, _validate_scene_plan should default to empty string."""
        plan_no_master = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                        "visual_prompt": "test", "motion": "static",
                        "transition": "cut", "overlay": "none"}],
        }
        mock_client = self._make_mock_client(mock_anthropic, plan_no_master)
        result = create_scene_plan(sample_analysis)
        assert "master_style" in result  # should be defaulted to ""
        assert result["master_style"] == ""

    @patch("musicvid.pipeline.director.anthropic")
    def test_animate_field_defaulted_when_missing(self, mock_anthropic, sample_analysis):
        """If Claude omits animate fields, _validate_scene_plan should default them."""
        plan_no_animate = {
            "overall_style": "contemplative",
            "master_style": "Warm grade",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                        "visual_prompt": "test", "motion": "static",
                        "transition": "cut", "overlay": "none"}],
        }
        mock_client = self._make_mock_client(mock_anthropic, plan_no_animate)
        result = create_scene_plan(sample_analysis)
        for scene in result["scenes"]:
            assert scene.get("animate") == False
            assert scene.get("motion_prompt") == ""
