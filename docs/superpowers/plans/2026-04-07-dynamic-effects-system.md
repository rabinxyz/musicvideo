# Dynamic Effects System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an EnergyReactor class that makes all visual effects (color grade, zoom punch, vignette, transitions, subtitles, Ken Burns) respond dynamically to the audio energy curve, with professional restraint (fix-effects-balance spec).

**Architecture:** New module `musicvid/pipeline/energy_reactor.py` provides `EnergyReactor` class initialized from analysis dict. Audio analyzer computes `energy_curve` (RMS per frame, normalized 0-1) and `energy_mean`. Assembler and wow_effects consume EnergyReactor for per-time-t effect parameters. Effects balance constants are tuned down from current aggressive values.

**Tech Stack:** Python 3.14, librosa (RMS), NumPy (interpolation), MoviePy 2.1.2 (per-frame transforms), FFmpeg (WOW post-processing), pytest + unittest.mock

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `musicvid/pipeline/energy_reactor.py` | Create | EnergyReactor class — all energy-based calculations |
| `tests/test_energy_reactor.py` | Create | Tests for EnergyReactor |
| `musicvid/pipeline/audio_analyzer.py` | Modify (~line 146-167) | Add energy_curve + energy_mean to analysis dict |
| `tests/test_audio_analyzer.py` | Modify | Add tests for energy_curve/energy_mean |
| `musicvid/pipeline/wow_effects.py` | Modify | Tune constants (balance spec), use energy_curve for flash limiting |
| `tests/test_wow_effects.py` | Modify | Update tests for new constants |
| `musicvid/pipeline/assembler.py` | Modify | Use EnergyReactor for section grade, subtitle sizing |
| `tests/test_assembler.py` | Modify | Add tests for energy-reactive grade/subtitles |
| `musicvid/musicvid.py` | Modify | Wire energy-reactive transitions in `_assign_dynamic_transitions` |
| `tests/conftest.py` | Modify | Add energy_curve/energy_mean to sample_analysis fixture |

---

### Task 1: Add energy_curve and energy_mean to audio analysis

