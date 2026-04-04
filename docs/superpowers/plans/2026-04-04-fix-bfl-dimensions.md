# Fix BFL API Dimensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change BFL API image dimensions from 1280x720 (invalid) to 1024x768 (valid) to fix 422 errors from flux-dev.

**Architecture:** Single-line change in `_submit_task` payload in `musicvid/pipeline/image_generator.py`. Test verifying the submitted payload dimensions must also be updated to match.

**Tech Stack:** Python 3.11+, requests, pytest, unittest.mock

---

### Task 1: Fix dimensions in image_generator.py

**Files:**
- Modify: `musicvid/pipeline/image_generator.py:60-61`
- Test: `tests/test_image_generator.py`

- [ ] **Step 1: Write a failing test that asserts the correct dimensions**

Search for existing test that checks `width`/`height` in the POST payload. If present, update it; if absent, add it.

```python
# In tests/test_image_generator.py, inside TestBFLFlowSubmitPollDownload
# (or whichever class tests _submit_task / generate_images)

@patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
@patch("musicvid.pipeline.image_generator.requests")
def test_submit_uses_correct_dimensions(self, mock_requests):
    mock_requests.post.return_value = _make_post_response()
    from musicvid.pipeline.image_generator import _submit_task
    _submit_task("flux-dev", "test prompt")
    _, kwargs = mock_requests.post.call_args
    payload = kwargs["json"]
    assert payload["width"] == 1024
    assert payload["height"] == 768
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_image_generator.py::TestBFLFlowSubmitPollDownload::test_submit_uses_correct_dimensions -v
```

Expected: FAIL — `assert 1280 == 1024` (or test not found yet)

- [ ] **Step 3: Fix dimensions in image_generator.py**

In `musicvid/pipeline/image_generator.py`, change lines 59-61:

```python
    payload = {
        "prompt": prompt,
        "width": 1024,
        "height": 768,
    }
```

- [ ] **Step 4: Run the new test to verify it passes**

```bash
python3 -m pytest tests/test_image_generator.py::TestBFLFlowSubmitPollDownload::test_submit_uses_correct_dimensions -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
python3 -m pytest tests/ -v
```

Expected: All tests pass (80 tests).

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/image_generator.py tests/test_image_generator.py
git commit -m "fix: change BFL image dimensions from 1280x720 to 1024x768 to fix 422 errors"
```
