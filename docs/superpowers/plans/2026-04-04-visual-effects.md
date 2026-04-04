# Visual Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cinematic visual effects (warm grade, vignette, cinematic bars, film grain, light leak) to generated music videos via a new `--effects` CLI flag.

**Architecture:** New `musicvid/pipeline/effects.py` module with pure-function effects that operate on MoviePy clips via numpy transforms. The assembler calls `apply_effects()` after Ken Burns and before subtitles. CLI passes the effects level through to assembler.

**Tech Stack:** numpy (frame transforms), MoviePy 2.x (ColorClip, CompositeVideoClip, transform()), Click (CLI option)

---

### Task 1: Warm Grade Effect

**Files:**
- Create: `musicvid/pipeline/effects.py`
- Create: `tests/test_effects.py`

- [ ] **Step 1: Write the failing test for apply_warm_grade**

```python
"""Tests for visual effects module."""

import numpy as np
import pytest
from unittest.mock import MagicMock

from musicvid.pipeline.effects import apply_warm_grade


class TestApplyWarmGrade:
    """Tests for warm color grading effect."""

    def test_increases_red_decreases_blue(self):
        """Red channel increases by 15, blue decreases by 10 after warm grade."""
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        result = apply_warm_grade(mock_clip)

        # Extract the transform function passed to clip.transform()
        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame
        output = transform_fn(get_frame, 0)

        assert output[:, :, 0].mean() == 143  # R: 128 + 15
        assert output[:, :, 1].mean() == 133  # G: 128 + 5
        assert output[:, :, 2].mean() == 118  # B: 128 - 10

    def test_clamps_values(self):
        """Values clamp to 0-255 range."""
        frame = np.full((100, 100, 3), 250, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_warm_grade(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame
        output = transform_fn(get_frame, 0)

        assert output[:, :, 0].mean() == 255  # R: clamped at 255
        assert output[:, :, 2].mean() == 240  # B: 250 - 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_effects.py::TestApplyWarmGrade -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'musicvid.pipeline.effects'`

- [ ] **Step 3: Write minimal implementation**

Create `musicvid/pipeline/effects.py`:

```python
"""Visual effects for music video clips."""

import numpy as np


def apply_warm_grade(clip):
    """Apply warm color grading: R+15, G+5, B-10, clamped to 0-255."""
    def _warm(get_frame, t):
        frame = get_frame(t).astype(np.int16)
        frame[:, :, 0] += 15
        frame[:, :, 1] += 5
        frame[:, :, 2] -= 10
        return np.clip(frame, 0, 255).astype(np.uint8)
    return clip.transform(_warm)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_effects.py::TestApplyWarmGrade -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/effects.py tests/test_effects.py
git commit -m "feat: add warm grade effect with TDD"
```

---

### Task 2: Vignette Effect

**Files:**
- Modify: `musicvid/pipeline/effects.py`
- Modify: `tests/test_effects.py`

- [ ] **Step 1: Write the failing test for apply_vignette**

Add to `tests/test_effects.py`:

```python
from musicvid.pipeline.effects import apply_vignette


class TestApplyVignette:
    """Tests for vignette (edge darkening) effect."""

    def test_edges_darker_than_center(self):
        """Edge pixels should be darker than center pixels after vignette."""
        frame = np.full((200, 200, 3), 200, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_vignette(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame
        output = transform_fn(get_frame, 0)

        center_val = output[100, 100, 0]
        corner_val = output[0, 0, 0]
        assert center_val > corner_val, f"Center {center_val} should be brighter than corner {corner_val}"

    def test_center_mostly_unchanged(self):
        """Center pixel should retain most of its original brightness."""
        frame = np.full((200, 200, 3), 200, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_vignette(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame
        output = transform_fn(get_frame, 0)

        center_val = output[100, 100, 0]
        assert center_val >= 190, f"Center {center_val} should be close to original 200"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_effects.py::TestApplyVignette -v`
Expected: FAIL with `ImportError: cannot import name 'apply_vignette'`

- [ ] **Step 3: Write minimal implementation**

Add to `musicvid/pipeline/effects.py`:

```python
def apply_vignette(clip):
    """Apply vignette: darken edges by up to 40% using Gaussian mask."""
    _vignette_cache = {}

    def _vignette(get_frame, t):
        frame = get_frame(t)
        h, w = frame.shape[:2]
        key = (h, w)
        if key not in _vignette_cache:
            y = np.linspace(-1, 1, h)
            x = np.linspace(-1, 1, w)
            xv, yv = np.meshgrid(x, y)
            dist = np.sqrt(xv ** 2 + yv ** 2)
            # Gaussian falloff: center=1.0, edges~0.6
            sigma = 0.8
            mask = np.exp(-(dist ** 2) / (2 * sigma ** 2))
            # Scale so center is 1.0, corners darken by ~40%
            mask = 0.6 + 0.4 * mask
            _vignette_cache[key] = mask[:, :, np.newaxis].astype(np.float32)
        return (frame * _vignette_cache[key]).astype(np.uint8)
    return clip.transform(_vignette)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_effects.py::TestApplyVignette -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/effects.py tests/test_effects.py
git commit -m "feat: add vignette effect with TDD"
```

---

### Task 3: Cinematic Bars

**Files:**
- Modify: `musicvid/pipeline/effects.py`
- Modify: `tests/test_effects.py`

- [ ] **Step 1: Write the failing test for create_cinematic_bars**

Add to `tests/test_effects.py`:

```python
from unittest.mock import patch

from musicvid.pipeline.effects import create_cinematic_bars


class TestCreateCinematicBars:
    """Tests for cinematic letterbox bars."""

    @patch("musicvid.pipeline.effects.ColorClip")
    def test_returns_two_bar_clips(self, mock_color_clip):
        mock_bar = MagicMock()
        mock_bar.with_duration.return_value = mock_bar
        mock_bar.with_position.return_value = mock_bar
        mock_color_clip.return_value = mock_bar

        bars = create_cinematic_bars(1920, 1080, 10.0)

        assert len(bars) == 2

    @patch("musicvid.pipeline.effects.ColorClip")
    def test_bar_height_is_12_percent(self, mock_color_clip):
        mock_bar = MagicMock()
        mock_bar.with_duration.return_value = mock_bar
        mock_bar.with_position.return_value = mock_bar
        mock_color_clip.return_value = mock_bar

        bars = create_cinematic_bars(1920, 1080, 10.0)

        # Bar height = 12% of 1080 = 129 (int)
        call_args_list = mock_color_clip.call_args_list
        size_arg = call_args_list[0][1]["size"]
        assert size_arg == (1920, 129)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_effects.py::TestCreateCinematicBars -v`
Expected: FAIL with `ImportError: cannot import name 'create_cinematic_bars'`

- [ ] **Step 3: Write minimal implementation**

Add imports and function to `musicvid/pipeline/effects.py`:

```python
from moviepy import ColorClip


def create_cinematic_bars(width, height, duration):
    """Create top and bottom black cinematic bars (12% height each)."""
    bar_h = int(height * 0.12)
    top = ColorClip(size=(width, bar_h), color=(0, 0, 0))
    top = top.with_duration(duration)
    top = top.with_position(("center", 0))

    bottom = ColorClip(size=(width, bar_h), color=(0, 0, 0))
    bottom = bottom.with_duration(duration)
    bottom = bottom.with_position(("center", height - bar_h))

    return [top, bottom]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_effects.py::TestCreateCinematicBars -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/effects.py tests/test_effects.py
git commit -m "feat: add cinematic bars effect with TDD"
```

---

### Task 4: Film Grain Effect

**Files:**
- Modify: `musicvid/pipeline/effects.py`
- Modify: `tests/test_effects.py`

- [ ] **Step 1: Write the failing test for apply_film_grain**

Add to `tests/test_effects.py`:

```python
from musicvid.pipeline.effects import apply_film_grain


class TestApplyFilmGrain:
    """Tests for film grain (animated noise) effect."""

    def test_adds_noise_to_frame(self):
        """Frame should differ from original after grain is applied."""
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_film_grain(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame.copy()

        np.random.seed(42)
        output = transform_fn(get_frame, 0)

        # Grain adds noise, so output should not be identical to input
        assert not np.array_equal(output, frame)

    def test_grain_is_subtle(self):
        """Mean pixel difference should be small (opacity 0.15, sigma 8)."""
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_film_grain(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame.copy()

        np.random.seed(42)
        output = transform_fn(get_frame, 0)

        diff = np.abs(output.astype(int) - frame.astype(int))
        assert diff.mean() < 5, f"Grain too strong: mean diff {diff.mean()}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_effects.py::TestApplyFilmGrain -v`
Expected: FAIL with `ImportError: cannot import name 'apply_film_grain'`

- [ ] **Step 3: Write minimal implementation**

