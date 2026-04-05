"""Runway Gen-4 image-to-video animation module."""

import base64
import os
import time
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception


RUNWAY_API_BASE = "https://api.dev.runwayml.com"
RUNWAY_API_VERSION = "2024-11-06"
POLL_INTERVAL = 3
POLL_TIMEOUT = 300


def _is_retryable(exc):
    """Return True for network errors and 5xx responses (retryable)."""
    if isinstance(exc, requests.exceptions.ConnectionError):
        return True
    if isinstance(exc, requests.exceptions.Timeout):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


def _get_headers():
    """Return auth headers for Runway API."""
    return {
        "Authorization": f"Bearer {os.environ.get('RUNWAY_API_KEY', '')}",
        "Content-Type": "application/json",
        "X-Runway-Version": RUNWAY_API_VERSION,
    }


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_retryable),
)
def _submit_animation(image_b64, motion_prompt, duration):
    """POST to Runway API to start image-to-video task. Returns task_id."""
    payload = {
        "model": "gen4.5",
        "promptImage": image_b64,
        "promptText": motion_prompt,
        "duration": duration,
        "ratio": "1280:720",
    }
    resp = requests.post(
        f"{RUNWAY_API_BASE}/v1/image_to_video",
        json=payload,
        headers=_get_headers(),
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _poll_animation(task_id):
    """Poll until task SUCCEEDED or FAILED/CANCELLED or timeout."""
    start = time.monotonic()
    while time.monotonic() - start < POLL_TIMEOUT:
        resp = requests.get(
            f"{RUNWAY_API_BASE}/v1/tasks/{task_id}",
            headers=_get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "SUCCEEDED":
            return data["output"][0]["url"]
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"Runway task {task_id} failed with status: {status}")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Runway animation timed out after {POLL_TIMEOUT}s")


def _download_video(url, output_path):
    """Download video stream from URL to output_path."""
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def animate_image(image_path, motion_prompt, duration=5, output_path=None):
    """Animate a still image using Runway Gen-4 image-to-video API.

    Args:
        image_path: Path to the source image (.jpg or .png).
        motion_prompt: Text describing the desired camera/scene motion.
        duration: Video duration in seconds (default 5).
        output_path: Path to write output .mp4. Required.

    Returns:
        str: Path to the generated .mp4 file.

    Raises:
        RuntimeError: If RUNWAY_API_KEY not set or Runway task fails.
        TimeoutError: If Runway API does not respond within 300s.
    """
    if not os.environ.get("RUNWAY_API_KEY"):
        raise RuntimeError(
            "RUNWAY_API_KEY not set. Get a key from app.runwayml.com → Settings → API Keys"
        )

    if output_path and Path(output_path).exists():
        return str(output_path)

    image_bytes = Path(image_path).read_bytes()
    ext = Path(image_path).suffix.lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    image_b64 = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"

    task_id = _submit_animation(image_b64, motion_prompt, duration)
    video_url = _poll_animation(task_id)
    _download_video(video_url, output_path)
    return str(output_path)
