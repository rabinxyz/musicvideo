"""Tests for EnergyReactor — energy-reactive effect parameter provider."""

import pytest

from musicvid.pipeline.energy_reactor import EnergyReactor


class TestGetEnergy:
    """Test energy interpolation at arbitrary time t."""

    def test_exact_match(self):
        """Energy at an exact curve point returns that value."""
        analysis = {"energy_curve": [[0.0, 0.5], [1.0, 0.8], [2.0, 0.3]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_energy(1.0) == pytest.approx(0.8)

    def test_interpolation(self):
        """Energy between two points is linearly interpolated."""
        analysis = {"energy_curve": [[0.0, 0.0], [2.0, 1.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_energy(1.0) == pytest.approx(0.5)

    def test_before_first_point(self):
        """Energy before the first curve point returns first value."""
        analysis = {"energy_curve": [[1.0, 0.6], [2.0, 0.8]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_energy(0.0) == pytest.approx(0.6)

    def test_after_last_point(self):
        """Energy after the last curve point returns last value."""
        analysis = {"energy_curve": [[0.0, 0.3], [1.0, 0.7]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_energy(5.0) == pytest.approx(0.7)

    def test_empty_curve(self):
        """Empty energy_curve returns 0.0."""
        analysis = {"energy_curve": []}
        reactor = EnergyReactor(analysis)
        assert reactor.get_energy(1.0) == pytest.approx(0.0)


class TestGetSection:
    """Test section lookup at time t."""

    def test_correct_section(self):
        """Returns the correct section label for a given time."""
        analysis = {
            "energy_curve": [[0.0, 0.5]],
            "sections": [
                {"label": "intro", "start": 0.0, "end": 10.0},
                {"label": "chorus", "start": 10.0, "end": 30.0},
                {"label": "verse", "start": 30.0, "end": 50.0},
            ],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_section(5.0) == "intro"
        assert reactor.get_section(15.0) == "chorus"
        assert reactor.get_section(35.0) == "verse"

    def test_no_sections_returns_verse(self):
        """When no sections are defined, defaults to 'verse'."""
        analysis = {"energy_curve": [[0.0, 0.5]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_section(5.0) == "verse"


class TestGetSaturation:
    """Test energy-reactive saturation."""

    def test_zero_energy(self):
        """Zero energy gives base saturation 0.82."""
        analysis = {"energy_curve": [[0.0, 0.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_saturation(0.0) == pytest.approx(0.82)

    def test_full_energy(self):
        """Full energy gives saturation 1.10."""
        analysis = {"energy_curve": [[0.0, 1.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_saturation(0.0) == pytest.approx(1.10)

    def test_half_energy(self):
        """Half energy gives saturation 0.96."""
        analysis = {"energy_curve": [[0.0, 0.5]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_saturation(0.0) == pytest.approx(0.96)


class TestGetContrast:
    """Test energy-reactive contrast."""

    def test_zero_energy(self):
        """Zero energy gives base contrast 1.05."""
        analysis = {"energy_curve": [[0.0, 0.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_contrast(0.0) == pytest.approx(1.05)

    def test_full_energy(self):
        """Full energy gives contrast 1.20."""
        analysis = {"energy_curve": [[0.0, 1.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_contrast(0.0) == pytest.approx(1.20)


class TestGetZoomScale:
    """Test energy-reactive zoom scale."""

    def test_low_energy(self):
        """Low energy gives zoom near 1.02."""
        analysis = {"energy_curve": [[0.0, 0.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_zoom_scale(0.0) == pytest.approx(1.02)

    def test_high_energy(self):
        """High energy gives zoom near 1.08."""
        analysis = {"energy_curve": [[0.0, 0.9]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_zoom_scale(0.0) == pytest.approx(1.074)

    def test_capped_at_max(self):
        """Zoom scale is capped at 1.08 even at full energy."""
        analysis = {"energy_curve": [[0.0, 1.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_zoom_scale(0.0) == pytest.approx(1.08)


class TestGetVignetteStrength:
    """Test energy-reactive vignette strength."""

    def test_zero_energy(self):
        """Zero energy gives max vignette 0.7."""
        analysis = {"energy_curve": [[0.0, 0.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_vignette_strength(0.0) == pytest.approx(0.7)

    def test_full_energy(self):
        """Full energy gives min vignette 0.2."""
        analysis = {"energy_curve": [[0.0, 1.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_vignette_strength(0.0) == pytest.approx(0.2)


class TestGetTransition:
    """Test energy-reactive transition selection."""

    def test_high_energy_cut(self):
        """Energy > 0.75 produces a cut transition."""
        analysis = {"energy_curve": [[0.0, 0.9]]}
        reactor = EnergyReactor(analysis)
        result = reactor.get_transition(0.0)
        assert result["type"] == "cut"
        assert result["duration"] == pytest.approx(max(0.15, 0.8 - 0.9 * 0.65))

    def test_mid_energy_cross_dissolve(self):
        """Energy in 0.45-0.75 range produces cross_dissolve."""
        analysis = {"energy_curve": [[0.0, 0.6]]}
        reactor = EnergyReactor(analysis)
        result = reactor.get_transition(0.0)
        assert result["type"] == "cross_dissolve"
        assert result["duration"] == pytest.approx(0.8 - 0.6 * 0.65)

    def test_low_energy_fade(self):
        """Energy in 0.20-0.45 range produces fade."""
        analysis = {"energy_curve": [[0.0, 0.3]]}
        reactor = EnergyReactor(analysis)
        result = reactor.get_transition(0.0)
        assert result["type"] == "fade"
        assert result["duration"] == pytest.approx(0.8 - 0.3 * 0.65)

    def test_very_low_energy_long_dissolve(self):
        """Energy <= 0.20 produces long cross_dissolve."""
        analysis = {"energy_curve": [[0.0, 0.1]]}
        reactor = EnergyReactor(analysis)
        result = reactor.get_transition(0.0)
        assert result["type"] == "cross_dissolve"
        assert result["duration"] == pytest.approx(0.8 - 0.1 * 0.65)


class TestGetFontSize:
    """Test energy-reactive font size."""

    def test_quiet(self):
        """Zero energy returns base font size 54."""
        analysis = {"energy_curve": [[0.0, 0.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_font_size(0.0) == 54

    def test_peak(self):
        """Full energy returns 66."""
        analysis = {"energy_curve": [[0.0, 1.0]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_font_size(0.0) == 66

    def test_custom_base(self):
        """Custom base font size is respected."""
        analysis = {"energy_curve": [[0.0, 0.5]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_font_size(0.0, base=40) == int(40 + 0.5 * 12)


class TestGetSubtitleAnimation:
    """Test energy-reactive subtitle animation."""

    def test_high_energy_scale_pop(self):
        """Energy > 0.7 returns scale_pop."""
        analysis = {"energy_curve": [[0.0, 0.9]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_subtitle_animation(0.0) == "scale_pop"

    def test_mid_energy_slide_up(self):
        """Energy in 0.4-0.7 range returns slide_up."""
        analysis = {"energy_curve": [[0.0, 0.5]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_subtitle_animation(0.0) == "slide_up"

    def test_low_energy_fade(self):
        """Energy <= 0.4 returns fade."""
        analysis = {"energy_curve": [[0.0, 0.2]]}
        reactor = EnergyReactor(analysis)
        assert reactor.get_subtitle_animation(0.0) == "fade"


class TestReelEnergyBoost:
    """Test reel mode energy boost."""

    def test_reel_boost_applied(self):
        """Reel mode applies 1.3x boost, capped at 1.0."""
        analysis = {"energy_curve": [[0.0, 0.5]]}
        reactor = EnergyReactor(analysis, reel_mode=True)
        assert reactor.get_energy(0.0) == pytest.approx(0.65)

    def test_no_boost_in_normal_mode(self):
        """Normal mode returns raw energy without boost."""
        analysis = {"energy_curve": [[0.0, 0.5]]}
        reactor = EnergyReactor(analysis, reel_mode=False)
        assert reactor.get_energy(0.0) == pytest.approx(0.5)

    def test_reel_boost_capped_at_one(self):
        """Reel boost does not exceed 1.0."""
        analysis = {"energy_curve": [[0.0, 0.9]]}
        reactor = EnergyReactor(analysis, reel_mode=True)
        assert reactor.get_energy(0.0) == pytest.approx(1.0)


class TestGetLightFlashTimes:
    """Test light flash spike detection."""

    def test_detects_spikes(self):
        """Detects energy spikes exceeding thresholds."""
        analysis = {
            "energy_curve": [
                [0.0, 0.3],
                [0.5, 0.3],
                [1.0, 0.9],  # spike: 0.9 - 0.3 = 0.6 > 0.4, energy 0.9 > 0.85
                [1.5, 0.5],
                [2.0, 0.5],
            ]
        }
        reactor = EnergyReactor(analysis)
        flashes = reactor.get_light_flash_times()
        assert 1.0 in flashes

    def test_max_two_flashes(self):
        """Returns at most MAX_FLASHES (2) flash times."""
        analysis = {
            "energy_curve": [
                [0.0, 0.2],
                [0.5, 0.9],   # spike
                [1.0, 0.2],
                [1.5, 0.95],  # spike
                [2.0, 0.2],
                [2.5, 0.88],  # spike
            ]
        }
        reactor = EnergyReactor(analysis)
        flashes = reactor.get_light_flash_times()
        assert len(flashes) <= 2

    def test_no_flashes_when_no_spikes(self):
        """Returns empty list when energy is smooth and low."""
        analysis = {
            "energy_curve": [
                [0.0, 0.3],
                [1.0, 0.35],
                [2.0, 0.4],
                [3.0, 0.38],
            ]
        }
        reactor = EnergyReactor(analysis)
        flashes = reactor.get_light_flash_times()
        assert flashes == []
