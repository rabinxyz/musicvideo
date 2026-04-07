# Lyrics Fuzzy Match Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the deterministic `merge_whisper_with_lyrics_file` lyrics alignment with a fuzzy-matching sliding-cursor algorithm (`rapidfuzz`) that handles Whisper typos, merged words, and timing drift — producing subtitles with correct Polish text from the lyrics file.

**Architecture:** New module `musicvid/pipeline/lyrics_aligner.py` exports `align_lyrics(whisper_segments, lyrics_path)`. It reads the lyrics file as a continuous word stream, filters noise segments, runs a sliding-window fuzzy match against each Whisper segment (cursor advances forward only), splits long matches into ≤7-word subtitles, and returns timed subtitle dicts. `audio_analyzer.py` switches from `merge_whisper_with_lyrics_file` to `align_lyrics`.

**Tech Stack:** `rapidfuzz>=3.0.0` (fuzzy string matching), Python `re` (text cleaning)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `musicvid/pipeline/lyrics_aligner.py` | Create | Fuzzy-match alignment: `align_lyrics()`, `_is_vocal()`, `_split_segment()` |
| `tests/test_lyrics_aligner.py` | Create | All tests for the new module |
| `musicvid/pipeline/audio_analyzer.py` | Modify (lines 130-136) | Switch import from `merge_whisper_with_lyrics_file` to `align_lyrics` |
| `musicvid/requirements.txt` | Modify | Add `rapidfuzz>=3.0.0` |

---

### Task 1: Create `lyrics_aligner.py` with noise filtering and text preparation

**Files:**
- Create: `musicvid/pipeline/lyrics_aligner.py`
- Create: `tests/test_lyrics_aligner.py`

- [ ] **Step 1: Write failing tests for noise filtering and text preparation**

```python
"""Tests for musicvid.pipeline.lyrics_aligner."""

import unittest

from musicvid.pipeline.lyrics_aligner import align_lyrics


class TestNoiseFiltering(unittest.TestCase):
    """Noise segments like 'Muzyka' or '♪' should be filtered out."""

    def test_noise_filtered(self):
        """Segment 'Muzyka' at 0.0s is filtered, not in results."""
        segments = [
            {"start": 0.0, "end": 5.0, "text": "Muzyka"},
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu moje jest zbawienie"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            texts = [r["text"] for r in result]
            self.assertNotIn("Muzyka", " ".join(texts))
            self.assertTrue(len(result) >= 1)
        finally:
            os.unlink(path)

    def test_music_symbols_filtered(self):
        """Segments with only ♪ symbols are filtered."""
        segments = [
            {"start": 0.0, "end": 3.0, "text": "♪♪♪"},
            {"start": 28.0, "end": 32.0, "text": "Pan jest pasterzem moim"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Pan jest pasterzem moim\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            self.assertTrue(len(result) >= 1)
            self.assertNotIn("♪", result[0]["text"])
        finally:
            os.unlink(path)


class TestBracketsIgnored(unittest.TestCase):
    """[Refren:] and similar brackets in lyrics file should be stripped."""

    def test_brackets_removed(self):
        """Lyrics file has '[Refren:]' — it does not appear in results."""
        segments = [
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("[Refren:]\nTylko w Bogu moje jest zbawienie\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            for r in result:
                self.assertNotIn("[Refren:]", r["text"])
                self.assertNotIn("Refren", r["text"])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_lyrics_aligner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'musicvid.pipeline.lyrics_aligner'`

- [ ] **Step 3: Implement lyrics_aligner.py with noise filter, text prep, and stub align_lyrics**

