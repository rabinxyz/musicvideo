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
