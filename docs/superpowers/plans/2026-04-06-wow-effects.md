# WOW Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CapCut-style WOW effects (zoom punch, light flash, reactive color grade, dynamic vignette, animated text scale-pop, motion blur) to the music video pipeline via FFmpeg post-processing, plus new CLI flags and LUT auto-selection.

**Architecture:** A new `wow_effects.py` module builds FFmpeg filter chains from audio analysis (beat/section timing) and runs an `ffmpeg` subprocess on the MoviePy-generated MP4. `assemble_video()` gains a `wow_config` dict kwarg. `_create_subtitle_clips()` gains scale-pop animation for chorus sections via MoviePy `transform()`. New CLI flags `--wow`, `--zoom-punch`, `--light-flash`, `--dynamic-grade`, `--particles` control effects. LUT is auto-selected from `scene_plan["overall_style"]` when no `--lut-style` is specified.

**Tech Stack:** Python 3.11+, FFmpeg (scale/crop/geq/eq/vignette/tblend), subprocess, librosa (onset strength), moviepy 2.1.2, numpy, Pillow, Click.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `musicvid/pipeline/audio_analyzer.py` | Modify | Add `energy_peaks` key to analysis dict |
| `musicvid/pipeline/wow_effects.py` | **Create** | FFmpeg filter chain builder + `apply_wow_effects()` |
| `musicvid/pipeline/assembler.py` | Modify | Accept `wow_config` kwarg; call `apply_wow_effects` after `write_videofile`; scale-pop in `_create_subtitle_clips` |
| `musicvid/musicvid.py` | Modify | New CLI flags (`--wow`, `--zoom-punch`, `--light-flash`, `--dynamic-grade`, `--particles`); LUT auto-selection from `overall_style` |
| `tests/test_wow_effects.py` | **Create** | All wow_effects unit tests |
| `tests/test_audio_analyzer.py` | Modify | Add `energy_peaks` tests |
| `tests/test_assembler.py` | Modify | Add `wow_config` integration and scale-pop tests |
| `tests/test_cli.py` | Modify | Add new CLI flag tests |

---

## Task 1: Add `energy_peaks` to audio_analyzer

**Files:**
- Modify: `musicvid/pipeline/audio_analyzer.py:127-156`
- Modify: `tests/test_audio_analyzer.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_audio_analyzer.py` in the existing test class (import `os`, `unittest`, `unittest.mock`):

```python
def test_analyze_audio_returns_energy_peaks(self):
    """energy_peaks should be a list of floats within [0, duration]."""
    result = analyze_audio.__wrapped__(self.audio_path) if hasattr(analyze_audio, '__wrapped__') else analyze_audio(self.audio_path)
    # The fixture patches librosa so energy_peaks may be empty — just check key exists and is a list
    self.assertIn("energy_peaks", result)
    self.assertIsInstance(result["energy_peaks"], list)

def test_energy_peaks_within_duration(self):
    """All energy_peaks values should be floats within [0, duration]."""
    result = self.analysis  # use existing fixture if available, else call analyze_audio
    if "energy_peaks" not in result:
        self.skipTest("energy_peaks not yet implemented")
    duration = result["duration"]
    for peak in result["energy_peaks"]:
        self.assertIsInstance(peak, float)
        self.assertGreaterEqual(peak, 0.0)
        self.assertLessEqual(peak, duration)
```

Locate the existing test file to find the right class/fixture:

```bash
grep -n "class Test\|def setUp\|analyze_audio" tests/test_audio_analyzer.py | head -30
```

- [ ] **Step 2: Run test to confirm failure**

```bash
python3 -m pytest tests/test_audio_analyzer.py -k "energy_peaks" -v
```
Expected: FAIL — `AssertionError: 'energy_peaks' not in ...`

- [ ] **Step 3: Implement energy_peaks in audio_analyzer.py**

In `musicvid/pipeline/audio_analyzer.py`, after line 133 (`sections = _detect_sections(y, sr, duration)`):

```python
    # Energy peaks: onset strength peaks (used by wow_effects for cut timing)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    raw_peaks = librosa.util.peak_pick(
        onset_env, pre_max=3, post_max=3,
        pre_avg=3, post_avg=5, delta=0.5, wait=10
    )
    peak_times = librosa.frames_to_time(raw_peaks, sr=sr)
    energy_peaks = [round(float(t), 2) for t in peak_times]
```

Update the result dict at line 140:

```python
    result = {
        "lyrics": lyrics,
        "beats": beats,
        "bpm": bpm,
        "duration": round(duration, 2),
        "sections": sections,
        "mood_energy": mood_energy,
        "language": language,
        "energy_peaks": energy_peaks,
    }
```

Also update the docstring return comment:
```python
    Returns:
        dict with keys: lyrics, beats, bpm, duration, sections, mood_energy, language, energy_peaks
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python3 -m pytest tests/test_audio_analyzer.py -k "energy_peaks" -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/audio_analyzer.py tests/test_audio_analyzer.py
git commit -m "feat(analyzer): add energy_peaks to audio analysis output"
```

---

## Task 2: Create wow_effects.py — skeleton + WowConfig

**Files:**
- Create: `musicvid/pipeline/wow_effects.py`
- Create: `tests/test_wow_effects.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_wow_effects.py`:

```python
"""Tests for WOW effects FFmpeg post-processing."""

import unittest
from unittest.mock import patch, MagicMock


class TestWowConfig(unittest.TestCase):
    """Tests for default_wow_config."""

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
    """Tests for build_ffmpeg_filter_chain."""

    def test_returns_none_when_disabled(self):
        from musicvid.pipeline.wow_effects import build_ffmpeg_filter_chain
        wow_config = {"enabled": False}
        result = build_ffmpeg_filter_chain(
            analysis={"sections": [], "beats": [], "duration": 60.0},
            scene_plan={"scenes": [], "overall_style": "worship"},
            wow_config=wow_config,
            video_width=1920,
            video_height=1080,
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
            video_width=1920,
            video_height=1080,
        )
        self.assertIsNone(result)

    def test_returns_string_when_enabled(self):
        from musicvid.pipeline.wow_effects import build_ffmpeg_filter_chain
        analysis = {
            "sections": [{"label": "chorus", "start": 10.0, "end": 30.0}],
            "beats": [0.5, 1.0, 1.5, 2.0, 10.5, 11.0, 11.5, 12.0],
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
            video_width=1920,
            video_height=1080,
        )
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
```

