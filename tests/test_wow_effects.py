"""Tests for WOW effects FFmpeg post-processing."""

import unittest
from unittest.mock import patch, MagicMock, call


class TestWowConfig(unittest.TestCase):
    def test_default_wow_config_has_required_keys(self):
        from musicvid.pipeline.wow_effects import default_wow_config
        cfg = default_wow_config()
        for key in ("enabled", "zoom_punch", "light_flash", "dynamic_grade",
                    "dynamic_vignette", "motion_blur", "particles"):
            self.assertIn(key, cfg, f"Missing key: {key}")

    def test_default_wow_config_enabled_defaults(self):
        from musicvid.pipeline.wow_effects import default_wow_config
        cfg = default_wow_config()
        self.assertTrue(cfg["enabled"])
        self.assertTrue(cfg["zoom_punch"])
        self.assertTrue(cfg["light_flash"])
        self.assertTrue(cfg["dynamic_grade"])
        self.assertTrue(cfg["dynamic_vignette"])
        self.assertTrue(cfg["motion_blur"])
        self.assertFalse(cfg["particles"])


class TestBuildFilterChain(unittest.TestCase):
    def test_returns_none_when_disabled(self):
        from musicvid.pipeline.wow_effects import build_ffmpeg_filter_chain
        result = build_ffmpeg_filter_chain(
            analysis={"sections": [], "beats": [], "duration": 60.0},
            scene_plan={"scenes": [], "overall_style": "worship"},
            wow_config={"enabled": False},
        )
        self.assertIsNone(result)

    def test_returns_none_when_all_effects_off(self):
        from musicvid.pipeline.wow_effects import build_ffmpeg_filter_chain
        wow_config = {
            "enabled": True,
            "zoom_punch": False,
            "light_flash": False,
            "dynamic_grade": False,
            "dynamic_vignette": False,
            "motion_blur": False,
            "particles": False,
        }
        result = build_ffmpeg_filter_chain(
            analysis={"sections": [], "beats": [], "duration": 60.0},
            scene_plan={"scenes": [], "overall_style": "worship"},
            wow_config=wow_config,
        )
        self.assertIsNone(result)

    def test_returns_string_when_zoom_punch_enabled(self):
        import musicvid.pipeline.wow_effects as wm
        original = wm.ENABLE_ZOOMPAN
        try:
            wm.ENABLE_ZOOMPAN = True
            from musicvid.pipeline.wow_effects import build_ffmpeg_filter_chain
            analysis = {
                "sections": [{"label": "chorus", "start": 10.0, "end": 30.0}],
                "beats": [0.5, 1.0, 1.5, 2.0, 10.5, 11.0, 11.5, 12.0,
                          12.5, 13.0, 13.5, 14.0, 14.5, 15.0, 15.5, 16.0],
                "duration": 60.0,
            }
            wow_config = {
                "enabled": True, "zoom_punch": True, "light_flash": False,
                "dynamic_grade": False, "dynamic_vignette": False,
                "motion_blur": False, "particles": False,
            }
            result = build_ffmpeg_filter_chain(
                analysis=analysis,
                scene_plan={"scenes": [], "overall_style": "worship"},
                wow_config=wow_config,
            )
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)
        finally:
            wm.ENABLE_ZOOMPAN = original

    def test_zoom_punch_skipped_when_enable_zoompan_false(self):
        import musicvid.pipeline.wow_effects as wm
        original = wm.ENABLE_ZOOMPAN
        try:
            wm.ENABLE_ZOOMPAN = False
            from musicvid.pipeline.wow_effects import build_ffmpeg_filter_chain
            analysis = {
                "sections": [{"label": "chorus", "start": 2.0, "end": 8.0}],
                "beats": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0,
                          4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0],
                "duration": 10.0,
            }
            wow_config = {
                "enabled": True, "zoom_punch": True, "light_flash": False,
                "dynamic_grade": False, "dynamic_vignette": False,
                "motion_blur": False, "particles": False,
            }
            result = build_ffmpeg_filter_chain(
                analysis=analysis,
                scene_plan={"scenes": [], "overall_style": "worship"},
                wow_config=wow_config,
            )
            self.assertIsNone(result)
        finally:
            wm.ENABLE_ZOOMPAN = original

    def test_motion_blur_adds_tblend(self):
        from musicvid.pipeline.wow_effects import build_ffmpeg_filter_chain
        wow_config = {
            "enabled": True, "zoom_punch": False, "light_flash": False,
            "dynamic_grade": False, "dynamic_vignette": False,
            "motion_blur": True, "particles": False,
        }
        result = build_ffmpeg_filter_chain(
            analysis={"sections": [], "beats": [], "duration": 60.0},
            scene_plan={},
            wow_config=wow_config,
        )
        self.assertIsNotNone(result)
        self.assertIn("tblend", result)


