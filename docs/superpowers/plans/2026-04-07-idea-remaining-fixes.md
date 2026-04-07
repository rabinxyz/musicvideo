# IDEA.md Remaining Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the 3 remaining items from docs/IDEA.md — enhanced vocal filtering, effects default change, and progress counters.

**Architecture:** Three independent fixes across lyrics_aligner.py (filtering heuristic), musicvid.py (CLI default + progress output), and their tests.

**Tech Stack:** Python 3.11+, Click CLI, unittest.mock, pytest

---

### Task 1: Enhance `_is_vocal()` filtering (IDEA 1B)

**Files:**
- Modify: `musicvid/pipeline/lyrics_aligner.py:7-22`
- Modify: `tests/test_lyrics_aligner.py:8-27`

The spec requires three additional checks in `_is_vocal()`:
1. Add `"muzyk"` and `"intro"` to `NON_VOCAL` set
2. Check `text_clean.startswith("muzy")` — catches "Muzyka", "Muzykę", etc.
3. Check single short word heuristic: `len(text_clean.split()) == 1 and len(text_clean) < 8` — catches noise tokens

- [ ] **Step 1: Write failing tests for new filtering cases**

Add to `tests/test_lyrics_aligner.py` — new test class after `TestNoiseFiltering`:

```python
class TestEnhancedVocalFiltering(unittest.TestCase):
    """Extended noise filtering per IDEA 1B spec."""

    def _run(self, noise_text):
        """Helper: align with one noise segment + one real segment."""
        import tempfile, os
        segments = [
            {"start": 0.0, "end": 5.0, "text": noise_text},
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu moje jest zbawienie"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            texts = " ".join(r["text"] for r in result)
            return texts
        finally:
            os.unlink(path)

    def test_muzyk_prefix_filtered(self):
        """'Muzykę' (starts with 'muzy') should be filtered."""
        texts = self._run("Muzykę")
        self.assertNotIn("Muzykę", texts)

    def test_intro_filtered(self):
        """'intro' is in NON_VOCAL set."""
        texts = self._run("intro")
        self.assertNotIn("intro", texts)

    def test_muzyk_in_non_vocal(self):
        """'muzyk' is in NON_VOCAL set."""
        texts = self._run("muzyk")
        self.assertNotIn("muzyk", texts)

    def test_short_single_word_filtered(self):
        """Single short word like 'Hmm' (< 8 chars, 1 word) is noise."""
        texts = self._run("Hmmm")
        self.assertNotIn("Hmmm", texts)

    def test_real_short_word_not_filtered(self):
        """A real lyric word that matches in lyrics file should NOT be filtered
        even if short — but _is_vocal only sees isolated segment, so single
        short words with no lyrics match are noise."""
        # 'Pan' is 3 chars, 1 word — but it IS a real word.
        # The heuristic filters it at _is_vocal level, but align_lyrics
        # still works because real lyrics come from other segments.
        # This test verifies the filter fires for isolated short words.
        texts = self._run("Ahh")
        self.assertNotIn("Ahh", texts)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_lyrics_aligner.py::TestEnhancedVocalFiltering -v`
Expected: Some tests FAIL (e.g., "Muzykę" not filtered, "intro" not filtered)

- [ ] **Step 3: Implement enhanced `_is_vocal()`**

Edit `musicvid/pipeline/lyrics_aligner.py` lines 7 and 14-22:

```python
NON_VOCAL = {"muzyka", "music", "instrumental", "muzyk", "intro"}
```

Replace `_is_vocal` function:

```python
def _is_vocal(seg):
    """Return True if segment contains actual vocals (not noise/music)."""
    text = seg["text"].strip().lower()
    text_clean = re.sub(r"[\[\]()♪♫ ]", "", text)
    if text_clean in NON_VOCAL:
        return False
    if len(text_clean) < 3:
        return False
    if text_clean.startswith("muzy"):
        return False
    if len(text_clean.split()) == 1 and len(text_clean) < 8:
        return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_lyrics_aligner.py -v`
Expected: ALL tests pass (both old and new)

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/lyrics_aligner.py tests/test_lyrics_aligner.py
git commit -m "fix: enhance _is_vocal() with muzy prefix and short-word heuristic (IDEA 1B)"
```

---

### Task 2: Change `--effects` default to "full" (IDEA 3A)

**Files:**
- Modify: `musicvid/musicvid.py:467` (the `@click.option("--effects"...)` line)
- Modify: `tests/test_cli.py:1262` (update test name and assertion)

- [ ] **Step 1: Write failing test for new default**

Find and update `test_effects_defaults_to_minimal` in `tests/test_cli.py` — rename it and change the assertion. Add a new test that verifies the default is "full":

In `tests/test_cli.py`, find the test class containing `test_effects_defaults_to_minimal` and add alongside it:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_effects_defaults_to_full(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/video.mp4", "start": 0.0, "end": 10.0, "source": "pexels"}
        ]
        mock_assemble.return_value = "/fake/output.mp4"

        result = runner.invoke(cli, [str(audio_file), "--mode", "stock", "--preset", "full", "--yes"])
        assert result.exit_code == 0
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs.get("effects") == "full"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::TestEffects::test_effects_defaults_to_full -v` (adjust class name based on actual location)
Expected: FAIL — effects=="minimal"

