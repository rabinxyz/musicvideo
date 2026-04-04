# Logo Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add logo overlay capability to the music video pipeline — logo appears as the topmost layer, positioned with broadcast-standard 5% safe-zone margins, auto-scaled to 12% frame width, supporting SVG and PNG formats.

**Architecture:** New `musicvid/pipeline/logo_overlay.py` module with pure computation functions + PIL image loading + MoviePy ImageClip integration. The assembler gains `logo_path`, `logo_position`, `logo_size`, `logo_opacity` kwargs; logo is composited as the final layer above everything. CLI adds four `--logo*` flags that pass through to `assemble_video()`.

**Tech Stack:** Pillow (image loading/scaling/opacity), cairosvg (SVG→PNG conversion), MoviePy 2.x ImageClip (compositing)

---

## File Structure

| File | Role |
|------|------|
| Create: `musicvid/pipeline/logo_overlay.py` | Pure functions: margin, sizing, positioning, image loading, MoviePy clip creation |
| Create: `tests/test_logo_overlay.py` | Unit tests for all logo_overlay functions |
| Modify: `musicvid/pipeline/assembler.py` | Accept logo params, call `apply_logo`, insert logo layer |
| Modify: `musicvid/musicvid.py` | Add `--logo*` CLI flags, pass to `assemble_video()` calls |
| Modify: `tests/test_assembler.py` | Test assembler with logo params |
| Modify: `tests/test_cli.py` | Test CLI logo flags end-to-end |
| Modify: `musicvid/requirements.txt` | Add `cairosvg>=2.7.0` |

---

### Task 1: Pure computation functions — margin, logo size, position

**Files:**
- Create: `tests/test_logo_overlay.py`
- Create: `musicvid/pipeline/logo_overlay.py`

- [ ] **Step 1: Write failing tests for `compute_margin`**

```python
# tests/test_logo_overlay.py
from musicvid.pipeline.logo_overlay import compute_margin, compute_logo_size, get_logo_position


class TestComputeMargin:
    def test_1920x1080(self):
        assert compute_margin(1920, 1080) == 54

    def test_1080x1920_portrait(self):
        assert compute_margin(1080, 1920) == 54

    def test_1080x1080_square(self):
        assert compute_margin(1080, 1080) == 54

    def test_3840x2160_4k(self):
        assert compute_margin(3840, 2160) == 108
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestComputeMargin -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement `compute_margin`**

```python
# musicvid/pipeline/logo_overlay.py
"""Logo overlay utilities for compositing logos onto video frames."""


