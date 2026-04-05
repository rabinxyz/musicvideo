# Fix Reels Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two remaining bugs in social reel assembly: Ken Burns incorrectly applied to .mp4 video files, and find_nearest_scene returning None instead of a fallback asset.

**Architecture:** Two targeted fixes in existing files — assembler's `_load_scene_clip` needs to skip Ken Burns for ALL .mp4 files (not just animated), and `find_nearest_scene` in musicvid.py needs a first-available-asset fallback when no time-overlap match exists.

**Tech Stack:** Python, MoviePy 2.x, unittest.mock

---

## Triage Notes

IDEA.md describes 4 problems. After code analysis:
- **Problem 1** (social_clips.json caching): Already implemented at `musicvid/musicvid.py:741-748`
- **Problem 2** (imread on .mp4): Already fixed — `_load_scene_clip` routes by file extension
- **Problem 3** (find_nearest_scene returns None): **Needs fix** — add first-available fallback
- **Problem 4** (Ken Burns on .mp4 video): **Bug exists** — line 375 only skips Ken Burns when `animate=True`

---

### Task 1: Fix Ken Burns skip for ALL .mp4 video files

**Files:**
- Modify: `musicvid/pipeline/assembler.py:374-378` (the Ken Burns skip condition in `_load_scene_clip`)
- Modify: `tests/test_assembler.py:671-694` (update existing test that asserts wrong behavior)
- Test: `tests/test_assembler.py`

**Context:** Currently `_load_scene_clip` at line 375 checks `scene.get("animate", False) and path.suffix.lower() == ".mp4"` to skip Ken Burns. This means non-animated .mp4 files (e.g., Pexels stock video) still get Ken Burns applied, which is wrong — video already has motion.

- [ ] **Step 1: Update the existing test to expect NO Ken Burns on non-animated .mp4**

In `tests/test_assembler.py`, the test `test_non_animated_mp4_uses_ken_burns` at line 671 currently asserts that Ken Burns IS applied. Change it to assert Ken Burns is NOT applied (just resize).

```python
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    def test_non_animated_mp4_skips_ken_burns(self, mock_vfc, tmp_path):
        """Non-animated .mp4 (stock video) should skip Ken Burns — video already has motion."""
        from musicvid.pipeline.assembler import _load_scene_clip

        fake_mp4 = tmp_path / "stock.mp4"
        fake_mp4.write_bytes(b"fake video")

        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_vfc.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.cropped.return_value = mock_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in", "animate": False}
        _load_scene_clip(str(fake_mp4), scene, (1920, 1080))

        # Ken Burns (transform) should NOT be called — .mp4 already has motion
        mock_clip.transform.assert_not_called()
        # Should just resize
        mock_clip.resized.assert_called()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_assembler.py::TestLoadSceneClip::test_non_animated_mp4_skips_ken_burns -v`
Expected: FAIL — transform IS currently called on non-animated .mp4

- [ ] **Step 3: Fix the condition in `_load_scene_clip`**

In `musicvid/pipeline/assembler.py`, change lines 374-378 from:

```python
    # Animated clips from Runway Gen-4: resize only, skip Ken Burns
    if scene.get("animate", False) and path.suffix.lower() == ".mp4":
        return clip.resized(new_size=target_size)

    return _create_ken_burns_clip(clip, duration, scene.get("motion", "static"), target_size)
```

To:

```python
    # Video files (.mp4): resize only, skip Ken Burns — video already has motion
    if path.suffix.lower() == ".mp4":
        return clip.resized(new_size=target_size)

    return _create_ken_burns_clip(clip, duration, scene.get("motion", "static"), target_size)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_assembler.py::TestLoadSceneClip::test_non_animated_mp4_skips_ken_burns -v`
Expected: PASS

- [ ] **Step 5: Also verify the animated .mp4 test still passes**