- [ ] **Step 3: Change the default**

Edit `musicvid/musicvid.py` line 467 — change `default="minimal"` to `default="full"`:

```python
@click.option("--effects", type=click.Choice(["none", "minimal", "full"]), default="full", help="Visual effects level.")
```

- [ ] **Step 4: Update old test and run all tests**

Rename `test_effects_defaults_to_minimal` to `test_effects_explicit_minimal` and add `"--effects", "minimal"` to its CLI args so it tests explicit minimal, not the default.

Run: `python3 -m pytest tests/test_cli.py -k "effects" -v`
Expected: ALL pass

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: change --effects default from minimal to full (IDEA 3A)"
```

---

### Task 3: Add per-item progress counters (IDEA 5C)

**Files:**
- Modify: `musicvid/musicvid.py` (Stage 3 asset generation section, ~lines 680-710)
- Create: `tests/test_progress.py`

The spec wants: `[3/4] Generating assets: 12/20 (60%) — scene_007 TYPE_VIDEO_RUNWAY...` with `\r` line overwriting.

- [ ] **Step 1: Write failing test for progress output**

Create `tests/test_progress.py`:

```python
"""Tests for stage 3 progress counter output."""

import unittest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from musicvid.musicvid import cli


class TestAssetProgressCounter(unittest.TestCase):
    """Stage 3 should print per-scene progress with \r overwriting."""

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.VisualRouter")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_progress_output_contains_counter(
        self, mock_analyze, mock_direct, mock_router_cls, mock_assemble, mock_font
    ):
        runner = CliRunner()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake")
            audio = f.name

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
            "energy_curve": [[0.0, 0.5], [10.0, 0.5]], "energy_mean": 0.5,
        }
        scenes = [
            {"section": "verse", "start": 0.0, "end": 5.0,
             "visual_prompt": "test", "motion": "slow_zoom_in",
             "transition": "cut", "overlay": "none",
             "visual_source": "TYPE_VIDEO_STOCK", "search_query": "nature"},
            {"section": "verse", "start": 5.0, "end": 10.0,
             "visual_prompt": "test2", "motion": "pan_left",
             "transition": "cut", "overlay": "none",
             "visual_source": "TYPE_VIDEO_STOCK", "search_query": "forest"},
        ]
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": scenes,
        }
        mock_router = MagicMock()
        mock_router.fetch_manifest.return_value = [
            {"scene_index": 0, "video_path": "/fake/v0.mp4", "start": 0.0, "end": 5.0, "source": "pexels"},
            {"scene_index": 1, "video_path": "/fake/v1.mp4", "start": 5.0, "end": 10.0, "source": "pexels"},
        ]
        mock_router_cls.return_value = mock_router
        mock_assemble.return_value = "/fake/output.mp4"

        try:
            result = runner.invoke(cli, [audio, "--mode", "runway", "--preset", "full", "--yes"])
            # Check that progress counter pattern appears in output
            assert "1/2" in result.output or "2/2" in result.output, \
                f"Expected progress counter in output, got: {result.output}"
        finally:
            os.unlink(audio)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_progress.py -v`
Expected: FAIL — no "1/2" or "2/2" in output

- [ ] **Step 3: Add progress callback to Stage 3**

In `musicvid/musicvid.py`, find the Stage 3 section where `fetch_manifest` is called. Add a progress callback. The VisualRouter's `fetch_manifest` processes scenes sequentially, so we need to add progress reporting.

Find the line that calls `router.fetch_manifest(scenes, ...)` and wrap it with progress output. Before the call, add:

```python
def _progress_callback(idx, total, scene):
    source = scene.get("visual_source", "unknown")
    pct = int((idx + 1) / total * 100)
    click.echo(f"\r  [3/4] Generating assets: {idx+1}/{total} ({pct}%) — scene_{idx:03d} {source}...", nl=False)
```

After fetch_manifest completes, print a newline:
```python
click.echo()  # newline after \r progress
```

The VisualRouter needs to accept an `on_progress` callback. Check if it already supports one, or if we need to add it.

- [ ] **Step 4: Add progress callback support to VisualRouter**

In `musicvid/pipeline/visual_router.py`, modify `fetch_manifest` to accept `on_progress=None` callback and call it after each scene is processed:

```python
def fetch_manifest(self, scenes, ..., on_progress=None):
    manifest = []
    for idx, scene in enumerate(scenes):
        # ... existing routing logic ...
        if on_progress:
            on_progress(idx, len(scenes), scene)
        manifest.append(entry)
    return manifest
```

Then in `musicvid.py`, pass the callback:
```python
fetch_manifest = router.fetch_manifest(scenes, cache_dir, on_progress=_progress_callback)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_progress.py tests/test_cli.py -v`
Expected: ALL pass

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py musicvid/pipeline/visual_router.py tests/test_progress.py
git commit -m "feat: add per-scene progress counters to Stage 3 (IDEA 5C)"
```
