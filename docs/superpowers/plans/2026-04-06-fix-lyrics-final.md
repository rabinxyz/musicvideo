# Fix Lyrics Pipeline — lyrics_path in analyze_audio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move lyrics file merging into `analyze_audio()` so the function returns already-merged lyrics when a lyrics file is provided, and fix the cache filename inconsistency.

**Architecture:** Add `lyrics_path` parameter to `analyze_audio()`. After Whisper transcription builds the raw `lyrics` list, if `lyrics_path` is set, call `merge_whisper_with_lyrics_file()` to replace Whisper text with file text while keeping Whisper timing. Remove the post-merge code from CLI. Fix internal cache filename from `analysis.json` to `audio_analysis.json`.

**Tech Stack:** Python, unittest.mock, pytest

---

### Task 1: Add lyrics_path parameter to analyze_audio and merge inside it

**Files:**
- Modify: `musicvid/pipeline/audio_analyzer.py:83-166`
- Test: `tests/test_audio_analyzer.py`

- [ ] **Step 1: Write failing test — analyze_audio accepts lyrics_path**

Add to `tests/test_audio_analyzer.py` in class `TestAnalyzeAudio`:

```python
@patch("musicvid.pipeline.audio_analyzer.merge_whisper_with_lyrics_file")
@patch("musicvid.pipeline.audio_analyzer.whisper")
@patch("musicvid.pipeline.audio_analyzer.librosa")
def test_lyrics_path_triggers_merge(self, mock_librosa, mock_whisper, mock_merge, mock_whisper_result, mock_audio_signal, tmp_path):
    """When lyrics_path is provided, merge_whisper_with_lyrics_file is called."""
    y, sr = mock_audio_signal
    mock_model = MagicMock()
    mock_model.transcribe.return_value = mock_whisper_result
    mock_whisper.load_model.return_value = mock_model
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.beat.beat_track.return_value = (120.0, np.array([0]))
    mock_librosa.get_duration.return_value = 10.0
    mock_librosa.frames_to_time.return_value = np.array([0.0])
    mock_merge.return_value = [{"start": 0.5, "end": 2.0, "text": "Merged line"}]

    lyrics_file = tmp_path / "tekst.txt"
    lyrics_file.write_text("Merged line\n", encoding="utf-8")
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio data")

    result = analyze_audio(str(audio_file), lyrics_path=str(lyrics_file))

    mock_merge.assert_called_once()
    assert result["lyrics"] == [{"start": 0.5, "end": 2.0, "text": "Merged line"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestAnalyzeAudio::test_lyrics_path_triggers_merge -v`
Expected: FAIL — `analyze_audio() got an unexpected keyword argument 'lyrics_path'`

- [ ] **Step 3: Write failing test — no lyrics_path means no merge**

Add to `tests/test_audio_analyzer.py` in class `TestAnalyzeAudio`:

```python
@patch("musicvid.pipeline.audio_analyzer.merge_whisper_with_lyrics_file")
@patch("musicvid.pipeline.audio_analyzer.whisper")
@patch("musicvid.pipeline.audio_analyzer.librosa")
def test_no_lyrics_path_skips_merge(self, mock_librosa, mock_whisper, mock_merge, mock_whisper_result, mock_audio_signal, tmp_path):
    """When lyrics_path is None, merge is not called."""
    y, sr = mock_audio_signal
    mock_model = MagicMock()
    mock_model.transcribe.return_value = mock_whisper_result
    mock_whisper.load_model.return_value = mock_model
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.beat.beat_track.return_value = (120.0, np.array([0]))
    mock_librosa.get_duration.return_value = 10.0
    mock_librosa.frames_to_time.return_value = np.array([0.0])

    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio data")

    result = analyze_audio(str(audio_file))

    mock_merge.assert_not_called()
    assert result["lyrics"][0]["text"] == "Amazing grace how sweet the sound"
```

- [ ] **Step 4: Implement lyrics_path in analyze_audio**

In `musicvid/pipeline/audio_analyzer.py`:

1. Add import at top of file:
```python
from musicvid.pipeline.lyrics_parser import merge_whisper_with_lyrics_file
```

2. Change function signature (line 83):
```python
def analyze_audio(audio_path, output_dir=None, whisper_model="small", lyrics_path=None):
```

3. After the lyrics extraction loop (after line 123, before `language = ...`), add:
```python
    if lyrics_path and Path(lyrics_path).exists():
        with open(lyrics_path, encoding="utf-8") as f:
            file_lines = [l.strip() for l in f.readlines() if l.strip()]
        lyrics = merge_whisper_with_lyrics_file(lyrics, file_lines, duration)
        print(f"[Lyrics] Plik: {len(file_lines)} linii + Whisper: {len(lyrics)} segmentów → {len(lyrics)} napisów")
        if lyrics:
            print(f"[Lyrics] Pierwszy: '{lyrics[0]['text']}' @ {lyrics[0]['start']:.1f}s")
    else:
        print(f"[Lyrics] Whisper: {len(lyrics)} segmentów (brak pliku tekstu)")
```

**Important:** The merge call needs `duration` which is computed later (line 128). Move the merge block to AFTER `duration = float(librosa.get_duration(y=y, sr=sr))` (after line 128). The full implementation order becomes:

```python
    # ... lyrics extraction loop ends ...

    language = transcription.get("language", "en")

    y, sr = librosa.load(audio_path)
    duration = float(librosa.get_duration(y=y, sr=sr))

    # Merge with lyrics file if provided (needs duration for timing corrections)
    if lyrics_path and Path(lyrics_path).exists():
        with open(lyrics_path, encoding="utf-8") as f:
            file_lines = [l.strip() for l in f.readlines() if l.strip()]
        lyrics = merge_whisper_with_lyrics_file(lyrics, file_lines, duration)
        print(f"[Lyrics] Plik: {len(file_lines)} linii → {len(lyrics)} napisów")
        if lyrics:
            print(f"[Lyrics] Pierwszy: '{lyrics[0]['text']}' @ {lyrics[0]['start']:.1f}s")
    else:
        print(f"[Lyrics] Whisper: {len(lyrics)} segmentów (brak pliku tekstu)")

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    # ... rest unchanged ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_audio_analyzer.py -v`
Expected: ALL PASS (including both new tests and all existing tests)

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/audio_analyzer.py tests/test_audio_analyzer.py
git commit -m "feat(analyzer): add lyrics_path param to analyze_audio for in-function merge"
```

---

### Task 2: Fix cache filename from analysis.json to audio_analysis.json

**Files:**
- Modify: `musicvid/pipeline/audio_analyzer.py:160-164`
- Test: `tests/test_audio_analyzer.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_audio_analyzer.py` in class `TestAnalyzeAudio`:

```python
@patch("musicvid.pipeline.audio_analyzer.whisper")
@patch("musicvid.pipeline.audio_analyzer.librosa")
def test_output_file_named_audio_analysis(self, mock_librosa, mock_whisper, mock_whisper_result, mock_audio_signal, tmp_path):
    """analyze_audio saves to audio_analysis.json, not analysis.json."""
    y, sr = mock_audio_signal
    mock_model = MagicMock()
    mock_model.transcribe.return_value = mock_whisper_result
    mock_whisper.load_model.return_value = mock_model
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.beat.beat_track.return_value = (120.0, np.array([0]))
    mock_librosa.get_duration.return_value = 10.0
    mock_librosa.frames_to_time.return_value = np.array([0.0])

    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio data")

    analyze_audio(str(audio_file), output_dir=str(tmp_path))

    assert (tmp_path / "audio_analysis.json").exists()
    assert not (tmp_path / "analysis.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestAnalyzeAudio::test_output_file_named_audio_analysis -v`
Expected: FAIL — `assert not (tmp_path / "analysis.json").exists()` fails (or `audio_analysis.json` doesn't exist)

- [ ] **Step 3: Fix the filename**

In `musicvid/pipeline/audio_analyzer.py`, change line 163:

Old:
```python
        with open(output_path / "analysis.json", "w") as f:
```

New:
```python
        with open(output_path / "audio_analysis.json", "w") as f:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_audio_analyzer.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/audio_analyzer.py tests/test_audio_analyzer.py
git commit -m "fix(analyzer): rename cache file from analysis.json to audio_analysis.json"
```

---

### Task 3: Simplify CLI — remove post-merge lyrics code, pass lyrics_path to analyze_audio

**Files:**
- Modify: `musicvid/musicvid.py:559-581`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Find and read the relevant CLI test for --lyrics**

Run: `python3 -m pytest tests/test_cli.py -k lyrics --collect-only` to find existing lyrics tests.

Read the existing test to understand what it mocks.

- [ ] **Step 2: Write failing test — analyze_audio receives lyrics_path**

Add/update test in `tests/test_cli.py`:

```python
def test_lyrics_path_passed_to_analyze_audio(self, ...):
    """When --lyrics is provided, analyze_audio is called with lyrics_path."""
    # ... standard pipeline mocks ...
    result = runner.invoke(cli, [str(audio), "--lyrics", str(lyrics_file), "--mode", "stock", "--preset", "full"])
    mock_analyze.assert_called_once()
    call_kwargs = mock_analyze.call_args
    assert call_kwargs[1].get("lyrics_path") == str(lyrics_file) or call_kwargs.kwargs.get("lyrics_path") == str(lyrics_file)
```

(Exact mock setup depends on existing test patterns — the implementer should read the existing `--lyrics` test and adapt.)

- [ ] **Step 3: Update CLI to pass lyrics_path and remove post-merge block**

In `musicvid/musicvid.py`:

1. Change the `analyze_audio` call (around line 561) to pass `lyrics_path`:
```python
        analysis = analyze_audio(str(audio_path), output_dir=str(cache_dir), lyrics_path=str(lyrics_file) if lyrics_file else None)
```

2. Remove the entire post-merge block (lines 564-581 approximately):
```python
    # DELETE THIS BLOCK — merge now happens inside analyze_audio:
    # if lyrics_file:
    #     aligned_cache_name = ...
    #     ...
    #     analysis["lyrics"] = aligned
    #     ...
```

3. Keep the lyrics_file detection (lines 535-546) and lyrics_hash computation (lines 548-552) — these are still needed for cache key naming.

4. Update the log message after analysis (keep existing click.echo for BPM/Duration).

- [ ] **Step 4: Remove merge_whisper_with_lyrics_file import from musicvid.py if no longer used**

Check if `merge_whisper_with_lyrics_file` is still imported/used in `musicvid.py`. If the only usage was the deleted block, remove the import.

- [ ] **Step 5: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS. If any CLI tests that mocked `merge_whisper_with_lyrics_file` at the CLI level fail, update them to remove that mock (since merge now happens inside `analyze_audio` which is already mocked in CLI tests).

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "refactor(cli): pass lyrics_path to analyze_audio, remove post-merge block"
```

---

### Task 4: Run full test suite and verify

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: ALL ~689 tests PASS

- [ ] **Step 2: Verify acceptance criteria**

Check that:
1. `analyze_audio()` signature includes `lyrics_path=None`
2. When `lyrics_path` is provided, returned `lyrics` contains file text with Whisper timing
3. `analyze_audio()` saves to `audio_analysis.json` (not `analysis.json`)
4. CLI no longer has separate post-merge lyrics block
5. Print output shows lyrics count when file provided

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address test failures from lyrics pipeline refactor"
```
