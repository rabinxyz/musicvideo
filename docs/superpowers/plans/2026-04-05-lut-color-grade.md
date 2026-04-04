# LUT Color Grading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add professional color grading via LUT (Look Up Table) to every video, applied through FFmpeg at export time for maximum performance.

**Architecture:** New `musicvid/pipeline/color_grade.py` module generates built-in LUT styles (warm/cold/cinematic/natural/faded) as numpy 33x33x33 3D arrays, saves them as `.cube` files, and returns FFmpeg filter strings. The assembler passes `ffmpeg_params` to `write_videofile()` so FFmpeg applies the LUT natively during export — no per-frame Python processing.

**Tech Stack:** numpy (LUT generation), FFmpeg lut3d filter (application), Click (CLI), pytest + unittest.mock (tests)

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `musicvid/pipeline/color_grade.py` | LUT generation, .cube file I/O, FFmpeg filter string building |
| **Create:** `tests/test_color_grade.py` | Unit tests for all color_grade functions |
| **Modify:** `musicvid/pipeline/assembler.py` | Accept LUT params, pass `ffmpeg_params` to `write_videofile()` |
| **Modify:** `musicvid/musicvid.py` | Add `--lut`, `--lut-style`, `--lut-intensity` CLI options; pass to assembler |
| **Modify:** `tests/test_assembler.py` | Test LUT params flow through assembler to `write_videofile` |
| **Modify:** `tests/test_cli.py` | Test CLI flags pass correct values to assembler |

---

### Task 1: Core LUT Generation — `generate_builtin_lut()`

**Files:**
- Create: `tests/test_color_grade.py`
- Create: `musicvid/pipeline/color_grade.py`

- [ ] **Step 1: Write failing tests for `generate_builtin_lut`**

```python
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
        # Check midpoint (16,16,16) — neutral gray input
        mid = lut[16, 16, 16]
        # Red channel should be boosted relative to blue
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_color_grade.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'musicvid.pipeline.color_grade'`

- [ ] **Step 3: Implement `generate_builtin_lut`**

Create `musicvid/pipeline/color_grade.py`:

