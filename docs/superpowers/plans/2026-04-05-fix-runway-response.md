# Fix Runway API Response Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `_poll_animation()` in `video_animator.py` to handle Runway Gen-4 API responses where `output` is a list of strings (URLs) instead of a list of dicts.

**Architecture:** The fix is a one-function change to `_poll_animation()` that detects the type of `output[0]` and extracts the URL accordingly. A debug print is added temporarily to confirm the actual API shape in production, then removed. Existing tests are updated and new tests for the string-list format are added.

**Tech Stack:** Python 3.11+, unittest.mock, pytest

---

### Task 1: Add tests for the new output format

**Files:**
- Modify: `tests/test_video_animator.py`

- [ ] **Step 1: Write a failing test for string-list output**

Add to `tests/test_video_animator.py` after the existing `_make_poll_response` helper:

```python
def _make_poll_response_str(status, video_url=None):
    """Runway response where output is a list of URL strings, not dicts."""
    resp = MagicMock()
    if status == "SUCCEEDED":
        resp.json.return_value = {"status": "SUCCEEDED", "output": [video_url]}
    else:
        resp.json.return_value = {"status": status}
    return resp
```

Then add this test class after `TestAnimateImage`:

```python
class TestPollAnimationOutputFormats:
    """Tests that _poll_animation handles both output formats from Runway API."""

    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_string_list_output(self, mock_time, mock_requests):
        from musicvid.pipeline.video_animator import _poll_animation

        mock_time.monotonic.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()
        mock_requests.get.return_value = _make_poll_response_str(
            "SUCCEEDED", "https://runway.ai/video.mp4"
        )

        url = _poll_animation("task-xyz")
        assert url == "https://runway.ai/video.mp4"

    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_dict_list_output(self, mock_time, mock_requests):
        from musicvid.pipeline.video_animator import _poll_animation

        mock_time.monotonic.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()
        mock_requests.get.return_value = _make_poll_response(
            "SUCCEEDED", "https://runway.ai/video.mp4"
        )

        url = _poll_animation("task-xyz")
        assert url == "https://runway.ai/video.mp4"

    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_unexpected_output_raises(self, mock_time, mock_requests):
        from musicvid.pipeline.video_animator import _poll_animation

        mock_time.monotonic.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()
        resp = MagicMock()
        resp.json.return_value = {"status": "SUCCEEDED", "output": []}
        mock_requests.get.return_value = resp

        with pytest.raises(RuntimeError, match="Unexpected output structure"):
            _poll_animation("task-xyz")
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_video_animator.py::TestPollAnimationOutputFormats -v
```

Expected: FAIL — `test_string_list_output` fails with `TypeError: string indices must be integers`; `test_unexpected_output_raises` fails because no `RuntimeError` is raised.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_video_animator.py
git commit -m "test: add failing tests for Runway string-list output format"
```

---

### Task 2: Fix `_poll_animation()` to handle both output formats

**Files:**
- Modify: `musicvid/pipeline/video_animator.py:61-77`

- [ ] **Step 1: Replace the URL extraction in `_poll_animation()`**

In `musicvid/pipeline/video_animator.py`, replace lines 72-73:

```python
        if status == "SUCCEEDED":
            return data["output"][0]["url"]
```

With:

```python
        if status == "SUCCEEDED":
            print(f"DEBUG Runway output: {data.get('output')}")
            output = data.get("output", [])
            if output:
                first = output[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict):
                    return first.get("url") or first.get("uri") or first.get("link")
            raise RuntimeError(f"Unexpected output structure: {output}")
```

- [ ] **Step 2: Run the new tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_video_animator.py::TestPollAnimationOutputFormats -v
```

Expected: 3/3 PASS

- [ ] **Step 3: Run the full test suite to confirm no regressions**

```bash
python3 -m pytest tests/test_video_animator.py -v
```

Expected: All existing tests plus 3 new tests PASS.

- [ ] **Step 4: Commit the fix**

```bash
git add musicvid/pipeline/video_animator.py
git commit -m "fix: handle Runway output as string list or dict list in _poll_animation"
```

---

### Task 3: Remove the debug print after confirming the fix

> Note: In autonomous/CI context, remove the debug print immediately since there is no production verification step.

**Files:**
- Modify: `musicvid/pipeline/video_animator.py`

- [ ] **Step 1: Remove the debug print line**

In `musicvid/pipeline/video_animator.py`, remove this line from `_poll_animation()`:

```python
            print(f"DEBUG Runway output: {data.get('output')}")
```

The function body after the change should be:

```python
        if status == "SUCCEEDED":
            output = data.get("output", [])
            if output:
                first = output[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict):
                    return first.get("url") or first.get("uri") or first.get("link")
            raise RuntimeError(f"Unexpected output structure: {output}")
```

- [ ] **Step 2: Run full test suite one final time**

```bash
python3 -m pytest tests/test_video_animator.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add musicvid/pipeline/video_animator.py
git commit -m "fix: remove debug print from _poll_animation"
```
