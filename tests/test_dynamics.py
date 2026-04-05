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