```python
"""LUT (Look Up Table) color grading for cinematic video output."""

import numpy as np


def _identity_lut(size=33):
    """Generate identity LUT — no color change."""
    r = np.linspace(0, 1, size)
    g = np.linspace(0, 1, size)
    b = np.linspace(0, 1, size)
    rr, gg, bb = np.meshgrid(r, g, b, indexing="ij")
    lut = np.stack([rr, gg, bb], axis=-1)
    return lut


def _apply_contrast(lut, amount):
    """Apply S-curve contrast to LUT values."""
    mid = 0.5
    lut = mid + (lut - mid) * (1 + amount)
    return np.clip(lut, 0, 1)


def _apply_saturation(lut, amount):
    """Adjust saturation. amount=-0.1 means 10% less saturated."""
    gray = 0.2126 * lut[..., 0] + 0.7152 * lut[..., 1] + 0.0722 * lut[..., 2]
    gray = gray[..., np.newaxis]
    lut = gray + (lut - gray) * (1 + amount)
    return np.clip(lut, 0, 1)


def _style_warm(lut):
    """Warm style: amber shadows, warm midtones, cream highlights."""
    # Warm shift: boost red, slight green, reduce blue
    lut[..., 0] = lut[..., 0] + 0.03  # R boost
    lut[..., 1] = lut[..., 1] + 0.01  # G slight
    lut[..., 2] = lut[..., 2] - 0.02  # B reduce
    lut = np.clip(lut, 0, 1)
    lut = _apply_contrast(lut, 0.10)
    lut = _apply_saturation(lut, -0.08)
    return lut


def _style_cinematic(lut):
    """Cinematic: lifted shadows, desaturated, S-curve contrast."""
    # Lift shadows (blacks become dark gray)
    lut = 0.05 + lut * 0.95
    # Cool midtone shift
    lut[..., 2] = lut[..., 2] + 0.01
    lut = np.clip(lut, 0, 1)
    lut = _apply_contrast(lut, 0.15)
    lut = _apply_saturation(lut, -0.15)
    # Highlight rolloff
    mask = lut > 0.85
    lut[mask] = 0.85 + (lut[mask] - 0.85) * 0.7
    return np.clip(lut, 0, 1)


def _style_cold(lut):
    """Cold: blue shadows, cool midtones."""
    lut[..., 0] = lut[..., 0] - 0.02  # R reduce
    lut[..., 2] = lut[..., 2] + 0.03  # B boost
    lut = np.clip(lut, 0, 1)
    lut = _apply_contrast(lut, 0.08)
    lut = _apply_saturation(lut, -0.05)
    return lut


def _style_natural(lut):
    """Natural: minimal changes, gentle contrast, slight shadow lift."""
    lut = 0.01 + lut * 0.99
    lut = _apply_contrast(lut, 0.05)
    return np.clip(lut, 0, 1)


def _style_faded(lut):
    """Faded: lifted blacks, desaturated, slight warmth."""
    # Lift blacks significantly
    lut = 0.08 + lut * 0.92
    # Slight warmth
    lut[..., 0] = lut[..., 0] + 0.01
    lut = np.clip(lut, 0, 1)
    lut = _apply_saturation(lut, -0.20)
    return lut


STYLES = {
    "warm": _style_warm,
    "cold": _style_cold,
    "cinematic": _style_cinematic,
    "natural": _style_natural,
    "faded": _style_faded,
}


def generate_builtin_lut(style, size=33):
    """Generate a 3D LUT array for the given style.

    Args:
        style: One of "warm", "cold", "cinematic", "natural", "faded".
        size: LUT cube size (default 33).

    Returns:
        numpy.ndarray of shape (size, size, size, 3) with float values 0.0-1.0.
    """
    if style not in STYLES:
        raise ValueError(f"Unknown LUT style: {style}. Choose from: {list(STYLES.keys())}")
    lut = _identity_lut(size)
    lut = STYLES[style](lut)
    return lut
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_color_grade.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/color_grade.py tests/test_color_grade.py
git commit -m "feat(lut): add generate_builtin_lut with 5 color grade styles"
```

---

### Task 2: .cube File I/O — `save_lut_as_cube()` and `load_lut_file()`

**Files:**
- Modify: `tests/test_color_grade.py`
- Modify: `musicvid/pipeline/color_grade.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_color_grade.py`:

```python
import os
from musicvid.pipeline.color_grade import save_lut_as_cube, load_lut_file


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_color_grade.py::TestSaveLutAsCube -v && python3 -m pytest tests/test_color_grade.py::TestLoadLutFile -v`
Expected: FAIL — `ImportError: cannot import name 'save_lut_as_cube'`

- [ ] **Step 3: Implement `save_lut_as_cube` and `load_lut_file`**

Add to `musicvid/pipeline/color_grade.py`:

```python
def save_lut_as_cube(lut, path):
    """Save a numpy LUT array as a .cube file.

    Args:
        lut: numpy array of shape (size, size, size, 3), values 0.0-1.0.
        path: Output file path (should end with .cube).

    Returns:
        The path to the saved .cube file.
    """
    size = lut.shape[0]
    with open(path, "w") as f:
        f.write(f"TITLE \"MusicVid LUT\"\n")
        f.write(f"LUT_3D_SIZE {size}\n")
        f.write("DOMAIN_MIN 0.0 0.0 0.0\n")
        f.write("DOMAIN_MAX 1.0 1.0 1.0\n")
        # .cube format: iterate B (outer), G (middle), R (inner)
        for b in range(size):
            for g in range(size):
                for r in range(size):
                    rgb = lut[r, g, b]
                    f.write(f"{rgb[0]:.6f} {rgb[1]:.6f} {rgb[2]:.6f}\n")
    return path


def load_lut_file(path):
    """Validate and return path to a .cube LUT file.

    Args:
        path: Path to a .cube file.

    Returns:
        Validated path string.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file does not have .cube extension.
    """
    import os
    if not os.path.exists(path):
        raise FileNotFoundError(f"LUT file not found: {path}")
    if not path.endswith(".cube"):
        raise ValueError(f"LUT file must have .cube extension, got: {path}")
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_color_grade.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/color_grade.py tests/test_color_grade.py
git commit -m "feat(lut): add .cube file save and load functions"
```