def compute_margin(frame_width, frame_height):
    """Return broadcast safe-zone margin (5% of shorter dimension)."""
    return int(min(frame_width, frame_height) * 0.05)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestComputeMargin -v`
Expected: 4 PASSED

- [ ] **Step 5: Write failing tests for `compute_logo_size`**

Add to `tests/test_logo_overlay.py`:

```python
class TestComputeLogoSize:
    def test_auto_1920x1080(self):
        w, h = compute_logo_size(1920, 1080, 100, 50)
        assert w == 230
        # height scaled proportionally: 50 * (230/100) = 115
        assert h == 115

    def test_auto_1080x1920_portrait(self):
        w, h = compute_logo_size(1080, 1920, 100, 50)
        assert w == 129
        assert h == 64

    def test_explicit_size(self):
        w, h = compute_logo_size(1920, 1080, 100, 50, requested_size=200)
        assert w == 200
        assert h == 100

    def test_auto_1080x1080_square(self):
        w, h = compute_logo_size(1080, 1080, 100, 50)
        assert w == 129
        assert h == 64
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestComputeLogoSize -v`
Expected: FAIL with `TypeError` (wrong signature)

- [ ] **Step 7: Implement `compute_logo_size`**

Add to `musicvid/pipeline/logo_overlay.py`:

```python
def compute_logo_size(frame_width, frame_height, orig_width, orig_height, requested_size=None):
    """Return (logo_width, logo_height) preserving aspect ratio.

    When requested_size is None, auto-scales to 12% of frame width.
    """
    logo_width = requested_size if requested_size else int(frame_width * 0.12)
    aspect = orig_height / orig_width
    logo_height = int(logo_width * aspect)
    return logo_width, logo_height
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestComputeLogoSize -v`
Expected: 4 PASSED

- [ ] **Step 9: Write failing tests for `get_logo_position`**

Add to `tests/test_logo_overlay.py`:

```python
class TestGetLogoPosition:
    def test_top_left_1080p(self):
        x, y = get_logo_position("top-left", (200, 100), (1920, 1080))
        assert x == 54
        assert y == 54

    def test_top_right_1080p(self):
        x, y = get_logo_position("top-right", (200, 100), (1920, 1080))
        assert x == 1920 - 200 - 54
        assert y == 54

    def test_bottom_left_1080p(self):
        x, y = get_logo_position("bottom-left", (200, 100), (1920, 1080))
        assert x == 54
        assert y == 1080 - 100 - 54

    def test_bottom_right_1080p(self):
        x, y = get_logo_position("bottom-right", (200, 100), (1920, 1080))
        assert x == 1920 - 200 - 54
        assert y == 1080 - 100 - 54

    def test_portrait(self):
        x, y = get_logo_position("top-left", (130, 65), (1080, 1920))
        assert x == 54
        assert y == 54

    def test_4k(self):
        x, y = get_logo_position("top-left", (400, 200), (3840, 2160))
        assert x == 108
        assert y == 108
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestGetLogoPosition -v`
Expected: FAIL

- [ ] **Step 11: Implement `get_logo_position`**

Add to `musicvid/pipeline/logo_overlay.py`:

```python
def get_logo_position(position, logo_size, frame_size):
    """Return (x, y) coordinates for logo placement.

    position: "top-left" | "top-right" | "bottom-left" | "bottom-right"
    logo_size: (width, height)
    frame_size: (width, height)
    """
    logo_w, logo_h = logo_size
    frame_w, frame_h = frame_size
    margin = compute_margin(frame_w, frame_h)

    positions = {
        "top-left": (margin, margin),
        "top-right": (frame_w - logo_w - margin, margin),
        "bottom-left": (margin, frame_h - logo_h - margin),
        "bottom-right": (frame_w - logo_w - margin, frame_h - logo_h - margin),
    }
    return positions[position]
```

- [ ] **Step 12: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestGetLogoPosition -v`
Expected: 6 PASSED

- [ ] **Step 13: Commit**

```bash
git add tests/test_logo_overlay.py musicvid/pipeline/logo_overlay.py
git commit -m "feat(logo): add pure computation functions — margin, size, position"
```

---

### Task 2: `load_logo` — PNG/JPG loading with opacity

**Files:**
- Modify: `tests/test_logo_overlay.py`
- Modify: `musicvid/pipeline/logo_overlay.py`

- [ ] **Step 1: Write failing tests for PNG loading**

Add to `tests/test_logo_overlay.py`:

```python
import numpy as np
from PIL import Image
from unittest.mock import patch, MagicMock
from musicvid.pipeline.logo_overlay import load_logo


class TestLoadLogo:
    def _create_test_png(self, tmp_path, width=100, height=50, mode="RGBA"):
        """Create a test PNG file and return its path."""
        img = Image.new(mode, (width, height), (255, 0, 0, 255) if mode == "RGBA" else (255, 0, 0))
        path = tmp_path / "logo.png"
        img.save(str(path))
        return str(path)

    def test_load_png_returns_rgba(self, tmp_path):
        path = self._create_test_png(tmp_path)
        result = load_logo(path, 200, 100, 0.85)
        assert result.mode == "RGBA"

    def test_load_png_correct_size(self, tmp_path):
        path = self._create_test_png(tmp_path)
        result = load_logo(path, 200, 100, 0.85)
        assert result.size == (200, 100)

    def test_load_png_opacity(self, tmp_path):
        path = self._create_test_png(tmp_path)
        result = load_logo(path, 200, 100, 0.85)
        alpha = np.array(result.getchannel("A"))
        assert alpha.max() == 216  # int(255 * 0.85)

    def test_load_png_full_opacity(self, tmp_path):
        path = self._create_test_png(tmp_path)
        result = load_logo(path, 200, 100, 1.0)
        alpha = np.array(result.getchannel("A"))
        assert alpha.max() == 255

    def test_load_rgb_png_converts_to_rgba(self, tmp_path):
        path = self._create_test_png(tmp_path, mode="RGB")
        result = load_logo(path, 200, 100, 0.85)
        assert result.mode == "RGBA"

    def test_file_not_found(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_logo("/nonexistent/logo.png", 200, 100, 0.85)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestLoadLogo -v`
