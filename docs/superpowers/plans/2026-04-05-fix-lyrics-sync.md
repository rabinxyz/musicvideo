# Fix Lyrics Sync — Deterministic Whisper+Lyrics Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `merge_whisper_with_lyrics_file()` to `lyrics_parser.py` that deterministically aligns correct lyrics text from a .txt file with timing from Whisper segments, and wire it into the CLI in place of the Claude API approach.

**Architecture:** Proportional grouping algorithm — maps N Whisper segments to M lyrics lines by computing proportional index ranges; handles 3 cases: N==M (1:1), N>M (group segments), N<M (split segment time). Timing corrections (min gap 0.15s, min/max duration, -0.05s pre-display offset) applied after mapping. The new function replaces `align_with_claude` in the CLI lyrics flow.

**Tech Stack:** Python 3.11+, pytest, existing `musicvid/pipeline/lyrics_parser.py` and `musicvid/musicvid.py`

---

### Task 1: Implement `merge_whisper_with_lyrics_file()` in lyrics_parser.py

**Files:**
- Modify: `musicvid/pipeline/lyrics_parser.py`
- Test: `tests/test_lyrics_parser.py`

- [ ] **Step 1: Write the failing tests**

Add the following class to `tests/test_lyrics_parser.py` (after existing test classes):

```python
from musicvid.pipeline.lyrics_parser import merge_whisper_with_lyrics_file


class TestMergeWhisperWithLyricsFile:
    """Tests for deterministic Whisper+lyrics alignment."""

    def _make_segments(self, count, start=0.0, duration=2.0):
        """Create N evenly-spaced whisper segments."""
        return [
            {"start": start + i * duration, "end": start + i * duration + duration - 0.2, "text": f"seg{i}"}
            for i in range(count)
        ]

    def _make_lines(self, count):
        return [f"Line {i+1}" for i in range(count)]

    # test_case_1: N_segments == N_lines (8 and 8)
    def test_equal_segments_and_lines_maps_one_to_one(self):
        segments = self._make_segments(8)
        lines = self._make_lines(8)
        result = merge_whisper_with_lyrics_file(segments, lines, 20.0)
        assert len(result) == 8
        assert result[3]["text"] == "Line 4"
        assert result[3]["start"] == pytest.approx(segments[3]["start"] - 0.05, abs=0.01)

    # test_case_2: N_segments > N_lines (12 segments, 6 lines)
    def test_more_segments_than_lines_groups_proportionally(self):
        segments = self._make_segments(12)
        lines = self._make_lines(6)
        result = merge_whisper_with_lyrics_file(segments, lines, 30.0)
        assert len(result) == 6
        assert result[0]["start"] == pytest.approx(segments[0]["start"] - 0.05, abs=0.01)
        assert result[5]["end"] == pytest.approx(segments[11]["end"], abs=0.01)
        for item in result:
            assert item["text"] in lines

    # test_case_3: N_segments < N_lines (4 segments, 12 lines)
    def test_fewer_segments_than_lines_splits_time(self):
        segments = self._make_segments(4, duration=3.0)
        lines = self._make_lines(12)
        result = merge_whisper_with_lyrics_file(segments, lines, 12.0)
        assert len(result) == 12
        # Each line must fall within its segment's time window
        for item in result:
            assert item["start"] >= 0.0
            assert item["end"] > item["start"]

    # test_case_4: timing corrections applied
    def test_no_overlap_between_subtitles(self):
        # Create tightly-spaced segments that would cause overlap
        segments = [
            {"start": 0.0, "end": 5.0, "text": "seg0"},
            {"start": 5.0, "end": 10.0, "text": "seg1"},
        ]
        lines = ["Line one", "Line two"]
        result = merge_whisper_with_lyrics_file(segments, lines, 10.0)
        # gap between consecutive subtitles must be >= 0.15s
        for i in range(len(result) - 1):
            gap = result[i+1]["start"] - result[i]["end"]
            assert gap >= 0.15 - 0.001  # float tolerance

    def test_minimum_subtitle_duration(self):
        # Very short segment should be extended to 0.8s
        segments = [{"start": 0.0, "end": 0.3, "text": "short"}]
        lines = ["Short line"]
        result = merge_whisper_with_lyrics_file(segments, lines, 10.0)
        assert result[0]["end"] - result[0]["start"] >= 0.8

    def test_maximum_subtitle_duration(self):
        # Very long segment should be capped at 8s
        segments = [{"start": 0.0, "end": 20.0, "text": "very long"}]
        lines = ["Long line"]
        result = merge_whisper_with_lyrics_file(segments, lines, 25.0)
        assert result[0]["end"] - result[0]["start"] <= 8.0

    # test_case_5: empty lyrics list raises ValueError
    def test_empty_lines_raises_value_error(self):
        segments = [{"start": 0.0, "end": 2.0, "text": "seg"}]
        with pytest.raises(ValueError, match="empty"):
            merge_whisper_with_lyrics_file(segments, [], 10.0)

    # test_case_6: blank lines already filtered by caller, but test robustness
    def test_empty_whisper_segments_filtered_before_matching(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": "  "},   # empty — should be filtered
            {"start": 1.0, "end": 3.0, "text": "real"},
        ]
        lines = ["Correct line"]
        result = merge_whisper_with_lyrics_file(segments, lines, 5.0)
        assert len(result) == 1
        assert result[0]["text"] == "Correct line"

    def test_result_sorted_chronologically(self):
        segments = self._make_segments(4)
        lines = self._make_lines(4)
        result = merge_whisper_with_lyrics_file(segments, lines, 10.0)
        starts = [r["start"] for r in result]
        assert starts == sorted(starts)

    def test_pre_display_offset_applied(self):
        segments = [{"start": 1.0, "end": 3.0, "text": "seg"}]
        lines = ["Line"]
        result = merge_whisper_with_lyrics_file(segments, lines, 5.0)
        # start should be shifted by -0.05s
        assert result[0]["start"] == pytest.approx(0.95, abs=0.01)

    def test_pre_display_offset_clamped_to_zero(self):
        segments = [{"start": 0.03, "end": 2.0, "text": "seg"}]
        lines = ["Line"]
        result = merge_whisper_with_lyrics_file(segments, lines, 5.0)
        assert result[0]["start"] >= 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```