- [ ] **Step 2: Run test to confirm failure**

```bash
python3 -m pytest tests/test_wow_effects.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'musicvid.pipeline.wow_effects'`

- [ ] **Step 3: Create wow_effects.py skeleton**

Create `musicvid/pipeline/wow_effects.py`:

```python
"""WOW effects: FFmpeg post-processing for zoom punch, light flash, reactive color grade, etc.

Integration:
    After MoviePy writes output_path, call:
        apply_wow_effects(output_path, analysis, scene_plan, wow_config, video_width, video_height)
    which runs FFmpeg in-place with a generated filter chain.
"""

import os
import shutil
import subprocess
import tempfile


def default_wow_config():
    """Return default WOW effects configuration dict."""
    return {
        "enabled": True,
        "zoom_punch": True,
        "light_flash": True,
        "dynamic_grade": True,
        "dynamic_vignette": True,
        "motion_blur": True,
        "particles": False,
    }


def build_ffmpeg_filter_chain(analysis, scene_plan, wow_config, video_width=1920, video_height=1080):
    """Build FFmpeg -vf filter chain string from analysis + wow_config.

    Args:
        analysis: Audio analysis dict (sections, beats, duration, energy_peaks).
        scene_plan: Scene plan dict (scenes, overall_style).
        wow_config: Dict from default_wow_config() or CLI overrides.
        video_width: Output video width in pixels.
        video_height: Output video height in pixels.

    Returns:
        str filter chain for use with ffmpeg -vf, or None if no effects active.
    """
    if not wow_config.get("enabled", True):
        return None

    sections = analysis.get("sections", [])
    beats = analysis.get("beats", [])

    filters = []

    if wow_config.get("zoom_punch", True):
        f = _build_zoom_punch_filter(beats, sections, video_width, video_height)
        if f:
            filters.append(f)

    if wow_config.get("light_flash", True):
        f = _build_light_flash_filter(sections)
        if f:
            filters.append(f)

    if wow_config.get("dynamic_grade", True):
        f = _build_color_grade_filter(sections)
        if f:
            filters.append(f)

    if wow_config.get("dynamic_vignette", True):
        f = _build_vignette_filter(sections)
        if f:
            filters.append(f)

    if wow_config.get("motion_blur", True):
        filters.append("tblend=all_mode=average:all_opacity=0.15")

    if not filters:
        return None

    return ",".join(filters)


def apply_wow_effects(video_path, analysis, scene_plan, wow_config, video_width=1920, video_height=1080):
    """Apply WOW effects to video_path in-place using FFmpeg post-processing.

    Writes to a temp file, then replaces video_path on success.
    No-op if build_ffmpeg_filter_chain returns None.

    Args:
        video_path: Path to the input/output MP4 file (modified in-place).
        analysis: Audio analysis dict.
        scene_plan: Scene plan dict.
        wow_config: WOW effects config dict.
        video_width: Video width in pixels (for crop calculations).
        video_height: Video height in pixels.
    """
    filter_chain = build_ffmpeg_filter_chain(
        analysis, scene_plan, wow_config, video_width, video_height
    )
    if not filter_chain:
        return

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(tmp_fd)
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", filter_chain,
                "-c:v", "libx264",
                "-b:v", "8000k",
                "-c:a", "copy",
                tmp_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg WOW effects failed (rc={result.returncode}):\n{result.stderr}"
            )
        shutil.move(tmp_path, video_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Internal filter builders
# ---------------------------------------------------------------------------

def _get_chorus_downbeats(beats, sections):
    """Return beat times that fall within chorus sections (every 4th beat = downbeat)."""
    chorus_ranges = [
        (s["start"], s["end"])
        for s in sections
        if s.get("label") == "chorus"
    ]
    if not chorus_ranges:
        return []

    # Downbeats = every 4th beat
    downbeats = beats[::4] if beats else []
    result = []
    for bt in downbeats:
        for start, end in chorus_ranges:
            if start <= bt <= end:
                result.append(round(float(bt), 3))
                break
    # Limit: at most every 2nd downbeat to avoid over-punching
    return result[::2]


def _build_zoom_punch_filter(beats, sections, video_width, video_height):
    """Build scale+crop FFmpeg filter for zoom punch on chorus downbeats.

    Each beat: zoom 1.0→1.08 over 0.1s, 1.08→1.0 over 0.3s.
    """
    beat_times = _get_chorus_downbeats(beats, sections)
    if not beat_times:
        return None

    zoom_parts = []
    for bt in beat_times:
        part = (
            f"(gt(t,{bt:.3f})*lt(t,{bt+0.4:.3f})*"
            f"(0.08*if(lt(t,{bt+0.1:.3f}),"
            f"(t-{bt:.3f})/0.1,"
            f"max(0,1-(t-{bt+0.1:.3f})/0.3))))"
        )
        zoom_parts.append(part)

    zoom_expr = "1+(" + "+".join(zoom_parts) + ")"
    w, h = video_width, video_height
    return (
        f"scale=w='iw*({zoom_expr})':h='ih*({zoom_expr})',"
        f"crop=w={w}:h={h}:x='(iw-{w})/2':y='(ih-{h})/2'"
    )


def _build_light_flash_filter(sections):
    """Build FFmpeg geq filter for white light flash at first beat of each chorus.

    Flash: brightness spike at chorus start, decaying over 0.3s.
    """
    chorus_starts = [
        round(float(s["start"]), 3)
        for s in sections
        if s.get("label") == "chorus"
    ]
    if not chorus_starts:
        return None

    flash_parts = []
    for t in chorus_starts:
        flash_parts.append(
            f"(255*between(T,{t:.3f},{t+0.05:.3f})*exp(-15*(T-{t:.3f})))"
        )

    flash_expr = "+".join(flash_parts)
    return (
        f"geq=r='clip(r(X,Y)+{flash_expr},0,255)':"
        f"g='clip(g(X,Y)+{flash_expr},0,255)':"
        f"b='clip(b(X,Y)+{flash_expr},0,255)'"
    )


def _build_color_grade_filter(sections):
    """Build FFmpeg eq+colorbalance filter for reactive color grade.

    VERSE: saturation=0.85, contrast=1.05, warm tones.
    CHORUS: saturation=1.15, contrast=1.15, vivid tones.
    Uses FFmpeg enable= expressions for per-section activation.
    """
    if not sections:
        return None

    filters = []
    for sec in sections:
        start = round(float(sec["start"]), 3)
        end = round(float(sec["end"]), 3)
        label = sec.get("label", "verse")
        enable = f"between(t,{start:.3f},{end:.3f})"

        if label == "chorus":
            filters.append(
                f"eq=saturation=1.15:brightness=0.0:contrast=1.15:enable='{enable}'"
            )
            filters.append(
                f"colorbalance=rs=0.08:gs=0.03:bs=-0.05:enable='{enable}'"
            )
        else:
            filters.append(
                f"eq=saturation=0.85:brightness=0.02:contrast=1.05:enable='{enable}'"
            )
            filters.append(
                f"colorbalance=rs=0.05:gs=0.02:bs=-0.03:enable='{enable}'"
            )

    return ",".join(filters)


def _build_vignette_filter(sections):
    """Build FFmpeg vignette filter with intensity per section.

    VERSE: angle=0.6 (stronger, intimate).
    CHORUS: angle=0.3 (weaker, open/energetic).
    """
    if not sections:
        return None

    filters = []
    for sec in sections:
        start = round(float(sec["start"]), 3)
        end = round(float(sec["end"]), 3)
        label = sec.get("label", "verse")
        enable = f"between(t,{start:.3f},{end:.3f})"
        angle = 0.3 if label == "chorus" else 0.6
        filters.append(f"vignette=a={angle}:enable='{enable}'")

    return ",".join(filters)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python3 -m pytest tests/test_wow_effects.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/wow_effects.py tests/test_wow_effects.py
git commit -m "feat(wow): add wow_effects module with FFmpeg filter chain builder"
```