Run: `python3 -m pytest tests/test_assembler.py::TestLoadSceneClip -v`
Expected: ALL PASS (animated .mp4 test at line ~650 should still pass since .mp4 check is now broader)

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "fix: skip Ken Burns for all .mp4 video files, not just animated"
```

---

### Task 2: Make find_nearest_scene never return None

**Files:**
- Modify: `musicvid/musicvid.py:117-146` (the `find_nearest_scene` function)
- Modify: `tests/test_cli.py:2959-2966` (update the "returns None" test)
- Test: `tests/test_cli.py`

**Context:** `find_nearest_scene` currently returns None when all manifest entries have None/missing video_path. The spec says it should NEVER return None — always fall back to the first available asset. `_validate_clip_manifest` drops scenes when no fallback is found, which can leave reels with missing scenes.

- [ ] **Step 1: Update the test for "no valid entries" to expect first-available fallback**

In `tests/test_cli.py`, the test `test_returns_none_when_no_valid_entries` at line 2959 currently asserts `result is None`. Change it to test the new fallback behavior, and add a test for "truly empty manifest":

```python
    def test_returns_first_available_when_no_overlap_and_no_close_match(self):
        """When no entry has a valid file on disk, return the first entry with a non-None path."""
        from musicvid.musicvid import find_nearest_scene
        manifest = [
            {"scene_index": 0, "start": 0.0, "end": 10.0, "video_path": None},
            {"scene_index": 1, "start": 10.0, "end": 20.0, "video_path": "/fake/b.jpg"},
        ]
        with patch("os.path.exists", return_value=False):
            result = find_nearest_scene(0.0, 10.0, manifest)
        # Falls back to first entry with non-None video_path (ignoring exists check)
        assert result is not None
        assert result["scene_index"] == 1

    def test_returns_none_only_when_all_paths_none(self):
        """Returns None only when every entry has video_path=None."""
        from musicvid.musicvid import find_nearest_scene
        manifest = [
            {"scene_index": 0, "start": 0.0, "end": 10.0, "video_path": None},
        ]
        with patch("os.path.exists", return_value=False):
            result = find_nearest_scene(0.0, 10.0, manifest)
        assert result is None
```

- [ ] **Step 2: Run the tests to verify the first one fails**

Run: `python3 -m pytest tests/test_cli.py::TestFindNearestScene -v`
Expected: `test_returns_first_available_when_no_overlap_and_no_close_match` FAILS (currently returns None for non-existent paths), `test_returns_none_only_when_all_paths_none` PASSES

- [ ] **Step 3: Add first-available fallback to find_nearest_scene**

In `musicvid/musicvid.py`, modify `find_nearest_scene` (lines 117-146). Add a last-resort fallback before returning None that picks the first entry with a non-None `video_path` (even if file doesn't exist on disk yet):

```python
def find_nearest_scene(start, end, fetch_manifest):
    """Return the fetch_manifest entry whose time range best overlaps [start, end].

    Skips entries where video_path is None or the file doesn't exist.
    When no overlap exists, falls back to the entry whose scene center is closest
    to the clip center. As a last resort, returns the first entry with a non-None
    video_path (ignoring file existence). Returns None only if every entry has
    video_path=None.
    """
    clip_center = (start + end) / 2
    best = None
    best_overlap = -1
    best_center_dist = float("inf")

    for entry in fetch_manifest:
        if not entry.get("video_path"):
            continue
        if not os.path.exists(entry["video_path"]):
            continue
        scene_start = entry.get("start", 0)
        scene_end = entry.get("end", 0)
        overlap = min(end, scene_end) - max(start, scene_start)
        if overlap > best_overlap:
            best_overlap = overlap
            best = entry
        elif overlap <= 0 and best_overlap <= 0:
            center_dist = abs((scene_start + scene_end) / 2 - clip_center)
            if center_dist < best_center_dist:
                best_center_dist = center_dist
                best = entry

    if best is not None:
        return best

    # Last resort: first entry with non-None video_path (file may not exist yet)
    for entry in fetch_manifest:
        if entry.get("video_path"):
            return entry

    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py::TestFindNearestScene -v`
Expected: ALL PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "fix: find_nearest_scene falls back to first available asset instead of None"
```
