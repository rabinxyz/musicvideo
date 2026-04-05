"""Tests for director module."""

import json
from unittest.mock import patch, MagicMock

import pytest

from musicvid.pipeline.director import (
    create_scene_plan,
    _build_user_message,
    _validate_scene_plan,
)


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

    @patch("musicvid.pipeline.director.anthropic")
    def test_calls_claude_with_8192_max_tokens(self, mock_anthropic, sample_analysis):
        mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
        create_scene_plan(sample_analysis)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 8192

    @patch("musicvid.pipeline.director.anthropic")
    def test_strips_json_markdown_fence(self, mock_anthropic, sample_analysis):
        plan = self._base_plan()
        wrapped = "```json\n" + json.dumps(plan) + "\n```"
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = wrapped
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client
        result = create_scene_plan(sample_analysis)
        assert "overall_style" in result

    @patch("musicvid.pipeline.director.anthropic")
    def test_strips_plain_markdown_fence(self, mock_anthropic, sample_analysis):
        plan = self._base_plan()
        wrapped = "```\n" + json.dumps(plan) + "\n```"
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = wrapped
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client
        result = create_scene_plan(sample_analysis)
        assert "overall_style" in result

    @patch("musicvid.pipeline.director.anthropic")
    def test_repairs_truncated_json(self, mock_anthropic, sample_analysis):
        """Should repair JSON truncated mid-string by finding last complete scene."""
        plan = self._base_plan()
        complete_json = json.dumps(plan)
        # Truncate in the middle — cut off last 20 chars
        truncated = complete_json[:-20]
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = truncated
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client
        result = create_scene_plan(sample_analysis)
        assert "scenes" in result
        assert len(result["scenes"]) > 0

    @patch("musicvid.pipeline.director.anthropic")
    def test_scene_limit_short_song(self, mock_anthropic, sample_analysis):
        """Songs under 3 minutes: BPM-based suggested count in prompt (120 BPM, 150s → 18 scenes)."""
        short_analysis = dict(sample_analysis, duration=150.0)  # 2.5 min, 120 BPM → bar=2s, suggested=18
        mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
        create_scene_plan(short_analysis)
        call_kwargs = mock_client.messages.create.call_args[1]
        user_msg = call_kwargs["messages"][0]["content"]
        assert "Suggested scene count" in user_msg
        assert "18" in user_msg

    @patch("musicvid.pipeline.director.anthropic")
    def test_scene_limit_medium_song(self, mock_anthropic, sample_analysis):
        """Songs 3-5 minutes: BPM-based suggested count in prompt (120 BPM, 240s → 30 scenes)."""
        medium_analysis = dict(sample_analysis, duration=240.0)  # 4 min, 120 BPM → bar=2s, suggested=30
        mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
        create_scene_plan(medium_analysis)
        call_kwargs = mock_client.messages.create.call_args[1]
        user_msg = call_kwargs["messages"][0]["content"]
        assert "Suggested scene count" in user_msg
        assert "30" in user_msg

    @patch("musicvid.pipeline.director.anthropic")
    def test_scene_limit_long_song(self, mock_anthropic, sample_analysis):
        """Songs over 5 minutes: BPM-based suggested count in prompt (120 BPM, 360s → 45 scenes)."""
        long_analysis = dict(sample_analysis, duration=360.0)  # 6 min, 120 BPM → bar=2s, suggested=45
        mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
        create_scene_plan(long_analysis)
        call_kwargs = mock_client.messages.create.call_args[1]
        user_msg = call_kwargs["messages"][0]["content"]
        assert "Suggested scene count" in user_msg
        assert "45" in user_msg

    @patch("musicvid.pipeline.director.anthropic")
    def test_retries_when_json_unreparable(self, mock_anthropic, sample_analysis):
        """Should retry Claude call when truncated JSON is unreparable."""
        plan = self._base_plan()
        good_json = json.dumps(plan)
        # First call returns garbage, second returns valid JSON
        bad_response = MagicMock()
        bad_response.content = [MagicMock()]
        bad_response.content[0].text = '{"scenes": [{'  # unreparable
        good_response = MagicMock()
        good_response.content = [MagicMock()]
        good_response.content[0].text = good_json
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [bad_response, good_response]
        mock_anthropic.Anthropic.return_value = mock_client
        result = create_scene_plan(sample_analysis)
        assert "scenes" in result
        assert mock_client.messages.create.call_count == 2

    @staticmethod
    def test_system_prompt_contains_visual_prompt_length_constraint():
        """System prompt must instruct Claude to keep visual_prompt under 200 chars."""
        from musicvid.pipeline.director import _load_system_prompt
        prompt = _load_system_prompt()
        assert "200 char" in prompt
        assert "visual_prompt" in prompt