class TestZoomPunchFilter(unittest.TestCase):
    def test_returns_none_when_no_chorus(self):
        from musicvid.pipeline.wow_effects import _build_zoom_punch_filter
        sections = [{"label": "verse", "start": 0.0, "end": 60.0}]
        beats = [0.5, 1.0, 1.5, 2.0]
        result = _build_zoom_punch_filter(beats, sections, 1920, 1080)
        self.assertIsNone(result)

    def test_returns_none_when_no_beats_in_chorus(self):
        from musicvid.pipeline.wow_effects import _build_zoom_punch_filter
        sections = [{"label": "chorus", "start": 50.0, "end": 70.0}]
        beats = [0.5, 1.0, 1.5, 2.0]  # beats don't fall in chorus range
        result = _build_zoom_punch_filter(beats, sections, 1920, 1080)
        self.assertIsNone(result)

    def test_returns_scale_and_crop_filters(self):
        from musicvid.pipeline.wow_effects import _build_zoom_punch_filter
        sections = [{"label": "chorus", "start": 10.0, "end": 30.0}]
        beats = [10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5,
                 14.0, 14.5, 15.0, 15.5, 16.0, 16.5, 17.0, 17.5]
        result = _build_zoom_punch_filter(beats, sections, 1920, 1080)
        self.assertIsNotNone(result)
        self.assertIn("scale=", result)
        self.assertIn("crop=", result)
        self.assertIn("1920", result)
        self.assertIn("1080", result)

    def test_zoom_factor_is_0_08(self):
        from musicvid.pipeline.wow_effects import _build_zoom_punch_filter
        sections = [{"label": "chorus", "start": 0.0, "end": 30.0}]
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        result = _build_zoom_punch_filter(beats, sections, 1920, 1080)
        self.assertIsNotNone(result)
        self.assertIn("0.08", result)


class TestLightFlashFilter(unittest.TestCase):
    def test_returns_none_when_no_chorus(self):
        from musicvid.pipeline.wow_effects import _build_light_flash_filter
        sections = [{"label": "verse", "start": 0.0, "end": 60.0}]
        result = _build_light_flash_filter(sections)
        self.assertIsNone(result)

    def test_returns_geq_filter(self):
        from musicvid.pipeline.wow_effects import _build_light_flash_filter
        sections = [
            {"label": "verse", "start": 0.0, "end": 20.0},
            {"label": "chorus", "start": 20.0, "end": 40.0},
        ]
        result = _build_light_flash_filter(sections)
        self.assertIsNotNone(result)
        self.assertIn("geq=", result)
        self.assertIn("20.000", result)

    def test_multiple_chorus_sections_included(self):
        from musicvid.pipeline.wow_effects import _build_light_flash_filter
        sections = [
            {"label": "chorus", "start": 20.0, "end": 40.0},
            {"label": "verse", "start": 40.0, "end": 60.0},
            {"label": "chorus", "start": 60.0, "end": 80.0},
        ]
        result = _build_light_flash_filter(sections)
        self.assertIsNotNone(result)
        self.assertIn("20.000", result)
        self.assertIn("60.000", result)


class TestColorGradeFilter(unittest.TestCase):
    def test_returns_none_when_no_sections(self):
        from musicvid.pipeline.wow_effects import _build_color_grade_filter
        result = _build_color_grade_filter([])
        self.assertIsNone(result)

    def test_chorus_has_higher_saturation(self):
        from musicvid.pipeline.wow_effects import _build_color_grade_filter
        sections = [{"label": "chorus", "start": 20.0, "end": 40.0}]
        result = _build_color_grade_filter(sections)
        self.assertIsNotNone(result)
        self.assertIn("saturation=1.15", result)
        self.assertIn("contrast=1.15", result)

    def test_verse_has_lower_saturation(self):
        from musicvid.pipeline.wow_effects import _build_color_grade_filter
        sections = [{"label": "verse", "start": 0.0, "end": 20.0}]
        result = _build_color_grade_filter(sections)
        self.assertIsNotNone(result)
        self.assertIn("saturation=0.85", result)
        self.assertIn("contrast=1.05", result)

    def test_uses_enable_expression(self):
        from musicvid.pipeline.wow_effects import _build_color_grade_filter
        sections = [{"label": "chorus", "start": 20.0, "end": 40.0}]
        result = _build_color_grade_filter(sections)
        self.assertIn("enable=", result)
        self.assertIn("between(t,20.000,40.000)", result)


