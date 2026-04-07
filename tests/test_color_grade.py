"""Tests for musicvid.pipeline.color_grade module."""

import os
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from musicvid.pipeline.color_grade import generate_builtin_lut, save_lut_as_cube, load_lut_file
from musicvid.pipeline.color_grade import get_ffmpeg_lut_filter
from musicvid.pipeline.color_grade import prepare_lut_ffmpeg_params
from musicvid.pipeline.color_grade import (
    get_curves_grade_filter, CURVES_GRADES, apply_global_color_grade,
)


class TestGenerateBuiltinLut:
    def test_warm_returns_correct_shape(self):
        lut = generate_builtin_lut("warm")
        assert lut.shape == (33, 33, 33, 3)

    def test_warm_returns_float_values_0_to_1(self):
        lut = generate_builtin_lut("warm")
        assert lut.dtype == np.float64 or lut.dtype == np.float32
        assert lut.min() >= 0.0
        assert lut.max() <= 1.0

    def test_cinematic_differs_from_warm(self):
        warm = generate_builtin_lut("warm")
        cinematic = generate_builtin_lut("cinematic")
        assert not np.array_equal(warm, cinematic)

    def test_cold_returns_correct_shape(self):
        lut = generate_builtin_lut("cold")
        assert lut.shape == (33, 33, 33, 3)

    def test_natural_returns_correct_shape(self):
        lut = generate_builtin_lut("natural")
        assert lut.shape == (33, 33, 33, 3)

    def test_faded_returns_correct_shape(self):
        lut = generate_builtin_lut("faded")
        assert lut.shape == (33, 33, 33, 3)

    def test_custom_size(self):
        lut = generate_builtin_lut("warm", size=17)
        assert lut.shape == (17, 17, 17, 3)

    def test_unknown_style_raises(self):
        with pytest.raises(ValueError, match="Unknown LUT style"):
            generate_builtin_lut("nonexistent")

    def test_warm_has_warm_shift(self):
        """Warm style should shift midtones toward red/yellow (R > B)."""
        lut = generate_builtin_lut("warm")
        mid = lut[16, 16, 16]
        assert mid[0] > mid[2], "Warm LUT should boost red over blue at midtones"

    def test_cold_has_cold_shift(self):
        """Cold style should shift toward blue (B > R at midtones)."""
        lut = generate_builtin_lut("cold")
        mid = lut[16, 16, 16]
        assert mid[2] > mid[0], "Cold LUT should boost blue over red at midtones"

    def test_faded_lifts_blacks(self):
        """Faded style should lift blacks (shadows not pure zero)."""
        lut = generate_builtin_lut("faded")
        black = lut[0, 0, 0]
        assert black.min() > 0.02, "Faded LUT should lift blacks above zero"


class TestSaveLutAsCube:
    def test_creates_cube_file(self, tmp_path):
        lut = generate_builtin_lut("warm")
        path = save_lut_as_cube(lut, str(tmp_path / "test.cube"))
        assert os.path.exists(path)
        assert path.endswith(".cube")

    def test_cube_file_has_correct_header(self, tmp_path):
        lut = generate_builtin_lut("warm", size=5)
        path = save_lut_as_cube(lut, str(tmp_path / "test.cube"))
        with open(path) as f:
            lines = f.readlines()
        assert any("LUT_3D_SIZE 5" in line for line in lines)
        assert any("TITLE" in line for line in lines)

    def test_cube_file_has_correct_data_count(self, tmp_path):
        size = 5
        lut = generate_builtin_lut("warm", size=size)
        path = save_lut_as_cube(lut, str(tmp_path / "test.cube"))
        with open(path) as f:
            lines = f.readlines()
        data_lines = [l for l in lines if l.strip() and not l.startswith("#") and not l.startswith("TITLE") and not l.startswith("LUT_3D_SIZE") and not l.startswith("DOMAIN")]
        assert len(data_lines) == size ** 3

    def test_values_in_0_to_1_range(self, tmp_path):
        lut = generate_builtin_lut("warm", size=5)
        path = save_lut_as_cube(lut, str(tmp_path / "test.cube"))
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("TITLE") or line.startswith("LUT_3D_SIZE") or line.startswith("DOMAIN"):
                    continue
                values = [float(v) for v in line.split()]
                assert len(values) == 3
                for v in values:
                    assert 0.0 <= v <= 1.0


class TestLoadLutFile:
    def test_valid_cube_file(self, tmp_path):
        cube_file = tmp_path / "grade.cube"
        cube_file.write_text("# dummy\nLUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1\n")
        result = load_lut_file(str(cube_file))
        assert result == str(cube_file)

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_lut_file("/nonexistent/path/grade.cube")

    def test_wrong_extension_raises(self, tmp_path):
        bad_file = tmp_path / "grade.txt"
        bad_file.write_text("not a lut")
        with pytest.raises(ValueError, match=".cube"):
            load_lut_file(str(bad_file))


