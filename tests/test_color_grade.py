"""Tests for musicvid.pipeline.color_grade module."""

import numpy as np
import pytest

from musicvid.pipeline.color_grade import generate_builtin_lut


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