Add to `musicvid/pipeline/effects.py`:

```python
def apply_film_grain(clip):
    """Apply animated film grain: Gaussian noise sigma=8, opacity 0.15."""
    def _grain(get_frame, t):
        frame = get_frame(t).astype(np.float32)
        noise = np.random.normal(0, 8, frame.shape).astype(np.float32)
        result = frame + noise * 0.15
        return np.clip(result, 0, 255).astype(np.uint8)
    return clip.transform(_grain)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_effects.py::TestApplyFilmGrain -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/effects.py tests/test_effects.py
git commit -m "feat: add film grain effect with TDD"
```

---

### Task 5: Light Leak Effect

**Files:**
- Modify: `musicvid/pipeline/effects.py`
- Modify: `tests/test_effects.py`

- [ ] **Step 1: Write the failing test for create_light_leak**

Add to `tests/test_effects.py`:

```python
from musicvid.pipeline.effects import create_light_leak


class TestCreateLightLeak:
    """Tests for light leak effect."""

    @patch("musicvid.pipeline.effects.ImageClip")
    def test_returns_clip_with_correct_duration(self, mock_image_clip):
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_end.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_image_clip.return_value = mock_clip

        result = create_light_leak(10.0, (1920, 1080))

        mock_clip.with_duration.assert_called_once()
        assert result is not None

    @patch("musicvid.pipeline.effects.ImageClip")
    def test_leak_appears_between_20_and_60_percent(self, mock_image_clip):
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_end.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_image_clip.return_value = mock_clip

        np.random.seed(42)
        create_light_leak(10.0, (1920, 1080))

        start_call = mock_clip.with_start.call_args[0][0]
        assert 2.0 <= start_call <= 6.0, f"Start {start_call} not in 20-60% of 10s"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_effects.py::TestCreateLightLeak -v`
Expected: FAIL with `ImportError: cannot import name 'create_light_leak'`

- [ ] **Step 3: Write minimal implementation**

Add import and function to `musicvid/pipeline/effects.py`:

```python
from moviepy import ImageClip


def create_light_leak(duration, size):
    """Create an animated light leak overlay for a scene.

    Orange-gold gradient, opacity 0.2, appears once between 20-60% of duration,
    sweeps across the frame over ~1.5 seconds.
    """
    w, h = size
    # Create orange-gold gradient image
    gradient = np.zeros((h, w, 4), dtype=np.uint8)
    for x in range(w):
        alpha = int(255 * (1 - abs(x - w // 2) / (w // 2)) * 0.2)
        gradient[:, x, 0] = 255  # R
        gradient[:, x, 1] = 180  # G
        gradient[:, x, 2] = 50   # B
        gradient[:, x, 3] = alpha  # A

    leak_duration = min(1.5, duration * 0.3)
    start_time = duration * (0.2 + np.random.random() * 0.4)

    clip = ImageClip(gradient[:, :, :3])
    clip = clip.with_duration(leak_duration)
    clip = clip.with_start(start_time)
    clip = clip.with_end(start_time + leak_duration)
    clip = clip.with_position("center")

    from moviepy import vfx
    clip = clip.with_effects([
        vfx.CrossFadeIn(leak_duration * 0.3),
        vfx.CrossFadeOut(leak_duration * 0.3),
    ])

    return clip
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_effects.py::TestCreateLightLeak -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/effects.py tests/test_effects.py
git commit -m "feat: add light leak effect with TDD"
```

---

### Task 6: apply_effects Orchestrator

**Files:**
- Modify: `musicvid/pipeline/effects.py`
- Modify: `tests/test_effects.py`

- [ ] **Step 1: Write the failing tests for apply_effects**

Add to `tests/test_effects.py`:

```python
from musicvid.pipeline.effects import apply_effects


class TestApplyEffects:
    """Tests for the apply_effects orchestrator."""

    def test_none_returns_clip_unchanged(self):
        """Level 'none' should not apply any effects."""
        mock_clip = MagicMock()
        result = apply_effects(mock_clip, level="none")
        assert result is mock_clip
        mock_clip.transform.assert_not_called()

    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_minimal_applies_warm_and_vignette(self, mock_warm, mock_vignette):
        """Level 'minimal' should apply warm grade and vignette."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip

        apply_effects(mock_clip, level="minimal")

        mock_warm.assert_called_once_with(mock_clip)
        mock_vignette.assert_called_once()

    @patch("musicvid.pipeline.effects.apply_film_grain")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_full_applies_all_frame_effects(self, mock_warm, mock_vignette, mock_grain):
        """Level 'full' should apply warm grade, vignette, and film grain."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip
        mock_grain.return_value = mock_clip

        apply_effects(mock_clip, level="full")

        mock_warm.assert_called_once()
        mock_vignette.assert_called_once()
        mock_grain.assert_called_once()

    def test_default_level_is_minimal(self):
        """Default level should be 'minimal'."""
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        with patch("musicvid.pipeline.effects.apply_warm_grade", return_value=mock_clip) as mock_warm, \
             patch("musicvid.pipeline.effects.apply_vignette", return_value=mock_clip):
            apply_effects(mock_clip)
            mock_warm.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_effects.py::TestApplyEffects -v`
