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

    def test_last_scene_has_cut_transition(self):
        scenes = self._make_scenes(["verse", "chorus"])
        result = _assign_dynamic_transitions(scenes, bpm=84.0)
        assert result[-1]["transition_to_next"] == "cut"

    def test_unknown_pair_defaults_to_cross_dissolve(self):
        scenes = self._make_scenes(["intro", "outro"])
        result = _assign_dynamic_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "cross_dissolve"


from musicvid.musicvid import _assign_reel_transitions, _REEL_TRANSITIONS_MAP


class TestReelTransitions:
    def _make_scenes(self, sections):
        scenes = []
        t = 0.0
        for s in sections:
            scenes.append({"section": s, "start": t, "end": t + 10.0})
            t += 10.0
        return scenes

    def test_verse_to_chorus_is_slide_up(self):
        scenes = self._make_scenes(["verse", "chorus"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "slide_up"

    def test_chorus_to_verse_is_zoom_in_hard(self):
        scenes = self._make_scenes(["chorus", "verse"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "zoom_in_hard"

    def test_chorus_to_chorus_is_wipe_right(self):
        scenes = self._make_scenes(["chorus", "chorus"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "wipe_right"

    def test_verse_to_verse_is_slide_left(self):
        scenes = self._make_scenes(["verse", "verse"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "slide_left"

    def test_bridge_to_chorus_is_slide_up(self):
        scenes = self._make_scenes(["bridge", "chorus"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "slide_up"

    def test_last_scene_has_no_transition(self):
        scenes = self._make_scenes(["verse", "chorus"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert "transition_to_next" not in result[-1]


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


class TestEnergyReactiveTransitions:
    def test_high_energy_gives_cut(self):
        from musicvid.musicvid import _assign_dynamic_transitions
        from musicvid.pipeline.energy_reactor import EnergyReactor

        analysis = {
            "energy_curve": [[0.0, 0.3], [5.0, 0.9], [10.0, 0.5]],
            "energy_mean": 0.6,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)

        scenes = [
            {"section": "verse", "start": 0.0, "end": 5.0},
            {"section": "chorus", "start": 5.0, "end": 10.0},
        ]
        _assign_dynamic_transitions(scenes, 120.0, reactor=reactor)
        assert scenes[0].get("transition_to_next") == "cut"

    def test_low_energy_gives_fade(self):
        from musicvid.musicvid import _assign_dynamic_transitions
        from musicvid.pipeline.energy_reactor import EnergyReactor

        analysis = {
            "energy_curve": [[0.0, 0.1], [5.0, 0.25], [10.0, 0.1]],
            "energy_mean": 0.15,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)

        scenes = [
            {"section": "intro", "start": 0.0, "end": 5.0},
            {"section": "verse", "start": 5.0, "end": 10.0},
        ]
        _assign_dynamic_transitions(scenes, 120.0, reactor=reactor)
        assert scenes[0].get("transition_to_next") == "fade"

    def test_no_reactor_uses_existing_map(self):
        from musicvid.musicvid import _assign_dynamic_transitions

        scenes = [
            {"section": "verse", "start": 0.0, "end": 5.0},
            {"section": "chorus", "start": 5.0, "end": 10.0},
        ]
        _assign_dynamic_transitions(scenes, 120.0)
        assert "transition_to_next" in scenes[0]

    def test_last_scene_gets_cut(self):
        from musicvid.musicvid import _assign_dynamic_transitions
        from musicvid.pipeline.energy_reactor import EnergyReactor

        analysis = {
            "energy_curve": [[0.0, 0.5], [10.0, 0.5]],
            "energy_mean": 0.5,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)

        scenes = [
            {"section": "verse", "start": 0.0, "end": 5.0},
            {"section": "chorus", "start": 5.0, "end": 10.0},
        ]
        _assign_dynamic_transitions(scenes, 120.0, reactor=reactor)
        assert scenes[-1]["transition_to_next"] == "cut"


class TestSocialReelsNoWow:
    """Verify social reel AssemblyJobs have wow_config=None."""

    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.select_social_clips")
    @patch("musicvid.musicvid._validate_clip_manifest")
    @patch("musicvid.musicvid._filter_manifest_to_clip")
    @patch("musicvid.musicvid._filter_scene_plan_to_clip")
    @patch("musicvid.musicvid._filter_analysis_to_clip")
    @patch("musicvid.musicvid.load_cache")
    @patch("musicvid.musicvid.save_cache")
    def test_social_job_wow_config_is_none(
        self, mock_save, mock_load, mock_filter_analysis, mock_filter_plan,
        mock_filter_manifest, mock_validate, mock_select_social, mock_assemble,
        tmp_path,
    ):
        from musicvid.musicvid import _run_preset_mode

        mock_load.return_value = None
        mock_select_social.return_value = {
            "clips": [
                {"id": 1, "start": 0.0, "end": 30.0, "section": "verse", "reason": "test"},
            ]
        }
        mock_filter_analysis.return_value = {"beats": [], "bpm": 120, "sections": [], "lyrics": []}
        mock_filter_plan.return_value = {"scenes": [{"section": "verse", "start": 0, "end": 30, "motion": "static"}]}
        mock_filter_manifest.return_value = [{"scene_index": 0, "video_path": "/fake.mp4", "start": 0, "end": 30}]
        mock_validate.side_effect = lambda cm, fm: cm

        analysis = {"beats": [1.0], "bpm": 120, "sections": [], "lyrics": [], "energy_peaks": []}
        scene_plan = {"scenes": [{"section": "verse", "start": 0, "end": 30}]}
        fetch_manifest = [{"scene_index": 0, "video_path": "/fake.mp4", "start": 0, "end": 30}]

        wow = {"enabled": True, "zoom_punch": True, "light_flash": True}

        _run_preset_mode(
            preset="social",
            reel_duration=30,
            analysis=analysis,
            scene_plan=scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_dir=tmp_path,
            stem="test",
            font="/fake/font.ttf",
            effects="minimal",
            cache_dir=tmp_path / "cache",
            new=False,
            wow_config=wow,
        )

        # Single social job goes through sequential path calling assemble_video directly
        assert mock_assemble.called
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["wow_config"] is None, (
            f"Expected wow_config=None for social reel, got {call_kwargs['wow_config']}"
        )
