# Fix Lyrics Timing (Case C) and Runway Error Logging

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure case C of `merge_whisper_with_lyrics_file` is properly tested with non-zero Whisper timing, and add error body logging to Runway API calls.

**Architecture:** Two independent fixes: (1) strengthen the lyrics parser test for the N_seg < N_lines case to verify timestamps derive from Whisper segments starting at ~30s (code already correct, test insufficient), (2) wrap Runway `raise_for_status()` calls to log the response body before re-raising.

**Tech Stack:** Python, pytest, requests

---

### Task 1: Strengthen test for case C (N_seg < N_lines) in lyrics parser

**Files:**
- Modify: `tests/test_lyrics_parser.py:119-126`

The current test `test_fewer_segments_than_lines_splits_time` creates segments starting at `start=0.0`, so it doesn't actually prove that output timing comes from Whisper segments. A broken implementation that generates timestamps from 0 would also pass.

- [ ] **Step 1: Update the existing test to use segments starting at ~30s**

In `tests/test_lyrics_parser.py`, replace the test at line 119:

```python
def test_fewer_segments_than_lines_splits_time(self):
    segments = self._make_segments(4, start=30.0, duration=3.0)
    lines = self._make_lines(12)
    result = merge_whisper_with_lyrics_file(segments, lines, 60.0)
    assert len(result) == 12
    # First subtitle must start at Whisper timing (~30s), not 0.0
    assert result[0]["start"] >= 25.0, f"Expected start >= 25.0, got {result[0]['start']}"
    # All subtitles must have valid timing
    for item in result:
        assert item["start"] >= 25.0
        assert item["end"] > item["start"]
    # Text comes from file lines, not Whisper
    assert result[0]["text"] == "Line 1"
    assert result[11]["text"] == "Line 12"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_lyrics_parser.py::TestMergeWhisperWithLyricsFile::test_fewer_segments_than_lines_splits_time -v`
Expected: PASS (the code is already correct, but now the test actually validates it)

- [ ] **Step 3: Commit**

```bash
git add tests/test_lyrics_parser.py
git commit -m "test(lyrics): strengthen case C test to verify Whisper-based timing"
```

---

### Task 2: Add Runway API error body logging

**Files:**
- Modify: `musicvid/pipeline/video_animator.py:38-58,66-80`
- Modify: `tests/test_video_animator.py`

Currently `resp.raise_for_status()` in `_submit_animation` and `_submit_text_to_video` raises `HTTPError` but the response body (which contains Runway's error details) is lost. Add a try/except to log the body before re-raising.

- [ ] **Step 1: Write the failing test for error body logging**

In `tests/test_video_animator.py`, add a new test to verify error body is printed:

```python
class TestRunwayErrorLogging:
    """Tests that Runway API error bodies are logged before re-raising."""

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_submit_text_to_video_logs_error_body(self, mock_time, mock_requests, capsys):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error": "promptText too long"}'
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
        mock_requests.post.return_value = mock_resp

        with pytest.raises(requests.exceptions.HTTPError):
            from musicvid.pipeline.video_animator import _submit_text_to_video
            _submit_text_to_video("test prompt", 5)

        captured = capsys.readouterr()
        assert "Runway error" in captured.out
        assert "promptText too long" in captured.out

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_submit_animation_logs_error_body(self, mock_time, mock_requests, capsys):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error": "invalid ratio"}'
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
        mock_requests.post.return_value = mock_resp

        with pytest.raises(requests.exceptions.HTTPError):
            from musicvid.pipeline.video_animator import _submit_animation
            _submit_animation("base64data", "zoom in", 5)

        captured = capsys.readouterr()
        assert "Runway error" in captured.out
        assert "invalid ratio" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_video_animator.py::TestRunwayErrorLogging -v`
Expected: FAIL — error body not printed yet

- [ ] **Step 3: Add error body logging to both submit functions**

In `musicvid/pipeline/video_animator.py`, update `_submit_animation` (line 52-57):

Replace:
```python
    resp = requests.post(
        f"{RUNWAY_API_BASE}/v1/image_to_video",
        json=payload,
        headers=_get_headers(),
    )
    resp.raise_for_status()
```

With:
```python
    resp = requests.post(
        f"{RUNWAY_API_BASE}/v1/image_to_video",
        json=payload,
        headers=_get_headers(),
    )
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(f"Runway error {resp.status_code}: {resp.text}")
        raise
```

Apply the same pattern to `_submit_text_to_video` (line 74-79):

Replace:
```python
    resp = requests.post(
        f"{RUNWAY_API_BASE}/v1/image_to_video",
        json=payload,
        headers=_get_headers(),
    )
    resp.raise_for_status()
```

With:
```python
    resp = requests.post(
        f"{RUNWAY_API_BASE}/v1/image_to_video",
        json=payload,
        headers=_get_headers(),
    )
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(f"Runway error {resp.status_code}: {resp.text}")
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_video_animator.py::TestRunwayErrorLogging -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to ensure no regressions**

Run: `python3 -m pytest tests/test_video_animator.py tests/test_lyrics_parser.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/video_animator.py tests/test_video_animator.py
git commit -m "feat(runway): log API error body before re-raising HTTPError"
```