Expected: FAIL with `ImportError: cannot import name 'apply_effects'`

- [ ] **Step 3: Write minimal implementation**

Add to `musicvid/pipeline/effects.py`:

```python
def apply_effects(clip, level="minimal"):
    """Apply visual effects based on level.

    Args:
        clip: MoviePy clip (after Ken Burns, before subtitles).
        level: "none" | "minimal" | "full"

    Returns:
        Processed clip.
    """
    if level == "none":
        return clip

    clip = apply_warm_grade(clip)
    clip = apply_vignette(clip)

    if level == "full":
        clip = apply_film_grain(clip)

    return clip
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_effects.py::TestApplyEffects -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/effects.py tests/test_effects.py
git commit -m "feat: add apply_effects orchestrator with TDD"
```

---

### Task 7: Integrate Effects into Assembler

**Files:**
- Modify: `musicvid/pipeline/assembler.py:1-2` (add import)
- Modify: `musicvid/pipeline/assembler.py:149` (add effects_level param)
- Modify: `musicvid/pipeline/assembler.py:164-180` (apply effects + bars)
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write the failing test for assembler effects integration**

Add to `tests/test_assembler.py`:

```python
class TestAssembleVideoEffects:
    """Tests for visual effects integration in assembler."""

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
    def test_minimal_effects_applied(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip, mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
            {"scene_index": 1, "video_path": "/fake/scene_001.mp4", "search_query": "test"},
            {"scene_index": 2, "video_path": "/fake/scene_002.png", "search_query": "test"},
        ]

        output_file = str(tmp_output / "output.mp4")

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            resolution="1080p",
            effects_level="minimal",
        )

        mock_apply_effects.assert_called()
        # Bars should be added for minimal
        mock_bars.assert_called_once()

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
    def test_none_effects_skip_all(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
            {"scene_index": 1, "video_path": "/fake/scene_001.mp4", "search_query": "test"},
            {"scene_index": 2, "video_path": "/fake/scene_002.png", "search_query": "test"},
        ]

        output_file = str(tmp_output / "output.mp4")

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            resolution="1080p",
            effects_level="none",
        )

        mock_apply_effects.assert_called()
        # Verify "none" was passed
        call_kwargs = mock_apply_effects.call_args
        assert call_kwargs[1]["level"] == "none" or call_kwargs[0][1] == "none"
        mock_bars.assert_not_called()
        mock_light_leak.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assembler.py::TestAssembleVideoEffects -v`
Expected: FAIL with `TypeError: assemble_video() got an unexpected keyword argument 'effects_level'`

- [ ] **Step 3: Modify assembler.py**

In `musicvid/pipeline/assembler.py`, add import at top:

```python
from musicvid.pipeline.effects import apply_effects, create_cinematic_bars, create_light_leak
```

Modify `assemble_video` function signature (line 149):

```python
def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path, resolution="1080p", font_path=None, effects_level="minimal"):
```

Replace the body from clip loading through compositing (lines 164-180) with:

```python
    scene_clips = []
    for manifest_entry in fetch_manifest:
        idx = manifest_entry["scene_index"]
        scene = scenes[idx]
        clip = _load_scene_clip(manifest_entry["video_path"], scene, target_size)
        clip = apply_effects(clip, level=effects_level)
        scene_clips.append(clip)

    video = concatenate_videoclips(scene_clips, method="compose")

    subtitle_clips = _create_subtitle_clips(
        analysis.get("lyrics", []),
        scene_plan.get("subtitle_style", {}),
        target_size,
        font_path=font_path,
    )

    layers = [video] + subtitle_clips

    if effects_level in ("minimal", "full"):
        bars = create_cinematic_bars(target_size[0], target_size[1], video.duration)
        layers.extend(bars)

    if effects_level == "full":
        for manifest_entry in fetch_manifest:
            idx = manifest_entry["scene_index"]
            scene = scenes[idx]
            scene_duration = scene["end"] - scene["start"]
            leak = create_light_leak(scene_duration, target_size)
            leak = leak.with_start(leak.start + scene["start"])
            leak = leak.with_end(leak.end + scene["start"])
            layers.append(leak)

    final = CompositeVideoClip(layers, size=target_size)
```

