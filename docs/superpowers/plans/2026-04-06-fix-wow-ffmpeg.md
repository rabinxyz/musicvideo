# Fix FFmpeg WOW Effects eval_mode Error Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix FFmpeg 7.x eval_mode crash in WOW effects and add graceful fallback so video always generates even when WOW effects fail.

**Architecture:** Two changes in `musicvid/pipeline/wow_effects.py`: (1) add `ENABLE_ZOOMPAN = False` constant to gate the `_build_zoom_punch_filter` call (which uses `t` in `scale` width/height expressions — invalid in FFmpeg 7.x init eval mode), (2) change `apply_wow_effects` from re-raising on FFmpeg failure to printing a warning and returning, preserving the original file.

**Tech Stack:** Python 3.11+, FFmpeg 7.1.1, `unittest.mock`, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `musicvid/pipeline/wow_effects.py` | Modify | Add `ENABLE_ZOOMPAN = False` flag; make fallback non-raising |
| `tests/test_wow_effects.py` | Modify | Update `test_raises_on_ffmpeg_failure` → warns; add ENABLE_ZOOMPAN test |

---

### Task 1: Add ENABLE_ZOOMPAN flag to disable scale-with-t zoom filter

FFmpeg 7.x evaluates `scale=w='...'` expressions in init mode (once before any frame), so `t` (frame time) is invalid there. The simplest fix is a module-level flag that disables zoom_punch entirely.

**Files:**
- Modify: `musicvid/pipeline/wow_effects.py`
- Test: `tests/test_wow_effects.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_wow_effects.py` inside `class TestBuildFilterChain`:

```python
def test_zoom_punch_skipped_when_enable_zoompan_false(self):
    import musicvid.pipeline.wow_effects as wm
    original = wm.ENABLE_ZOOMPAN
    try:
        wm.ENABLE_ZOOMPAN = False
        from musicvid.pipeline.wow_effects import build_ffmpeg_filter_chain
        analysis = {
            "sections": [{"label": "chorus", "start": 2.0, "end": 8.0}],
            "beats": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0,
                      4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0],
            "duration": 10.0,
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
        )
        self.assertIsNone(result)
    finally:
        wm.ENABLE_ZOOMPAN = original
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_wow_effects.py::TestBuildFilterChain::test_zoom_punch_skipped_when_enable_zoompan_false -v
```

Expected: FAIL — `AttributeError: module has no attribute 'ENABLE_ZOOMPAN'`

- [ ] **Step 3: Add ENABLE_ZOOMPAN constant and gate zoom_punch in wow_effects.py**

In `musicvid/pipeline/wow_effects.py`, add the constant after the imports block (after line 12, before `def default_wow_config()`):

```python
# Set to False to skip the zoom-punch (scale+t) filter that crashes FFmpeg 7.x
# in init eval_mode. Safe to re-enable when FFmpeg fixes scale eval.
ENABLE_ZOOMPAN = False
```

Then in `build_ffmpeg_filter_chain`, change the zoom_punch block (currently lines 49-53):

```python
    if ENABLE_ZOOMPAN and wow_config.get("zoom_punch", True):
        f = _build_zoom_punch_filter(beats, sections, video_width, video_height)
        if f:
            filters.append(f)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_wow_effects.py::TestBuildFilterChain::test_zoom_punch_skipped_when_enable_zoompan_false -v
```

Expected: PASS

- [ ] **Step 5: Run full wow_effects test suite**

```bash
python3 -m pytest tests/test_wow_effects.py -v
```

Expected: All pass. Note: `test_returns_string_when_zoom_punch_enabled` uses `zoom_punch=True` but with `ENABLE_ZOOMPAN=False` the result may now be None — check if this test needs updating.

If `test_returns_string_when_zoom_punch_enabled` fails because ENABLE_ZOOMPAN=False causes `result=None`:

Update that test to temporarily set `ENABLE_ZOOMPAN = True`:

```python
def test_returns_string_when_zoom_punch_enabled(self):
    import musicvid.pipeline.wow_effects as wm
    original = wm.ENABLE_ZOOMPAN
    try:
        wm.ENABLE_ZOOMPAN = True
        from musicvid.pipeline.wow_effects import build_ffmpeg_filter_chain
        analysis = {
            "sections": [{"label": "chorus", "start": 10.0, "end": 30.0}],
            "beats": [0.5, 1.0, 1.5, 2.0, 10.5, 11.0, 11.5, 12.0,
                      12.5, 13.0, 13.5, 14.0, 14.5, 15.0, 15.5, 16.0],
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
        )
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
    finally:
        wm.ENABLE_ZOOMPAN = original
```

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/wow_effects.py tests/test_wow_effects.py
git commit -m "fix(wow): add ENABLE_ZOOMPAN=False flag to skip scale+t filter crashing FFmpeg 7.x"
```

---

### Task 2: Add graceful fallback in apply_wow_effects (warn, don't raise)

Currently `apply_wow_effects` re-raises on FFmpeg failure, crashing the whole pipeline. The fix: catch the exception, print a warning, and return — the original file at `video_path` is already intact (the temp file is deleted, original untouched).

**Files:**
- Modify: `musicvid/pipeline/wow_effects.py`
- Test: `tests/test_wow_effects.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_wow_effects.py` inside `class TestApplyWowEffects`:

```python
def test_warns_and_continues_on_ffmpeg_failure(self):
    """apply_wow_effects should print WARN and not raise when FFmpeg fails."""
    from musicvid.pipeline.wow_effects import apply_wow_effects
    import musicvid.pipeline.wow_effects as wm
    original = wm.ENABLE_ZOOMPAN
    try:
        wm.ENABLE_ZOOMPAN = True  # ensure filter chain is built
        analysis = {
            "sections": [{"label": "chorus", "start": 2.0, "end": 8.0}],
            "beats": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0,
                      4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0],
            "duration": 10.0,
        }
        wow_config = {
            "enabled": True, "zoom_punch": True, "light_flash": False,
            "dynamic_grade": False, "dynamic_vignette": False,
            "motion_blur": False, "particles": False,
        }
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "ffmpeg error: eval_mode"
        with patch("musicvid.pipeline.wow_effects.subprocess") as mock_sub, \
             patch("musicvid.pipeline.wow_effects.tempfile.mkstemp",
                   return_value=(0, "/tmp/wow_tmp.mp4")), \
             patch("musicvid.pipeline.wow_effects.os.close"), \
             patch("musicvid.pipeline.wow_effects.os.path.exists", return_value=True), \
             patch("musicvid.pipeline.wow_effects.os.unlink"), \
             patch("builtins.print") as mock_print:
            mock_sub.run.return_value = mock_result
            # Should NOT raise
            apply_wow_effects(
                video_path="/fake/out.mp4",
                analysis=analysis,
                scene_plan={"scenes": [], "overall_style": "worship"},
                wow_config=wow_config,
            )
            # Should have printed a warning
            printed_args = " ".join(str(a) for call in mock_print.call_args_list for a in call[0])
            self.assertIn("WARN", printed_args)
    finally:
        wm.ENABLE_ZOOMPAN = original
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_wow_effects.py::TestApplyWowEffects::test_warns_and_continues_on_ffmpeg_failure -v
```

Expected: FAIL — raises `RuntimeError` instead of warning

- [ ] **Step 3: Update apply_wow_effects to warn instead of raise**

In `musicvid/pipeline/wow_effects.py`, change the `except` block in `apply_wow_effects` (currently lines 119-122):

```python
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        print(f"WARN: WOW effects failed — używam wideo bez efektów: {e}")
```

Also change the `RuntimeError` raise inside the `try` block (currently lines 114-117) to an exception that gets caught by the outer `except`:

The full updated function body:

```python
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
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        print(f"WARN: WOW effects failed — używam wideo bez efektów: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_wow_effects.py::TestApplyWowEffects::test_warns_and_continues_on_ffmpeg_failure -v
```

Expected: PASS

- [ ] **Step 5: Update existing test_raises_on_ffmpeg_failure**

The existing test `test_raises_on_ffmpeg_failure` now expects a raise that no longer happens. Update it to verify the warning behavior instead (or rename it to document the old behavior is gone).

Replace `test_raises_on_ffmpeg_failure` in `tests/test_wow_effects.py`:

```python
def test_does_not_raise_on_ffmpeg_failure(self):
    """apply_wow_effects must NOT raise on FFmpeg error — graceful fallback."""
    from musicvid.pipeline.wow_effects import apply_wow_effects
    import musicvid.pipeline.wow_effects as wm
    original = wm.ENABLE_ZOOMPAN
    try:
        wm.ENABLE_ZOOMPAN = True
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
             patch("musicvid.pipeline.wow_effects.os.unlink"), \
             patch("builtins.print"):
            mock_sub.run.return_value = mock_result
            # Must not raise
            apply_wow_effects(
                video_path="/fake/out.mp4",
                analysis=analysis,
                scene_plan={"scenes": [], "overall_style": "worship"},
                wow_config=wow_config,
            )
    finally:
        wm.ENABLE_ZOOMPAN = original
```

- [ ] **Step 6: Run full wow_effects suite**

```bash
python3 -m pytest tests/test_wow_effects.py -v
```

Expected: All pass (count may change by +1 net if old test renamed).

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -20
```

Expected: All tests pass (no regressions in assembler tests that mock `apply_wow_effects`).

- [ ] **Step 8: Commit**

```bash
git add musicvid/pipeline/wow_effects.py tests/test_wow_effects.py
git commit -m "fix(wow): graceful fallback on FFmpeg failure — warn and keep original video"
```

---

## Acceptance Criteria Verification

After both tasks:

- [ ] `python3 -m pytest tests/test_wow_effects.py -v` — all pass
- [ ] `python3 -m pytest tests/ -v 2>&1 | grep -E 'FAILED|ERROR'` — empty output
- [ ] `ENABLE_ZOOMPAN = False` in `wow_effects.py` (grep to verify)
- [ ] `apply_wow_effects` no longer raises on FFmpeg error (confirmed by `test_does_not_raise_on_ffmpeg_failure`)
- [ ] `print("WARN:` appears in `apply_wow_effects` exception handler