```python
"""Lyrics aligner — fuzzy-match Whisper segments to lyrics file text."""

import re

from rapidfuzz import fuzz

NON_VOCAL = {"muzyka", "music", "instrumental"}

MAX_WORDS_PER_SUBTITLE = 7

MIN_RATIO = 45


def _is_vocal(seg):
    """Return True if segment contains actual vocals (not noise/music)."""
    text = seg["text"].strip().lower()
    text_clean = re.sub(r"[\[\]()♪♫ ]", "", text)
    if text_clean in NON_VOCAL:
        return False
    if len(text_clean) < 3:
        return False
    return True


def _prepare_lyrics(lyrics_path):
    """Read lyrics file, strip brackets, return (all_words, word_string).

    all_words: list of original-case words from the file.
    word_string: lowercase joined string for fuzzy matching.
    """
    with open(lyrics_path, encoding="utf-8") as f:
        raw = f.read()

    # Remove stage directions in brackets: [Refren:], [x2], [Bridge], etc.
    raw = re.sub(r"\[.*?\]", "", raw, flags=re.DOTALL)

    # Split into words — ignore line breaks
    all_words = re.findall(r"\b\w+\b", raw, re.UNICODE)

    # Continuous lowercase string for fuzzy matching
    word_string = " ".join(w.lower() for w in all_words)

    return all_words, word_string


def _split_segment(seg):
    """Split a segment with >MAX_WORDS_PER_SUBTITLE words into shorter subtitles."""
    words = seg["text"].split()
    if len(words) <= MAX_WORDS_PER_SUBTITLE:
        return [seg]

    groups = []
    for i in range(0, len(words), MAX_WORDS_PER_SUBTITLE):
        groups.append(" ".join(words[i : i + MAX_WORDS_PER_SUBTITLE]))

    duration = seg["end"] - seg["start"]
    time_per = duration / len(groups)

    result = []
    for i, group in enumerate(groups):
        result.append(
            {
                "start": round(seg["start"] + i * time_per, 2),
                "end": round(seg["start"] + (i + 1) * time_per - 0.1, 2),
                "text": group,
                "words": [],
                "match_ratio": seg.get("match_ratio", 0),
            }
        )
    return result


def align_lyrics(whisper_segments, lyrics_path):
    """Align Whisper segments to lyrics file using fuzzy sliding-cursor match.

    Args:
        whisper_segments: list of dicts with start/end/text from Whisper.
        lyrics_path: path to .txt lyrics file.

    Returns:
        list[dict] with keys: start, end, text, match_ratio, words.
    """
    all_words, word_string = _prepare_lyrics(lyrics_path)

    if not all_words:
        return []

    vocal_segments = [s for s in whisper_segments if _is_vocal(s)]

    cursor = 0  # character position in word_string
    result_lyrics = []

    for seg in vocal_segments:
        whisper_raw = seg["text"].strip()
        whisper_clean = " ".join(re.findall(r"\b\w+\b", whisper_raw.lower()))

        if not whisper_clean or len(whisper_clean) < 3:
            continue

        # Search window: from cursor forward
        max_window = max(300, len(whisper_clean) * 6)
        search_text = word_string[cursor : cursor + max_window]

        if not search_text.strip():
            break  # end of lyrics text

        # Sliding window — find best matching substring
        target_len = len(whisper_clean)
        best_ratio = 0
        best_pos = 0

        step = max(1, target_len // 8)

        for i in range(0, max(1, len(search_text) - target_len + 1), step):
            window = search_text[i : i + int(target_len * 1.5)]
            ratio = fuzz.partial_ratio(whisper_clean, window)
            if ratio > best_ratio:
                best_ratio = ratio
                best_pos = i

        if best_ratio >= MIN_RATIO:
            abs_pos = cursor + best_pos
            matched_len = int(target_len * 1.3)

            # Convert character position to word index
            words_before = word_string[:abs_pos].split()
            word_idx = len(words_before)

            n_words = max(1, len(whisper_clean.split()))
            original_words = all_words[word_idx : word_idx + n_words]
            matched_text = " ".join(original_words)

            result_lyrics.append(
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": matched_text,
                    "match_ratio": best_ratio,
                    "words": [],
                }
            )

            new_cursor = abs_pos + matched_len
            cursor = min(new_cursor, len(word_string))

            print(f"  {seg['start']:.1f}s: '{matched_text}' (ratio={best_ratio})")
        else:
            # Weak match — use Whisper text as fallback
            print(
                f"  WARN {seg['start']:.1f}s: weak match ({best_ratio}) — Whisper: '{whisper_raw}'"
            )
            result_lyrics.append(
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": whisper_raw,
                    "match_ratio": best_ratio,
                    "words": [],
                }
            )
            cursor += max(50, len(whisper_clean))

    # Split long segments into shorter subtitles
    final = []
    for seg in result_lyrics:
        final.extend(_split_segment(seg))

    return final
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_lyrics_aligner.py::TestNoiseFiltering -v && python3 -m pytest tests/test_lyrics_aligner.py::TestBracketsIgnored -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/lyrics_aligner.py tests/test_lyrics_aligner.py
git commit -m "feat: add lyrics_aligner module with noise filtering and text prep"
```

---

### Task 2: Add fuzzy matching and cursor tests

**Files:**
- Modify: `tests/test_lyrics_aligner.py`

- [ ] **Step 1: Write failing tests for cursor advancement and fuzzy matching**

Append to `tests/test_lyrics_aligner.py`:

```python
class TestCursorAdvances(unittest.TestCase):
    """After matching segment 1, cursor advances so segment 2 searches forward."""

    def test_cursor_advances(self):
        """Two segments should match sequential parts of lyrics."""
        segments = [
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu"},
            {"start": 33.0, "end": 37.0, "text": "moje jest zbawienie"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie od Niego\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            self.assertTrue(len(result) >= 2)
            # Second result should NOT re-match first words
            self.assertNotEqual(result[0]["text"], result[1]["text"])
        finally:
            os.unlink(path)


class TestFuzzyTypos(unittest.TestCase):
    """Whisper typos should still fuzzy-match to correct lyrics text."""

    def test_fuzzy_match_typos(self):
        """whisper 'tolko w bogu mojest' matches 'Tylko w Bogu moje jest'."""
        segments = [
            {"start": 28.0, "end": 35.0, "text": "tolko w bogu mojest zbawienie"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            self.assertTrue(len(result) >= 1)
            self.assertGreaterEqual(result[0]["match_ratio"], MIN_RATIO)
            # Text should come from file, not Whisper
            self.assertIn("Bogu", result[0]["text"])
        finally:
            os.unlink(path)


class TestSequentialOrder(unittest.TestCase):
    """Results should be sorted chronologically."""

    def test_sequential(self):
        """lyrics[i]['start'] < lyrics[i+1]['start'] always."""
        segments = [
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu"},
            {"start": 33.0, "end": 37.0, "text": "moje jest zbawienie"},
            {"start": 38.0, "end": 42.0, "text": "od Niego pochodzi"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie od Niego pochodzi moc\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            for i in range(len(result) - 1):
                self.assertLess(result[i]["start"], result[i + 1]["start"])
        finally:
            os.unlink(path)
```

Also import `MIN_RATIO` at the top:

```python
from musicvid.pipeline.lyrics_aligner import align_lyrics, MIN_RATIO
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_lyrics_aligner.py -v`
Expected: ALL PASS (implementation already handles these cases)

- [ ] **Step 3: Commit**

```bash
git add tests/test_lyrics_aligner.py
git commit -m "test: add cursor advancement and fuzzy matching tests for lyrics_aligner"
```

---

### Task 3: Add segment splitting and first-subtitle timing tests

**Files:**
- Modify: `tests/test_lyrics_aligner.py`

- [ ] **Step 1: Write tests for splitting and timing**

Append to `tests/test_lyrics_aligner.py`:

```python
class TestSplitLong(unittest.TestCase):
    """Long segments should be split into <=7-word subtitles."""

    def test_split_14_words(self):
        """Segment with 14 words splits into 2 subtitles of 7 words."""
        segments = [
            {
                "start": 28.0,
                "end": 40.0,
                "text": "Tylko w Bogu moje jest zbawienie od Niego pochodzi moc i chwała na wieki",
            },
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie od Niego pochodzi moc i chwała na wieki\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            self.assertTrue(len(result) >= 2)
            for r in result:
                self.assertLessEqual(len(r["text"].split()), 7)
            # Timing distributed evenly
            self.assertAlmostEqual(result[0]["start"], 28.0, places=1)
            self.assertGreater(result[1]["start"], result[0]["start"])
        finally:
            os.unlink(path)


class TestFirstSubtitleTiming(unittest.TestCase):
    """First subtitle should start at the Whisper segment time, not 0.0s."""

    def test_first_subtitle_timing(self):
        """lyrics[0]['start'] >= 28.0 (not 0.0s)."""
        segments = [
            {"start": 0.0, "end": 5.0, "text": "Muzyka"},
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu moje"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            self.assertTrue(len(result) >= 1)
            self.assertGreaterEqual(result[0]["start"], 28.0)
        finally:
            os.unlink(path)
```

- [ ] **Step 2: Run all tests to verify they pass**

Run: `python3 -m pytest tests/test_lyrics_aligner.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_lyrics_aligner.py
git commit -m "test: add segment splitting and first-subtitle timing tests"
```

---

### Task 4: Integrate into audio_analyzer.py and add dependency

**Files:**
- Modify: `musicvid/pipeline/audio_analyzer.py:130-136`
- Modify: `musicvid/requirements.txt`
- Modify: `tests/test_audio_analyzer.py` (update mock target)

- [ ] **Step 1: Write failing integration test**

Add to `tests/test_audio_analyzer.py` (in the existing lyrics test class or as a new class):