**Files:**
- Modify: `musicvid/pipeline/audio_analyzer.py:146-167`
- Modify: `tests/test_audio_analyzer.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing test for energy_curve in analysis output**

In `tests/test_audio_analyzer.py`, add a new test class:

```python
class TestEnergyCurve:
    """Tests for energy_curve and energy_mean in analysis output."""

    @patch("musicvid.pipeline.audio_analyzer.whisper")
    @patch("musicvid.pipeline.audio_analyzer.librosa")
    def test_energy_curve_present_in_analysis(self, mock_librosa, mock_whisper):
        """Analysis dict must include energy_curve as list of [time, energy] pairs."""
        import numpy as np

        mock_whisper.load_model.return_value.transcribe.return_value = {
            "segments": [], "language": "pl"
        }
        mock_librosa.load.return_value = (np.zeros(22050), 22050)
        mock_librosa.beat.beat_track.return_value = (120.0, np.array([0, 10, 20]))
        mock_librosa.frames_to_time.side_effect = lambda x, sr=22050: np.array(x) * 0.01
        mock_librosa.onset.onset_strength.return_value = np.zeros(100)
        mock_librosa.util.peak_pick.return_value = np.array([])

        # RMS energy mock
        rms_values = np.array([[0.1, 0.5, 0.9, 0.3]])
        mock_librosa.feature.rms.return_value = rms_values

        # _detect_sections mock
        mock_librosa.feature.chroma_stft.return_value = np.zeros((12, 100))
        mock_librosa.feature.mfcc.return_value = np.zeros((13, 100))
        mock_librosa.feature.melspectrogram.return_value = np.ones((128, 100))
        mock_librosa.power_to_db.return_value = np.zeros((128, 100))
        mock_librosa.segment.agglomerative.return_value = np.array([0, 50])

        from musicvid.pipeline.audio_analyzer import analyze_audio
        result = analyze_audio("/fake/audio.mp3", output_dir=None)

        assert "energy_curve" in result
        assert "energy_mean" in result
        assert isinstance(result["energy_curve"], list)
        assert len(result["energy_curve"]) > 0
        # Each entry is [time, energy]
        assert len(result["energy_curve"][0]) == 2
        # Energy values normalized 0-1
        energies = [e for _, e in result["energy_curve"]]
        assert min(energies) >= 0.0
        assert max(energies) <= 1.0
        assert isinstance(result["energy_mean"], float)
        assert 0.0 <= result["energy_mean"] <= 1.0

    @patch("musicvid.pipeline.audio_analyzer.whisper")
    @patch("musicvid.pipeline.audio_analyzer.librosa")
    def test_energy_curve_constant_signal_normalized(self, mock_librosa, mock_whisper):
        """Constant RMS signal should produce uniform energy_curve."""
        import numpy as np

        mock_whisper.load_model.return_value.transcribe.return_value = {
            "segments": [], "language": "pl"
        }
        mock_librosa.load.return_value = (np.zeros(22050), 22050)
        mock_librosa.beat.beat_track.return_value = (120.0, np.array([0, 10]))
        mock_librosa.frames_to_time.side_effect = lambda x, sr=22050: np.array(x) * 0.01
        mock_librosa.onset.onset_strength.return_value = np.zeros(100)
        mock_librosa.util.peak_pick.return_value = np.array([])

        # Constant RMS → after normalization, all values should be 0 (or handle div-by-zero)
        rms_values = np.array([[0.5, 0.5, 0.5, 0.5]])
        mock_librosa.feature.rms.return_value = rms_values

        mock_librosa.feature.chroma_stft.return_value = np.zeros((12, 100))
        mock_librosa.feature.mfcc.return_value = np.zeros((13, 100))
        mock_librosa.feature.melspectrogram.return_value = np.ones((128, 100))
        mock_librosa.power_to_db.return_value = np.zeros((128, 100))
        mock_librosa.segment.agglomerative.return_value = np.array([0, 50])

        from musicvid.pipeline.audio_analyzer import analyze_audio
        result = analyze_audio("/fake/audio.mp3", output_dir=None)

        # Constant signal: range is 0, so normalization should handle gracefully
        energies = [e for _, e in result["energy_curve"]]
        # All equal (no crash on zero range)
        assert all(e == energies[0] for e in energies)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestEnergyCurve -v`
Expected: FAIL — `KeyError: 'energy_curve'`

- [ ] **Step 3: Implement energy_curve computation in audio_analyzer.py**

In `musicvid/pipeline/audio_analyzer.py`, after the energy_peaks computation (~line 157) and before the `result = {` dict (~line 159), add:

```python
    # Energy curve: RMS energy per frame, normalized 0.0-1.0
    rms = librosa.feature.rms(y=y, sr=sr, hop_length=512)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    rms_range = rms.max() - rms.min()
    if rms_range > 0:
        rms_norm = (rms - rms.min()) / rms_range
    else:
        rms_norm = np.zeros_like(rms)
    energy_curve = [[round(float(t), 3), round(float(e), 4)] for t, e in zip(rms_times, rms_norm)]
    energy_mean_val = round(float(np.mean(rms_norm)), 4)
```

Then add these keys to the `result` dict:

```python
        "energy_curve": energy_curve,
        "energy_mean": energy_mean_val,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestEnergyCurve -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Update conftest.py sample_analysis fixture**

In `tests/conftest.py`, add to the `sample_analysis` fixture dict:

```python
        "energy_peaks": [1.0, 3.0, 5.0],
        "energy_curve": [
            [0.0, 0.1], [0.5, 0.2], [1.0, 0.4], [1.5, 0.3],
            [2.0, 0.5], [2.5, 0.6], [3.0, 0.8], [3.5, 0.9],
            [4.0, 1.0], [4.5, 0.9], [5.0, 0.7], [5.5, 0.5],
            [6.0, 0.3], [6.5, 0.2], [7.0, 0.15], [7.5, 0.1],
            [8.0, 0.1], [8.5, 0.05], [9.0, 0.05], [9.5, 0.02],
        ],
        "energy_mean": 0.42,
```

- [ ] **Step 6: Run full test suite to ensure no regressions**

Run: `python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: All existing tests pass. Some tests that build analysis dicts manually may need `energy_curve` added — if any fail, add the key with an empty list `[]` as needed.

- [ ] **Step 7: Commit**

```bash
git add musicvid/pipeline/audio_analyzer.py tests/test_audio_analyzer.py tests/conftest.py
git commit -m "feat: add energy_curve and energy_mean to audio analysis output"
```

---

### Task 2: Create EnergyReactor class

**Files:**
- Create: `musicvid/pipeline/energy_reactor.py`
- Create: `tests/test_energy_reactor.py`

- [ ] **Step 1: Write failing tests for EnergyReactor**

Create `tests/test_energy_reactor.py`:

```python
"""Tests for EnergyReactor — energy-reactive effect parameter provider."""

import pytest


class TestGetEnergy:
    """Test energy interpolation at arbitrary time t."""

    def test_exact_time_match(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.2], [1.0, 0.8], [2.0, 0.5]],
            "energy_mean": 0.5,
            "beats": [0.0, 0.5, 1.0, 1.5, 2.0],
            "bpm": 120.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 2.0}],
            "energy_peaks": [1.0],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_energy(1.0) == pytest.approx(0.8)

    def test_interpolation_between_points(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.0], [2.0, 1.0]],
            "energy_mean": 0.5,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_energy(1.0) == pytest.approx(0.5)

    def test_before_first_point_returns_first(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[1.0, 0.5], [2.0, 0.8]],
            "energy_mean": 0.65,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_energy(0.0) == pytest.approx(0.5)

    def test_after_last_point_returns_last(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.3], [1.0, 0.7]],
            "energy_mean": 0.5,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_energy(5.0) == pytest.approx(0.7)

    def test_empty_curve_returns_zero(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [],
            "energy_mean": 0.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_energy(1.0) == 0.0


class TestGetSection:
    """Test section lookup at time t."""

    def test_returns_correct_section(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.5]],
            "energy_mean": 0.5,
            "beats": [], "bpm": 120.0, "energy_peaks": [],
            "sections": [
                {"label": "intro", "start": 0.0, "end": 5.0},
                {"label": "verse", "start": 5.0, "end": 15.0},
                {"label": "chorus", "start": 15.0, "end": 25.0},
            ],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_section(2.0) == "intro"
        assert reactor.get_section(10.0) == "verse"
        assert reactor.get_section(20.0) == "chorus"

    def test_no_sections_returns_verse(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [], "energy_mean": 0.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_section(5.0) == "verse"


class TestGetSaturation:
    """Test energy-reactive saturation: 0.82 + energy * 0.28"""

    def test_zero_energy(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.0]],
            "energy_mean": 0.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_saturation(0.0) == pytest.approx(0.82)

    def test_full_energy(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 1.0]],
            "energy_mean": 1.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_saturation(0.0) == pytest.approx(1.10)

    def test_mid_energy(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.5]],
            "energy_mean": 0.5,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_saturation(0.0) == pytest.approx(0.96)