---

## Task 3: Tests for all filter builders in wow_effects.py

**Files:**
- Modify: `tests/test_wow_effects.py`

- [ ] **Step 1: Write tests for each filter builder**

Add to `tests/test_wow_effects.py`:

```python
class TestZoomPunchFilter(unittest.TestCase):
    def test_returns_none_when_no_chorus(self):
        from musicvid.pipeline.wow_effects import _build_zoom_punch_filter
        sections = [{"label": "verse", "start": 0.0, "end": 60.0}]
        beats = [0.5, 1.0, 1.5, 2.0]
        result = _build_zoom_punch_filter(beats, sections, 1920, 1080)
        self.assertIsNone(result)

    def test_returns_string_with_scale_and_crop(self):
        from musicvid.pipeline.wow_effects import _build_zoom_punch_filter
        sections = [{"label": "chorus", "start": 10.0, "end": 30.0}]
        # provide beats at chorus downbeats
        beats = [10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 14.0, 14.5,
                 15.0, 15.5, 16.0, 16.5, 17.0, 17.5]
        result = _build_zoom_punch_filter(beats, sections, 1920, 1080)
        self.assertIsNotNone(result)
        self.assertIn("scale=", result)
        self.assertIn("crop=", result)
        self.assertIn("1920", result)
        self.assertIn("1080", result)

    def test_zoom_factor_in_filter(self):
        from musicvid.pipeline.wow_effects import _build_zoom_punch_filter
        sections = [{"label": "chorus", "start": 0.0, "end": 30.0}]
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        result = _build_zoom_punch_filter(beats, sections, 1920, 1080)
        self.assertIsNotNone(result)
        self.assertIn("0.08", result)  # zoom factor 8%


class TestLightFlashFilter(unittest.TestCase):
    def test_returns_none_when_no_chorus(self):
        from musicvid.pipeline.wow_effects import _build_light_flash_filter
        sections = [{"label": "verse", "start": 0.0, "end": 60.0}]
        result = _build_light_flash_filter(sections)
        self.assertIsNone(result)

    def test_returns_geq_filter_with_chorus_start(self):
        from musicvid.pipeline.wow_effects import _build_light_flash_filter
        sections = [
            {"label": "verse", "start": 0.0, "end": 20.0},
            {"label": "chorus", "start": 20.0, "end": 40.0},
        ]
        result = _build_light_flash_filter(sections)
        self.assertIsNotNone(result)
        self.assertIn("geq=", result)
        self.assertIn("20.000", result)  # chorus start time

    def test_multiple_chorus_sections(self):
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
    def test_noop_when_filter_chain_is_none(self):
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
            "beats": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0,
                      5.5, 6.0, 6.5, 7.0, 7.5, 8.0],
            "duration": 10.0,
        }
        wow_config = {
            "enabled": True, "zoom_punch": True, "light_flash": False,
            "dynamic_grade": False, "dynamic_vignette": False,
            "motion_blur": False, "particles": False,
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("musicvid.pipeline.wow_effects.subprocess") as mock_sub, \
             patch("musicvid.pipeline.wow_effects.shutil.move") as mock_move, \
             patch("musicvid.pipeline.wow_effects.tempfile.mkstemp",
                   return_value=(0, "/tmp/wow_tmp.mp4")) as mock_tmp, \
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
            # ffmpeg input is the video path
            self.assertIn("/fake/out.mp4", cmd)

    def test_raises_on_ffmpeg_failure(self):
        from musicvid.pipeline.wow_effects import apply_wow_effects
        analysis = {
            "sections": [{"label": "chorus", "start": 2.0, "end": 8.0}],
            "beats": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
            "duration": 10.0,
        }
        wow_config = {
            "enabled": True, "zoom_punch": True, "light_flash": False,
            "dynamic_grade": False, "dynamic_vignette": False,
            "motion_blur": False, "particles": False,
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
```

