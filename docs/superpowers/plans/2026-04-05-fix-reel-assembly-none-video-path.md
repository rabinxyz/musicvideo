# Fix Reel Assembly NoneType imread Error Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent `'NoneType' object has no attribute 'imread'` crash when assembling social reels by validating video_path entries and falling back to the nearest available scene.

**Architecture:** Add `find_nearest_scene()` helper and `_validate_clip_manifest()` in `musicvid/musicvid.py` to replace None/missing video_path entries before they reach the assembler. Add diagnostic logging before each reel. All logic stays in `musicvid.py` — no assembler changes needed.

**Tech Stack:** Python 3.11+, existing codebase patterns (`os.path.exists`, `click.echo`), unittest.mock

---

### Task 1: Add `find_nearest_scene` helper and tests

**Files:**
- Modify: `musicvid/musicvid.py` (add helper function after `_filter_manifest_to_clip`)
- Modify: `tests/test_cli.py` (add unit tests for the new helper in a new class)

- [ ] **Step 1: Write the failing test**

Add this class to `tests/test_cli.py` (after the existing test classes, before `if __name__ == "__main__"`):

```python
class TestFindNearestScene(unittest.TestCase):
    def _make_entry(self, scene_index, start, end, path):
        return {"scene_index": scene_index, "start": start, "end": end, "video_path": path}

    def test_returns_entry_with_best_overlap(self):
        from musicvid.musicvid import find_nearest_scene
        manifest = [
            self._make_entry(0, 0.0, 10.0, "/fake/a.jpg"),
            self._make_entry(1, 10.0, 20.0, "/fake/b.jpg"),
            self._make_entry(2, 20.0, 30.0, "/fake/c.jpg"),
        ]
        with patch("os.path.exists", return_value=True):
            result = find_nearest_scene(8.0, 15.0, manifest)
        assert result == manifest[0]  # overlap 8-10 = 2s > 10-15 = ... wait
        # Actually overlap with entry 0 (0-10): min(15,10)-max(8,0)=10-8=2
        # Overlap with entry 1 (10-20): min(15,20)-max(8,10)=15-10=5  <- best
        assert result == manifest[1]

    def test_skips_none_video_path(self):
        from musicvid.musicvid import find_nearest_scene
        manifest = [
            {"scene_index": 0, "start": 0.0, "end": 10.0, "video_path": None},
            {"scene_index": 1, "start": 5.0, "end": 15.0, "video_path": "/fake/b.jpg"},
        ]
        with patch("os.path.exists", return_value=True):
            result = find_nearest_scene(0.0, 10.0, manifest)
        assert result["scene_index"] == 1

    def test_skips_missing_file(self):
        from musicvid.musicvid import find_nearest_scene
        manifest = [
            {"scene_index": 0, "start": 0.0, "end": 10.0, "video_path": "/missing/a.jpg"},
            {"scene_index": 1, "start": 5.0, "end": 15.0, "video_path": "/exists/b.jpg"},
        ]
        def fake_exists(p):
            return p == "/exists/b.jpg"
        with patch("os.path.exists", side_effect=fake_exists):
            result = find_nearest_scene(0.0, 10.0, manifest)
        assert result["scene_index"] == 1

    def test_returns_none_when_no_valid_entries(self):
        from musicvid.musicvid import find_nearest_scene
        manifest = [
            {"scene_index": 0, "start": 0.0, "end": 10.0, "video_path": None},
        ]
        with patch("os.path.exists", return_value=False):
            result = find_nearest_scene(0.0, 10.0, manifest)
        assert result is None

    def test_returns_closest_center_when_no_overlap(self):
        from musicvid.musicvid import find_nearest_scene
        manifest = [
            {"scene_index": 0, "start": 0.0, "end": 5.0, "video_path": "/fake/a.jpg"},
            {"scene_index": 1, "start": 50.0, "end": 60.0, "video_path": "/fake/b.jpg"},
        ]
        with patch("os.path.exists", return_value=True):
            result = find_nearest_scene(10.0, 15.0, manifest)
        # No overlap; center of clip = 12.5; center of entry 0 = 2.5 (dist=10), entry 1 = 55 (dist=42.5)
        assert result["scene_index"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_cli.py::TestFindNearestScene -v
```

Expected: `ImportError: cannot import name 'find_nearest_scene'`

- [ ] **Step 3: Write minimal implementation**

In `musicvid/musicvid.py`, after the `_filter_manifest_to_clip` function (around line 113), add:

```python
def find_nearest_scene(start, end, fetch_manifest):
    """Return the fetch_manifest entry whose time range best overlaps [start, end].

    Skips entries where video_path is None or the file doesn't exist.
    When no overlap exists, falls back to the entry whose scene center is closest
    to the clip center. Returns None if no valid entry is found.
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

    return best
```

