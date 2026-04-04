# BFL Image Generator Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fal-client Flux integration with direct HTTP calls to Black Forest Labs' official API (bfl.ai), removing the fal-client and DALL-E dependencies.

**Architecture:** The image_generator module switches from fal_client.run() to a three-step HTTP flow: POST task → poll for result → download image. The CLI drops the `dalle` provider option, keeping only `flux-dev`, `flux-pro`, and `schnell`. All Flux calls go through BFL's API at `https://api.bfl.ai` with `X-Key` header auth.

**Tech Stack:** Python requests, tenacity (retry), BFL REST API

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `musicvid/pipeline/image_generator.py` | **Rewrite** | BFL API client: submit task, poll result, download image, retry logic |
| `tests/test_image_generator.py` | **Rewrite** | Tests for BFL flow, polling, timeout, errors, retry |
| `musicvid/musicvid.py` | **Modify** (line 33) | Remove `dalle` from `--provider` choices |
| `musicvid/requirements.txt` | **Modify** | Remove `fal-client` and `openai` lines |
| `musicvid/.env.example` | **Rewrite** | Replace `FAL_KEY`/`OPENAI_API_KEY` with `BFL_API_KEY` |

---

### Task 1: Rewrite image_generator.py with BFL API

**Files:**
- Rewrite: `musicvid/pipeline/image_generator.py`

- [ ] **Step 1: Write the new image_generator.py**

Replace the entire file with:

```python
"""Stage 3 (AI mode): Generate images via Black Forest Labs API."""

import os
import time
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

BFL_BASE_URL = "https://api.bfl.ai"

BFL_MODELS = {
    "flux-dev": "flux-dev",
    "flux-pro": "flux-pro1.1",
    "schnell": "flux-schnell",
}

POLL_INTERVAL = 1.5
POLL_TIMEOUT = 120


def _is_retryable(exc):
    """Return True for network errors and 5xx responses (retryable)."""
    if isinstance(exc, requests.exceptions.ConnectionError):
        return True
    if isinstance(exc, requests.exceptions.Timeout):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


def _detect_provider(requested):
    """Validate that BFL_API_KEY is set and provider is known."""
    if requested not in BFL_MODELS:
        available = ", ".join(BFL_MODELS.keys())
        raise ValueError(f"Unknown provider: {requested}. Choose from: {available}")
    if not os.environ.get("BFL_API_KEY", ""):
        raise EnvironmentError(
            "BFL_API_KEY not set. Register at https://bfl.ai/dashboard for an API key, "
            "then export BFL_API_KEY or add to .env file."
        )


def _get_headers():
    """Return auth headers for BFL API."""
    return {"X-Key": os.environ["BFL_API_KEY"]}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_retryable),
)
def _submit_task(model_name, prompt):
    """Submit an image generation task to BFL API. Returns task ID."""
    url = f"{BFL_BASE_URL}/v1/{model_name}"
    payload = {
        "prompt": prompt,
        "width": 1280,
        "height": 720,
        "output_format": "jpeg",
    }
    resp = requests.post(url, json=payload, headers=_get_headers())
    resp.raise_for_status()
    return resp.json()["id"]


def _poll_result(task_id):
    """Poll BFL API until task is Ready or timeout (120s)."""
    url = f"{BFL_BASE_URL}/v1/get_result"
    start = time.monotonic()
    while time.monotonic() - start < POLL_TIMEOUT:
        resp = requests.get(url, params={"id": task_id}, headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        if data["status"] == "Ready":
            return data["result"]["sample"]
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(
        f"BFL task {task_id} did not complete within {POLL_TIMEOUT} seconds."
    )


def _download_image(image_url, output_path):
    """Download image from URL to local path."""
    resp = requests.get(image_url)
    resp.raise_for_status()
    Path(output_path).write_bytes(resp.content)


def generate_images(scene_plan, output_dir, provider="flux-dev"):
    """Generate one image per scene using BFL API.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save generated images.
        provider: One of flux-dev, flux-pro, schnell.

    Returns:
        list of image file paths in scene order.
    """
    _detect_provider(provider)

    model_name = BFL_MODELS[provider]
    scenes = scene_plan.get("scenes", [])
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    image_paths = []
    total = len(scenes)

    for i, scene in enumerate(scenes):
        visual_prompt = scene.get("visual_prompt", "nature landscape")
        full_prompt = f"{visual_prompt}, cinematic 16:9, photorealistic, high quality"

        task_id = _submit_task(model_name, full_prompt)
        image_url = _poll_result(task_id)

        dest = output_path / f"scene_{i:03d}.jpg"
        _download_image(image_url, str(dest))
        image_paths.append(str(dest))
        print(f"Scena {i + 1}/{total} gotowa")

    return image_paths
```