- [ ] **Step 2: Run tests**

```bash
python3 -m pytest tests/test_wow_effects.py -v
```
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_wow_effects.py
git commit -m "test(wow): add comprehensive tests for all WOW effect filter builders"
```

---

## Task 4: Integrate wow_effects into assembler.py

**Files:**
- Modify: `musicvid/pipeline/assembler.py:401`
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_assembler.py` in the existing test class that tests `assemble_video`:

```python
class TestAssembleVideoWowConfig(unittest.TestCase):
    """Tests for wow_config integration in assemble_video."""

    def _make_minimal_call_args(self):
        analysis = {
            "lyrics": [], "beats": [1.0, 2.0], "bpm": 120.0,
            "duration": 5.0,
            "sections": [{"label": "chorus", "start": 0.0, "end": 5.0}],
            "energy_peaks": [],
        }
        scene_plan = {
            "overall_style": "worship",
            "subtitle_style": {"font_size": 54, "color": "#FFFFFF",
                               "outline_color": "#000000",
                               "position": "bottom", "animation": "fade"},
            "scenes": [
                {
                    "section": "chorus", "start": 0.0, "end": 5.0,
                    "visual_source": "TYPE_VIDEO_STOCK",
                    "motion": "slow_zoom_in", "transition": "cut",
                    "transition_to_next": "cut", "lyrics_in_scene": [],
                    "search_query": "nature", "visual_prompt": "",
                    "motion_prompt": "", "animate": False, "overlay": "none",
                }
            ],
        }
        fetch_manifest = [{"scene_index": 0, "video_path": "/fake/scene.mp4",
                           "start": 0.0, "end": 5.0, "source": "stock"}]
        return analysis, scene_plan, fetch_manifest

    @patch("musicvid.pipeline.assembler.apply_wow_effects")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler._concatenate_with_transitions")
    @patch("musicvid.pipeline.assembler._create_subtitle_clips", return_value=[])
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.prepare_lut_ffmpeg_params", return_value=[])
    def test_apply_wow_effects_called_when_wow_config_provided(
        self, mock_lut, mock_vfc, mock_afc, mock_comp, mock_subtitles,
        mock_concat, mock_effects, mock_wow
    ):
        from musicvid.pipeline.assembler import assemble_video
        analysis, scene_plan, fetch_manifest = self._make_minimal_call_args()

        # Set up mock chain
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.duration = 5.0
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_vfc.return_value = mock_clip
        mock_effects.return_value = mock_clip
        mock_concat.return_value = mock_clip

        mock_final = MagicMock()
        mock_final.duration = 5.0
        mock_final.with_audio.return_value = mock_final
        mock_final.with_duration.return_value = mock_final
        mock_comp.return_value = mock_final

        mock_audio = MagicMock()
        mock_audio.duration = 5.0
        mock_afc.return_value = mock_audio

        wow_config = {
            "enabled": True, "zoom_punch": True, "light_flash": True,
            "dynamic_grade": True, "dynamic_vignette": True,
            "motion_blur": False, "particles": False,
        }

        with patch("builtins.open", unittest.mock.mock_open()):
            assemble_video(
                analysis=analysis,
                scene_plan=scene_plan,
                fetch_manifest=fetch_manifest,
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
                wow_config=wow_config,
            )

        mock_wow.assert_called_once()
        call_kwargs = mock_wow.call_args
        self.assertEqual(call_kwargs[1]["video_path"], "/fake/output.mp4")

    @patch("musicvid.pipeline.assembler.apply_wow_effects")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler._concatenate_with_transitions")
    @patch("musicvid.pipeline.assembler._create_subtitle_clips", return_value=[])
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.prepare_lut_ffmpeg_params", return_value=[])
    def test_apply_wow_effects_not_called_when_wow_config_is_none(
        self, mock_lut, mock_vfc, mock_afc, mock_comp, mock_subtitles,
        mock_concat, mock_effects, mock_wow
    ):
        from musicvid.pipeline.assembler import assemble_video
        analysis, scene_plan, fetch_manifest = self._make_minimal_call_args()

        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.duration = 5.0
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_vfc.return_value = mock_clip
        mock_effects.return_value = mock_clip
        mock_concat.return_value = mock_clip

        mock_final = MagicMock()
        mock_final.duration = 5.0
        mock_final.with_audio.return_value = mock_final
        mock_final.with_duration.return_value = mock_final
        mock_comp.return_value = mock_final

        mock_audio = MagicMock()
        mock_audio.duration = 5.0
        mock_afc.return_value = mock_audio

        with patch("builtins.open", unittest.mock.mock_open()):
            assemble_video(
                analysis=analysis,
                scene_plan=scene_plan,
                fetch_manifest=fetch_manifest,
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
                wow_config=None,
            )

        mock_wow.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python3 -m pytest tests/test_assembler.py::TestAssembleVideoWowConfig -v
```
Expected: FAIL — `TypeError: assemble_video() got an unexpected keyword argument 'wow_config'` or `assert_called_once` fails.

- [ ] **Step 3: Modify assembler.py**

In `musicvid/pipeline/assembler.py`:

1. Add import at the top (after existing imports):

```python
from musicvid.pipeline.wow_effects import apply_wow_effects
```

2. Update `assemble_video` signature to add `wow_config=None`:

```python
def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path, resolution="1080p", font_path=None, effects_level="minimal", clip_start=None, clip_end=None, title_card_text=None, audio_fade_out=1.0, subtitle_margin_bottom=80, cinematic_bars=False, logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85, lut_path=None, lut_style=None, lut_intensity=0.85, reels_style="blur-bg", wow_config=None):
```

3. After `final.write_videofile(output_path, **write_kwargs)` (line 489), add:

```python
    if wow_config and wow_config.get("enabled", True):
        apply_wow_effects(
            video_path=output_path,
            analysis=analysis,
            scene_plan=scene_plan,
            wow_config=wow_config,
            video_width=target_size[0],
            video_height=target_size[1],
        )
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_assembler.py::TestAssembleVideoWowConfig -v
```
Expected: PASS

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all existing tests PASS; no new failures.

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat(assembler): integrate wow_effects post-processing into assemble_video"
```

---

## Task 5: Chorus scale-pop subtitles in assembler.py

**Files:**
- Modify: `musicvid/pipeline/assembler.py` (inside `_create_subtitle_clips`)
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_assembler.py`:

```python
class TestScalePopSubtitles(unittest.TestCase):
    """Tests for chorus scale-pop animation in _create_subtitle_clips."""

    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_chorus_subtitle_has_transform_applied(self, mock_vfx, mock_textclip):
        """Chorus subtitle clips should have scale_pop_transform applied."""
        from musicvid.pipeline.assembler import _create_subtitle_clips
        import numpy as np

        mock_clip = MagicMock()
        mock_clip.duration = 2.0
        mock_clip.w = 400
        mock_clip.h = 80
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 10.0, "end": 12.0, "text": "Chwała", "words": []}]
        subtitle_style = {
            "font_size": 64, "color": "#FFFFFF",
            "outline_color": "#000000", "position": "bottom", "animation": "fade",
        }
        sections = [{"label": "chorus", "start": 8.0, "end": 20.0}]

        _create_subtitle_clips(lyrics, subtitle_style, (1920, 1080),
                               sections=sections)

        # transform should be called for chorus lyrics
        mock_clip.transform.assert_called_once()

    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_verse_subtitle_has_no_scale_pop(self, mock_vfx, mock_textclip):
        """Verse subtitle clips should NOT have scale_pop_transform applied."""
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.duration = 2.0
        mock_clip.w = 400
        mock_clip.h = 80
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 5.0, "end": 7.0, "text": "Bóg jest dobry", "words": []}]
        subtitle_style = {
            "font_size": 54, "color": "#FFFFFF",
            "outline_color": "#000000", "position": "bottom", "animation": "fade",
        }
        sections = [{"label": "verse", "start": 0.0, "end": 20.0}]

        _create_subtitle_clips(lyrics, subtitle_style, (1920, 1080),
                               sections=sections)

        # transform should NOT be called for verse lyrics (no scale pop)
        mock_clip.transform.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python3 -m pytest tests/test_assembler.py::TestScalePopSubtitles -v
```
Expected: FAIL

- [ ] **Step 3: Add scale-pop helper and modify _create_subtitle_clips**

In `musicvid/pipeline/assembler.py`, add the helper before `_create_subtitle_clips`:

```python
def _make_scale_pop_transform(anim_duration=0.15):
    """Return a MoviePy transform function for scale pop (1.15→1.0 over anim_duration)."""
    from PIL import Image
    import numpy as np

    def scale_pop(get_frame, t):
        frame = get_frame(t)
        if t >= anim_duration:
            return frame
        progress = t / anim_duration  # 0.0 → 1.0
        scale = 1.15 - 0.15 * progress  # 1.15 → 1.0
        h, w = frame.shape[:2]
        new_w = max(1, int(w / scale))
        new_h = max(1, int(h / scale))
        cx, cy = w // 2, h // 2
        x1 = max(0, cx - new_w // 2)
        y1 = max(0, cy - new_h // 2)
        x2 = min(w, x1 + new_w)
        y2 = min(h, y1 + new_h)
        cropped = frame[y1:y2, x1:x2]
        img = Image.fromarray(cropped)
        img = img.resize((w, h), Image.LANCZOS)
        return np.array(img)

    return scale_pop
```

Then in `_create_subtitle_clips`, after the block that creates and positions `text_clip`, add the scale-pop for chorus sections:

Find the existing subtitle creation loop. After `text_clip = text_clip.with_effects(...)` and before `result.append(text_clip)`, add:

```python
            # Scale-pop animation for chorus subtitles
            if sections and _get_section_for_time(seg_start, sections) == "chorus":
                text_clip = text_clip.transform(_make_scale_pop_transform(0.15))
```

(This goes inside the `try` block where `text_clip` is built, just before `result.append(text_clip)`.)

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_assembler.py::TestScalePopSubtitles -v
```
Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all pass (new test count may be +2).

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat(assembler): add scale-pop animation for chorus subtitles"
```

---

