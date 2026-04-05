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