- [ ] **Step 2: Verify the file was written correctly**

Run: `python3 -c "from musicvid.pipeline.image_generator import generate_images, BFL_MODELS; print('OK', list(BFL_MODELS.keys()))"`

Expected: `OK ['flux-dev', 'flux-pro', 'schnell']`

- [ ] **Step 3: Commit**

```bash
git add musicvid/pipeline/image_generator.py
git commit -m "feat: rewrite image_generator to use BFL API instead of fal-client"
```

---

### Task 2: Rewrite test_image_generator.py for BFL API

**Files:**
- Rewrite: `tests/test_image_generator.py`

- [ ] **Step 1: Write the new test file**

Replace the entire file with:

```python
"""Tests for BFL API image generator pipeline stage."""

import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest
import requests
from tenacity import wait_none


BANNED_WORDS = [
    "catholic", "rosary", "madonna", "saint", "cross with figure",
    "stained glass", "church interior", "religious", "icon", "byzantine",
    "papal", "crucifix", "prayer beads", "maria", "monastery", "monk",
    "nun", "cathedral", "chapel", "shrine", "altar", "candle altar",
    "sacred heart", "ihs",
]


class TestBFLFlowSubmitPollDownload:
    """Tests for the full BFL submit → poll → download flow."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_full_flow_returns_correct_paths(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "mountain sunrise golden light", "start": 0.0, "end": 5.0},
                {"visual_prompt": "calm water reflection", "start": 5.0, "end": 10.0},
            ]
        }

        # Mock POST (submit) → returns task id
        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"id": "task-123"}
        mock_post_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_post_resp

        # Mock GET (poll) → Ready immediately, then download
        mock_poll_resp = MagicMock()
        mock_poll_resp.json.return_value = {"status": "Ready", "result": {"sample": "https://example.com/image.jpg"}}
        mock_poll_resp.raise_for_status = MagicMock()

        mock_download_resp = MagicMock()
        mock_download_resp.content = b"fake jpeg data"
        mock_download_resp.raise_for_status = MagicMock()

        mock_requests.get.side_effect = [
            mock_poll_resp, mock_download_resp,  # scene 0
            mock_poll_resp, mock_download_resp,  # scene 1
        ]

        result = generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        assert len(result) == 2
        assert all(p.endswith(".jpg") for p in result)
        assert all(Path(p).exists() for p in result)

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_submit_uses_correct_model_and_params(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test prompt", "start": 0.0, "end": 5.0}]}

        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"id": "task-123"}
        mock_post_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_post_resp

        mock_poll_resp = MagicMock()
        mock_poll_resp.json.return_value = {"status": "Ready", "result": {"sample": "https://example.com/img.jpg"}}
        mock_poll_resp.raise_for_status = MagicMock()

        mock_download_resp = MagicMock()
        mock_download_resp.content = b"fake jpeg"
        mock_download_resp.raise_for_status = MagicMock()

        mock_requests.get.side_effect = [mock_poll_resp, mock_download_resp]

        generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        post_call = mock_requests.post.call_args
        assert "/v1/flux-dev" in post_call[0][0]
        payload = post_call[1]["json"]
        assert payload["width"] == 1280
        assert payload["height"] == 720
        assert payload["output_format"] == "jpeg"
        assert "test prompt" in payload["prompt"]

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_flux_pro_uses_correct_model(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"id": "task-456"}
        mock_post_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_post_resp

        mock_poll_resp = MagicMock()
        mock_poll_resp.json.return_value = {"status": "Ready", "result": {"sample": "https://example.com/img.jpg"}}
        mock_poll_resp.raise_for_status = MagicMock()

        mock_download_resp = MagicMock()
        mock_download_resp.content = b"fake jpeg"
        mock_download_resp.raise_for_status = MagicMock()

        mock_requests.get.side_effect = [mock_poll_resp, mock_download_resp]

        generate_images(scene_plan, str(tmp_path), provider="flux-pro")

        assert "/v1/flux-pro1.1" in mock_requests.post.call_args[0][0]

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_schnell_uses_correct_model(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"id": "task-789"}
        mock_post_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_post_resp

        mock_poll_resp = MagicMock()
        mock_poll_resp.json.return_value = {"status": "Ready", "result": {"sample": "https://example.com/img.jpg"}}
        mock_poll_resp.raise_for_status = MagicMock()

        mock_download_resp = MagicMock()
        mock_download_resp.content = b"fake jpeg"
        mock_download_resp.raise_for_status = MagicMock()

        mock_requests.get.side_effect = [mock_poll_resp, mock_download_resp]

        generate_images(scene_plan, str(tmp_path), provider="schnell")

        assert "/v1/flux-schnell" in mock_requests.post.call_args[0][0]

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_auth_header_sent(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"id": "task-123"}
        mock_post_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_post_resp

        mock_poll_resp = MagicMock()
        mock_poll_resp.json.return_value = {"status": "Ready", "result": {"sample": "https://example.com/img.jpg"}}
        mock_poll_resp.raise_for_status = MagicMock()

        mock_download_resp = MagicMock()
        mock_download_resp.content = b"fake jpeg"
        mock_download_resp.raise_for_status = MagicMock()

        mock_requests.get.side_effect = [mock_poll_resp, mock_download_resp]

        generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        headers = mock_requests.post.call_args[1]["headers"]
        assert headers["X-Key"] == "test-key"


class TestPolling:
    """Tests for BFL polling behavior."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.time")
    @patch("musicvid.pipeline.image_generator.requests")
    def test_polling_with_pending_before_ready(self, mock_requests, mock_time, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"id": "task-123"}
        mock_post_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_post_resp

        # Simulate time progression under timeout
        mock_time.monotonic.side_effect = [0, 0, 2, 4, 6]
        mock_time.sleep = MagicMock()

        pending_resp = MagicMock()
        pending_resp.json.return_value = {"status": "Pending"}
        pending_resp.raise_for_status = MagicMock()

        ready_resp = MagicMock()
        ready_resp.json.return_value = {"status": "Ready", "result": {"sample": "https://example.com/img.jpg"}}
        ready_resp.raise_for_status = MagicMock()

        download_resp = MagicMock()
        download_resp.content = b"fake jpeg"
        download_resp.raise_for_status = MagicMock()

        mock_requests.get.side_effect = [pending_resp, pending_resp, ready_resp, download_resp]

        result = generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        assert len(result) == 1
        assert mock_time.sleep.call_count == 2

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.time")
    @patch("musicvid.pipeline.image_generator.requests")
    def test_polling_timeout_raises_error(self, mock_requests, mock_time, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"id": "task-timeout"}
        mock_post_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_post_resp

        # Time jumps past 120s
        mock_time.monotonic.side_effect = [0, 0, 130]
        mock_time.sleep = MagicMock()

        pending_resp = MagicMock()
        pending_resp.json.return_value = {"status": "Pending"}
        pending_resp.raise_for_status = MagicMock()

        mock_requests.get.return_value = pending_resp

        with pytest.raises(TimeoutError, match="did not complete"):
            generate_images(scene_plan, str(tmp_path), provider="flux-dev")


class TestProviderDetection:
    """Tests for provider validation and error messages."""

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_error_when_bfl_key_missing(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        with pytest.raises(EnvironmentError, match="BFL_API_KEY"):
            generate_images(scene_plan, str(tmp_path), provider="flux-dev")

    def test_raises_error_for_unknown_provider(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        with pytest.raises(ValueError, match="Unknown provider"):
            generate_images(scene_plan, str(tmp_path), provider="midjourney")

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_default_provider_is_flux_dev(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"id": "task-123"}
        mock_post_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_post_resp

        mock_poll_resp = MagicMock()
        mock_poll_resp.json.return_value = {"status": "Ready", "result": {"sample": "https://example.com/img.jpg"}}
        mock_poll_resp.raise_for_status = MagicMock()

        mock_download_resp = MagicMock()
        mock_download_resp.content = b"fake jpeg"
        mock_download_resp.raise_for_status = MagicMock()

        mock_requests.get.side_effect = [mock_poll_resp, mock_download_resp]

        generate_images(scene_plan, str(tmp_path))

        assert "/v1/flux-dev" in mock_requests.post.call_args[0][0]


class TestRetryBehavior:
    """Tests for retry on 5xx errors and no retry on 4xx."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_retry_on_5xx_submit(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, _submit_task

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        error_resp = MagicMock()
        error_resp.status_code = 500
        error_5xx = requests.HTTPError(response=error_resp)

        success_post = MagicMock()
        success_post.json.return_value = {"id": "task-retry"}
        success_post.raise_for_status = MagicMock()

        mock_requests.post.side_effect = [error_5xx, error_5xx, success_post]
        mock_requests.exceptions = requests.exceptions
        mock_requests.HTTPError = requests.HTTPError

        mock_poll_resp = MagicMock()
        mock_poll_resp.json.return_value = {"status": "Ready", "result": {"sample": "https://example.com/img.jpg"}}
        mock_poll_resp.raise_for_status = MagicMock()

        mock_download_resp = MagicMock()
        mock_download_resp.content = b"fake jpeg"
        mock_download_resp.raise_for_status = MagicMock()

        mock_requests.get.side_effect = [mock_poll_resp, mock_download_resp]

        original_wait = _submit_task.retry.wait
        _submit_task.retry.wait = wait_none()
        try:
            result = generate_images(scene_plan, str(tmp_path), provider="flux-dev")
        finally:
            _submit_task.retry.wait = original_wait

        assert len(result) == 1
        assert mock_requests.post.call_count == 3

    @patch.dict(os.environ, {"BFL_API_KEY": "bad-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_no_retry_on_4xx(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, _submit_task

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        error_resp = MagicMock()
        error_resp.status_code = 401
        error_resp.raise_for_status.side_effect = requests.HTTPError(response=error_resp)

        mock_requests.post.return_value = error_resp
        mock_requests.exceptions = requests.exceptions
        mock_requests.HTTPError = requests.HTTPError

        original_wait = _submit_task.retry.wait
        _submit_task.retry.wait = wait_none()
        try:
            with pytest.raises(requests.HTTPError):
                generate_images(scene_plan, str(tmp_path), provider="flux-dev")
        finally:
            _submit_task.retry.wait = original_wait

        assert mock_requests.post.call_count == 1


class TestBannedWords:
    """Tests that banned words never appear in prompts sent to BFL API."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_prompt_has_no_banned_words(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "golden wheat fields, warm light, peaceful", "start": 0.0, "end": 5.0},
                {"visual_prompt": "mountain peaks, morning mist, majestic", "start": 5.0, "end": 10.0},
            ]
        }

        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"id": "task-123"}
        mock_post_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_post_resp

        mock_poll_resp = MagicMock()
        mock_poll_resp.json.return_value = {"status": "Ready", "result": {"sample": "https://example.com/img.jpg"}}
        mock_poll_resp.raise_for_status = MagicMock()

        mock_download_resp = MagicMock()
        mock_download_resp.content = b"fake jpeg"
        mock_download_resp.raise_for_status = MagicMock()

        mock_requests.get.side_effect = [
            mock_poll_resp, mock_download_resp,
            mock_poll_resp, mock_download_resp,
        ]

        generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        for c in mock_requests.post.call_args_list:
            prompt = c[1]["json"]["prompt"].lower()
            for word in BANNED_WORDS:
                assert word not in prompt, f"Banned word '{word}' found in prompt: {prompt}"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_image_generator.py -v`

