# MoviePy 2.x Migration - assembler.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite assembler.py to work with MoviePy 2.1.2 API (currently broken with v1.x API calls)

**Architecture:** Single-file rewrite of `musicvid/pipeline/assembler.py` plus test updates. All MoviePy v1 method calls must be replaced with v2 equivalents. Tests must mock v2 method names.

**Tech Stack:** Python 3.14, MoviePy 2.1.2, PIL/Pillow, numpy, pytest

---

## API Migration Reference

| MoviePy 1.x | MoviePy 2.x |
|---|---|
| `clip.fl(func)` | `clip.transform(func)` |
| `clip.set_position(pos)` | `clip.with_position(pos)` |
| `clip.crossfadein(d)` | `clip.with_effects([vfx.CrossFadeIn(d)])` |
| `clip.crossfadeout(d)` | `clip.with_effects([vfx.CrossFadeOut(d)])` |
| `TextClip(text, fontsize=N, font=F, ...)` | `TextClip(text=text, font=F, font_size=N, ...)` |
| `moviepy.editor` | `moviepy` (no `.editor` submodule) |
| `Image.fromarray(x).resized(...)` | `Image.fromarray(x).resize(...)` (PIL fix, not MoviePy) |

**Verified on installed MoviePy 2.1.2:**
- `VideoClip.fl` → does NOT exist
- `VideoClip.transform` → exists, signature: `(self, func, apply_to=None, keep_duration=True)`
- `VideoClip.crossfadein` → does NOT exist
- `VideoClip.with_effects` → exists
- `TextClip.__init__` signature: `(self, font=None, text=None, filename=None, font_size=None, size=(None, None), ...)`

---

### Task 1: Fix assembler.py - Ken Burns effects (fl → transform, PIL .resized → .resize)

**Files:**
- Modify: `musicvid/pipeline/assembler.py:37-100`

- [ ] **Step 1: Fix PIL `.resized()` → `.resize()` calls**

In `_create_ken_burns_clip`, lines 55 and 71 call `Image.fromarray(cropped).resized(...)` but PIL Image uses `.resize()`, not `.resized()`. Fix both occurrences:

```python
# Line 55 (inside zoom_in):
img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)

# Line 71 (inside zoom_out):
img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
```

- [ ] **Step 2: Replace `clip.fl(func)` → `clip.transform(func)`**

Replace all 4 occurrences of `clip.fl(...)` with `clip.transform(...)`:

```python
# Line 57: return clip.fl(zoom_in) →
return clip.transform(zoom_in)

# Line 73: return clip.fl(zoom_out) →
return clip.transform(zoom_out)

# Line 84: return clip.fl(pan_l) →
return clip.transform(pan_l)

# Line 95: return clip.fl(pan_r) →
return clip.transform(pan_r)
```

- [ ] **Step 3: Run tests to verify Ken Burns changes don't break**

Run: `python3 -m pytest tests/test_assembler.py -v`

---

### Task 2: Fix assembler.py - TextClip and subtitle methods

**Files:**
- Modify: `musicvid/pipeline/assembler.py:1-5,103-135`

- [ ] **Step 1: Add vfx import**

Add `from moviepy import vfx` to the import block (inside the try/except):

```python
try:
    from moviepy.editor import (
        VideoFileClip, ImageClip, AudioFileClip, TextClip,
        CompositeVideoClip, concatenate_videoclips,
    )
    from moviepy import vfx
except ImportError:
    from moviepy import (
        VideoFileClip, ImageClip, AudioFileClip, TextClip,
        CompositeVideoClip, concatenate_videoclips, vfx,
    )
```

- [ ] **Step 2: Fix TextClip constructor call**

In `_create_subtitle_clips`, the TextClip constructor must use keyword args with v2 names. Change lines 116-125:

```python
txt_clip = TextClip(
    text=segment["text"],
    font_size=font_size,
    color=color,
    stroke_color=outline_color,
    stroke_width=2,
    font="Arial-Bold",
    method="caption",
    size=(size[0] - 100, None),
)
```

Key changes: positional `segment["text"]` → `text=segment["text"]`, `fontsize` → `font_size`.

- [ ] **Step 3: Fix set_position → with_position**

Line 128:
```python
# Old:
txt_clip = txt_clip.set_position(("center", size[1] - margin_bottom - font_size))
# New:
txt_clip = txt_clip.with_position(("center", size[1] - margin_bottom - font_size))
```

- [ ] **Step 4: Fix crossfadein/crossfadeout → with_effects**

Lines 130-131:
```python
# Old:
fade_duration = min(0.3, duration / 3)
txt_clip = txt_clip.crossfadein(fade_duration).crossfadeout(fade_duration)
# New:
fade_duration = min(0.3, duration / 3)
txt_clip = txt_clip.with_effects([
    vfx.CrossFadeIn(fade_duration),
    vfx.CrossFadeOut(fade_duration),
])
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_assembler.py -v`

---

### Task 3: Fix the import block (remove dead moviepy.editor fallback)

**Files:**
- Modify: `musicvid/pipeline/assembler.py:1-22`

- [ ] **Step 1: Simplify imports**

MoviePy 2.x has no `moviepy.editor`. The try/except is unnecessary. Replace the entire import block:

```python
from moviepy import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
    vfx,
)
```

- [ ] **Step 2: Run tests**

Run: `python3 -m pytest tests/test_assembler.py -v`

---

### Task 4: Update tests to mock MoviePy 2.x method names

**Files:**
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Update TestCreateSubtitleClips mocks**

The mock in `test_creates_clips_for_lyrics` (lines 39-44) uses v1 method names. Update to v2:

```python
mock_clip = MagicMock()
mock_clip.with_duration.return_value = mock_clip
mock_clip.with_start.return_value = mock_clip
mock_clip.with_position.return_value = mock_clip
mock_clip.with_effects.return_value = mock_clip
mock_text_clip.return_value = mock_clip
```

- [ ] **Step 2: Update TestAssembleVideo mocks**

The mock in `test_produces_output_file` (lines 75-90) uses v1 method names. Update to v2:

```python
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
```

Also add a mock for `vfx` module:
```python
@patch("musicvid.pipeline.assembler.vfx")
```
to each test that uses it (the subtitle and assemble tests).

- [ ] **Step 3: Run all tests and verify they pass**

Run: `python3 -m pytest tests/test_assembler.py -v`
Expected: All 7 tests PASS

- [ ] **Step 4: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All 27 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "fix: migrate assembler.py from MoviePy 1.x to 2.x API"
```
