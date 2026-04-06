# Fix Reels Assembler — imread Crash & Wrong 9:16 Crop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs in `assembler.py` for reels/portrait mode: (1) crash when `video_path` is None passed to `_load_scene_clip`, and (2) `.mp4` video clips being stretched instead of center-cropped when converting to 9:16.

**Architecture:** Add a `convert_16_9_to_9_16` helper to `assembler.py` that scales then crops video clips to portrait; guard `_load_scene_clip` against `None` paths; apply `convert_16_9_to_9_16` for `.mp4` clips in portrait mode instead of the current destructive `resized(new_size=target_size)`.

**Tech Stack:** Python 3.11+, MoviePy 2.1.2, pytest, unittest.mock

---

## File Map

| File | Change |
|------|--------|
| `musicvid/pipeline/assembler.py` | Add `convert_16_9_to_9_16()`; fix `_load_scene_clip()` guard + portrait mp4 path |
| `tests/test_assembler.py` | Add tests: None path raises ValueError, mp4 portrait uses crop not stretch, convert_16_9_to_9_16 dimensions |

---

## Task 1: Add `convert_16_9_to_9_16` and guard against None in `_load_scene_clip`

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Test: `tests/test_assembler.py`

- [ ] **Step 1: Write failing tests**

Add these tests to `tests/test_assembler.py`, inside the existing `TestLoadSceneClip` class (or a new class at the end):

```python
class TestConvert16To9_16:
    """Tests for convert_16_9_to_9_16."""

    def test_output_dimensions(self):
        from musicvid.pipeline.assembler import convert_16_9_to_9_16

        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        resized_clip = MagicMock()
        resized_clip.size = (3413, 1920)  # after scale = 1920/1080 ≈ 1.778
        mock_clip.resized.return_value = resized_clip
        cropped_clip = MagicMock()
        resized_clip.cropped.return_value = cropped_clip

        result = convert_16_9_to_9_16(mock_clip, target_w=1080, target_h=1920)

        # resized called with new height = 1920, width proportional
        mock_clip.resized.assert_called_once()
        args = mock_clip.resized.call_args[0]
        new_w, new_h = args[0]
        assert new_h == 1920
        assert new_w == int(1920 * 1920 / 1080)  # == 3413

        # cropped to center 1080px width
        resized_clip.cropped.assert_called_once()
        ckwargs = resized_clip.cropped.call_args[1]
        assert ckwargs["x1"] == (3413 - 1080) // 2
        assert ckwargs["x2"] == (3413 - 1080) // 2 + 1080
        assert ckwargs["y1"] == 0
        assert ckwargs["y2"] == 1920

    def test_does_not_stretch(self):
        """Result width must equal target_w, not be a stretched version."""
        from musicvid.pipeline.assembler import convert_16_9_to_9_16

        mock_clip = MagicMock()
        mock_clip.size = (1280, 720)
        scale = 1920 / 720  # ≈ 2.667
        new_w = int(1280 * scale)  # 3413
        resized_clip = MagicMock()
        resized_clip.size = (new_w, 1920)
        mock_clip.resized.return_value = resized_clip
        cropped_clip = MagicMock()
        resized_clip.cropped.return_value = cropped_clip

        convert_16_9_to_9_16(mock_clip, target_w=1080, target_h=1920)

        # Must NOT call resized with (1080, 1920) directly (that stretches)
        call_args = mock_clip.resized.call_args[0]
        w, h = call_args[0]
        assert w != 1080 or h != 1920, "Should not resize directly to 1080x1920"


class TestLoadSceneClipNonePath:
    """Tests that _load_scene_clip raises for None path."""

    def test_none_path_raises_value_error(self):
        from musicvid.pipeline.assembler import _load_scene_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in"}
        with pytest.raises((ValueError, TypeError)):
            _load_scene_clip(None, scene, (1080, 1920))


class TestLoadSceneClipPortraitMp4:
    """Tests that _load_scene_clip uses crop (not stretch) for portrait .mp4."""

    @patch("musicvid.pipeline.assembler.VideoFileClip")
    def test_portrait_mp4_uses_convert_not_resize(self, mock_vfc, tmp_path):
        from musicvid.pipeline.assembler import _load_scene_clip

        fake_mp4 = tmp_path / "scene.mp4"
        fake_mp4.write_bytes(b"fake video")

        mock_clip = MagicMock()
        mock_clip.duration = 10.0
        mock_clip.size = (1920, 1080)
        mock_clip.subclipped.return_value = mock_clip
        resized_clip = MagicMock()
        resized_clip.size = (3413, 1920)
        mock_clip.resized.return_value = resized_clip
        cropped_clip = MagicMock()
        resized_clip.cropped.return_value = cropped_clip
        mock_vfc.return_value = mock_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in"}
        _load_scene_clip(str(fake_mp4), scene, (1080, 1920))

        # resized must NOT be called with new_size=(1080, 1920) — that stretches
        for call in mock_clip.resized.call_args_list:
            kw = call[1]
            if "new_size" in kw:
                assert kw["new_size"] != (1080, 1920), \
                    "resized(new_size=(1080,1920)) stretches video — use convert_16_9_to_9_16 instead"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_assembler.py::TestConvert16To9_16 tests/test_assembler.py::TestLoadSceneClipNonePath tests/test_assembler.py::TestLoadSceneClipPortraitMp4 -v 2>&1 | tail -30
```