---

### Task 3: FFmpeg Filter String — `get_ffmpeg_lut_filter()`

**Files:**
- Modify: `tests/test_color_grade.py`
- Modify: `musicvid/pipeline/color_grade.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_color_grade.py`:

```python
from musicvid.pipeline.color_grade import get_ffmpeg_lut_filter


class TestGetFfmpegLutFilter:
    def test_contains_lut3d(self):
        result = get_ffmpeg_lut_filter("/tmp/test.cube", 0.85)
        assert "lut3d" in result

    def test_contains_file_path(self):
        result = get_ffmpeg_lut_filter("/tmp/test.cube", 0.85)
        assert "/tmp/test.cube" in result

    def test_default_intensity(self):
        result = get_ffmpeg_lut_filter("/tmp/test.cube", 1.0)
        # At intensity 1.0, no blend needed — just lut3d
        assert "lut3d" in result

    def test_partial_intensity_uses_blend(self):
        result = get_ffmpeg_lut_filter("/tmp/test.cube", 0.5)
        # For partial intensity, need to split and merge streams
        assert "0.5" in result or "0.50" in result

    def test_zero_intensity_returns_none(self):
        result = get_ffmpeg_lut_filter("/tmp/test.cube", 0.0)
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_color_grade.py::TestGetFfmpegLutFilter -v`
Expected: FAIL — `ImportError: cannot import name 'get_ffmpeg_lut_filter'`

- [ ] **Step 3: Implement `get_ffmpeg_lut_filter`**

Add to `musicvid/pipeline/color_grade.py`:

```python
def get_ffmpeg_lut_filter(lut_path, intensity):
    """Build FFmpeg video filter string for LUT application.

    Args:
        lut_path: Path to .cube file.
        intensity: Float 0.0-1.0. 0.0 = no effect, 1.0 = full LUT.

    Returns:
        FFmpeg -vf filter string, or None if intensity is 0.
    """
    if intensity <= 0.0:
        return None
    if intensity >= 1.0:
        return f"lut3d='{lut_path}':interp=trilinear"
    # Partial intensity: blend original with LUT-graded
    # Use split + lut3d + merge with opacity
    return (
        f"split[a][b];"
        f"[b]lut3d='{lut_path}':interp=trilinear[graded];"
        f"[a][graded]blend=all_mode=normal:all_opacity={intensity:.2f}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_color_grade.py::TestGetFfmpegLutFilter -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/color_grade.py tests/test_color_grade.py
git commit -m "feat(lut): add FFmpeg lut3d filter string builder"
```

---

### Task 4: Pipeline Entry Point — `prepare_lut_ffmpeg_params()`

**Files:**
- Modify: `tests/test_color_grade.py`
- Modify: `musicvid/pipeline/color_grade.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_color_grade.py`:

```python
import tempfile
from musicvid.pipeline.color_grade import prepare_lut_ffmpeg_params


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_color_grade.py::TestPrepareLutFfmpegParams -v`
Expected: FAIL — `ImportError: cannot import name 'prepare_lut_ffmpeg_params'`

- [ ] **Step 3: Implement `prepare_lut_ffmpeg_params`**

Add to `musicvid/pipeline/color_grade.py`:

```python
import tempfile
import os


def prepare_lut_ffmpeg_params(lut_path=None, lut_style=None, intensity=0.85):
    """Prepare FFmpeg params for LUT color grading.

    Priority: lut_path (custom .cube file) > lut_style (built-in).
    If neither is provided, returns empty list (no LUT).

    Args:
        lut_path: Path to custom .cube file (optional).
        lut_style: Built-in style name (optional).
        intensity: LUT intensity 0.0-1.0 (default 0.85).

    Returns:
        List of FFmpeg params, e.g. ["-vf", "lut3d='...'"] or [].
    """
    if intensity <= 0.0:
        return []

    cube_path = None

    if lut_path:
        cube_path = load_lut_file(lut_path)
    elif lut_style:
        lut = generate_builtin_lut(lut_style)
        tmp_dir = tempfile.gettempdir()
        cube_path = os.path.join(tmp_dir, f"musicvid_lut_{lut_style}.cube")
        save_lut_as_cube(lut, cube_path)

    if not cube_path:
        return []

    vf_filter = get_ffmpeg_lut_filter(cube_path, intensity)
    if vf_filter is None:
        return []

    return ["-vf", vf_filter]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_color_grade.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/color_grade.py tests/test_color_grade.py
git commit -m "feat(lut): add prepare_lut_ffmpeg_params pipeline entry point"
```

---

### Task 5: Assembler Integration — Pass `ffmpeg_params` to `write_videofile()`

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write failing test**

Add a new test class to `tests/test_assembler.py`. Follow the exact mock pattern used by existing assembler tests (see the `@patch` decorator stack in `TestAssembleVideo`):

```python
class TestAssembleVideoLut:
    @patch("musicvid.pipeline.assembler.apply_logo")
    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    @patch("musicvid.pipeline.assembler.prepare_lut_ffmpeg_params")
    def test_lut_params_passed_to_write_videofile(
        self, mock_prepare_lut, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars, mock_apply_logo,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_end.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_video.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = []
        mock_prepare_lut.return_value = ["-vf", "lut3d='/tmp/test.cube':interp=trilinear"]

        output_file = str(tmp_output / "test_lut.mp4")
        manifest = [{"scene_index": 0, "video_path": "/fake/vid.mp4", "search_query": "test"}]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            lut_style="warm",
            lut_intensity=0.85,
        )

        mock_prepare_lut.assert_called_once_with(
            lut_path=None, lut_style="warm", intensity=0.85
        )
        call_kwargs = mock_clip.write_videofile.call_args[1]
        assert "ffmpeg_params" in call_kwargs
        assert "lut3d" in str(call_kwargs["ffmpeg_params"])

    @patch("musicvid.pipeline.assembler.apply_logo")
    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    @patch("musicvid.pipeline.assembler.prepare_lut_ffmpeg_params")
    def test_no_lut_means_no_ffmpeg_params(
        self, mock_prepare_lut, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars, mock_apply_logo,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_end.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_video.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = []
        mock_prepare_lut.return_value = []

        output_file = str(tmp_output / "test_no_lut.mp4")
        manifest = [{"scene_index": 0, "video_path": "/fake/vid.mp4", "search_query": "test"}]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
        )

        call_kwargs = mock_clip.write_videofile.call_args[1]
        # When no LUT, ffmpeg_params should not contain lut3d
        if "ffmpeg_params" in call_kwargs:
            assert "lut3d" not in str(call_kwargs["ffmpeg_params"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assembler.py::TestAssembleVideoLut -v`
Expected: FAIL — `assemble_video() got an unexpected keyword argument 'lut_style'`

- [ ] **Step 3: Modify assembler to accept and use LUT params**

In `musicvid/pipeline/assembler.py`:

1. Add import at top:
```python
from musicvid.pipeline.color_grade import prepare_lut_ffmpeg_params
```

2. Add `lut_path=None, lut_style=None, lut_intensity=0.85` parameters to `assemble_video()` signature (add after `logo_opacity=0.85`):
```python
def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path, resolution="1080p", font_path=None, effects_level="minimal", clip_start=None, clip_end=None, title_card_text=None, audio_fade_out=1.0, subtitle_margin_bottom=80, cinematic_bars=True, logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85, lut_path=None, lut_style=None, lut_intensity=0.85):
```

3. Before the `write_videofile` call, prepare LUT params:
```python
    lut_ffmpeg_params = prepare_lut_ffmpeg_params(
        lut_path=lut_path, lut_style=lut_style, intensity=lut_intensity
    )
```