Expected: FAIL with `ImportError` (load_logo not defined)

- [ ] **Step 3: Implement `load_logo`**

Add to `musicvid/pipeline/logo_overlay.py`:

```python
from pathlib import Path
from PIL import Image


def load_logo(path, logo_width, logo_height, opacity):
    """Load a logo image, resize it, and apply opacity.

    Supports PNG and JPG. Returns a PIL Image in RGBA mode.
    Raises FileNotFoundError if path does not exist.
    """
    logo_path = Path(path)
    if not logo_path.exists():
        raise FileNotFoundError(f"Logo file not found: {path}")

    ext = logo_path.suffix.lower()

    if ext == ".svg":
        img = _load_svg(path, logo_width, logo_height)
    else:
        img = Image.open(path)

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    img = img.resize((logo_width, logo_height), Image.LANCZOS)

    # Apply opacity to alpha channel
    alpha_value = int(255 * opacity)
    r, g, b, a = img.split()
    # Scale existing alpha by opacity (preserves transparent regions)
    a = a.point(lambda x: int(x * opacity))
    img = Image.merge("RGBA", (r, g, b, a))

    return img
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestLoadLogo -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_logo_overlay.py musicvid/pipeline/logo_overlay.py
git commit -m "feat(logo): add load_logo for PNG/JPG with opacity support"
```

---

### Task 3: `load_logo` — SVG support via cairosvg

**Files:**
- Modify: `tests/test_logo_overlay.py`
- Modify: `musicvid/pipeline/logo_overlay.py`
- Modify: `musicvid/requirements.txt`

- [ ] **Step 1: Write failing tests for SVG loading**

Add to `tests/test_logo_overlay.py`:

```python
class TestLoadLogoSvg:
    def _create_test_svg(self, tmp_path):
        """Create a minimal test SVG and return its path."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><rect width="100" height="50" fill="red"/></svg>'
        path = tmp_path / "logo.svg"
        path.write_text(svg_content)
        return str(path)

    @patch("musicvid.pipeline.logo_overlay.cairosvg")
    def test_load_svg_calls_cairosvg(self, mock_cairosvg, tmp_path):
        # cairosvg.svg2png returns a valid PNG bytes
        img = Image.new("RGBA", (200, 100), (255, 0, 0, 255))
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        mock_cairosvg.svg2png.return_value = buf.getvalue()

        path = self._create_test_svg(tmp_path)
        result = load_logo(path, 200, 100, 1.0)
        assert result.mode == "RGBA"
        assert result.size == (200, 100)
        mock_cairosvg.svg2png.assert_called_once()

    @patch("musicvid.pipeline.logo_overlay.cairosvg")
    def test_svg_renders_at_2x_for_retina(self, mock_cairosvg, tmp_path):
        img = Image.new("RGBA", (400, 200), (255, 0, 0, 255))
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        mock_cairosvg.svg2png.return_value = buf.getvalue()

        path = self._create_test_svg(tmp_path)
        load_logo(path, 200, 100, 1.0)
        call_kwargs = mock_cairosvg.svg2png.call_args
        # Should render at 2x size for retina sharpness
        assert call_kwargs[1]["output_width"] == 400
        assert call_kwargs[1]["output_height"] == 200

    def test_svg_without_cairosvg_raises(self, tmp_path):
        import pytest
        path = self._create_test_svg(tmp_path)
        with patch("musicvid.pipeline.logo_overlay.cairosvg", None):
            with pytest.raises(ImportError, match="cairosvg"):
                load_logo(path, 200, 100, 1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestLoadLogoSvg -v`
