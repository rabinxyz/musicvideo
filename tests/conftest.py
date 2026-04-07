"""Shared test fixtures for musicvid tests."""

import pytest


@pytest.fixture
def sample_analysis():
    """Sample audio analysis output for testing downstream stages."""
    return {
        "lyrics": [
            {"start": 0.5, "end": 2.0, "text": "Amazing grace how sweet the sound",
             "words": [
                 {"word": "Amazing", "start": 0.5, "end": 0.9},
                 {"word": "grace", "start": 0.9, "end": 1.2},
                 {"word": "how", "start": 1.2, "end": 1.4},
                 {"word": "sweet", "start": 1.4, "end": 1.6},
                 {"word": "the", "start": 1.6, "end": 1.7},
                 {"word": "sound", "start": 1.7, "end": 2.0},
             ]},
            {"start": 2.5, "end": 4.0, "text": "That saved a wretch like me",
             "words": [
                 {"word": "That", "start": 2.5, "end": 2.7},
                 {"word": "saved", "start": 2.7, "end": 3.0},
                 {"word": "a", "start": 3.0, "end": 3.1},
                 {"word": "wretch", "start": 3.1, "end": 3.5},
                 {"word": "like", "start": 3.5, "end": 3.7},
                 {"word": "me", "start": 3.7, "end": 4.0},
             ]},
        ],
        "beats": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        "bpm": 120.0,
        "duration": 10.0,
        "sections": [
            {"label": "intro", "start": 0.0, "end": 2.0},
            {"label": "verse", "start": 2.0, "end": 6.0},
            {"label": "outro", "start": 6.0, "end": 10.0},
        ],
        "mood_energy": "contemplative",
        "language": "en",
        "energy_peaks": [1.0, 3.0, 5.0],
        "energy_curve": [
            [0.0, 0.1], [0.5, 0.2], [1.0, 0.4], [1.5, 0.3],
            [2.0, 0.5], [2.5, 0.6], [3.0, 0.8], [3.5, 0.9],
            [4.0, 1.0], [4.5, 0.9], [5.0, 0.7], [5.5, 0.5],
            [6.0, 0.3], [6.5, 0.2], [7.0, 0.15], [7.5, 0.1],
            [8.0, 0.1], [8.5, 0.05], [9.0, 0.05], [9.5, 0.02],
        ],
        "energy_mean": 0.42,
    }


@pytest.fixture
def sample_scene_plan():
    """Sample director output for testing downstream stages."""
    return {
        "overall_style": "contemplative",
        "master_style": "Consistent warm cinematic grade, golden amber tones",
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
                "visual_prompt": "mountain sunrise golden light peaceful morning",
                "motion": "slow_zoom_in",
                "transition": "fade_black",
                "overlay": "none",
                "animate": False,
                "motion_prompt": "",
            },
            {
                "section": "verse",
                "start": 2.0,
                "end": 6.0,
                "visual_prompt": "calm water reflection forest lake serene",
                "motion": "slow_zoom_out",
                "transition": "crossfade",
                "overlay": "light_rays",
                "animate": False,
                "motion_prompt": "",
            },
            {
                "section": "outro",
                "start": 6.0,
                "end": 10.0,
                "visual_prompt": "sunset clouds golden horizon peaceful",
                "motion": "pan_left",
                "transition": "fade_black",
                "overlay": "particles",
                "animate": False,
                "motion_prompt": "",
            },
        ],
    }


@pytest.fixture
def tmp_output(tmp_path):
    """Temporary output directory for tests."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = output_dir / "tmp"
    tmp_dir.mkdir()
    return output_dir