class TestGetFfmpegLutFilter:
    def test_contains_lut3d(self):
        result = get_ffmpeg_lut_filter("/tmp/test.cube", 0.85)
        assert "lut3d" in result

    def test_contains_file_path(self):
        result = get_ffmpeg_lut_filter("/tmp/test.cube", 0.85)
        assert "/tmp/test.cube" in result

    def test_default_intensity(self):
        result = get_ffmpeg_lut_filter("/tmp/test.cube", 1.0)
        assert "lut3d" in result

    def test_partial_intensity_uses_blend(self):
        result = get_ffmpeg_lut_filter("/tmp/test.cube", 0.5)
        assert "0.5" in result or "0.50" in result

    def test_zero_intensity_returns_none(self):
        result = get_ffmpeg_lut_filter("/tmp/test.cube", 0.0)
        assert result is None


class TestPrepareLutFfmpegParams:
    def test_builtin_style_returns_ffmpeg_params(self):
        params = prepare_lut_ffmpeg_params(lut_style="warm", intensity=0.85)
        assert isinstance(params, list)
        assert "-vf" in params
        assert any("lut3d" in p for p in params)

    def test_custom_lut_file(self, tmp_path):
        cube_file = tmp_path / "custom.cube"
        cube_file.write_text("TITLE \"Test\"\nLUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1\n")
        params = prepare_lut_ffmpeg_params(lut_path=str(cube_file), intensity=1.0)
        assert "-vf" in params
        assert any(str(cube_file) in p for p in params)

    def test_custom_lut_overrides_style(self, tmp_path):
        """When both --lut and --lut-style given, --lut wins."""
        cube_file = tmp_path / "custom.cube"
        cube_file.write_text("TITLE \"Test\"\nLUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1\n")
        params = prepare_lut_ffmpeg_params(lut_path=str(cube_file), lut_style="warm", intensity=0.85)
        assert any(str(cube_file) in p for p in params)

    def test_zero_intensity_returns_empty(self):
        params = prepare_lut_ffmpeg_params(lut_style="warm", intensity=0.0)
        assert params == []

    def test_no_lut_no_style_returns_empty(self):
        params = prepare_lut_ffmpeg_params(intensity=0.85)
        assert params == []

    def test_all_styles_produce_valid_params(self):
        for style in ["warm", "cold", "cinematic", "natural", "faded"]:
            params = prepare_lut_ffmpeg_params(lut_style=style, intensity=0.85)
            assert "-vf" in params, f"Style '{style}' should produce valid ffmpeg params"

    def test_intensity_value_in_params(self):
        params = prepare_lut_ffmpeg_params(lut_style="warm", intensity=0.5)
        vf_idx = params.index("-vf")
        filter_str = params[vf_idx + 1]
        assert "0.50" in filter_str


class TestCurvesGrades:
    def test_all_grade_names_defined(self):
        for name in ["worship-warm", "teal-orange", "bleach", "natural"]:
            assert name in CURVES_GRADES

    def test_worship_warm_contains_curves(self):
        f = get_curves_grade_filter("worship-warm")
        assert "curves=" in f

    def test_teal_orange_contains_curves(self):
        f = get_curves_grade_filter("teal-orange")
        assert "curves=" in f

    def test_bleach_contains_eq(self):
        f = get_curves_grade_filter("bleach")
        assert "eq=" in f

    def test_natural_contains_eq(self):
        f = get_curves_grade_filter("natural")
        assert "eq=" in f

    def test_unknown_grade_defaults_to_worship_warm(self):
        f = get_curves_grade_filter("nonexistent")
        assert f == get_curves_grade_filter("worship-warm")

    def test_social_mode_adjusts_filter(self):
        full = get_curves_grade_filter("worship-warm", is_social=False)
        social = get_curves_grade_filter("worship-warm", is_social=True)
        assert full != social


class TestApplyGlobalColorGrade:
    @patch("musicvid.pipeline.color_grade.subprocess")
    def test_runs_ffmpeg_with_curves(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        result = apply_global_color_grade("/tmp/in.mp4", "/tmp/out.mp4", "worship-warm")
        assert result is True
        mock_subprocess.run.assert_called_once()
        cmd = mock_subprocess.run.call_args[0][0]
        assert "ffmpeg" in cmd[0]
        assert "-vf" in cmd

    @patch("musicvid.pipeline.color_grade.subprocess")
    def test_ffmpeg_failure_returns_false(self, mock_subprocess):
        mock_subprocess.run.side_effect = Exception("ffmpeg crashed")
        result = apply_global_color_grade("/tmp/in.mp4", "/tmp/out.mp4", "worship-warm")
        assert result is False

    @patch("musicvid.pipeline.color_grade.subprocess")
    def test_social_flag_passes_social_filter(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        apply_global_color_grade("/tmp/in.mp4", "/tmp/out.mp4", "worship-warm", is_social=True)
        cmd = mock_subprocess.run.call_args[0][0]
        vf_idx = cmd.index("-vf")
        vf_str = cmd[vf_idx + 1]
        assert "1.05" in vf_str or "1.15" in vf_str