Expected: FAIL

- [ ] **Step 3: Implement `_load_svg` and update imports**

Update `musicvid/pipeline/logo_overlay.py` — add at top after existing imports:

```python
import io

try:
    import cairosvg
except ImportError:
    cairosvg = None
```

Add the `_load_svg` function:

```python
def _load_svg(path, logo_width, logo_height):
    """Convert SVG to PIL Image via cairosvg at 2x resolution for retina sharpness."""
    if cairosvg is None:
        raise ImportError(
            "cairosvg is required for SVG logo files. Install it with: pip install cairosvg"
        )
    # Render at 2x for sharp edges, then downscale
    png_data = cairosvg.svg2png(
        url=path,
        output_width=logo_width * 2,
        output_height=logo_height * 2,
    )
    return Image.open(io.BytesIO(png_data))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestLoadLogoSvg -v`
Expected: 3 PASSED

- [ ] **Step 5: Add cairosvg to requirements.txt**

Add `cairosvg>=2.7.0` to `musicvid/requirements.txt`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_logo_overlay.py musicvid/pipeline/logo_overlay.py musicvid/requirements.txt
git commit -m "feat(logo): add SVG support via cairosvg with retina rendering"
```

---

### Task 4: `apply_logo` — MoviePy ImageClip integration

**Files:**
- Modify: `tests/test_logo_overlay.py`
- Modify: `musicvid/pipeline/logo_overlay.py`

- [ ] **Step 1: Write failing tests for `apply_logo`**

Add to `tests/test_logo_overlay.py`:

```python
from unittest.mock import patch, MagicMock, call
from musicvid.pipeline.logo_overlay import apply_logo


class TestApplyLogo:
    def _create_test_png(self, tmp_path, width=100, height=50):
        img = Image.new("RGBA", (width, height), (255, 0, 0, 255))
        path = tmp_path / "logo.png"
        img.save(str(path))
        return str(path)

    @patch("musicvid.pipeline.logo_overlay.ImageClip")
    def test_apply_logo_creates_image_clip(self, mock_image_clip, tmp_path):
        logo_path = self._create_test_png(tmp_path)
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.duration = 30.0

        mock_logo_clip = MagicMock()
        mock_image_clip.return_value = mock_logo_clip
        mock_logo_clip.with_duration.return_value = mock_logo_clip
        mock_logo_clip.with_position.return_value = mock_logo_clip

        result = apply_logo(mock_clip, logo_path, "top-left", None, 0.85)

        mock_image_clip.assert_called_once()
        mock_logo_clip.with_duration.assert_called_once_with(30.0)
        mock_logo_clip.with_position.assert_called_once()

    @patch("musicvid.pipeline.logo_overlay.ImageClip")
    def test_apply_logo_position_top_right(self, mock_image_clip, tmp_path):
        logo_path = self._create_test_png(tmp_path)
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.duration = 10.0

        mock_logo_clip = MagicMock()
        mock_image_clip.return_value = mock_logo_clip
        mock_logo_clip.with_duration.return_value = mock_logo_clip
        mock_logo_clip.with_position.return_value = mock_logo_clip

        apply_logo(mock_clip, logo_path, "top-right", None, 0.85)

        pos_call = mock_logo_clip.with_position.call_args[0][0]
        # For 1080p with auto-size (12% of 1920 = 230): margin=54, x = 1920-230-54 = 1636
        assert pos_call[0] == 1920 - 230 - 54

    @patch("musicvid.pipeline.logo_overlay.ImageClip")
    def test_apply_logo_explicit_size(self, mock_image_clip, tmp_path):
        logo_path = self._create_test_png(tmp_path)
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.duration = 10.0

        mock_logo_clip = MagicMock()
        mock_image_clip.return_value = mock_logo_clip
        mock_logo_clip.with_duration.return_value = mock_logo_clip
        mock_logo_clip.with_position.return_value = mock_logo_clip

        apply_logo(mock_clip, logo_path, "top-left", 200, 0.85)

        # Verify ImageClip was created (the numpy array passed should be 200px wide)
        arr = mock_image_clip.call_args[0][0]
        assert arr.shape[1] == 200  # width

    @patch("musicvid.pipeline.logo_overlay.ImageClip")
    def test_apply_logo_returns_logo_clip(self, mock_image_clip, tmp_path):
        logo_path = self._create_test_png(tmp_path)
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.duration = 10.0

        mock_logo_clip = MagicMock()
        mock_image_clip.return_value = mock_logo_clip
        mock_logo_clip.with_duration.return_value = mock_logo_clip
        mock_logo_clip.with_position.return_value = mock_logo_clip

        result = apply_logo(mock_clip, logo_path, "top-left", None, 0.85)
        assert result is mock_logo_clip
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestApplyLogo -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `apply_logo`**