```python
class TestLyricsAlignerIntegration(unittest.TestCase):
    """audio_analyzer calls align_lyrics when lyrics_path is provided."""

    @patch("musicvid.pipeline.audio_analyzer.align_lyrics")
    @patch("musicvid.pipeline.audio_analyzer.whisper")
    @patch("musicvid.pipeline.audio_analyzer.librosa")
    @patch("musicvid.pipeline.audio_analyzer.np")
    def test_lyrics_path_triggers_align_lyrics(self, mock_np, mock_librosa, mock_whisper, mock_align):
        """When lyrics_path is provided, align_lyrics is called instead of merge."""
        import tempfile, os
        mock_librosa.load.return_value = (MagicMock(), 22050)
        mock_librosa.get_duration.return_value = 180.0
        mock_librosa.beat.beat_track.return_value = (120.0, [])
        mock_librosa.frames_to_time.return_value = []
        mock_librosa.onset.onset_strength.return_value = MagicMock()
        mock_librosa.util.peak_pick.return_value = []
        mock_librosa.feature.melspectrogram.return_value = MagicMock()
        mock_librosa.power_to_db.return_value = MagicMock(mean=MagicMock(return_value=0.0))
        mock_np.mean.return_value = 0.0
        mock_np.asarray.return_value = MagicMock(__len__=lambda s: 0)
        mock_whisper.load_model.return_value.transcribe.return_value = {
            "segments": [{"start": 28.0, "end": 32.0, "text": "test", "words": []}],
            "language": "pl",
        }
        mock_align.return_value = [{"start": 28.0, "end": 32.0, "text": "Poprawny tekst"}]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Poprawny tekst\n")
            lyrics_path = f.name
        try:
            from musicvid.pipeline.audio_analyzer import analyze_audio
            result = analyze_audio("fake.mp3", lyrics_path=lyrics_path)
            mock_align.assert_called_once()
            call_args = mock_align.call_args
            self.assertEqual(call_args[1]["lyrics_path"] if "lyrics_path" in call_args[1] else call_args[0][1], lyrics_path)
        finally:
            os.unlink(lyrics_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestLyricsAlignerIntegration -v`
Expected: FAIL — `align_lyrics` not imported in `audio_analyzer.py`

- [ ] **Step 3: Update audio_analyzer.py to use align_lyrics**

In `musicvid/pipeline/audio_analyzer.py`, replace lines 130-136:

Old:
```python
    # Merge with lyrics file if provided (needs duration for timing corrections)
    if lyrics_path and Path(lyrics_path).exists():
        from musicvid.pipeline.lyrics_parser import merge_whisper_with_lyrics_file
        with open(lyrics_path, encoding="utf-8") as f:
            file_lines = [l.strip() for l in f.readlines() if l.strip()]
        lyrics = merge_whisper_with_lyrics_file(lyrics, file_lines, duration)
        print(f"[Lyrics] Plik: {len(file_lines)} linii → {len(lyrics)} napisów")
        if lyrics:
            print(f"[Lyrics] Pierwszy: '{lyrics[0]['text']}' @ {lyrics[0]['start']:.1f}s")
```

New:
```python
    # Align with lyrics file if provided (fuzzy match Whisper to file text)
    if lyrics_path and Path(lyrics_path).exists():
        from musicvid.pipeline.lyrics_aligner import align_lyrics
        lyrics = align_lyrics(lyrics, lyrics_path)
        print(f"[Lyrics] Aligned: {len(lyrics)} napisów")
        if lyrics:
            print(f"[Lyrics] Pierwszy: '{lyrics[0]['text']}' @ {lyrics[0]['start']:.1f}s")
```

- [ ] **Step 4: Add rapidfuzz to requirements.txt**

Append to `musicvid/requirements.txt`:

```
rapidfuzz>=3.0.0
```

- [ ] **Step 5: Install rapidfuzz**

Run: `pip install rapidfuzz>=3.0.0`

- [ ] **Step 6: Update existing audio_analyzer lyrics tests**

In `tests/test_audio_analyzer.py`, update the two existing lyrics tests to mock the new import path:

Old mock decorator:
```python
@patch("musicvid.pipeline.lyrics_parser.merge_whisper_with_lyrics_file")
```

New mock decorator:
```python
@patch("musicvid.pipeline.audio_analyzer.align_lyrics")
```

The test body should verify `align_lyrics` is called with `(lyrics_list, lyrics_path)` instead of `(lyrics_list, file_lines, duration)`.

- [ ] **Step 7: Run all tests**

Run: `python3 -m pytest tests/test_lyrics_aligner.py tests/test_audio_analyzer.py -v`
Expected: ALL PASS

- [ ] **Step 8: Run full test suite to check for regressions**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS (no regressions)

- [ ] **Step 9: Commit**

```bash
git add musicvid/pipeline/audio_analyzer.py musicvid/requirements.txt tests/test_audio_analyzer.py
git commit -m "feat: integrate lyrics_aligner fuzzy match into audio_analyzer pipeline"
```

---

## Acceptance Criteria Checklist

- [ ] `lyrics[0]['start'] >= 28.0s` — noise segments filtered, first real lyric starts at Whisper time
- [ ] Text comes from lyrics file (correct Polish, no Whisper typos)
- [ ] Cursor advances forward only — no backward matching
- [ ] Weak matches use Whisper text as fallback
- [ ] `[Refren:]` and similar brackets stripped from lyrics file
- [ ] Long segments split into ≤7-word subtitles
- [ ] `python3 -m pytest tests/test_lyrics_aligner.py -v` passes
- [ ] `python3 -m pytest tests/ -v` passes (no regressions)