python3 -m pytest tests/test_lyrics_parser.py::TestMergeWhisperWithLyricsFile -v
```
Expected: ImportError or NameError — `merge_whisper_with_lyrics_file` not defined yet.

- [ ] **Step 3: Implement `merge_whisper_with_lyrics_file` in lyrics_parser.py**

Add after the existing `align_with_claude` function (end of file):

```python
def merge_whisper_with_lyrics_file(whisper_segments, lyrics_lines, audio_duration):
    """Deterministically align lyrics file lines to Whisper timing.

    Uses proportional grouping: maps N Whisper segments to M lyrics lines
    handling N==M, N>M, and N<M cases. Applies timing corrections after.

    Args:
        whisper_segments: list of dicts with start/end/text from Whisper.
        lyrics_lines: list of non-empty lyrics strings from the .txt file.
        audio_duration: total audio duration in seconds.

    Returns:
        list[dict] with keys: start (float), end (float), text (str),
        sorted chronologically.

    Raises:
        ValueError: If lyrics_lines is empty.
    """
    if not lyrics_lines:
        raise ValueError("lyrics_lines is empty — no lines to align")

    # Filter empty Whisper segments
    segments = [s for s in whisper_segments if s["text"].strip()]

    if not segments:
        # Fallback: distribute lines evenly over full audio
        count = len(lyrics_lines)
        seg_dur = audio_duration / count
        result = [
            {
                "start": i * seg_dur,
                "end": (i + 1) * seg_dur,
                "text": lyrics_lines[i],
            }
            for i in range(count)
        ]
        return _apply_timing_corrections(result, audio_duration)

    n_seg = len(segments)
    n_lines = len(lyrics_lines)

    if n_seg == n_lines:
        # Case A: 1:1 mapping
        result = [
            {
                "start": segments[i]["start"],
                "end": segments[i]["end"],
                "text": lyrics_lines[i],
            }
            for i in range(n_lines)
        ]

    elif n_seg > n_lines:
        # Case B: more segments than lines — group segments proportionally
        segments_per_line = n_seg / n_lines
        result = []
        for i, line in enumerate(lyrics_lines):
            seg_start_idx = round(i * segments_per_line)
            seg_end_idx = min(round((i + 1) * segments_per_line), n_seg)
            group = segments[seg_start_idx:seg_end_idx]
            if not group:
                continue
            result.append({
                "start": group[0]["start"],
                "end": group[-1]["end"],
                "text": line,
            })

    else:
        # Case C: fewer segments than lines — split each segment's time
        lines_per_seg = n_lines / n_seg
        result = []
        for i, seg in enumerate(segments):
            line_start_idx = round(i * lines_per_seg)
            line_end_idx = min(round((i + 1) * lines_per_seg), n_lines)
            group_lines = lyrics_lines[line_start_idx:line_end_idx]
            if not group_lines:
                continue
            seg_duration = seg["end"] - seg["start"]
            time_per_line = seg_duration / len(group_lines)
            for j, line in enumerate(group_lines):
                result.append({
                    "start": seg["start"] + j * time_per_line,
                    "end": seg["start"] + (j + 1) * time_per_line,
                    "text": line,
                })

    return _apply_timing_corrections(result, audio_duration)