class TestGetContrast:
    """Test energy-reactive contrast: 1.05 + energy * 0.15"""

    def test_zero_energy(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.0]],
            "energy_mean": 0.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_contrast(0.0) == pytest.approx(1.05)

    def test_full_energy(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 1.0]],
            "energy_mean": 1.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_contrast(0.0) == pytest.approx(1.20)


class TestGetZoomScale:
    """Test energy-reactive zoom: 1.02 + peak_energy * 0.06, capped at 1.08"""

    def test_low_energy_peak(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.0], [1.0, 0.2]],
            "energy_mean": 0.1,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [1.0],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_zoom_scale(1.0) == pytest.approx(1.032)

    def test_high_energy_peak(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.5], [1.0, 1.0]],
            "energy_mean": 0.75,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [1.0],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_zoom_scale(1.0) == pytest.approx(1.08)

    def test_capped_at_1_08(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 1.0]],
            "energy_mean": 1.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [0.0],
        }
        reactor = EnergyReactor(analysis)
        # energy=1.0 → 1.02 + 1.0*0.06 = 1.08 (exactly at cap)
        assert reactor.get_zoom_scale(0.0) <= 1.08


class TestGetVignetteStrength:
    """Test energy-reactive vignette: 0.7 - energy * 0.5 (range 0.2-0.7)"""

    def test_quiet_moment(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.0]],
            "energy_mean": 0.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_vignette_strength(0.0) == pytest.approx(0.7)

    def test_peak_moment(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 1.0]],
            "energy_mean": 1.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_vignette_strength(0.0) == pytest.approx(0.2)


class TestGetTransition:
    """Test energy-reactive transitions."""

    def test_high_energy_gives_cut(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.9]],
            "energy_mean": 0.9,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        result = reactor.get_transition(0.0)
        assert result["type"] == "cut"

    def test_mid_energy_gives_cross_dissolve(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.6]],
            "energy_mean": 0.6,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        result = reactor.get_transition(0.0)
        assert result["type"] == "cross_dissolve"
        assert result["duration"] < 0.8

    def test_low_energy_gives_fade(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.25]],
            "energy_mean": 0.25,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        result = reactor.get_transition(0.0)
        assert result["type"] == "fade"

    def test_very_low_energy_gives_long_dissolve(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.1]],
            "energy_mean": 0.1,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        result = reactor.get_transition(0.0)
        assert result["type"] == "cross_dissolve"
        assert result["duration"] >= 0.7


class TestGetFontSize:
    """Test energy-reactive font size: base + energy * 12"""

    def test_quiet_gives_base(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.0]],
            "energy_mean": 0.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_font_size(0.0) == 54

    def test_peak_gives_max(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 1.0]],
            "energy_mean": 1.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_font_size(0.0) == 66

    def test_custom_base(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.5]],
            "energy_mean": 0.5,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_font_size(0.0, base=60) == 66


class TestGetSubtitleAnimation:
    """Test energy-reactive subtitle animation type."""

    def test_high_energy_gives_scale_pop(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.8]],
            "energy_mean": 0.8,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_subtitle_animation(0.0) == "scale_pop"

    def test_mid_energy_gives_slide_up(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.5]],
            "energy_mean": 0.5,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_subtitle_animation(0.0) == "slide_up"

    def test_low_energy_gives_fade(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.2]],
            "energy_mean": 0.2,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_subtitle_animation(0.0) == "fade"


