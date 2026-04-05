# Fix Whisper Configuration for Polish Language Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Whisper transcription for Polish Christian songs by forcing Polish language, using a better model, and improving segment filtering.

**Architecture:** Three changes to `audio_analyzer.py`: (1) add `language="pl"` and tuning params to `model.transcribe()`, (2) change default model from "base" to "small", (3) improve segment filtering to be less aggressive. CLI already handles lyrics file alignment separately via `merge_whisper_with_lyrics_file`.

**Tech Stack:** Python, Whisper, pytest with unittest.mock

---

### Task 1: Add Polish language parameters to Whisper transcribe call

**Files:**
- Modify: `musicvid/pipeline/audio_analyzer.py:94-95`
- Test: `tests/test_audio_analyzer.py`

- [ ] **Step 1: Write failing test — verify transcribe receives Polish language params**

Add this test to `tests/test_audio_analyzer.py` inside `TestAnalyzeAudio`:

```python
@patch("musicvid.pipeline.audio_analyzer.whisper")
@patch("musicvid.pipeline.audio_analyzer.librosa")
def test_transcribe_uses_polish_language_params(self, mock_librosa, mock_whisper, mock_whisper_result, mock_audio_signal, tmp_path):
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

    analyze_audio(str(audio_file))

    call_kwargs = mock_model.transcribe.call_args[1]
    assert call_kwargs["language"] == "pl"
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["condition_on_previous_text"] is True
    assert "initial_prompt" in call_kwargs
    assert "pieśń" in call_kwargs["initial_prompt"].lower() or "Polska" in call_kwargs["initial_prompt"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestAnalyzeAudio::test_transcribe_uses_polish_language_params -v`
Expected: FAIL — `language` key not in call_kwargs

- [ ] **Step 3: Implement — add Polish params to transcribe call**

In `musicvid/pipeline/audio_analyzer.py`, replace line 95:

```python
transcription = model.transcribe(audio_path, word_timestamps=True)
```

With:

```python
transcription = model.transcribe(
    audio_path,
    word_timestamps=True,
    language="pl",
    initial_prompt="Polska pieśń chrześcijańska. Słowa: tylko, Bogu, zbawienie, Pan, dusza, serce, chwała.",
    temperature=0.0,
    condition_on_previous_text=True,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestAnalyzeAudio::test_transcribe_uses_polish_language_params -v`
Expected: PASS

- [ ] **Step 5: Run all existing audio analyzer tests to check no regressions**

Run: `python3 -m pytest tests/test_audio_analyzer.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/audio_analyzer.py tests/test_audio_analyzer.py
git commit -m "feat: add Polish language params to Whisper transcribe call"
```

---

### Task 2: Change default Whisper model from "base" to "small"

**Files:**
- Modify: `musicvid/pipeline/audio_analyzer.py:83`
- Test: `tests/test_audio_analyzer.py`

- [ ] **Step 1: Write failing test — verify default model is "small"**

Add this test to `tests/test_audio_analyzer.py` inside `TestAnalyzeAudio`:

```python
@patch("musicvid.pipeline.audio_analyzer.whisper")
@patch("musicvid.pipeline.audio_analyzer.librosa")
def test_default_whisper_model_is_small(self, mock_librosa, mock_whisper, mock_whisper_result, mock_audio_signal, tmp_path):
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

    analyze_audio(str(audio_file))

    mock_whisper.load_model.assert_called_once_with("small")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestAnalyzeAudio::test_default_whisper_model_is_small -v`
Expected: FAIL — called with "base" not "small"

- [ ] **Step 3: Implement — change default model to "small"**

In `musicvid/pipeline/audio_analyzer.py`, change the function signature on line 83:

```python
def analyze_audio(audio_path, output_dir=None, whisper_model="small"):
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestAnalyzeAudio::test_default_whisper_model_is_small -v`
Expected: PASS

- [ ] **Step 5: Run all audio analyzer tests**

Run: `python3 -m pytest tests/test_audio_analyzer.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/audio_analyzer.py tests/test_audio_analyzer.py
git commit -m "feat: change default Whisper model from base to small for better Polish"
```

---

### Task 3: Improve segment filtering — less aggressive

**Files:**
- Modify: `musicvid/pipeline/audio_analyzer.py:97-111`
- Test: `tests/test_audio_analyzer.py`

- [ ] **Step 1: Write failing test — single-char segments are filtered out**

Add this test to `tests/test_audio_analyzer.py` inside `TestAnalyzeAudio`:

```python
@patch("musicvid.pipeline.audio_analyzer.whisper")
@patch("musicvid.pipeline.audio_analyzer.librosa")
def test_filters_out_short_segments(self, mock_librosa, mock_whisper, mock_audio_signal, tmp_path):
    y, sr = mock_audio_signal

    mock_model = MagicMock()
    mock_model.transcribe.return_value = {
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "A", "words": []},
            {"start": 1.0, "end": 2.0, "text": "Bogu chwała na wieki", "words": [
                {"word": "Bogu", "start": 1.0, "end": 1.3},
                {"word": "chwała", "start": 1.3, "end": 1.6},
                {"word": "na", "start": 1.6, "end": 1.7},
                {"word": "wieki", "start": 1.7, "end": 2.0},
            ]},
            {"start": 2.0, "end": 3.0, "text": "", "words": []},
            {"start": 3.0, "end": 4.0, "text": " ", "words": []},
        ],
        "language": "pl",
    }
    mock_whisper.load_model.return_value = mock_model

    mock_librosa.load.return_value = (y, sr)
    mock_librosa.beat.beat_track.return_value = (120.0, np.array([0]))
    mock_librosa.get_duration.return_value = 10.0
    mock_librosa.frames_to_time.return_value = np.array([0.0])

    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio data")

    result = analyze_audio(str(audio_file))

    assert len(result["lyrics"]) == 1
    assert result["lyrics"][0]["text"] == "Bogu chwała na wieki"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestAnalyzeAudio::test_filters_out_short_segments -v`
Expected: FAIL — current code keeps the single-char "A" segment (len 3 with "A" stripped = 1, which passes current `.strip()` filter)

- [ ] **Step 3: Implement — replace segment loop with improved filtering**

In `musicvid/pipeline/audio_analyzer.py`, replace lines 97-111 (the lyrics building loop):

```python
    lyrics = []
    for segment in transcription.get("segments", []):
        text = segment["text"].strip()
        if not text:
            continue
        if len(text) < 2:
            continue
        words = []
        for w in segment.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": round(float(w["start"]), 2),
                "end": round(float(w["end"]), 2),
            })
        lyrics.append({
            "start": round(float(segment["start"]), 2),
            "end": round(float(segment["end"]), 2),
            "text": text,
            "words": words,
        })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_audio_analyzer.py::TestAnalyzeAudio::test_filters_out_short_segments -v`
Expected: PASS

- [ ] **Step 5: Run all audio analyzer tests**

Run: `python3 -m pytest tests/test_audio_analyzer.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite to check no regressions**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (no other modules depend on single-char segments)

- [ ] **Step 7: Commit**

```bash
git add musicvid/pipeline/audio_analyzer.py tests/test_audio_analyzer.py
git commit -m "feat: improve Whisper segment filtering — skip segments shorter than 2 chars"
```