def test_build_user_message_includes_bpm_guidance():
    """User message contains BPM, bar_duration, and suggested scene count."""
    analysis = {
        "duration": 240.0,
        "bpm": 84.0,
        "beats": [i * (60.0 / 84.0) for i in range(200)],
        "lyrics": [],
        "sections": [],
        "mood_energy": "medium",
    }
    msg = _build_user_message(analysis)

    assert "BPM: 84" in msg
    assert "Bar duration" in msg
    assert "Suggested scene count" in msg


def test_build_user_message_scene_count_based_on_bpm():
    """Suggested scene count is derived from BPM and duration."""
    # 180s song at 120 BPM: bar = 2s, suggested = int(180/(2*4)) = 22
    analysis = {
        "duration": 180.0,
        "bpm": 120.0,
        "beats": [i * 0.5 for i in range(360)],
        "lyrics": [],
        "sections": [],
        "mood_energy": "high",
    }
    msg = _build_user_message(analysis)
    # suggested_scene_count = max(4, int(180 / (2.0 * 4))) = 22
    assert "22" in msg


def test_section_length_guidance_included():
    analysis = {
        "duration": 120.0,
        "bpm": 84.0,
        "beats": [i * (60/84) for i in range(200)],
        "sections": [
            {"label": "intro", "start": 0.0, "end": 20.0},
            {"label": "verse", "start": 20.0, "end": 60.0},
            {"label": "chorus", "start": 60.0, "end": 80.0},
            {"label": "outro", "start": 80.0, "end": 120.0},
        ],
        "lyrics": [],
        "mood_energy": "contemplative",
        "language": "en",
    }
    from musicvid.pipeline.director import _build_user_message
    msg = _build_user_message(analysis)
    assert "DŁUGOŚCI SCEN" in msg
    assert "chorus" in msg.lower()
    assert "KRÓTKIE" in msg


def test_validate_scene_plan_defaults_lyrics_in_scene():
    """_validate_scene_plan adds lyrics_in_scene=[] when field is absent."""
    plan = {
        "overall_style": "worship",
        "master_style": "",
        "color_palette": [],
        "subtitle_style": {},
        "scenes": [
            {"start": 0.0, "end": 10.0, "visual_prompt": "test", "animate": False, "motion_prompt": ""},
        ],
    }
    validated = _validate_scene_plan(plan, 10.0)
    assert validated["scenes"][0]["lyrics_in_scene"] == []


class TestValidateScenePlanNewFields:
    """Tests that _validate_scene_plan defaults new hybrid sourcing fields."""

    def test_defaults_visual_source_to_type_ai(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {"start": 0.0, "end": 10.0, "section": "verse"},
            ]
        }
        result = _validate_scene_plan(plan, duration=10.0)
        assert result["scenes"][0]["visual_source"] == "TYPE_AI"

    def test_defaults_search_query_to_empty_string(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {"start": 0.0, "end": 10.0, "section": "verse"},
            ]
        }
        result = _validate_scene_plan(plan, duration=10.0)
        assert result["scenes"][0]["search_query"] == ""

    def test_preserves_existing_visual_source(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {
                    "start": 0.0,
                    "end": 10.0,
                    "section": "verse",
                    "visual_source": "TYPE_VIDEO_STOCK",
                    "search_query": "mountain sunrise",
                },
            ]
        }
        result = _validate_scene_plan(plan, duration=10.0)
        assert result["scenes"][0]["visual_source"] == "TYPE_VIDEO_STOCK"
        assert result["scenes"][0]["search_query"] == "mountain sunrise"

    def test_defaults_visual_prompt_to_empty_string_when_missing(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {
                    "start": 0.0,
                    "end": 10.0,
                    "section": "verse",
                    "visual_source": "TYPE_VIDEO_STOCK",
                    "search_query": "mountain sunrise",
                    # visual_prompt intentionally omitted
                },
            ]
        }
        result = _validate_scene_plan(plan, duration=10.0)
        assert result["scenes"][0]["visual_prompt"] == ""
