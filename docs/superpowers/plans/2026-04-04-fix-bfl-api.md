# Fix BFL API (422 Error) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three bugs in the BFL API integration that cause 422 Unprocessable Entity errors: wrong endpoint names, wrong polling URL, and invalid request parameters.

**Architecture:** Single-file fix to `musicvid/pipeline/image_generator.py` — update the model map, change `_submit_task` to return `(task_id, polling_url)`, change `_poll_result` to accept `polling_url` instead of `task_id`, remove unsupported params. Update tests to match new flow.

**Tech Stack:** Python, requests, tenacity, pytest, unittest.mock

---

### Task 1: Update tests for new BFL API flow

**Files:**
- Modify: `tests/test_image_generator.py`

- [ ] **Step 1: Update mock helper `_make_post_response` to return polling_url**

Replace the existing helper:

```python
def _make_post_response(task_id="task-123"):
    """Create a mock POST response returning a task ID and polling URL."""
    resp = MagicMock()
    resp.json.return_value = {
        "id": task_id,
        "polling_url": f"https://api.bfl.ai/v1/get_result?id={task_id}",
    }
    return resp
```

- [ ] **Step 2: Update `test_submit_uses_correct_model_and_params` to assert no `output_format`**

Replace the assertion block in `test_submit_uses_correct_model_and_params`:

```python
    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_submit_uses_correct_model_and_params(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response()
        mock_requests.get.side_effect = [
            _make_poll_response(),
            _make_download_response(),
        ]

        generate_images(ONE_SCENE_PLAN, str(tmp_path), provider="flux-dev")

        post_call = mock_requests.post.call_args
        url = post_call[0][0] if post_call[0] else post_call[1].get("url", "")
        assert "/v1/flux-dev" in url

        payload = post_call[1]["json"]
        assert payload["width"] == 1280
        assert payload["height"] == 720
        assert "prompt" in payload
        assert "output_format" not in payload
        assert "safety_tolerance" not in payload
        assert "prompt_upsampling" not in payload
```

- [ ] **Step 3: Update `test_flux_pro_uses_correct_model` to assert `/v1/flux-pro-1.1`**

```python
    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_flux_pro_uses_correct_model(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response()
        mock_requests.get.side_effect = [
            _make_poll_response(),
            _make_download_response(),
        ]

        generate_images(ONE_SCENE_PLAN, str(tmp_path), provider="flux-pro")

        url = mock_requests.post.call_args[0][0]
        assert "/v1/flux-pro-1.1" in url
```

- [ ] **Step 4: Update `test_schnell_uses_correct_model` to assert `/v1/flux-2-klein-4b`**

```python
    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_schnell_uses_correct_model(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response()
        mock_requests.get.side_effect = [
            _make_poll_response(),
            _make_download_response(),
        ]

        generate_images(ONE_SCENE_PLAN, str(tmp_path), provider="flux-schnell")

        url = mock_requests.post.call_args[0][0]
        assert "/v1/flux-2-klein-4b" in url
```

- [ ] **Step 5: Update `test_polling_with_pending_before_ready` to use polling_url**

```python
    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.time")
    @patch("musicvid.pipeline.image_generator.requests")
    def test_polling_with_pending_before_ready(self, mock_requests, mock_time, tmp_path):
        from musicvid.pipeline.image_generator import _poll_result

        mock_time.monotonic.side_effect = [0, 1.5, 3.0, 4.5]
        mock_time.sleep = MagicMock()

        mock_requests.get.side_effect = [
            _make_poll_response("Pending"),
            _make_poll_response("Pending"),
            _make_poll_response("Ready", "https://bfl.ai/result.jpg"),
        ]

        result = _poll_result("https://api.bfl.ai/v1/get_result?id=task-abc")

        assert result == "https://bfl.ai/result.jpg"
        assert mock_requests.get.call_count == 3
        assert mock_time.sleep.call_count == 2
```

- [ ] **Step 6: Update `test_polling_timeout_raises_error` to use polling_url**

```python
    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.time")
    @patch("musicvid.pipeline.image_generator.requests")
    def test_polling_timeout_raises_error(self, mock_requests, mock_time, tmp_path):
        from musicvid.pipeline.image_generator import _poll_result

        mock_time.monotonic.side_effect = [0, 121]
        mock_time.sleep = MagicMock()

        with pytest.raises(TimeoutError):
            _poll_result("https://api.bfl.ai/v1/get_result?id=task-timeout")
```