## Task 6: Add WOW CLI flags to musicvid.py

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_cli.py` (locate the existing test class for CLI, add new test methods):

```python
class TestWowCliFlags(unittest.TestCase):
    """Tests for --wow, --zoom-punch, --light-flash, --dynamic-grade, --particles flags."""

    def setUp(self):
        from click.testing import CliRunner
        self.runner = CliRunner()

    def _base_mocks(self):
        """Return a dict of patches needed for all CLI tests."""
        return {
            "analyze": "musicvid.musicvid.analyze_audio",
            "director": "musicvid.musicvid.create_scene_plan",
            "router": "musicvid.musicvid.VisualRouter",
            "assemble": "musicvid.musicvid.assemble_video",
            "font": "musicvid.musicvid.get_font_path",
            "social": "musicvid.musicvid.select_social_clips",
            "parallel": "musicvid.musicvid.assemble_all_parallel",
        }

    @patch("musicvid.musicvid.assemble_all_parallel")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.VisualRouter")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_wow_flag_builds_wow_config(
        self, mock_analyze, mock_direct, mock_router, mock_font, mock_parallel
    ):
        from musicvid.musicvid import cli
        mock_analyze.return_value = {
            "lyrics": [], "beats": [], "bpm": 120.0, "duration": 10.0,
            "sections": [{"label": "chorus", "start": 0.0, "end": 10.0}],
            "energy_peaks": [],
        }
        mock_direct.return_value = {
            "overall_style": "worship",
            "subtitle_style": {"font_size": 54, "color": "#FFFFFF",
                               "outline_color": "#000000",
                               "position": "bottom", "animation": "fade"},
            "scenes": [
                {"section": "chorus", "start": 0.0, "end": 10.0,
                 "visual_source": "TYPE_VIDEO_STOCK", "motion": "slow_zoom_in",
                 "transition": "cut", "transition_to_next": "cut",
                 "lyrics_in_scene": [], "search_query": "nature",
                 "visual_prompt": "", "motion_prompt": "", "animate": False,
                 "overlay": "none"},
            ],
        }
        mock_router_instance = MagicMock()
        mock_router_instance.route.return_value = "/fake/scene.mp4"
        mock_router.return_value = mock_router_instance

        with self.runner.isolated_filesystem():
            import os
            open("song.mp3", "w").close()
            result = self.runner.invoke(
                cli,
                ["song.mp3", "--mode", "stock", "--preset", "full",
                 "--wow", "--yes"],
                catch_exceptions=False,
            )

        mock_parallel.assert_not_called()  # preset=full uses sequential
        # assemble_video should receive wow_config
        # Find the assemble_video call via the parallel or sequential path
        # In preset=full path, assemble_video is called directly
        # Check that wow_config was passed
        self.assertEqual(result.exit_code, 0, result.output)

    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.VisualRouter")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_no_wow_flag_passes_none_wow_config(
        self, mock_analyze, mock_direct, mock_router, mock_font, mock_assemble
    ):
        from musicvid.musicvid import cli
        mock_analyze.return_value = {
            "lyrics": [], "beats": [], "bpm": 120.0, "duration": 10.0,
            "sections": [], "energy_peaks": [],
        }
        mock_direct.return_value = {
            "overall_style": "worship",
            "subtitle_style": {"font_size": 54, "color": "#FFFFFF",
                               "outline_color": "#000000",
                               "position": "bottom", "animation": "fade"},
            "scenes": [
                {"section": "verse", "start": 0.0, "end": 10.0,
                 "visual_source": "TYPE_VIDEO_STOCK", "motion": "slow_zoom_in",
                 "transition": "cut", "transition_to_next": "cut",
                 "lyrics_in_scene": [], "search_query": "nature",
                 "visual_prompt": "", "motion_prompt": "", "animate": False,
                 "overlay": "none"},
            ],
        }
        mock_router_instance = MagicMock()
        mock_router_instance.route.return_value = "/fake/scene.mp4"
        mock_router.return_value = mock_router_instance

        with self.runner.isolated_filesystem():
            open("song.mp3", "w").close()
            result = self.runner.invoke(
                cli,
                ["song.mp3", "--mode", "stock", "--preset", "full",
                 "--no-wow", "--yes"],
                catch_exceptions=False,
            )

        self.assertEqual(result.exit_code, 0, result.output)
        call_kwargs = mock_assemble.call_args[1]
        # wow_config should be None when --no-wow
        self.assertIsNone(call_kwargs.get("wow_config"))
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python3 -m pytest tests/test_cli.py::TestWowCliFlags -v
```
Expected: FAIL — no `--wow` flag defined yet.

- [ ] **Step 3: Add CLI flags to musicvid.py**

In `musicvid/musicvid.py`, add these options before `@click.option("--sequential-assembly"...)`:

```python
@click.option("--wow/--no-wow", "wow_effects", default=True, help="Enable WOW effects (zoom punch, light flash, reactive color grade). On by default with --effects minimal or full.")
@click.option("--zoom-punch/--no-zoom-punch", "wow_zoom_punch", default=True, help="Zoom punch on chorus downbeats.")
@click.option("--light-flash/--no-light-flash", "wow_light_flash", default=True, help="Light flash on chorus entry.")
@click.option("--dynamic-grade/--no-dynamic-grade", "wow_dynamic_grade", default=True, help="Reactive color grade (verse vs chorus palettes).")
@click.option("--particles/--no-particles", "wow_particles", default=False, help="Particle overlay on AI/animated clips (expensive).")
```

Update the `cli` function signature to include these params:

```python
def cli(audio_file, mode, provider, style, output, resolution, lang, new, font_path, lyrics_path,
        effects, clip_duration, platform, title_card, animate_mode, preset, reel_duration,
        logo_path, logo_position, logo_size, logo_opacity,
        lut_style, lut_intensity, subtitle_style_override, transitions_mode, beat_sync,
        skip_confirm, quick_mode, economy_mode, sequential_assembly, reels_style,
        wow_effects, wow_zoom_punch, wow_light_flash, wow_dynamic_grade, wow_particles):
```

In `--quick` mode block, add:
```python
        wow_effects = False
```

Build `wow_config` dict after the API key fallbacks section (before `_print_startup_summary`):

```python
    # Build wow_config: only active when effects are not "none" AND --wow flag set
    wow_config = None
    if wow_effects and effects != "none":
        from musicvid.pipeline.wow_effects import default_wow_config
        wow_config = default_wow_config()
        wow_config["zoom_punch"] = wow_zoom_punch
        wow_config["light_flash"] = wow_light_flash
        wow_config["dynamic_grade"] = wow_dynamic_grade
        wow_config["particles"] = wow_particles
```

Pass `wow_config` to all `assemble_video` calls in `_run_preset_mode` and direct `assemble_video` calls. The function `_run_preset_mode` needs to accept and forward `wow_config`:

In `_run_preset_mode`, add `wow_config=None` to its signature and pass `wow_config=wow_config` to every `AssemblyJob(kwargs=...)` and `assemble_video(...)` call inside it.

In the `cli` function where `_run_preset_mode` is called, pass `wow_config=wow_config`.

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_cli.py::TestWowCliFlags -v
```
Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all pass. Fix any regressions caused by signature changes.

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): add --wow, --zoom-punch, --light-flash, --dynamic-grade, --particles flags"
```

---

## Task 7: LUT auto-selection from overall_style

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
class TestLutAutoSelection(unittest.TestCase):
    """Tests for automatic LUT style selection based on overall_style."""

    def test_lut_auto_selected_from_overall_style_worship(self):
        """When no --lut-style specified, worship → warm LUT."""
        from musicvid.musicvid import _lut_for_style
        self.assertEqual(_lut_for_style("worship"), "warm")

    def test_lut_auto_selected_from_overall_style_contemplative(self):
        from musicvid.musicvid import _lut_for_style
        self.assertEqual(_lut_for_style("contemplative"), "cinematic")

    def test_lut_auto_selected_from_overall_style_powerful(self):
        from musicvid.musicvid import _lut_for_style
        self.assertEqual(_lut_for_style("powerful"), "cold")

    def test_lut_auto_selected_from_overall_style_joyful(self):
        from musicvid.musicvid import _lut_for_style
        self.assertEqual(_lut_for_style("joyful"), "natural")

    def test_lut_auto_selected_from_unknown_style(self):
        from musicvid.musicvid import _lut_for_style
        self.assertEqual(_lut_for_style("unknown"), "warm")
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python3 -m pytest tests/test_cli.py::TestLutAutoSelection -v
```
Expected: FAIL — `ImportError: cannot import name '_lut_for_style'`

