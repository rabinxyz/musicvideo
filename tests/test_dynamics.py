"""Tests for Spec 4: Music Video Dynamics."""
import pytest
from musicvid.musicvid import _enforce_motion_variety


class TestEnforceMotionVariety:
    def test_no_same_motion_twice_in_a_row(self):
        scenes = [
            {"section": "verse", "motion": "slow_zoom_in"},
            {"section": "verse", "motion": "slow_zoom_in"},
            {"section": "verse", "motion": "pan_left"},
        ]
        result = _enforce_motion_variety(scenes)
        motions = [s["motion"] for s in result]
        for i in range(len(motions) - 1):
            assert motions[i] != motions[i + 1], f"Adjacent motions equal at {i}: {motions[i]}"

    def test_no_change_when_already_varied(self):
        scenes = [
            {"section": "verse", "motion": "slow_zoom_in"},
            {"section": "verse", "motion": "pan_left"},
            {"section": "chorus", "motion": "slow_zoom_out"},
        ]
        result = _enforce_motion_variety(scenes)
        motions = [s["motion"] for s in result]
        assert motions == ["slow_zoom_in", "pan_left", "slow_zoom_out"]

    def test_single_scene_unchanged(self):
        scenes = [{"section": "intro", "motion": "static"}]
        result = _enforce_motion_variety(scenes)
        assert result[0]["motion"] == "static"

    def test_uses_section_allowed_motions(self):
        scenes = [
            {"section": "outro", "motion": "slow_zoom_out"},
            {"section": "outro", "motion": "slow_zoom_out"},
        ]
        result = _enforce_motion_variety(scenes)
        # After dedup, adjacent motions must differ
        assert result[0]["motion"] != result[1]["motion"]


from musicvid.musicvid import _assign_dynamic_transitions


class TestAssignDynamicTransitions:
    def _make_scenes(self, sections):
        scenes = []
        t = 0.0
        for s in sections:
            scenes.append({"section": s, "start": t, "end": t + 10.0, "transition": "crossfade"})
            t += 10.0
        return scenes

    def test_verse_to_chorus_is_cut(self):
        scenes = self._make_scenes(["verse", "chorus"])
        result = _assign_dynamic_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "cut"

    def test_chorus_to_verse_is_fade(self):
        scenes = self._make_scenes(["chorus", "verse"])
        result = _assign_dynamic_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "fade"

    def test_bridge_to_chorus_is_cut(self):
        scenes = self._make_scenes(["bridge", "chorus"])
        result = _assign_dynamic_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "cut"

    def test_intro_to_verse_is_cross_dissolve(self):
        scenes = self._make_scenes(["intro", "verse"])
        result = _assign_dynamic_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "cross_dissolve"

    def test_chorus_to_chorus_is_dip_white(self):
        scenes = self._make_scenes(["chorus", "chorus"])
        result = _assign_dynamic_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "dip_white"

    def test_last_scene_has_no_transition_to_next(self):
        scenes = self._make_scenes(["verse", "chorus"])
        result = _assign_dynamic_transitions(scenes, bpm=84.0)
        assert "transition_to_next" not in result[-1]

    def test_unknown_pair_defaults_to_cross_dissolve(self):
        scenes = self._make_scenes(["intro", "outro"])
        result = _assign_dynamic_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "cross_dissolve"


from unittest.mock import patch, MagicMock


class TestSectionFontSizes:
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_chorus_uses_large_font(self, mock_text_clip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        lyrics = [{"start": 5.0, "end": 7.0, "text": "Hallelujah"}]
        sections = [{"label": "chorus", "start": 0.0, "end": 10.0}]
        subtitle_style = {"font_size": 54, "color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, subtitle_style, (1920, 1080), sections=sections)

        call_kwargs = mock_text_clip.call_args[1]
        assert call_kwargs["font_size"] == 64, f"Expected 64 for chorus, got {call_kwargs['font_size']}"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_verse_uses_standard_font(self, mock_text_clip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        lyrics = [{"start": 5.0, "end": 7.0, "text": "Amazing grace"}]
        sections = [{"label": "verse", "start": 0.0, "end": 10.0}]
        subtitle_style = {"font_size": 54, "color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, subtitle_style, (1920, 1080), sections=sections)

        call_kwargs = mock_text_clip.call_args[1]
        assert call_kwargs["font_size"] == 54, f"Expected 54 for verse, got {call_kwargs['font_size']}"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_no_sections_uses_style_font_size(self, mock_text_clip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        lyrics = [{"start": 1.0, "end": 3.0, "text": "Hello"}]
        subtitle_style = {"font_size": 48, "color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, subtitle_style, (1920, 1080), sections=None)

        call_kwargs = mock_text_clip.call_args[1]
        assert call_kwargs["font_size"] == 48


from musicvid.musicvid import _snap_to_downbeat


class TestSnapToDownbeat:
    def test_returns_nearest_downbeat_within_window(self):
        # |44.3-44.0|=0.3, |44.3-44.7|=0.4 — both within 0.8, 44.0 is closer
        result = _snap_to_downbeat(44.3, [44.0, 44.7], window=0.8)
        assert result == 44.0

    def test_returns_t_when_all_outside_window(self):
        # |10.0-8.0|=2.0 > 0.8, |10.0-13.0|=3.0 > 0.8 — both outside window
        result = _snap_to_downbeat(10.0, [8.0, 13.0], window=0.8)
        assert result == 10.0

    def test_returns_exact_match(self):
        result = _snap_to_downbeat(5.0, [4.0, 5.0, 6.0], window=0.8)
        assert result == 5.0

    def test_empty_downbeats_returns_t(self):
        result = _snap_to_downbeat(10.0, [], window=0.8)
        assert result == 10.0