class TestVignetteFilter(unittest.TestCase):
    def test_returns_none_when_no_sections(self):
        from musicvid.pipeline.wow_effects import _build_vignette_filter
        result = _build_vignette_filter([])
        self.assertIsNone(result)

    def test_chorus_has_smaller_angle(self):
        from musicvid.pipeline.wow_effects import _build_vignette_filter
        sections = [{"label": "chorus", "start": 10.0, "end": 30.0}]
        result = _build_vignette_filter(sections)
        self.assertIsNotNone(result)
        self.assertIn("a=0.3", result)

    def test_verse_has_larger_angle(self):
        from musicvid.pipeline.wow_effects import _build_vignette_filter
        sections = [{"label": "verse", "start": 0.0, "end": 10.0}]
        result = _build_vignette_filter(sections)
        self.assertIsNotNone(result)
        self.assertIn("a=0.6", result)


class TestApplyWowEffects(unittest.TestCase):
    def test_noop_when_disabled(self):
        from musicvid.pipeline.wow_effects import apply_wow_effects
        with patch("musicvid.pipeline.wow_effects.subprocess") as mock_sub:
            apply_wow_effects(
                video_path="/fake/out.mp4",
                analysis={"sections": [], "beats": [], "duration": 10.0},
                scene_plan={"scenes": [], "overall_style": "worship"},
                wow_config={"enabled": False},
            )
            mock_sub.run.assert_not_called()

    def test_calls_ffmpeg_with_filter_chain(self):
        from musicvid.pipeline.wow_effects import apply_wow_effects
        analysis = {
            "sections": [{"label": "chorus", "start": 2.0, "end": 8.0}],
            "beats": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0,
                      4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0],
            "duration": 10.0,
        }
        wow_config = {
            "enabled": True, "zoom_punch": False, "light_flash": False,
            "dynamic_grade": False, "dynamic_vignette": False,
            "motion_blur": True, "particles": False,
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("musicvid.pipeline.wow_effects.subprocess") as mock_sub, \
             patch("musicvid.pipeline.wow_effects.shutil.move"), \
             patch("musicvid.pipeline.wow_effects.tempfile.mkstemp",
                   return_value=(0, "/tmp/wow_tmp.mp4")), \
             patch("musicvid.pipeline.wow_effects.os.close"), \
             patch("musicvid.pipeline.wow_effects.os.path.exists", return_value=False):
            mock_sub.run.return_value = mock_result
            apply_wow_effects(
                video_path="/fake/out.mp4",
                analysis=analysis,
                scene_plan={"scenes": [], "overall_style": "worship"},
                wow_config=wow_config,
            )
            mock_sub.run.assert_called_once()
            cmd = mock_sub.run.call_args[0][0]
            self.assertIn("ffmpeg", cmd)
            self.assertIn("-vf", cmd)
            self.assertIn("/fake/out.mp4", cmd)

    def test_raises_on_ffmpeg_failure(self):
        from musicvid.pipeline.wow_effects import apply_wow_effects
        analysis = {
            "sections": [{"label": "chorus", "start": 2.0, "end": 8.0}],
            "beats": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
            "duration": 10.0,
        }
        wow_config = {
            "enabled": True, "zoom_punch": False, "light_flash": False,
            "dynamic_grade": False, "dynamic_vignette": False,
            "motion_blur": True, "particles": False,
        }
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "ffmpeg error"
        with patch("musicvid.pipeline.wow_effects.subprocess") as mock_sub, \
             patch("musicvid.pipeline.wow_effects.tempfile.mkstemp",
                   return_value=(0, "/tmp/wow_tmp.mp4")), \
             patch("musicvid.pipeline.wow_effects.os.close"), \
             patch("musicvid.pipeline.wow_effects.os.path.exists", return_value=True), \
             patch("musicvid.pipeline.wow_effects.os.unlink"):
            mock_sub.run.return_value = mock_result
            with self.assertRaises(RuntimeError):
                apply_wow_effects(
                    video_path="/fake/out.mp4",
                    analysis=analysis,
                    scene_plan={"scenes": [], "overall_style": "worship"},
                    wow_config=wow_config,
                )


if __name__ == "__main__":
    unittest.main()