4. Pass to `write_videofile`:
```python
    write_kwargs = dict(
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        fps=30,
    )
    if lut_ffmpeg_params:
        write_kwargs["ffmpeg_params"] = lut_ffmpeg_params

    final.write_videofile(output_path, **write_kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestAssembleVideoLut -v`
Expected: All 2 tests PASS

Then run existing assembler tests to check no regressions:
Run: `python3 -m pytest tests/test_assembler.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat(lut): integrate LUT color grading into assembler via ffmpeg_params"
```

---

### Task 6: CLI Flags — `--lut`, `--lut-style`, `--lut-intensity`

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add to `tests/test_cli.py` — follow the exact mock pattern used by `test_logo_passed_to_assembler` (patch `get_font_path`, `assemble_video`, `fetch_videos`, `create_scene_plan`, `analyze_audio`):

```python
class TestLutCli:
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_lut_style_passed_to_assembler(self, mock_analyze, mock_director, mock_fetch,
                                            mock_assemble, mock_font, runner, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")

        mock_analyze.return_value = {"lyrics": [], "beats": [], "sections": [], "duration": 10.0, "bpm": 120}
        mock_director.return_value = {"scenes": [{"start": 0, "end": 10, "motion": "static"}], "subtitle_style": {}}
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/vid.mp4", "search_query": "test"}]

        result = runner.invoke(cli, [str(audio), "--lut-style", "cinematic", "--output", str(tmp_path / "out")])

        assert result.exit_code == 0
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["lut_style"] == "cinematic"
        assert call_kwargs["lut_intensity"] == 0.85

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_lut_file_passed_to_assembler(self, mock_analyze, mock_director, mock_fetch,
                                           mock_assemble, mock_font, runner, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")
        lut_file = tmp_path / "grade.cube"
        lut_file.write_text("TITLE\nLUT_3D_SIZE 2\n0 0 0\n1 1 1\n0 0 0\n1 1 1\n0 0 0\n1 1 1\n0 0 0\n1 1 1\n")

        mock_analyze.return_value = {"lyrics": [], "beats": [], "sections": [], "duration": 10.0, "bpm": 120}
        mock_director.return_value = {"scenes": [{"start": 0, "end": 10, "motion": "static"}], "subtitle_style": {}}
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/vid.mp4", "search_query": "test"}]

        result = runner.invoke(cli, [str(audio), "--lut", str(lut_file), "--output", str(tmp_path / "out")])

        assert result.exit_code == 0
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["lut_path"] == str(lut_file)

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_lut_intensity_passed_to_assembler(self, mock_analyze, mock_director, mock_fetch,
                                                mock_assemble, mock_font, runner, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")

        mock_analyze.return_value = {"lyrics": [], "beats": [], "sections": [], "duration": 10.0, "bpm": 120}
        mock_director.return_value = {"scenes": [{"start": 0, "end": 10, "motion": "static"}], "subtitle_style": {}}
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/vid.mp4", "search_query": "test"}]

        result = runner.invoke(cli, [str(audio), "--lut-style", "warm", "--lut-intensity", "0.5", "--output", str(tmp_path / "out")])

        assert result.exit_code == 0
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["lut_intensity"] == 0.5

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_default_no_lut(self, mock_analyze, mock_director, mock_fetch,
                             mock_assemble, mock_font, runner, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")

        mock_analyze.return_value = {"lyrics": [], "beats": [], "sections": [], "duration": 10.0, "bpm": 120}
        mock_director.return_value = {"scenes": [{"start": 0, "end": 10, "motion": "static"}], "subtitle_style": {}}
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/vid.mp4", "search_query": "test"}]

        result = runner.invoke(cli, [str(audio), "--output", str(tmp_path / "out")])

        assert result.exit_code == 0
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs.get("lut_path") is None
        assert call_kwargs.get("lut_style") is None
        assert call_kwargs["lut_intensity"] == 0.85
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py::TestLutCli -v`
Expected: FAIL — `NameError: name 'TestLutCli' is not defined` (class not found yet) or option not recognized

- [ ] **Step 3: Add CLI options and pass to assembler**

In `musicvid/musicvid.py`:

1. Add 3 new Click options after the `--logo-opacity` option:
```python
@click.option("--lut", "lut_path", type=click.Path(), default=None, help="Path to .cube LUT file for color grading.")
@click.option("--lut-style", type=click.Choice(["warm", "cold", "cinematic", "natural", "faded"]), default=None, help="Built-in LUT color grade style.")
@click.option("--lut-intensity", type=float, default=0.85, help="LUT intensity 0.0-1.0 (default: 0.85).")
```

2. Add `lut_path, lut_style, lut_intensity` to the `cli()` function parameters.

3. Pass to `assemble_video()` call in single-output mode (lines ~336-352):
```python
        lut_path=lut_path,
        lut_style=lut_style,
        lut_intensity=lut_intensity,
```

4. Pass to `_run_preset_mode()` call (lines ~300-318):
```python
        lut_path=lut_path,
        lut_style=lut_style,
        lut_intensity=lut_intensity,
```

5. Update `_run_preset_mode()` signature and both `assemble_video()` calls inside it to pass the LUT params.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py::TestLutCli -v`
Expected: All 4 tests PASS

Then run full CLI test suite:
Run: `python3 -m pytest tests/test_cli.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(lut): add --lut, --lut-style, --lut-intensity CLI flags"
```

---

### Task 7: Preset Mode LUT Integration

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `musicvid/musicvid.py` (if not already done in Task 6)

- [ ] **Step 1: Write failing test for preset mode + LUT**

Add to `tests/test_cli.py` inside `TestLutCli`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.select_social_clips")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_preset_mode_passes_lut_to_assembler(self, mock_analyze, mock_director, mock_fetch,
                                                   mock_assemble, mock_font, mock_social, runner, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")

        mock_analyze.return_value = {"lyrics": [], "beats": [], "sections": [{"start": 0, "end": 30, "label": "verse"}], "duration": 30.0, "bpm": 120}
        mock_director.return_value = {"scenes": [{"start": 0, "end": 30, "motion": "static"}], "subtitle_style": {}}
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/vid.mp4", "search_query": "test"}]
        mock_social.return_value = {"clips": [
            {"id": 1, "start": 0, "end": 15, "section": "verse", "reason": "test"},
            {"id": 2, "start": 5, "end": 20, "section": "verse", "reason": "test"},
            {"id": 3, "start": 10, "end": 25, "section": "verse", "reason": "test"},
        ]}

        result = runner.invoke(cli, [str(audio), "--preset", "all", "--lut-style", "cinematic", "--lut-intensity", "0.7", "--output", str(tmp_path / "out")])

        assert result.exit_code == 0
        # assemble_video called 4 times: 1 full + 3 social
        assert mock_assemble.call_count == 4
        for call in mock_assemble.call_args_list:
            assert call[1]["lut_style"] == "cinematic"
            assert call[1]["lut_intensity"] == 0.7
```

- [ ] **Step 2: Run test to verify it fails (if preset integration not done in Task 6)**

Run: `python3 -m pytest tests/test_cli.py::TestLutCli::test_preset_mode_passes_lut_to_assembler -v`
Expected: PASS (if Task 6 already added preset mode params) or FAIL (fix in Step 3)

- [ ] **Step 3: Fix if needed — ensure `_run_preset_mode` passes LUT params**

Already covered in Task 6 Step 3.5 — verify `_run_preset_mode` has `lut_path`, `lut_style`, `lut_intensity` in its signature and passes them to all `assemble_video()` calls.

- [ ] **Step 4: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (no regressions)

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py musicvid/musicvid.py
git commit -m "test(lut): add preset mode LUT integration tests"
```

---

### Task 8: Move spec to done

**Files:**
- Move: `docs/IDEA.md` → `docs/superpowers/specs/done/4lut-color-grade.md`

- [ ] **Step 1: Move spec file**

```bash
mv docs/IDEA.md docs/superpowers/specs/done/4lut-color-grade.md
```

- [ ] **Step 2: Commit**

```bash
git add docs/IDEA.md docs/superpowers/specs/done/4lut-color-grade.md
git commit -m "docs: move LUT spec to done"
```