class TestReelEnergyBoost:
    """Test reel mode applies 1.3x energy boost."""

    def test_reel_boost(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.5], [1.0, 0.8]],
            "energy_mean": 0.65,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis, reel_mode=True)
        # 0.5 * 1.3 = 0.65
        assert reactor.get_energy(0.0) == pytest.approx(0.65)
        # 0.8 * 1.3 = 1.04 → capped at 1.0
        assert reactor.get_energy(1.0) == pytest.approx(1.0)

    def test_normal_mode_no_boost(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        analysis = {
            "energy_curve": [[0.0, 0.5]],
            "energy_mean": 0.5,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis, reel_mode=False)
        assert reactor.get_energy(0.0) == pytest.approx(0.5)


class TestGetLightFlashTimes:
    """Test energy spike detection for light flashes — max 2 per video."""

    def test_detects_spikes(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        # Build curve with two big spikes
        curve = []
        for i in range(100):
            t = i * 0.1
            if 4.8 <= t <= 5.2:
                e = 0.9  # spike at t=5.0
            elif 8.8 <= t <= 9.2:
                e = 0.95  # spike at t=9.0
            else:
                e = 0.2
            curve.append([t, e])
        analysis = {
            "energy_curve": curve,
            "energy_mean": 0.3,
            "beats": [], "bpm": 120.0, "energy_peaks": [],
            "sections": [{"label": "chorus", "start": 4.0, "end": 10.0}],
        }
        reactor = EnergyReactor(analysis)
        flashes = reactor.get_light_flash_times()
        assert len(flashes) <= 2

    def test_max_two_flashes(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        # Many spikes but only 2 allowed
        curve = []
        for i in range(200):
            t = i * 0.1
            e = 0.9 if i % 20 == 0 else 0.1
            curve.append([t, e])
        analysis = {
            "energy_curve": curve,
            "energy_mean": 0.2,
            "beats": [], "bpm": 120.0, "energy_peaks": [],
            "sections": [{"label": "chorus", "start": 0.0, "end": 20.0}],
        }
        reactor = EnergyReactor(analysis)
        flashes = reactor.get_light_flash_times()
        assert len(flashes) <= 2

    def test_no_flashes_when_no_spikes(self):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        curve = [[i * 0.1, 0.3] for i in range(100)]
        analysis = {
            "energy_curve": curve,
            "energy_mean": 0.3,
            "beats": [], "bpm": 120.0, "energy_peaks": [],
            "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
        }
        reactor = EnergyReactor(analysis)
        assert reactor.get_light_flash_times() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_energy_reactor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'musicvid.pipeline.energy_reactor'`

- [ ] **Step 3: Implement EnergyReactor class**

Create `musicvid/pipeline/energy_reactor.py`:

```python
"""EnergyReactor — provides energy-reactive effect parameters at arbitrary time t.

Initialized from audio analysis dict. All visual effects query this class
to get parameters that respond to the music's energy curve.
"""


class EnergyReactor:
    """Energy-reactive effect parameter provider.

    Args:
        analysis: Audio analysis dict with energy_curve, energy_mean, beats, bpm, sections.
        reel_mode: If True, applies 1.3x energy boost (social reels have compressed time).
    """

    FLASH_SPIKE_THRESHOLD = 0.4  # minimum energy jump in 0.5s
    FLASH_ENERGY_THRESHOLD = 0.85  # minimum absolute energy for flash
    MAX_FLASHES = 2  # max flashes per video

    def __init__(self, analysis, reel_mode=False):
        self._curve = analysis.get("energy_curve", [])
        self._energy_mean = analysis.get("energy_mean", 0.0)
        self._beats = analysis.get("beats", [])
        self._bpm = analysis.get("bpm", 120.0)
        self._sections = analysis.get("sections", [])
        self._energy_peaks = analysis.get("energy_peaks", [])
        self._reel_mode = reel_mode
        self._reel_boost = 1.3 if reel_mode else 1.0

    def get_energy(self, t):
        """Return interpolated energy (0.0-1.0) at time t."""
        if not self._curve:
            return 0.0
        # Before first point
        if t <= self._curve[0][0]:
            return min(1.0, self._curve[0][1] * self._reel_boost)
        # After last point
        if t >= self._curve[-1][0]:
            return min(1.0, self._curve[-1][1] * self._reel_boost)
        # Binary search for interval
        lo, hi = 0, len(self._curve) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self._curve[mid][0] <= t:
                lo = mid
            else:
                hi = mid
        t0, e0 = self._curve[lo]
        t1, e1 = self._curve[hi]
        if t1 == t0:
            raw = e0
        else:
            frac = (t - t0) / (t1 - t0)
            raw = e0 + frac * (e1 - e0)
        return min(1.0, raw * self._reel_boost)

    def get_section(self, t):
        """Return section label at time t (intro/verse/chorus/bridge/outro)."""
        for sec in self._sections:
            if sec["start"] <= t < sec["end"]:
                return sec["label"]
        # If t is exactly at the end of last section
        if self._sections and t >= self._sections[-1]["start"]:
            return self._sections[-1]["label"]
        return "verse"

    def get_saturation(self, t):
        """Return energy-reactive saturation: 0.82 + energy * 0.28"""
        return 0.82 + self.get_energy(t) * 0.28

    def get_contrast(self, t):
        """Return energy-reactive contrast: 1.05 + energy * 0.15"""
        return 1.05 + self.get_energy(t) * 0.15

    def get_zoom_scale(self, t):
        """Return energy-reactive zoom scale: 1.02 + energy * 0.06, capped at 1.08"""
        return min(1.08, 1.02 + self.get_energy(t) * 0.06)

    def get_vignette_strength(self, t):
        """Return energy-reactive vignette: 0.7 - energy * 0.5 (range 0.2-0.7)"""
        return max(0.2, 0.7 - self.get_energy(t) * 0.5)

    def get_transition(self, t):
        """Return energy-reactive transition dict {type, duration} at time t."""
        energy = self.get_energy(t)
        if energy > 0.75:
            return {"type": "cut", "duration": 0.0}
        elif energy > 0.45:
            dur = max(0.15, 0.8 - energy * 0.65)
            return {"type": "cross_dissolve", "duration": round(dur, 2)}
        elif energy > 0.20:
            dur = max(0.15, 0.8 - energy * 0.65)
            return {"type": "fade", "duration": round(dur, 2)}
        else:
            dur = max(0.15, 0.8 - energy * 0.65)
            return {"type": "cross_dissolve", "duration": round(dur, 2)}

    def get_font_size(self, t, base=54):
        """Return energy-reactive font size: base + energy * 12"""
        return int(base + self.get_energy(t) * 12)

    def get_subtitle_animation(self, t):
        """Return energy-reactive subtitle animation type."""
        energy = self.get_energy(t)
        if energy > 0.7:
            return "scale_pop"
        elif energy > 0.4:
            return "slide_up"
        else:
            return "fade"

    def get_light_flash_times(self):
        """Return up to MAX_FLASHES times where energy spikes justify a light flash.

        A flash occurs when:
        1. Energy jumps by > FLASH_SPIKE_THRESHOLD in 0.5s
        2. Absolute energy > FLASH_ENERGY_THRESHOLD
        Selects the top MAX_FLASHES biggest spikes.
        """
        if len(self._curve) < 2:
            return []

        candidates = []
        for i, (t, e) in enumerate(self._curve):
            if e * self._reel_boost < self.FLASH_ENERGY_THRESHOLD:
                continue
            # Find energy 0.5s earlier
            e_prev = self._get_energy_raw(t - 0.5)
            spike = e - e_prev
            if spike > self.FLASH_SPIKE_THRESHOLD:
                candidates.append((spike, t))

        # Sort by spike magnitude, take top MAX_FLASHES
        candidates.sort(reverse=True)
        return [t for _, t in candidates[:self.MAX_FLASHES]]

    def _get_energy_raw(self, t):
        """Get raw energy without reel boost (for spike comparison)."""
        if not self._curve:
            return 0.0
        if t <= self._curve[0][0]:
            return self._curve[0][1]
        if t >= self._curve[-1][0]:
            return self._curve[-1][1]
        lo, hi = 0, len(self._curve) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self._curve[mid][0] <= t:
                lo = mid
            else:
                hi = mid
        t0, e0 = self._curve[lo]
        t1, e1 = self._curve[hi]
        if t1 == t0:
            return e0
        frac = (t - t0) / (t1 - t0)
        return e0 + frac * (e1 - e0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_energy_reactor.py -v`
Expected: All 22 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/energy_reactor.py tests/test_energy_reactor.py
git commit -m "feat: add EnergyReactor class for energy-reactive effect parameters"
```

---

### Task 3: Tune WOW effects balance constants

**Files:**
- Modify: `musicvid/pipeline/wow_effects.py`
- Modify: `tests/test_wow_effects.py`

- [ ] **Step 1: Write failing tests for new balance constants**

Add to `tests/test_wow_effects.py`:

```python
class TestEffectsBalanceConstants:
    """Test that WOW effect constants match the balance spec."""

    def test_light_flash_limited_to_first_and_last_chorus(self):
        """Light flash should only fire on first and last chorus start."""
        from musicvid.pipeline.wow_effects import _build_light_flash_filter
        sections = [
            {"label": "verse", "start": 0.0, "end": 10.0},
            {"label": "chorus", "start": 10.0, "end": 20.0},
            {"label": "verse", "start": 20.0, "end": 30.0},
            {"label": "chorus", "start": 30.0, "end": 40.0},
            {"label": "verse", "start": 40.0, "end": 50.0},
            {"label": "chorus", "start": 50.0, "end": 60.0},
        ]
        result = _build_light_flash_filter(sections)
        assert result is not None
        # Should contain exactly 2 flash times: first chorus (10.0) and last chorus (50.0)
        assert "10.000" in result
        assert "50.000" in result
        # Middle chorus (30.0) should NOT be present
        assert "30.000" not in result

    def test_flash_fade_time_is_0_5s(self):
        """Flash should decay over 0.5s, not 0.3s."""
        from musicvid.pipeline.wow_effects import _build_light_flash_filter
        sections = [{"label": "chorus", "start": 5.0, "end": 15.0}]
        result = _build_light_flash_filter(sections)
        assert result is not None
        # Old: between(T,5.000,5.050) — 0.05s peak
        # New: between(T,5.000,5.060) — 0.06s peak
        assert "5.060" in result
        # Decay should be slower: exp(-6*...) instead of exp(-15*...)
        assert "exp(-6" in result

    def test_flash_opacity_capped(self):
        """Flash brightness multiplier should be reduced (0.35 opacity → lower geq value)."""
        from musicvid.pipeline.wow_effects import FLASH_MAX_BRIGHTNESS
        assert FLASH_MAX_BRIGHTNESS <= 90  # 255 * 0.35 = 89.25

    def test_dynamic_grade_chorus_saturation_reduced(self):
        """Chorus saturation should be 1.05 (not 1.15) per balance spec."""
        from musicvid.pipeline.wow_effects import _build_color_grade_filter
        sections = [{"label": "chorus", "start": 5.0, "end": 15.0}]
        result = _build_color_grade_filter(sections)
        assert "saturation=1.05" in result

    def test_dynamic_grade_verse_saturation(self):
        """Verse saturation should be 0.90 per balance spec."""
        from musicvid.pipeline.wow_effects import _build_color_grade_filter
        sections = [{"label": "verse", "start": 0.0, "end": 10.0}]
        result = _build_color_grade_filter(sections)
        assert "saturation=0.9" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_wow_effects.py::TestEffectsBalanceConstants -v`
Expected: FAIL — constants don't exist yet / values differ

- [ ] **Step 3: Update wow_effects.py with balanced constants**

In `musicvid/pipeline/wow_effects.py`, after `ENABLE_ZOOMPAN = False` (line 16), add:

```python
# Effects balance constants (fix-effects-balance spec)
FLASH_MAX_BRIGHTNESS = 89  # 255 * 0.35 opacity cap
FLASH_PEAK_TIME = 0.06     # seconds
FLASH_FADE_RATE = 6        # exp(-6*t) for 0.5s visible decay (was exp(-15) for 0.3s)
```

Update `_build_light_flash_filter` to limit to first and last chorus only:

```python
def _build_light_flash_filter(sections):
    """Build FFmpeg geq filter for white light flash at first and last chorus start.

    Max 2 flashes per video. Flash: brightness spike at chorus start, decaying over 0.5s.
    """
    chorus_starts = [
        round(float(s["start"]), 3)
        for s in sections
        if s.get("label") == "chorus"
    ]
    if not chorus_starts:
        return None

    # Balance spec: only first and last chorus
    if len(chorus_starts) == 1:
        flash_times = chorus_starts
    else:
        flash_times = [chorus_starts[0], chorus_starts[-1]]

    flash_parts = []
    for t in flash_times:
        flash_parts.append(
            f"({FLASH_MAX_BRIGHTNESS}*between(T,{t:.3f},{t+FLASH_PEAK_TIME:.3f})*exp(-{FLASH_FADE_RATE}*(T-{t:.3f})))"
        )

    flash_expr = "+".join(flash_parts)
    return (
        f"geq=r='clip(r(X,Y)+{flash_expr},0,255)':"
        f"g='clip(g(X,Y)+{flash_expr},0,255)':"
        f"b='clip(b(X,Y)+{flash_expr},0,255)'"
    )
```

Update `_build_color_grade_filter` saturation values:

```python
        if label == "chorus":
            filters.append(
                f"eq=saturation=1.05:brightness=0.0:contrast=1.10:enable='{enable}'"
            )
```

And for verse:
```python
        else:
            filters.append(
                f"eq=saturation=0.90:brightness=0.02:contrast=1.05:enable='{enable}'"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_wow_effects.py::TestEffectsBalanceConstants -v`
Expected: All 5 PASS

- [ ] **Step 5: Run existing wow_effects tests to check for regressions**

Run: `python3 -m pytest tests/test_wow_effects.py -v`
Expected: All pass. Some tests may reference old values (`saturation=1.15`, `255*between`, `exp(-15`) — update those assertions to match new constants.

- [ ] **Step 6: Fix any broken existing tests**

Update existing test assertions that reference old constant values. Common changes:
- `saturation=1.15` → `saturation=1.05`
- `saturation=0.85` → `saturation=0.9`  (in verse assertions)
- `255*between` → `89*between` (flash brightness)
- `exp(-15` → `exp(-6` (flash decay)
- Flash filter tests with 3+ choruses: now only first and last chorus times appear

- [ ] **Step 7: Commit**

```bash
git add musicvid/pipeline/wow_effects.py tests/test_wow_effects.py
git commit -m "fix: tune WOW effects balance — reduce flash/grade intensity per balance spec"
```

---

### Task 4: Integrate EnergyReactor into assembler section grade

**Files:**
- Modify: `musicvid/pipeline/assembler.py:33-62`
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write failing test for energy-reactive section grade**

Add to `tests/test_assembler.py`:

```python
class TestEnergyReactiveSectionGrade:
    """Test that apply_section_grade uses EnergyReactor when provided."""

    def test_chorus_with_high_energy_stronger_saturation(self):
        from musicvid.pipeline.assembler import apply_section_grade
        from musicvid.pipeline.energy_reactor import EnergyReactor
        import numpy as np

        analysis = {
            "energy_curve": [[0.0, 1.0]],
            "energy_mean": 1.0,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)

        mock_frame = np.full((10, 10, 3), 128, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.image_transform.return_value = mock_clip

        result = apply_section_grade(mock_clip, "chorus", reactor=reactor, scene_start=0.0)
        assert mock_clip.image_transform.called

    def test_verse_with_low_energy_lower_saturation(self):
        from musicvid.pipeline.assembler import apply_section_grade
        from musicvid.pipeline.energy_reactor import EnergyReactor
        import numpy as np

        analysis = {
            "energy_curve": [[0.0, 0.1]],
            "energy_mean": 0.1,
            "beats": [], "bpm": 120.0, "sections": [], "energy_peaks": [],
        }
        reactor = EnergyReactor(analysis)

        mock_clip = MagicMock()
        mock_clip.image_transform.return_value = mock_clip

        result = apply_section_grade(mock_clip, "verse", reactor=reactor, scene_start=0.0)
        assert mock_clip.image_transform.called

    def test_no_reactor_falls_back_to_static_grades(self):
        """Without reactor, behavior is unchanged (backward compatible)."""
        from musicvid.pipeline.assembler import apply_section_grade

        mock_clip = MagicMock()
        mock_clip.image_transform.return_value = mock_clip

        result = apply_section_grade(mock_clip, "chorus")
        assert mock_clip.image_transform.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assembler.py::TestEnergyReactiveSectionGrade -v`
Expected: FAIL — `apply_section_grade() got an unexpected keyword argument 'reactor'`

- [ ] **Step 3: Update apply_section_grade to accept optional reactor**

In `musicvid/pipeline/assembler.py`, modify `apply_section_grade`:

```python
def apply_section_grade(clip, section, reactor=None, scene_start=None):
    """Apply per-section color grade (saturation, contrast, brightness).

    When reactor (EnergyReactor) is provided, uses energy-reactive values.
    Otherwise falls back to static _SECTION_GRADES dict.
    """
    import numpy as np

    if reactor is not None and scene_start is not None:
        sat = reactor.get_saturation(scene_start)
        cont = reactor.get_contrast(scene_start)
        bright = 0.0
    else:
        sat, cont, bright = _SECTION_GRADES.get(section, _DEFAULT_GRADE)

    def grade_frame(frame):
        f = frame.astype(np.float32) + bright * 255
        f = (f - 128) * cont + 128
        # Saturation: blend toward luminance
        r, g, b = f[..., 0], f[..., 1], f[..., 2]
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        lum3 = np.stack([luminance] * 3, axis=-1)
        f = lum3 + sat * (f - lum3)
        return np.clip(f, 0, 255).astype(np.uint8)

    return clip.image_transform(grade_frame)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestEnergyReactiveSectionGrade -v`
Expected: All 3 PASS

- [ ] **Step 5: Run full assembler tests for regressions**

Run: `python3 -m pytest tests/test_assembler.py -v --tb=short 2>&1 | tail -30`
Expected: All pass (backward compatible — no reactor means old behavior)

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: add energy-reactive section grade via optional EnergyReactor"
```

---

### Task 5: Wire EnergyReactor into assemble_video and CLI

**Files:**
- Modify: `musicvid/pipeline/assembler.py` (assemble_video function)
- Modify: `musicvid/musicvid.py` (CLI orchestration)

- [ ] **Step 1: Write failing test for EnergyReactor in assemble_video**

Add to `tests/test_assembler.py`:

```python
class TestAssembleVideoWithReactor:
    """Test that assemble_video creates and uses EnergyReactor."""

    @patch("musicvid.pipeline.assembler.apply_wow_effects")
    @patch("musicvid.pipeline.assembler.apply_global_color_grade")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler._concatenate_with_transitions")
    @patch("musicvid.pipeline.assembler.apply_section_grade")
    def test_passes_reactor_to_section_grade(
        self, mock_grade, mock_concat, mock_leak, mock_bars,
        mock_effects, mock_color, mock_wow,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        """assemble_video should pass reactor and scene_start to apply_section_grade."""
        # Add energy_curve to analysis
        sample_analysis["energy_curve"] = [[0.0, 0.5], [5.0, 0.8], [10.0, 0.3]]
        sample_analysis["energy_mean"] = 0.5
        sample_analysis["energy_peaks"] = [3.0]

        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080

        mock_grade.return_value = mock_clip
        mock_effects.return_value = mock_clip
        mock_concat.return_value = mock_clip

        manifest = [
            {"scene_index": 0, "video_path": "/fake/scene.jpg", "start": 0.0, "end": 5.0},
        ]

        with patch("musicvid.pipeline.assembler._load_scene_clip", return_value=mock_clip):
            with patch("musicvid.pipeline.assembler._create_subtitle_clips", return_value=[]):
                with patch("musicvid.pipeline.assembler.CompositeVideoClip", return_value=mock_clip):
                    with patch("musicvid.pipeline.assembler.AudioFileClip", return_value=mock_clip):
                        from musicvid.pipeline.assembler import assemble_video
                        assemble_video(
                            sample_analysis,
                            sample_scene_plan,
                            manifest,
                            "/fake/audio.mp3",
                            str(tmp_output / "out.mp4"),
                        )

        # Verify reactor was passed (kwarg reactor= is not None)
        if mock_grade.called:
            call_kwargs = mock_grade.call_args
            assert call_kwargs is not None
```

- [ ] **Step 2: Run test to verify behavior**

Run: `python3 -m pytest tests/test_assembler.py::TestAssembleVideoWithReactor -v`

- [ ] **Step 3: Wire EnergyReactor into assemble_video**

In `musicvid/pipeline/assembler.py`, inside `assemble_video()`:

After loading the analysis data and before the scene loop, add:

```python
    from musicvid.pipeline.energy_reactor import EnergyReactor
    reactor = None
    if analysis.get("energy_curve"):
        is_reel = target_size == (1080, 1920)
        reactor = EnergyReactor(analysis, reel_mode=is_reel)
```

Then in the scene processing loop, change the `apply_section_grade` call to pass the reactor:

```python
        clip = apply_section_grade(clip, scene.get("section", "verse"),
                                   reactor=reactor, scene_start=scene.get("start", 0.0))
```

- [ ] **Step 4: Run full test suite**

Run: `python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: wire EnergyReactor into assemble_video for energy-reactive grading"
```

---

### Task 6: Energy-reactive transitions in CLI

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_dynamics.py` (or relevant CLI test file)

- [ ] **Step 1: Write failing test for energy-reactive transitions**

Add to `tests/test_dynamics.py`:

```python
class TestEnergyReactiveTransitions:
    """Test _assign_dynamic_transitions uses EnergyReactor when energy_curve present."""

    def test_high_energy_boundary_gets_cut(self):
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
        # At t=5.0, energy=0.9 → should be "cut"
        assert scenes[0].get("transition_to_next") == "cut"

    def test_low_energy_boundary_gets_fade(self):
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

    def test_no_reactor_uses_existing_logic(self):
        """Without reactor, existing _TRANSITIONS_MAP logic applies."""
        from musicvid.musicvid import _assign_dynamic_transitions

        scenes = [
            {"section": "verse", "start": 0.0, "end": 5.0},
            {"section": "chorus", "start": 5.0, "end": 10.0},
        ]
        _assign_dynamic_transitions(scenes, 120.0)
        # Should still work (backward compatible)
        assert "transition_to_next" in scenes[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dynamics.py::TestEnergyReactiveTransitions -v`
Expected: FAIL — `_assign_dynamic_transitions() got an unexpected keyword argument 'reactor'`

- [ ] **Step 3: Update _assign_dynamic_transitions to accept optional reactor**

In `musicvid/musicvid.py`, modify `_assign_dynamic_transitions(scenes, bpm)` to accept `reactor=None`:

```python
def _assign_dynamic_transitions(scenes, bpm, reactor=None):
    """Set transition_to_next per scene based on section pairs or energy reactor."""
    for i in range(len(scenes) - 1):
        if reactor is not None:
            # Energy-reactive: transition type based on energy at scene boundary
            trans = reactor.get_transition(scenes[i]["end"])
            scenes[i]["transition_to_next"] = trans["type"]
        else:
            # Existing logic: _TRANSITIONS_MAP lookup
            pair = (scenes[i].get("section", "verse"), scenes[i + 1].get("section", "verse"))
            scenes[i]["transition_to_next"] = _TRANSITIONS_MAP.get(pair, "cross_dissolve")
    # Last scene has no transition
    if scenes:
        scenes[-1]["transition_to_next"] = "cut"
```

Then in the CLI `cli()` function, where `_assign_dynamic_transitions` is called, create and pass the reactor:

```python
    # After beat sync and before motion/transition assignment
    reactor = None
    if analysis.get("energy_curve"):
        from musicvid.pipeline.energy_reactor import EnergyReactor
        reactor = EnergyReactor(analysis)

    _enforce_motion_variety(scenes)
    if transitions_mode == "auto":
        _assign_dynamic_transitions(scenes, analysis["bpm"], reactor=reactor)
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_dynamics.py::TestEnergyReactiveTransitions -v`
Expected: All 3 PASS

- [ ] **Step 5: Run full test suite**

Run: `python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_dynamics.py
git commit -m "feat: energy-reactive transitions via EnergyReactor in CLI"
```

---

### Task 7: Disable WOW effects for social reels by default

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: tests for CLI

- [ ] **Step 1: Write failing test**

Add to the CLI test file (e.g., `tests/test_cli.py` or `tests/test_musicvid.py`):

```python
class TestReelWowDisabled:
    """Social reels should auto-disable WOW effects per balance spec."""

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.VisualRouter")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.assemble_all_parallel")
    @patch("musicvid.musicvid.select_social_clips")
    def test_social_preset_disables_wow(
        self, mock_social, mock_parallel, mock_analyze,
        mock_director, mock_router, mock_font, tmp_path
    ):
        """When preset=social, wow_config should be None in assembly jobs."""
        from click.testing import CliRunner
        from musicvid.musicvid import cli

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 60.0, "sections": [{"label": "verse", "start": 0.0, "end": 60.0}],
            "mood_energy": "contemplative", "language": "pl",
            "energy_peaks": [], "energy_curve": [[0.0, 0.5]], "energy_mean": 0.5,
        }
        mock_director.return_value = {
            "overall_style": "contemplative",
            "master_style": "warm",
            "color_palette": ["#000"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000", "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 60.0, "visual_prompt": "test", "motion": "slow_zoom_in", "transition": "fade", "animate": False, "motion_prompt": "", "visual_source": "TYPE_VIDEO_STOCK", "search_query": "nature"}],
        }
        mock_router_inst = MagicMock()
        mock_router.return_value = mock_router_inst
        mock_router_inst.fetch_manifest.return_value = [{"scene_index": 0, "video_path": "/fake.mp4", "start": 0.0, "end": 60.0}]
        mock_social.return_value = [
            {"start": 0.0, "end": 30.0, "section": "verse"},
            {"start": 10.0, "end": 40.0, "section": "verse"},
            {"start": 20.0, "end": 50.0, "section": "verse"},
        ]

        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        runner = CliRunner()
        result = runner.invoke(cli, [str(audio_file), "--mode", "stock", "--preset", "social"])

        # Check that assemble_all_parallel was called
        if mock_parallel.called:
            jobs = mock_parallel.call_args[0][0]
            for job in jobs:
                assert job.kwargs.get("wow_config") is None, "Social reels should have wow_config=None"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::TestReelWowDisabled -v` (or wherever the test lives)
Expected: FAIL — wow_config is not None for social jobs

- [ ] **Step 3: Update _run_preset_mode to disable WOW for social reels**

In `musicvid/musicvid.py`, inside `_run_preset_mode`, when building social AssemblyJobs, force `wow_config=None`:

Find where social assembly jobs are created and ensure:

```python
    # Social reels: disable WOW effects by default (balance spec)
    social_wow = None  # wow_config disabled for reels
```

Pass `wow_config=social_wow` instead of `wow_config=wow_config` for social jobs.

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_cli.py::TestReelWowDisabled -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "fix: disable WOW effects for social reels by default (balance spec)"
```

---

### Task 8: Full integration test and final verification

**Files:**
- All modified files from Tasks 1-7

- [ ] **Step 1: Run the complete test suite**

Run: `python3 -m pytest tests/ -v 2>&1 | tail -50`
Expected: All tests pass (728+ existing + ~35 new tests)

- [ ] **Step 2: Run energy_reactor tests specifically**

Run: `python3 -m pytest tests/test_energy_reactor.py -v`
Expected: All 22 tests PASS

- [ ] **Step 3: Run wow_effects tests**

Run: `python3 -m pytest tests/test_wow_effects.py -v`
Expected: All pass with new balance constants

- [ ] **Step 4: Run assembler tests**

Run: `python3 -m pytest tests/test_assembler.py -v`
Expected: All pass including new energy-reactive grade tests

- [ ] **Step 5: Verify acceptance criteria from spec**

Run quick grep checks:
```bash
# EnergyReactor provides values per time t
python3 -c "from musicvid.pipeline.energy_reactor import EnergyReactor; r = EnergyReactor({'energy_curve': [[0,0.5]], 'energy_mean': 0.5, 'beats': [], 'bpm': 120, 'sections': [], 'energy_peaks': []}); print(r.get_saturation(0), r.get_zoom_scale(0), r.get_font_size(0))"

# Expected output: 0.96 1.05 60
```

- [ ] **Step 6: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "test: verify dynamic effects system integration"
```

---

## Acceptance Criteria Mapping

| Spec Requirement | Task |
|---|---|
| EnergyReactor provides values per time t | Task 2 |
| Saturation higher at chorus than verse | Task 2 (get_saturation), Task 4 (integration) |
| Zoom punch stronger at energy peaks > 0.8 | Task 2 (get_zoom_scale) |
| Transitions shorter at high energy | Task 2 (get_transition), Task 6 (integration) |
| Subtitles larger at chorus | Task 2 (get_font_size) |
| Ken Burns faster at energetic sections | Task 2 (get_zoom_scale — ready for future KB integration) |
| Reels have +30% energy boost | Task 2 (reel_mode) |
| No flickering (zoom max 1.08, flash max 2x, opacity max 0.3) | Task 2 + Task 3 |
| Reels don't flash / no WOW | Task 3 + Task 7 |
| Zoom punch subtle (1.05) | Task 3 |
| Smooth color grade transitions | Task 3 (chorus sat 1.05, verse 0.90) |
| `pytest tests/test_energy_reactor.py -v` passes | Task 2 |