Add to `musicvid/pipeline/logo_overlay.py`:

```python
import numpy as np
from moviepy import ImageClip


def apply_logo(clip, logo_path, position, size, opacity):
    """Create a logo ImageClip positioned over the video.

    Args:
        clip: The base MoviePy video clip (used for size/duration).
        logo_path: Path to logo file (SVG, PNG, JPG).
        position: "top-left" | "top-right" | "bottom-left" | "bottom-right"
        size: Logo width in px, or None for auto (12% of frame width).
        opacity: Float 0.0-1.0 for logo transparency.

    Returns:
        MoviePy ImageClip positioned and sized for compositing.
    """
    frame_w, frame_h = clip.size
    orig_img = Image.open(logo_path) if not logo_path.lower().endswith(".svg") else _load_svg(logo_path, 100, 100)
    orig_w, orig_h = orig_img.size

    logo_w, logo_h = compute_logo_size(frame_w, frame_h, orig_w, orig_h, requested_size=size)
    logo_img = load_logo(logo_path, logo_w, logo_h, opacity)
    logo_arr = np.array(logo_img)

    logo_clip = ImageClip(logo_arr)
    logo_clip = logo_clip.with_duration(clip.duration)

    pos = get_logo_position(position, (logo_w, logo_h), (frame_w, frame_h))
    logo_clip = logo_clip.with_position(pos)

    return logo_clip
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_logo_overlay.py::TestApplyLogo -v`
Expected: 4 PASSED

- [ ] **Step 5: Run all logo tests**

Run: `python3 -m pytest tests/test_logo_overlay.py -v`
Expected: All PASSED (17 tests)

- [ ] **Step 6: Commit**

```bash
git add tests/test_logo_overlay.py musicvid/pipeline/logo_overlay.py
git commit -m "feat(logo): add apply_logo MoviePy integration"
```

---

### Task 5: Assembler integration — logo as topmost layer

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write failing test for assembler with logo**

Add to `tests/test_assembler.py` inside the existing `TestAssembleVideo` class:

```python
@patch("musicvid.pipeline.assembler.apply_logo")
def test_logo_overlay_added_as_last_layer(self, mock_apply_logo, ...existing_patches...):
    """Logo should be the last layer in CompositeVideoClip."""
    mock_logo_clip = MagicMock()
    mock_apply_logo.return_value = mock_logo_clip

    assemble_video(
        analysis=self.analysis,
        scene_plan=self.scene_plan,
        fetch_manifest=self.manifest,
        audio_path=str(self.audio_path),
        output_path=str(self.output_path),
        logo_path="/fake/logo.png",
        logo_position="top-left",
        logo_size=None,
        logo_opacity=0.85,
    )

    mock_apply_logo.assert_called_once()
    # Logo clip should be in the layers list passed to CompositeVideoClip
    composite_call = mock_composite.call_args
    layers = composite_call[0][0]
    assert layers[-1] is mock_logo_clip

@patch("musicvid.pipeline.assembler.apply_logo")
def test_no_logo_when_path_is_none(self, mock_apply_logo, ...existing_patches...):
    """When logo_path is None, apply_logo should not be called."""
    assemble_video(
        analysis=self.analysis,
        scene_plan=self.scene_plan,
        fetch_manifest=self.manifest,
        audio_path=str(self.audio_path),
        output_path=str(self.output_path),
    )
    mock_apply_logo.assert_not_called()
```

