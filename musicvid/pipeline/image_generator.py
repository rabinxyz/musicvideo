"""Stage 3 (AI mode): Generate images with multiple providers."""

import os
from pathlib import Path

import fal_client
import openai
import requests
from tenacity import retry, stop_after_attempt, wait_exponential


NEGATIVE_PROMPT = (
    "catholic church interior, religious figures, icon, stained glass with people, "
    "cross with body crucifix, statue figurine, rosary prayer beads, altar tabernacle, "
    "monastery nun monk pope bishop, cathedral chapel shrine, byzantine painting, "
    "sacred heart with thorns, watermark text logo, ugly blurry low quality, nsfw"
)

FLUX_MODELS = {
    "flux-dev": "fal-ai/flux/dev",
    "flux-pro": "fal-ai/flux-pro",
    "schnell": "fal-ai/flux/schnell",
}

FLUX_STEPS = {
    "flux-dev": 28,
    "flux-pro": 28,
    "schnell": 4,
}


def _detect_provider(requested):
    """Validate that the API key for the requested provider is available."""
    if requested in FLUX_MODELS:
        if not os.environ.get("FAL_KEY", ""):
            raise EnvironmentError(
                "FAL_KEY not set. Register at https://fal.ai for free $10 credits, "
                "then export FAL_KEY or add to .env file."
            )
    elif requested == "dalle":
        if not os.environ.get("OPENAI_API_KEY", ""):
            raise EnvironmentError(
                "OPENAI_API_KEY not set. Export it or add to .env file."
            )
    else:
        raise ValueError(f"Unknown provider: {requested}. Choose from: flux-dev, flux-pro, schnell, dalle")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _generate_flux(prompt, model_id, output_path, num_steps):
    """Call fal.ai Flux API to generate a single image."""
    result = fal_client.run(
        model_id,
        arguments={
            "prompt": prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "image_size": {"width": 1280, "height": 720},
            "num_inference_steps": num_steps,
            "guidance_scale": 3.5,
            "num_images": 1,
            "output_format": "jpeg",
        },
    )
    image_url = result["images"][0]["url"]
    response = requests.get(image_url)
    response.raise_for_status()
    Path(output_path).write_bytes(response.content)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _generate_dalle(client, prompt):
    """Call DALL-E 3 to generate a single image."""
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url


def generate_images(scene_plan, output_dir, provider="flux-dev"):
    """Generate one image per scene using the specified provider.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save generated images.
        provider: One of flux-dev, flux-pro, schnell, dalle.

    Returns:
        list of image file paths in scene order.
    """
    _detect_provider(provider)

    scenes = scene_plan.get("scenes", [])
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    image_paths = []

    if provider == "dalle":
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        for i, scene in enumerate(scenes):
            visual_prompt = scene.get("visual_prompt", "nature landscape")
            full_prompt = f"{visual_prompt}, cinematic 16:9, photorealistic, high quality"

            image_url = _generate_dalle(client, full_prompt)

            dest = output_path / f"scene_{i:03d}.jpg"
            resp = requests.get(image_url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            image_paths.append(str(dest))
    else:
        model_id = FLUX_MODELS[provider]
        num_steps = FLUX_STEPS[provider]
        for i, scene in enumerate(scenes):
            visual_prompt = scene.get("visual_prompt", "nature landscape")
            dest = output_path / f"scene_{i:03d}.jpg"

            _generate_flux(visual_prompt, model_id, str(dest), num_steps)
            image_paths.append(str(dest))

    return image_paths
