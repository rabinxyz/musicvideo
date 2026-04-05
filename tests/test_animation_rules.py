# tests/test_animation_rules.py
import pytest
from musicvid.musicvid import get_section_priority, enforce_animation_rules


class TestGetSectionPriority:
    def test_chorus_highest(self):
        assert get_section_priority("chorus") == 5

    def test_bridge(self):
        assert get_section_priority("bridge") == 4

    def test_verse(self):
        assert get_section_priority("verse") == 3

    def test_intro(self):
        assert get_section_priority("intro") == 2

    def test_outro_zero(self):
        assert get_section_priority("outro") == 0

    def test_unknown_section_default(self):
        assert get_section_priority("interlude") == 1

    def test_empty_string_default(self):
        assert get_section_priority("") == 1


def _make_scene(section, animate, start=0.0, end=10.0):
    return {"section": section, "animate": animate, "start": start, "end": end}


class TestEnforceAnimationRules:

    # ---- adjacency ----

    def test_adjacent_animated_lower_priority_disabled(self):
        # 8 scenes so max(1, 8//4) = 2; after adjacency pass: chorus[0] and chorus[3] remain
        scenes = [
            _make_scene("chorus", True, 0, 10),
            _make_scene("verse", True, 10, 20),
            _make_scene("verse", False, 20, 30),
            _make_scene("chorus", True, 30, 40),
            _make_scene("verse", False, 40, 50),
            _make_scene("verse", False, 50, 60),
            _make_scene("verse", False, 60, 70),
            _make_scene("verse", False, 70, 80),
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is True   # chorus keeps
        assert result[1]["animate"] is False  # verse loses to adjacent chorus
        assert result[2]["animate"] is False  # already false
        assert result[3]["animate"] is True   # chorus keeps (non-adjacent now, within cap)

    def test_two_adjacent_same_priority_second_disabled(self):
        scenes = [
            _make_scene("verse", True, 0, 10),
            _make_scene("verse", True, 10, 20),
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is True
        assert result[1]["animate"] is False

    def test_non_adjacent_both_keep_animation(self):
        # 8 scenes: max(1, 8//4) = 2 — both non-adjacent animated scenes should be kept
        scenes = [
            _make_scene("chorus", True, 0, 10),
            _make_scene("verse", False, 10, 20),
            _make_scene("bridge", True, 20, 30),
            _make_scene("verse", False, 30, 40),
            _make_scene("verse", False, 40, 50),
            _make_scene("verse", False, 50, 60),
            _make_scene("verse", False, 60, 70),
            _make_scene("verse", False, 70, 80),
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is True
        assert result[2]["animate"] is True

    # ---- max count ----

    def test_max_animated_25_percent(self):
        # 20 scenes, 8 animated → max 5 (20 // 4)
        scenes = []
        for i in range(20):
            animate = i < 8
            scenes.append(_make_scene("verse", animate, i * 10, (i + 1) * 10))
        result = enforce_animation_rules(scenes)
        animated = [s for s in result if s["animate"]]
        assert len(animated) <= 5

    def test_min_one_animated_allowed(self):
        # 3 scenes → max(1, 3//4) = max(1,0) = 1
        scenes = [
            _make_scene("chorus", True, 0, 10),
            _make_scene("verse", False, 10, 20),
            _make_scene("verse", False, 20, 30),
        ]
        result = enforce_animation_rules(scenes)
        assert sum(1 for s in result if s["animate"]) == 1

    def test_excess_animated_keeps_highest_priority(self):
        # 8 scenes, 3 animated (max 2) — keep the two with highest section priority
        scenes = [
            _make_scene("verse", True, 0, 10),    # priority 3 — should be dropped
            _make_scene("verse", False, 10, 20),
            _make_scene("chorus", True, 20, 30),  # priority 5 — keep
            _make_scene("verse", False, 30, 40),
            _make_scene("bridge", True, 40, 50),  # priority 4 — keep
            _make_scene("verse", False, 50, 60),
            _make_scene("verse", False, 60, 70),
            _make_scene("verse", False, 70, 80),
        ]
        result = enforce_animation_rules(scenes)
        animated = [s for s in result if s["animate"]]
        assert len(animated) == 2
        sections = {s["section"] for s in animated}
        assert "chorus" in sections
        assert "bridge" in sections

    # ---- short scenes ----

    def test_short_scene_disabled(self):
        scenes = [
            _make_scene("chorus", True, 0, 4),  # 4s < 6s
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is False

    def test_exactly_6s_allowed(self):
        scenes = [
            _make_scene("chorus", True, 0, 6),  # exactly 6s
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is True

    def test_short_scene_under_6s_disabled(self):
        scenes = [
            _make_scene("chorus", True, 0.0, 5.9),  # 5.9s < 6s
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is False

    # ---- outro ----

    def test_outro_never_animated(self):
        scenes = [
            _make_scene("outro", True, 0, 20),
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is False

    # ---- priority tie-breaking ----

    def test_priority_chorus_beats_verse_when_adjacent(self):
        scenes = [
            _make_scene("verse", True, 0, 10),
            _make_scene("chorus", True, 10, 20),
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is False  # verse loses
        assert result[1]["animate"] is True   # chorus wins

    # ---- returns list ----

    def test_returns_list(self):
        scenes = [_make_scene("verse", False, 0, 10)]
        result = enforce_animation_rules(scenes)
        assert isinstance(result, list)

    # ---- log output ----

    def test_short_scene_prints_warning(self, capsys):
        scenes = [_make_scene("chorus", True, 0, 4)]
        enforce_animation_rules(scenes)
        captured = capsys.readouterr()
        assert "WARN" in captured.out or "za krótka" in captured.out

    def test_prints_animation_plan_summary(self, capsys):
        scenes = [
            _make_scene("chorus", True, 0, 10),
            _make_scene("verse", False, 10, 20),
        ]
        enforce_animation_rules(scenes)
        captured = capsys.readouterr()
        assert "Plan animacji Runway" in captured.out