Expected: All tests pass (approximately 14 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_image_generator.py
git commit -m "test: rewrite image_generator tests for BFL API"
```

---

### Task 3: Update CLI, requirements, and env example

**Files:**
- Modify: `musicvid/musicvid.py` (line 33)
- Modify: `musicvid/requirements.txt` (lines 2-3)
- Rewrite: `musicvid/.env.example`

- [ ] **Step 1: Remove `dalle` from CLI provider choices**

In `musicvid/musicvid.py`, change line 33 from:

```python
@click.option("--provider", type=click.Choice(["dalle", "flux-dev", "flux-pro", "schnell"]), default="flux-dev", help="Image provider for --mode ai.")
```

to:

```python
@click.option("--provider", type=click.Choice(["flux-dev", "flux-pro", "schnell"]), default="flux-dev", help="Image provider for --mode ai.")
```

- [ ] **Step 2: Remove fal-client and openai from requirements.txt**

Remove these two lines from `musicvid/requirements.txt`:
```
openai>=1.50.0
fal-client>=0.10.0
```

Keep `openai-whisper>=20231117` (still needed for audio transcription).

- [ ] **Step 3: Update .env.example**

Replace `musicvid/.env.example` with:

```
ANTHROPIC_API_KEY=your_key_here
PEXELS_API_KEY=your_key_here
BFL_API_KEY=your_key_here        # bfl.ai — flux-dev, flux-pro, schnell (get key at https://bfl.ai/dashboard)
```

- [ ] **Step 4: Run all tests to verify nothing is broken**

Run: `python3 -m pytest tests/ -v`

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py musicvid/requirements.txt musicvid/.env.example
git commit -m "chore: remove fal-client/openai deps, update CLI and env for BFL API"
```