Note: The order from the spec is: (1) Ken Burns, (2) warm grade, (3) vignette applied per-scene-clip via `apply_effects`. Then compositing order: video → subtitles → cinematic bars (bars on top to cover subtitle overflow). Light leak overlays are added for "full" mode. Film grain is applied in `apply_effects`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_assembler.py -v`
Expected: ALL PASS (existing + new tests)

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: integrate visual effects into assembler"
```

---

### Task 8: Add --effects CLI Flag

**Files:**
- Modify: `musicvid/musicvid.py:33-44` (add CLI option)
- Modify: `musicvid/musicvid.py:143-151` (pass effects_level to assemble_video)
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test for CLI effects flag**

Read `tests/test_cli.py` first to match existing test patterns, then add:

```python
class TestEffectsFlag:
    """Tests for --effects CLI flag."""

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.get_audio_hash", return_value="abc123def456")
    def test_effects_flag_passes_to_assembler(
        self, mock_hash, mock_analyze, mock_plan, mock_fetch,
        mock_assemble, mock_font, tmp_path, sample_analysis, sample_scene_plan
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        mock_analyze.return_value = sample_analysis
        mock_plan.return_value = sample_scene_plan
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/scene.mp4", "search_query": "test"}
        ]

        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, [str(audio_file), "--effects", "full", "--output", str(tmp_path)])

        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["effects_level"] == "full"

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.get_audio_hash", return_value="abc123def456")
    def test_effects_defaults_to_minimal(
        self, mock_hash, mock_analyze, mock_plan, mock_fetch,
        mock_assemble, mock_font, tmp_path, sample_analysis, sample_scene_plan
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        mock_analyze.return_value = sample_analysis
        mock_plan.return_value = sample_scene_plan
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/scene.mp4", "search_query": "test"}
        ]

        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, [str(audio_file), "--output", str(tmp_path)])

        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["effects_level"] == "minimal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::TestEffectsFlag -v`
Expected: FAIL (no effects_level in assemble_video call)

- [ ] **Step 3: Modify musicvid.py**

Add CLI option after the `--lyrics` line (line 43):

```python
@click.option("--effects", type=click.Choice(["none", "minimal", "full"]), default="minimal", help="Visual effects level.")
```

Update function signature (line 44):

```python
def cli(audio_file, mode, provider, style, output, resolution, lang, new, font_path, lyrics_path, effects):
```

Update `assemble_video` call (lines 143-151) to pass effects_level:

```python
    assemble_video(
        analysis=analysis,
        scene_plan=scene_plan,
        fetch_manifest=fetch_manifest,
        audio_path=str(audio_path),
        output_path=output_path,
        resolution=resolution,
        font_path=font,
        effects_level=effects,
    )
```

- [ ] **Step 4: Run ALL tests to verify everything passes**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add --effects CLI flag for visual effects level"
```

---

### Task 9: Run Full Test Suite and Fix Any Issues

**Files:**
- Potentially any file from Tasks 1-8

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Fix any failing tests**

If any tests fail, analyze the error and fix. Common issues:
- Existing assembler tests may fail because `assemble_video` now imports from `effects.py` — these tests need `@patch("musicvid.pipeline.assembler.apply_effects")`, `@patch("musicvid.pipeline.assembler.create_cinematic_bars")`, and `@patch("musicvid.pipeline.assembler.create_light_leak")` added to their decorators.
- Existing CLI tests may need the `effects` parameter mocked.

For existing `TestAssembleVideo` tests, add these three patches:

```python
@patch("musicvid.pipeline.assembler.create_cinematic_bars")
@patch("musicvid.pipeline.assembler.create_light_leak")
@patch("musicvid.pipeline.assembler.apply_effects")
```

And update mock setup to include:
```python
mock_apply_effects.return_value = mock_clip
mock_bars.return_value = [mock_clip, mock_clip]
```

- [ ] **Step 3: Run tests again after fixes**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit fixes if any**

```bash
git add -A
git commit -m "fix: update existing tests for effects integration"
```
