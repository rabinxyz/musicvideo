"""Stage 3 (AI mode): Generate images via Black Forest Labs API."""

import os
import time
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

BFL_BASE_URL = "https://api.bfl.ai"

BFL_MODELS = {
    "flux-dev": "flux-dev",
    "flux-pro": "flux-pro-1.1",
    "flux-schnell": "flux-2-klein-4b",
}

POLL_INTERVAL = 1.5
POLL_TIMEOUT = 120

DOCUMENTARY_SUFFIX = (
    "documentary photography style, authentic and unposed, "
    "natural available light only, film grain, natural color grading, "
    "real location feel, photojournalism aesthetic"
)

NEGATIVE_CONTEXT = (
    "no Catholic imagery, no religious figures, no rosary, no crucifix, "
    "no saints, natural light not artificial, authentic not staged, "
    "film grain not oversaturated"
)


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
def _submit_task(model_name, prompt, width=1360, height=768):
    """Submit an image generation task to BFL API. Returns (task_id, polling_url)."""
    url = f"{BFL_BASE_URL}/v1/{model_name}"
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
    }
    resp = requests.post(url, json=payload, headers=_get_headers())
    resp.raise_for_status()
    data = resp.json()
    return data["id"], data["polling_url"]


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


def _download_image(image_url, output_path):
    """Download image from URL to local path."""
    resp = requests.get(image_url)
    resp.raise_for_status()
    Path(output_path).write_bytes(resp.content)


def generate_images(scene_plan, output_dir, provider="flux-pro", platform=None):
    """Generate one image per scene using BFL API.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save generated images.
        provider: One of flux-dev, flux-pro, flux-schnell. Default: flux-pro (flux-pro-1.1).
        platform: Optional platform hint — "reels" generates native 9:16 (768x1360).

    Returns:
        list of image file paths in scene order.
    """
    _detect_provider(provider)

    model_name = BFL_MODELS[provider]
    scenes = scene_plan.get("scenes", [])
    master_style = scene_plan.get("master_style", "")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    is_portrait = platform in ("reels", "shorts")
    img_w, img_h = (768, 1360) if is_portrait else (1360, 768)
    orientation_hint = "portrait 9:16" if is_portrait else "cinematic 16:9"

    image_paths = []
    total = len(scenes)

    for i, scene in enumerate(scenes):
        visual_prompt = scene.get("visual_prompt", "nature landscape")
        if master_style:
            full_prompt = f"{visual_prompt}, {master_style}, {orientation_hint}, {DOCUMENTARY_SUFFIX}, {NEGATIVE_CONTEXT}"
        else:
            full_prompt = f"{visual_prompt}, {orientation_hint}, {DOCUMENTARY_SUFFIX}, {NEGATIVE_CONTEXT}"

        task_id, polling_url = _submit_task(model_name, full_prompt, width=img_w, height=img_h)
        image_url = _poll_result(polling_url)

        dest = output_path / f"scene_{i:03d}.jpg"
        _download_image(image_url, str(dest))
        image_paths.append(str(dest))
        print(f"Scena {i + 1}/{total} gotowa")

    return image_paths


def generate_single_image(prompt, output_path, provider="flux-pro"):
    """Generate a single image using BFL API.

    Args:
        prompt: Visual description string (without suffix — suffix is added here).
        output_path: Path to save result .jpg.
        provider: One of flux-dev, flux-pro, flux-schnell.

    Returns:
        str: output_path after download.
    """
    _detect_provider(provider)
    model_name = BFL_MODELS[provider]

    if Path(output_path).exists():
        return str(output_path)

    full_prompt = f"{prompt}, cinematic 16:9, {DOCUMENTARY_SUFFIX}, {NEGATIVE_CONTEXT}"
    task_id, polling_url = _submit_task(model_name, full_prompt, width=1024, height=768)
    image_url = _poll_result(polling_url)
    _download_image(image_url, output_path)
    return str(output_path)