- [ ] **Step 7: Update `test_full_flow_returns_correct_paths` — mock GET calls for polling use polling_url**

The full flow test already works with `mock_requests.get.side_effect` for both poll and download responses. The mock intercepts all `requests.get` calls regardless of URL, so the side_effect list remains:
```python
        mock_requests.get.side_effect = [
            _make_poll_response("Ready", "https://bfl.ai/img1.jpg"),
            _make_download_response(),
            _make_poll_response("Ready", "https://bfl.ai/img2.jpg"),
            _make_download_response(),
        ]
```
No change needed to this test body — the `_make_post_response` helper change in Step 1 already returns `polling_url`.

- [ ] **Step 8: Update retry test `test_retry_on_5xx_submit` to expect tuple return**

```python
    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_retry_on_5xx_submit(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import _submit_task

        mock_requests.exceptions = requests.exceptions
        mock_requests.HTTPError = requests.HTTPError

        error_resp = MagicMock()
        error_resp.status_code = 500
        error = requests.HTTPError(response=error_resp)

        success_resp = _make_post_response("task-ok")

        mock_requests.post.side_effect = [error, error, success_resp]

        original_wait = _submit_task.retry.wait
        _submit_task.retry.wait = wait_none()
        try:
            task_id, polling_url = _submit_task("flux-dev", "test prompt")
        finally:
            _submit_task.retry.wait = original_wait

        assert task_id == "task-ok"
        assert "task-ok" in polling_url
        assert mock_requests.post.call_count == 3
```

- [ ] **Step 9: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_image_generator.py -v`
Expected: Multiple failures (implementation not yet updated)

- [ ] **Step 10: Commit failing tests**

```bash
git add tests/test_image_generator.py
git commit -m "test: update BFL API tests for correct endpoints, polling_url, and params"
```

---

### Task 2: Fix BFL API implementation

**Files:**
- Modify: `musicvid/pipeline/image_generator.py:12-16` (BFL_MODELS)
- Modify: `musicvid/pipeline/image_generator.py:55-66` (_submit_task)
- Modify: `musicvid/pipeline/image_generator.py:69-82` (_poll_result)
- Modify: `musicvid/pipeline/image_generator.py:113-118` (generate_images loop)

- [ ] **Step 1: Fix BFL_MODELS mapping**

Replace lines 12-16:

```python
BFL_MODELS = {
    "flux-dev": "flux-dev",
    "flux-pro": "flux-pro-1.1",
    "flux-schnell": "flux-2-klein-4b",
}
```

- [ ] **Step 2: Fix `_submit_task` — remove `output_format`, return tuple `(task_id, polling_url)`**

Replace the `_submit_task` function:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_retryable),
)
def _submit_task(model_name, prompt):
    """Submit an image generation task to BFL API. Returns (task_id, polling_url)."""
    url = f"{BFL_BASE_URL}/v1/{model_name}"
    payload = {
        "prompt": prompt,
        "width": 1280,
        "height": 720,
    }
    resp = requests.post(url, json=payload, headers=_get_headers())
    resp.raise_for_status()
    data = resp.json()
    return data["id"], data["polling_url"]
```

- [ ] **Step 3: Fix `_poll_result` — accept `polling_url` instead of `task_id`**

Replace the `_poll_result` function:

```python
def _poll_result(polling_url):
    """Poll BFL API until task is Ready or timeout (120s)."""
    start = time.monotonic()
    while time.monotonic() - start < POLL_TIMEOUT:
        resp = requests.get(polling_url, headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        if data["status"] == "Ready":
            return data["result"]["sample"]
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(
        f"BFL task did not complete within {POLL_TIMEOUT} seconds."
    )
```

- [ ] **Step 4: Update `generate_images` to unpack tuple from `_submit_task`**

Replace lines 117-118 in the loop:

```python
        task_id, polling_url = _submit_task(model_name, full_prompt)
        image_url = _poll_result(polling_url)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_image_generator.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All 80+ tests PASS

- [ ] **Step 7: Commit implementation fix**

```bash
git add musicvid/pipeline/image_generator.py
git commit -m "fix: correct BFL API endpoints, polling flow, and request params"
```