Note: The existing test class uses `@patch` decorators stacked on the class. Add `@patch("musicvid.pipeline.assembler.apply_logo")` to the decorator stack. The exact patch order depends on the existing decorators — see `tests/test_assembler.py` for the current pattern.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assembler.py::TestAssembleVideo::test_logo_overlay_added_as_last_layer -v`
Expected: FAIL (apply_logo not imported in assembler, or logo_path not accepted)

- [ ] **Step 3: Modify assembler to accept and apply logo**

In `musicvid/pipeline/assembler.py`:

Add import at line 17 (after the effects import):

```python
from musicvid.pipeline.logo_overlay import apply_logo
```

Update the `assemble_video` function signature (line 200) to add logo params:

```python
def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path,
                   resolution="1080p", font_path=None, effects_level="minimal",
                   clip_start=None, clip_end=None, title_card_text=None,
                   audio_fade_out=1.0, subtitle_margin_bottom=80, cinematic_bars=True,
                   logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85):
```

After the light leak layers block (after line 247) and before `final = CompositeVideoClip(...)` (line 249), add:

```python
    # Logo overlay — topmost layer
    if logo_path:
        logo_clip = apply_logo(
            video, logo_path, logo_position, logo_size, logo_opacity
        )
        layers.append(logo_clip)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py -v`
Expected: All PASSED (existing + new tests)

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat(logo): integrate logo overlay into assembler as topmost layer"
```

---

### Task 6: CLI integration — add `--logo*` flags

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI test for `--logo` flag**

Add to `tests/test_cli.py`:

```python
class TestLogoFlag:
    """Tests for --logo CLI flag."""

    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    def test_logo_passed_to_assembler(self, mock_font, mock_analyze, mock_director, mock_fetch, mock_assemble, tmp_path, sample_analysis, sample_scene_plan):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"fake_png")

        mock_analyze.return_value = sample_analysis
        mock_director.return_value = sample_scene_plan
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4"}]

        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, [str(audio), "--logo", str(logo), "--output", str(tmp_path)])

        mock_assemble.assert_called_once()
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["logo_path"] == str(logo)
        assert call_kwargs["logo_position"] == "top-left"
        assert call_kwargs["logo_opacity"] == 0.85
        assert call_kwargs["logo_size"] is None

    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    def test_logo_all_options(self, mock_font, mock_analyze, mock_director, mock_fetch, mock_assemble, tmp_path, sample_analysis, sample_scene_plan):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")
        logo = tmp_path / "logo.svg"
        logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')

        mock_analyze.return_value = sample_analysis
        mock_director.return_value = sample_scene_plan
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4"}]

        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, [
            str(audio), "--logo", str(logo),
            "--logo-position", "bottom-right",
            "--logo-size", "200",
            "--logo-opacity", "0.5",
            "--output", str(tmp_path),
        ])

        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["logo_path"] == str(logo)
        assert call_kwargs["logo_position"] == "bottom-right"
        assert call_kwargs["logo_size"] == 200
        assert call_kwargs["logo_opacity"] == 0.5

    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    def test_no_logo_by_default(self, mock_font, mock_analyze, mock_director, mock_fetch, mock_assemble, tmp_path, sample_analysis, sample_scene_plan):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")

        mock_analyze.return_value = sample_analysis
        mock_director.return_value = sample_scene_plan
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4"}]

        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, [str(audio), "--output", str(tmp_path)])

        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["logo_path"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py::TestLogoFlag -v`
Expected: FAIL (no `--logo` option)

- [ ] **Step 3: Add CLI flags to `musicvid.py`**

Add these click options after line 130 (`--reel-duration`):