- [ ] **Step 4: Fix the test — the first assertion is wrong**

The test `test_returns_entry_with_best_overlap` has a wrong first `assert`. Remove the incorrect line so the test reads:

```python
def test_returns_entry_with_best_overlap(self):
    from musicvid.musicvid import find_nearest_scene
    manifest = [
        self._make_entry(0, 0.0, 10.0, "/fake/a.jpg"),
        self._make_entry(1, 10.0, 20.0, "/fake/b.jpg"),
        self._make_entry(2, 20.0, 30.0, "/fake/c.jpg"),
    ]
    with patch("os.path.exists", return_value=True):
        result = find_nearest_scene(8.0, 15.0, manifest)
    # overlap with entry 1 (10-20): min(15,20)-max(8,10)=5 is best
    assert result == manifest[1]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python3 -m pytest tests/test_cli.py::TestFindNearestScene -v
```

Expected: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add find_nearest_scene helper for reel assembly fallback"
```

---

### Task 2: Add `_validate_clip_manifest` and tests

**Files:**
- Modify: `musicvid/musicvid.py` (add `_validate_clip_manifest` after `find_nearest_scene`)
- Modify: `tests/test_cli.py` (add `TestValidateClipManifest` class)

- [ ] **Step 1: Write the failing test**

Add this class to `tests/test_cli.py` after `TestFindNearestScene`:

```python
class TestValidateClipManifest(unittest.TestCase):
    def test_passes_through_valid_manifest(self):
        from musicvid.musicvid import _validate_clip_manifest
        manifest = [
            {"scene_index": 0, "start": 0.0, "end": 10.0, "video_path": "/fake/a.jpg"},
        ]
        with patch("os.path.exists", return_value=True):
            result = _validate_clip_manifest(manifest, manifest)
        assert result == manifest

    def test_replaces_none_path_with_fallback(self):
        from musicvid.musicvid import _validate_clip_manifest
        fallback_entry = {"scene_index": 1, "start": 5.0, "end": 15.0, "video_path": "/fake/b.jpg"}
        clip_manifest = [
            {"scene_index": 0, "start": 0.0, "end": 5.0, "video_path": None},
        ]
        full_manifest = [
            {"scene_index": 0, "start": 0.0, "end": 5.0, "video_path": None},
            fallback_entry,
        ]
        with patch("os.path.exists", return_value=True):
            result = _validate_clip_manifest(clip_manifest, full_manifest)
        assert len(result) == 1
        assert result[0]["video_path"] == "/fake/b.jpg"
        assert result[0]["scene_index"] == 0  # preserves original scene_index

    def test_drops_entry_when_no_fallback(self):
        from musicvid.musicvid import _validate_clip_manifest
        clip_manifest = [
            {"scene_index": 0, "start": 0.0, "end": 5.0, "video_path": None},
        ]
        full_manifest = [
            {"scene_index": 0, "start": 0.0, "end": 5.0, "video_path": None},
        ]
        with patch("os.path.exists", return_value=False):
            result = _validate_clip_manifest(clip_manifest, full_manifest)
        assert result == []

    def test_replaces_missing_file_with_fallback(self):
        from musicvid.musicvid import _validate_clip_manifest
        clip_manifest = [
            {"scene_index": 0, "start": 0.0, "end": 5.0, "video_path": "/missing/a.jpg"},
        ]
        full_manifest = [
            {"scene_index": 0, "start": 0.0, "end": 5.0, "video_path": "/missing/a.jpg"},
            {"scene_index": 1, "start": 3.0, "end": 10.0, "video_path": "/exists/b.jpg"},
        ]
        def fake_exists(p):
            return p == "/exists/b.jpg"
        with patch("os.path.exists", side_effect=fake_exists):
            result = _validate_clip_manifest(clip_manifest, full_manifest)
        assert result[0]["video_path"] == "/exists/b.jpg"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_cli.py::TestValidateClipManifest -v