def _apply_timing_corrections(result, audio_duration):
    """Apply timing corrections to aligned subtitle list.

    1. Extend subtitles shorter than 0.8s to 0.8s minimum
    2. Cap subtitles longer than 8s to 8s maximum
    3. Enforce minimum 0.15s gap between consecutive subtitles
    4. Apply -0.05s pre-display offset (clamped to 0)
    5. Clamp all end times to audio_duration
    """
    # Step 1 & 2: min/max duration
    for item in result:
        duration = item["end"] - item["start"]
        if duration < 0.8:
            item["end"] = item["start"] + 0.8
        elif duration > 8.0:
            item["end"] = item["start"] + 8.0

    # Step 3: enforce minimum 0.15s gap (process in order)
    for i in range(len(result) - 1):
        if result[i]["end"] > result[i + 1]["start"] - 0.15:
            result[i]["end"] = result[i + 1]["start"] - 0.15

    # Step 4: pre-display offset (-0.05s, clamped to 0)
    for item in result:
        item["start"] = max(0.0, item["start"] - 0.05)

    # Step 5: clamp end to audio_duration
    for item in result:
        item["end"] = min(item["end"], audio_duration)

    # Ensure sorted
    result.sort(key=lambda x: x["start"])

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```
python3 -m pytest tests/test_lyrics_parser.py::TestMergeWhisperWithLyricsFile -v
```
Expected: All tests PASS.

- [ ] **Step 5: Run full lyrics parser test suite**

```
python3 -m pytest tests/test_lyrics_parser.py tests/test_lyrics_alignment.py -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/lyrics_parser.py tests/test_lyrics_parser.py
git commit -m "feat: add merge_whisper_with_lyrics_file deterministic lyrics sync"
```

---

### Task 2: Wire `merge_whisper_with_lyrics_file` into the CLI

**Files:**
- Modify: `musicvid/musicvid.py` (lines ~22, ~407-420)
- Test: existing CLI tests that cover `--lyrics` flag

- [ ] **Step 1: Write a failing CLI integration test**

Add the following to `tests/test_cli.py` (or the existing CLI test file — find it first with `grep -r "test.*lyrics" tests/`). Add this test alongside existing `--lyrics` tests:

```python
@patch("musicvid.musicvid.merge_whisper_with_lyrics_file")
@patch("musicvid.musicvid.analyze_audio")
@patch("musicvid.musicvid.plan_scenes")
@patch("musicvid.musicvid.fetch_stock_videos")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
def test_lyrics_flag_uses_merge_function(
    mock_font, mock_assemble, mock_fetch, mock_plan, mock_analyze, mock_merge,
    tmp_path, runner
):
    """--lyrics flag should call merge_whisper_with_lyrics_file, not align_with_claude."""
    lyrics_file = tmp_path / "lyrics.txt"
    lyrics_file.write_text("Line one\nLine two\n")
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"fake")

    mock_analyze.return_value = {
        "duration": 10.0,
        "lyrics": [{"start": 0.0, "end": 5.0, "text": "seg"}],
        "beats": [], "sections": [], "bpm": 120.0,
    }
    mock_merge.return_value = [
        {"start": 0.0, "end": 5.0, "text": "Line one"},
        {"start": 5.0, "end": 10.0, "text": "Line two"},
    ]
    mock_plan.return_value = {"scenes": [], "subtitle_style": {"animation": "none"}}
    mock_fetch.return_value = []
    mock_assemble.return_value = None

    result = runner.invoke(cli, [
        str(audio), "--mode", "stock", "--preset", "full",
        "--lyrics", str(lyrics_file), "--yes"
    ])

    mock_merge.assert_called_once()
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

```
python3 -m pytest tests/test_cli.py::test_lyrics_flag_uses_merge_function -v
```
Expected: FAIL — `merge_whisper_with_lyrics_file` not imported or patching wrong path.

- [ ] **Step 3: Update musicvid.py to use merge_whisper_with_lyrics_file**

Change line ~22:
```python
# Before:
from musicvid.pipeline.lyrics_parser import align_with_claude

# After:
from musicvid.pipeline.lyrics_parser import align_with_claude, merge_whisper_with_lyrics_file
```

Change lines ~407-420 (the lyrics replacement block):
```python
    # Replace lyrics using deterministic alignment if lyrics file available
    if lyrics_file:
        aligned_cache_name = f"lyrics_aligned_{lyrics_hash}.json"
        aligned = load_cache(cache_dir, aligned_cache_name)
        if aligned is None:
            with open(lyrics_file, "r", encoding="utf-8") as f:
                raw = f.read()
            file_lines = [l.strip() for l in raw.split("\n") if l.strip()]
            aligned = merge_whisper_with_lyrics_file(
                analysis["lyrics"], file_lines, analysis["duration"]
            )
            save_cache(cache_dir, aligned_cache_name, aligned)
        analysis["lyrics"] = aligned
```

- [ ] **Step 4: Run the CLI test to verify it passes**

```
python3 -m pytest tests/test_cli.py::test_lyrics_flag_uses_merge_function -v
```
Expected: PASS.

- [ ] **Step 5: Run full test suite to catch regressions**

```
python3 -m pytest tests/ -v 2>&1 | tail -30
```
Expected: All tests PASS (or same count as before this change).

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: use deterministic merge_whisper_with_lyrics_file in CLI lyrics flow"
```

---

## Self-Review Against Spec

**Spec requirement mapping:**

| Spec requirement | Task/Step |
|---|---|
| `merge_whisper_with_lyrics_file(whisper_segments, lyrics_lines, audio_duration)` | Task 1 Step 3 |
| Case A: N_segments == N_lines → 1:1 | Task 1 Step 3 (Case A branch) |
| Case B: N_segments > N_lines → proportional groups | Task 1 Step 3 (Case B branch) |
| Case C: N_segments < N_lines → split segment time | Task 1 Step 3 (Case C branch) |
| Min gap 0.15s | `_apply_timing_corrections` Step 3 |
| Min duration 0.8s | `_apply_timing_corrections` Step 1 |
| Max duration 8s | `_apply_timing_corrections` Step 2 |
| Pre-display offset -0.05s clamped to 0 | `_apply_timing_corrections` Step 4 |
| test_case_1 (8 seg, 8 lines) | `test_equal_segments_and_lines_maps_one_to_one` |
| test_case_2 (12 seg, 6 lines) | `test_more_segments_than_lines_groups_proportionally` |
| test_case_3 (4 seg, 12 lines) | `test_fewer_segments_than_lines_splits_time` |
| test_case_4 (timing corrections) | `test_no_overlap_between_subtitles`, `test_minimum_subtitle_duration`, `test_maximum_subtitle_duration` |
| test_case_5 (empty lyrics → ValueError) | `test_empty_lines_raises_value_error` |
| test_case_6 (blank lines ignored) | `test_empty_whisper_segments_filtered_before_matching` |
| Integration in musicvid.py when lyrics_path available | Task 2 |
| `pytest tests/test_lyrics_parser.py -v` passes | Task 1 Steps 4-5 |