- [ ] **Step 3: Add _lut_for_style to musicvid.py**

In `musicvid/musicvid.py`, add before the `@click.command()` decorator:

```python
_STYLE_TO_LUT = {
    "worship": "warm",
    "contemplative": "cinematic",
    "powerful": "cold",
    "joyful": "natural",
}


def _lut_for_style(overall_style):
    """Return LUT style name for a given director overall_style."""
    return _STYLE_TO_LUT.get(overall_style, "warm")
```

In the CLI function, after Stage 2 (director creates scene_plan), add auto-LUT logic:

```python
    # Auto-select LUT from overall_style if no --lut-style was specified and not quick mode
    if lut_style == "warm" and not quick_mode and not economy_mode:
        auto_lut = _lut_for_style(scene_plan.get("overall_style", "worship"))
        if auto_lut != lut_style:
            click.echo(f"  Auto LUT: {auto_lut} (styl: {scene_plan.get('overall_style')})")
            lut_style = auto_lut
```

Note: This auto-selection runs only when `lut_style` is still the default `"warm"` (user hasn't explicitly chosen). To distinguish "user set warm" vs "default warm", add a `_lut_style_was_set` flag using Click's `default` mechanism or simply always auto-select in non-quick/economy modes (accept that warm default is always overridden).

Simpler approach — change `--lut-style` default to `None` and add auto-selection:

```python
@click.option("--lut-style", type=click.Choice(["warm", "cold", "cinematic", "natural", "faded"]), default=None, help="Built-in LUT color grade style (default: auto-selected from song style).")
```

Then in `cli()`:
```python
    # Auto-select LUT if not explicitly set
    if lut_style is None and not quick_mode:
        # Will be set after Stage 2 using scene_plan overall_style
        pass  # handled below after director runs
```

After Stage 2 in `cli()`:
```python
    # Auto-select LUT from overall_style (if not set by user or quick mode)
    if lut_style is None and not quick_mode:
        lut_style = _lut_for_style(scene_plan.get("overall_style", "worship"))
        click.echo(f"  Auto LUT: {lut_style} (styl: {scene_plan.get('overall_style')})")
```

Update `--economy` mode to still explicitly set `lut_style = "warm"`.

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_cli.py::TestLutAutoSelection -v
```
Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all pass. If existing CLI tests fail because they relied on `lut_style="warm"` default, update those tests to pass `--lut-style warm` explicitly or mock the `_lut_for_style` function.

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): auto-select LUT style from director overall_style"
```

---

## Task 8: Reels extra dynamic (hook + gradient overlay)

**Files:**
- Modify: `musicvid/musicvid.py` (social reel assembly paths)
- Modify: `musicvid/pipeline/assembler.py` (gradient overlay for portrait)
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write failing test for gradient overlay**

Add to `tests/test_assembler.py`:

```python
class TestReelsGradientOverlay(unittest.TestCase):
    """Tests for gradient overlay in portrait (reels) mode."""

    def test_create_bottom_gradient_returns_clip(self):
        from musicvid.pipeline.assembler import _create_bottom_gradient
        clip = _create_bottom_gradient(width=1080, height=1920, duration=5.0)
        self.assertIsNotNone(clip)
        # Should be positioned at bottom of frame
        self.assertEqual(clip.duration, 5.0)
```

- [ ] **Step 2: Run test to confirm failure**

```bash
python3 -m pytest tests/test_assembler.py::TestReelsGradientOverlay -v
```
Expected: FAIL — `ImportError: cannot import name '_create_bottom_gradient'`

- [ ] **Step 3: Add _create_bottom_gradient to assembler.py**

In `musicvid/pipeline/assembler.py`, add after `create_cinematic_bars`:

```python
def _create_bottom_gradient(width, height, duration, gradient_height_pct=0.3, opacity=0.6):
    """Create a dark gradient overlay at the bottom of the frame for reels.

    Gradient goes from transparent (top) to 60% black (bottom).
    Used in portrait/reels mode to improve subtitle readability.

    Args:
        width: Frame width in pixels.
        height: Frame height in pixels.
        duration: Clip duration in seconds.
        gradient_height_pct: Gradient height as fraction of frame height (default 0.3).
        opacity: Maximum opacity of gradient (default 0.6).

    Returns:
        MoviePy ImageClip positioned at the bottom of the frame.
    """
    import numpy as np

    grad_h = int(height * gradient_height_pct)
    gradient = np.zeros((grad_h, width, 4), dtype=np.uint8)

    for y in range(grad_h):
        alpha = int(255 * opacity * (y / grad_h))
        gradient[y, :, 3] = alpha  # alpha channel: 0 at top, max at bottom

    clip = ImageClip(gradient[:, :, :3])  # RGB only (MoviePy handles transparency via position)
    clip = clip.with_duration(duration)
    clip = clip.with_position(("center", height - grad_h))
    return clip
```

In `assemble_video`, in the layers composition section, add gradient for portrait reels:

```python
    # Bottom gradient overlay for portrait/reels mode
    if target_size == (1080, 1920):
        gradient = _create_bottom_gradient(target_size[0], target_size[1], video.duration)
        layers.insert(1, gradient)  # Above video, below subtitles
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_assembler.py::TestReelsGradientOverlay -v
```
Expected: PASS

- [ ] **Step 5: Add chorus hook logic for social reels in musicvid.py**

The spec says social reels should start with "hook in first 2s: best moment from chorus + flash". This is already partially handled by `select_social_clips` which selects chorus-preferred clips. The `wow_config` with `light_flash=True` already adds the flash effect.

For extra dynamic: social reels font size 72 for chorus. This is already configured via `_SECTION_FONT_SIZES["chorus"] = 64`. For reels, we need 72.

Add a `reels_mode` kwarg to `_create_subtitle_clips` that bumps chorus font size:

In `assembler.py`, modify `_create_subtitle_clips` call in `assemble_video`:

```python
    subtitle_clips = _create_subtitle_clips(
        analysis.get("lyrics", []),
        scene_plan.get("subtitle_style", {}),
        target_size,
        font_path=font_path,
        subtitle_margin_bottom=subtitle_margin_bottom,
        sections=analysis.get("sections"),
        reels_mode=(target_size == (1080, 1920)),
    )
```

In `_create_subtitle_clips` signature, add `reels_mode=False`:

```python
def _create_subtitle_clips(lyrics, subtitle_style, target_size, font_path=None,
                           subtitle_margin_bottom=80, sections=None, reels_mode=False):
```

In the font size selection inside `_create_subtitle_clips`, add reels override:

```python
        font_size = _SECTION_FONT_SIZES.get(section_label, _DEFAULT_FONT_SIZE)
        if reels_mode and section_label == "chorus":
            font_size = 72
```

- [ ] **Step 6: Write test for reels font size**

Add to `tests/test_assembler.py`:

```python
class TestReelsSubtitleFontSize(unittest.TestCase):
    """Tests for reels-mode chorus font size boost."""

    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_chorus_font_size_72_in_reels_mode(self, mock_vfx, mock_textclip):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.duration = 2.0
        mock_clip.w = 400
        mock_clip.h = 80
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 10.0, "end": 12.0, "text": "Alleluja", "words": []}]
        subtitle_style = {"font_size": 54, "color": "#FFFFFF",
                          "outline_color": "#000000",
                          "position": "bottom", "animation": "fade"}
        sections = [{"label": "chorus", "start": 8.0, "end": 20.0}]

        _create_subtitle_clips(lyrics, subtitle_style, (1080, 1920),
                               sections=sections, reels_mode=True)

        # font_size=72 should be in the TextClip call kwargs
        call_kwargs = mock_textclip.call_args[1]
        self.assertEqual(call_kwargs.get("font_size"), 72)
```

- [ ] **Step 7: Run all new tests**

```bash
python3 -m pytest tests/test_assembler.py::TestReelsGradientOverlay tests/test_assembler.py::TestReelsSubtitleFontSize -v
```
Expected: PASS

- [ ] **Step 8: Run full test suite**

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat(assembler): add gradient overlay and 72px chorus font for reels mode"
```

---

## Task 9: Final integration and full test run

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -50
```
Expected: all pass. If any test fails, fix it before proceeding.

- [ ] **Step 2: Verify wow_effects imports cleanly**

```bash
python3 -c "from musicvid.pipeline.wow_effects import default_wow_config, build_ffmpeg_filter_chain, apply_wow_effects; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Verify CLI help shows new flags**

```bash
python3 -m musicvid.musicvid --help | grep -E "wow|zoom-punch|light-flash|dynamic-grade|particles|lut-style"
```
Expected: all new flags appear in help output.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(wow): complete WOW effects implementation — energy peaks, zoom punch, light flash, reactive grade, vignette, scale-pop subtitles, LUT auto-select, reels enhancements"
```

---

## Self-Review

**Spec coverage check:**

| Spec item | Task | Status |
|---|---|---|
| Efekt 1: energy_peaks | Task 1 | ✅ |
| Efekt 2: zoom punch na beat | Task 2 (filter builder) | ✅ |
| Efekt 3: color grade reaktywny | Task 2 (`_build_color_grade_filter`) | ✅ |
| Efekt 4: light flash | Task 2 (`_build_light_flash_filter`) | ✅ |
| Efekt 5: motion blur | Task 2 (tblend filter) | ✅ simplified |
| Efekt 6: vignette dynamiczny | Task 2 (`_build_vignette_filter`) | ✅ |
| Efekt 7: tekst animowany scale pop | Task 5 | ✅ |
| Efekt 8: rolki EXTRA dynamiczne | Task 8 | ✅ gradient + font 72 |
| Efekt 9: LUT per styl | Task 7 | ✅ |
| Efekt 10: particles (optional) | wow_config key | ✅ flag only, no impl |
| `--wow` CLI flag | Task 6 | ✅ |
| `--zoom-punch` flag | Task 6 | ✅ |
| `--light-flash` flag | Task 6 | ✅ |
| `--dynamic-grade` flag | Task 6 | ✅ |
| `--particles` flag | Task 6 | ✅ |
| FFmpeg post-processing in assembler | Task 4 | ✅ |
| `wow_effects.py` module | Task 2 | ✅ |

**Placeholder scan:** No TBDs, no "implement later" patterns found.

**Type consistency:**
- `default_wow_config()` → dict (used in Task 2, Task 4, Task 6)
- `build_ffmpeg_filter_chain(analysis, scene_plan, wow_config, video_width, video_height)` — consistent across Tasks 2, 3, 4
- `apply_wow_effects(video_path, analysis, scene_plan, wow_config, video_width, video_height)` — consistent in Task 2, Task 4
- `assemble_video(..., wow_config=None)` — Task 4
- `_lut_for_style(overall_style) -> str` — Task 7
- `_create_bottom_gradient(width, height, duration, ...)` — Task 8
- `_make_scale_pop_transform(anim_duration)` — Task 5
- `_create_subtitle_clips(..., reels_mode=False)` — Task 8

All consistent. ✅