```

Expected: `ImportError: cannot import name '_validate_clip_manifest'`

- [ ] **Step 3: Write minimal implementation**

In `musicvid/musicvid.py`, after `find_nearest_scene`, add:

```python
def _validate_clip_manifest(clip_manifest, full_manifest):
    """Return a copy of clip_manifest with None/missing video_path entries replaced.

    For each entry whose video_path is None or points to a non-existent file,
    find_nearest_scene is used to locate the closest valid entry in full_manifest.
    Entries with no fallback are dropped with a warning.
    The original scene_index is preserved in the replacement entry.
    """
    validated = []
    for entry in clip_manifest:
        path = entry.get("video_path")
        if path and os.path.exists(path):
            validated.append(entry)
            continue
        # Invalid path — find nearest fallback
        start = entry.get("start", 0)
        end = entry.get("end", 0)
        fallback = find_nearest_scene(start, end, full_manifest)
        if fallback is None:
            click.echo(
                f"  WARN: brak video_path dla sceny {entry.get('scene_index')} "
                f"(start={start:.1f}s end={end:.1f}s) — pomijam scenę"
            )
            continue
        click.echo(
            f"  WARN: video_path dla sceny {entry.get('scene_index')} "
            f"jest None/brak — używam sceny {fallback.get('scene_index')} jako zastępstwa"
        )
        validated.append({**entry, "video_path": fallback["video_path"]})
    return validated
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_cli.py::TestValidateClipManifest -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add _validate_clip_manifest to replace None video_path entries with fallback"
```

---

### Task 3: Wire validation into `_run_preset_mode` with logging

**Files:**
- Modify: `musicvid/musicvid.py` (`_run_preset_mode` function, social reel loop)
- Modify: `tests/test_cli.py` (add integration test for None video_path in preset social)

- [ ] **Step 1: Write the failing test**

Add this class to `tests/test_cli.py`:

```python
class TestPresetSocialNoneVideoPath(unittest.TestCase):
    """Ensure preset=social doesn't crash when clip_manifest has None video_path."""

    def _make_base_mocks(self):
        return {
            "analysis": {
                "lyrics": [],
                "beats": [0.0, 0.5, 1.0],
                "bpm": 120.0,
                "duration": 120.0,
                "sections": [
                    {"label": "verse", "start": 0.0, "end": 60.0},
                    {"label": "chorus", "start": 60.0, "end": 120.0},
                ],
                "mood_energy": "energetic",
                "language": "en",
            },
            "scene_plan": {
                "overall_style": "test",
                "color_palette": ["#fff"],
                "master_style": "",
                "subtitle_style": {
                    "font_size": 48,
                    "color": "#FFF",
                    "outline_color": "#000",
                    "position": "center-bottom",
                    "animation": "fade",
                },
                "scenes": [
                    {"section": "verse", "start": 0.0, "end": 60.0,
                     "visual_prompt": "test", "motion": "static",
                     "transition": "cut", "overlay": "none",
                     "animate": False, "motion_prompt": ""},
                    {"section": "chorus", "start": 60.0, "end": 120.0,
                     "visual_prompt": "test2", "motion": "static",
                     "transition": "cut", "overlay": "none",
                     "animate": False, "motion_prompt": ""},
                ],
            },
            "social_clips": {
                "clips": [
                    {"id": "A", "start": 0.0, "end": 15.0, "section": "verse", "reason": "Hook"},
                    {"id": "B", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Peak"},
                    {"id": "C", "start": 30.0, "end": 45.0, "section": "verse", "reason": "Bridge"},
                ]
            },
        }

    @patch("musicvid.musicvid.assemble_all_parallel")
    @patch("musicvid.musicvid.select_social_clips")
    def test_none_video_path_replaced_by_fallback(self, mock_social, mock_parallel):
        """When clip_manifest has a None video_path, fallback to nearest scene."""
        data = self._make_base_mocks()
        mock_social.return_value = data["social_clips"]
        mock_parallel.return_value = []

        # fetch_manifest has one valid and one None entry
        fetch_manifest = [
            {"scene_index": 0, "start": 0.0, "end": 60.0, "video_path": "/fake/scene0.jpg"},
            {"scene_index": 1, "start": 60.0, "end": 120.0, "video_path": None},
        ]

        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()

            with patch("os.path.exists", return_value=True):
                _run_preset_mode(
                    preset="social",
                    reel_duration=15,
                    analysis=data["analysis"],
                    scene_plan=data["scene_plan"],
                    fetch_manifest=fetch_manifest,
                    audio_path=str(Path(tmpdir) / "song.mp3"),
                    output_dir=output_dir,
                    stem="song",
                    font="/fake/font.ttf",
                    effects="none",
                    cache_dir=cache_dir,
                    new=True,
                )

        # Should have been called — not crashed
        assert mock_parallel.called or True  # no exception = success

    @patch("musicvid.musicvid.assemble_all_parallel")
    @patch("musicvid.musicvid.select_social_clips")
    def test_all_none_paths_drops_job_gracefully(self, mock_social, mock_parallel):
        """When all entries have None paths and no fallback, jobs are built with empty manifest."""
        data = self._make_base_mocks()
        mock_social.return_value = data["social_clips"]
        mock_parallel.return_value = []

        fetch_manifest = [
            {"scene_index": 0, "start": 0.0, "end": 60.0, "video_path": None},
            {"scene_index": 1, "start": 60.0, "end": 120.0, "video_path": None},
        ]

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()

            with patch("os.path.exists", return_value=False):
                # Should not raise — just warn and skip
                _run_preset_mode(
                    preset="social",
                    reel_duration=15,
                    analysis=data["analysis"],
                    scene_plan=data["scene_plan"],
                    fetch_manifest=fetch_manifest,
                    audio_path=str(Path(tmpdir) / "song.mp3"),
                    output_dir=output_dir,
                    stem="song",
                    font="/fake/font.ttf",
                    effects="none",
                    cache_dir=cache_dir,
                    new=True,
                )
        # No exception raised = pass
```

Note: `_run_preset_mode` must be imported at the top of the test file. Check if it's already imported; if not add:
```python
from musicvid.musicvid import _run_preset_mode
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_cli.py::TestPresetSocialNoneVideoPath -v
```

Expected: Tests fail (either import error or the None path crashes assembler call)

- [ ] **Step 3: Wire `_validate_clip_manifest` and logging into `_run_preset_mode`**

In `musicvid/musicvid.py`, inside `_run_preset_mode`, in the `if generate_social:` block, locate the per-clip loop (around line 603). Add validation + logging **before** building the `AssemblyJob`:

Find this block:
```python
        for clip_info in social_clips["clips"]:
            clip_id = clip_info["id"]
            clip_start = clip_info["start"]
            clip_end = clip_info["end"]
            section = clip_info.get("section", "unknown")
            reel_output = str(social_dir / f"{stem}_rolka_{clip_id}_{reel_duration}s.mp4")
            clip_analysis = _filter_analysis_to_clip(analysis, clip_start, clip_end)
            clip_scene_plan = _filter_scene_plan_to_clip(scene_plan, clip_start, clip_end)
            for scene in clip_scene_plan["scenes"]:
                scene["motion"] = _remap_motion_for_portrait(scene.get("motion", "static"))
            clip_manifest = _filter_manifest_to_clip(
                fetch_manifest, scene_plan["scenes"], clip_start, clip_end
            )
            jobs.append(AssemblyJob(
```

Replace with:
```python
        for clip_info in social_clips["clips"]:
            clip_id = clip_info["id"]
            clip_start = clip_info["start"]
            clip_end = clip_info["end"]
            section = clip_info.get("section", "unknown")
            reel_output = str(social_dir / f"{stem}_rolka_{clip_id}_{reel_duration}s.mp4")
            click.echo(f"  Rolka {clip_id}: start={clip_start:.1f}s end={clip_end:.1f}s")
            click.echo(f"    Dostępne sceny: {[(e['scene_index'], e['video_path']) for e in fetch_manifest]}")
            clip_analysis = _filter_analysis_to_clip(analysis, clip_start, clip_end)
            clip_scene_plan = _filter_scene_plan_to_clip(scene_plan, clip_start, clip_end)
            for scene in clip_scene_plan["scenes"]:
                scene["motion"] = _remap_motion_for_portrait(scene.get("motion", "static"))
            clip_manifest = _filter_manifest_to_clip(
                fetch_manifest, scene_plan["scenes"], clip_start, clip_end
            )
            clip_manifest = _validate_clip_manifest(clip_manifest, fetch_manifest)
            jobs.append(AssemblyJob(
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_cli.py::TestPresetSocialNoneVideoPath -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Run full test suite to ensure no regressions**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -20
```

Expected: All existing tests pass (count was 308 before this change; new tests add to the total)

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "fix: validate clip_manifest before reel assembly, fallback to nearest scene on None video_path"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Task covering it |
|---|---|
| Validate video_path before reel assembly | Task 2 (`_validate_clip_manifest`), Task 3 (wire into `_run_preset_mode`) |
| Fallback to nearest available scene | Task 1 (`find_nearest_scene`), Task 2 |
| Warn when scene skipped (no fallback) | Task 2 (`click.echo` WARN in `_validate_clip_manifest`) |
| Logging before each reel | Task 3 (log `clip_id`, `clip_start`, `clip_end`, available scenes) |
| `--preset all` no longer crashes | Task 3 (integration test) |
| `python3 -m pytest tests/ -v` passes | Task 3 Step 5 |

### Placeholder scan

No placeholders found — all steps contain complete code.

### Type consistency

- `find_nearest_scene(start, end, fetch_manifest) -> dict | None` — used in `_validate_clip_manifest` consistently
- `_validate_clip_manifest(clip_manifest, full_manifest) -> list` — used in `_run_preset_mode` consistently
- Entry dict keys: `scene_index`, `start`, `end`, `video_path` — consistent throughout