```python
@click.option("--logo", "logo_path", type=click.Path(), default=None, help="Path to logo file (SVG/PNG) to overlay on video.")
@click.option("--logo-position", type=click.Choice(["top-left", "top-right", "bottom-left", "bottom-right"]), default="top-left", help="Logo position on screen.")
@click.option("--logo-size", type=int, default=None, help="Logo width in pixels (default: auto 12%% of frame width).")
@click.option("--logo-opacity", type=float, default=0.85, help="Logo opacity 0.0-1.0.")
```

Update the `cli` function signature (line 131) to add `logo_path, logo_position, logo_size, logo_opacity` parameters.

- [ ] **Step 4: Pass logo params to all `assemble_video` calls**

There are 3 call sites for `assemble_video` in `musicvid.py`:

**Call 1 — single-output mode (line 328):** Add to the kwargs:

```python
    assemble_video(
        ...existing kwargs...,
        logo_path=logo_path,
        logo_position=logo_position,
        logo_size=logo_size,
        logo_opacity=logo_opacity,
    )
```

**Call 2 — preset full mode (line 378 in `_run_preset_mode`):** The function `_run_preset_mode` needs the logo params too. Update its signature and the call at line ~305 where it's invoked from `cli()`.

Update `_run_preset_mode` signature to include `logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85`.

Add logo kwargs to the full-mode `assemble_video` call:

```python
        assemble_video(
            ...existing kwargs...,
            logo_path=logo_path,
            logo_position=logo_position,
            logo_size=logo_size,
            logo_opacity=logo_opacity,
        )
```

**Call 3 — preset social mode (line 418 in `_run_preset_mode`):** Add logo kwargs to the social-mode `assemble_video` call:

```python
            assemble_video(
                ...existing kwargs...,
                logo_path=logo_path,
                logo_position=logo_position,
                logo_size=logo_size,
                logo_opacity=logo_opacity,
            )
```

Update the `_run_preset_mode` invocation (around line 305 in the `cli` function) to pass logo params:

```python
    _run_preset_mode(
        ...existing args...,
        logo_path=logo_path,
        logo_position=logo_position,
        logo_size=logo_size,
        logo_opacity=logo_opacity,
    )
```

- [ ] **Step 5: Run CLI tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py::TestLogoFlag -v`
Expected: 3 PASSED

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASSED (existing + new ~193 tests)

- [ ] **Step 7: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(logo): add --logo, --logo-position, --logo-size, --logo-opacity CLI flags"
```

---

### Task 7: Preset mode CLI tests for logo

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write test for logo in preset mode**

Add to `tests/test_cli.py`:

```python
class TestLogoWithPreset:
    """Tests that logo params are passed through preset mode."""

    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.select_social_clips")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    def test_preset_all_passes_logo_to_all_assemblies(self, mock_font, mock_analyze, mock_director, mock_fetch, mock_social, mock_assemble, tmp_path, sample_analysis, sample_scene_plan):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake")
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"fake_png")

        mock_analyze.return_value = sample_analysis
        mock_director.return_value = sample_scene_plan
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4"}]
        mock_social.return_value = {
            "clips": [
                {"id": 1, "start": 0.0, "end": 15.0, "section": "intro"},
                {"id": 2, "start": 30.0, "end": 45.0, "section": "chorus"},
                {"id": 3, "start": 60.0, "end": 75.0, "section": "outro"},
            ]
        }

        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, [
            str(audio), "--preset", "all",
            "--logo", str(logo), "--logo-position", "top-right",
            "--output", str(tmp_path),
        ])

        # 1 full + 3 social = 4 assemble calls
        assert mock_assemble.call_count == 4
        for call_obj in mock_assemble.call_args_list:
            kwargs = call_obj[1]
            assert kwargs["logo_path"] == str(logo)
            assert kwargs["logo_position"] == "top-right"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py::TestLogoWithPreset -v`
Expected: PASSED (should pass if Task 6 was done correctly)

- [ ] **Step 3: Run full test suite one final time**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASSED

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli.py
git commit -m "test(logo): add preset mode logo integration tests"
```