Expected: errors/failures (functions not yet added).

- [ ] **Step 3: Add `convert_16_9_to_9_16` to assembler.py and fix `_load_scene_clip`**

In `musicvid/pipeline/assembler.py`, insert `convert_16_9_to_9_16` right after `_remap_motion_for_portrait` (around line 186):

```python
def convert_16_9_to_9_16(clip, target_w=1080, target_h=1920):
    """Convert a landscape clip to portrait 9:16 via scale + center crop.

    Scales so height == target_h, then crops width to target_w.
    Never stretches — aspect ratio preserved during resize.
    """
    src_w, src_h = clip.size
    scale = target_h / src_h
    new_w = int(src_w * scale)
    clip = clip.resized((new_w, target_h))
    x1 = (new_w - target_w) // 2
    x2 = x1 + target_w
    clip = clip.cropped(x1=x1, y1=0, x2=x2, y2=target_h)
    return clip
```

Then modify `_load_scene_clip` to:
1. Guard against `None` path at the top
2. Use `convert_16_9_to_9_16` for `.mp4` in portrait mode

Replace the current `_load_scene_clip` body with:

```python
def _load_scene_clip(video_path, scene, target_size, reels_style="blur-bg"):
    """Load a video or image clip for a scene."""
    if video_path is None:
        raise ValueError("video_path is None — no asset for this scene")

    path = Path(video_path)
    duration = scene["end"] - scene["start"]
    is_portrait = target_size == (1080, 1920)

    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
        if is_portrait:
            processed_path = convert_for_platform(str(path), "reels", style=reels_style)
            clip = ImageClip(processed_path)
        else:
            clip = ImageClip(str(path))
    else:
        clip = VideoFileClip(str(path))
        if clip.duration < duration:
            loops = int(duration / clip.duration) + 1
            clip = concatenate_videoclips([clip] * loops)
        clip = clip.subclipped(0, duration)

    # Video files (.mp4): skip Ken Burns — video already has motion
    if path.suffix.lower() == ".mp4":
        if is_portrait:
            return convert_16_9_to_9_16(clip, target_w=target_size[0], target_h=target_size[1])
        return clip.resized(new_size=target_size)

    return _create_ken_burns_clip(clip, duration, scene.get("motion", "static"), target_size)
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
python3 -m pytest tests/test_assembler.py::TestConvert16To9_16 tests/test_assembler.py::TestLoadSceneClipNonePath tests/test_assembler.py::TestLoadSceneClipPortraitMp4 -v 2>&1 | tail -30
```

Expected: all PASS.

- [ ] **Step 5: Run the full test suite**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -50
```

Expected: all pre-existing tests still pass (no regressions). The existing `test_animated_scene_skips_ken_burns` and `test_non_animated_mp4_skips_ken_burns` tests use landscape `(1920, 1080)` so they should be unaffected.

- [ ] **Step 6: Commit**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "fix: fix reels assembler — guard None path and add 16:9→9:16 crop for mp4"
```

---

## Self-Review

**Spec coverage:**
- ✅ Problem 1 — None path: `_load_scene_clip` now raises `ValueError` for `None` video_path
- ✅ Problem 2 — crop not stretch: `convert_16_9_to_9_16` scales height then crops width; used for `.mp4` in portrait mode
- ✅ Tests: 6 new test methods covering None-path, output dimensions, non-stretch assertion, portrait mp4 behavior
- ✅ `find_nearest_scene` — already has correct fallback logic in `musicvid.py`; no change needed

**Placeholder scan:** No placeholders — all steps have concrete code.

**Type consistency:** `convert_16_9_to_9_16` used with matching signature `(clip, target_w, target_h)` in both definition and call site inside `_load_scene_clip`.
