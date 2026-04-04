"""Stage 3 (AI mode): Generate images with DALL-E 3."""

import os
from pathlib import Path

import openai
import requests
from tenacity import retry, stop_after_attempt, wait_exponential


PROTESTANT_DISCLAIMER = (
    "Protestant Christian aesthetic, no religious figures, "
    "no Catholic symbols, no rosary, no stained glass with figures, "
    "no crucifix, no Madonna, no saints, no monks, no papal imagery, "
    "no incense burner, no tabernacle, no confessional, "
    "no Byzantine icons, cinematic 16:9, photorealistic, high quality"
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _generate_image(client, prompt):
    """Call DALL-E 3 to generate a single image."""
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url


def generate_images(scene_plan, output_dir):
    """Generate one DALL-E 3 image per scene.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save generated images.

    Returns:
        list of image file paths in scene order.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY not set. Export it or add to .env file."
        )

    client = openai.OpenAI(api_key=api_key)
    scenes = scene_plan.get("scenes", [])
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    image_paths = []

    for i, scene in enumerate(scenes):
        visual_prompt = scene.get("visual_prompt", "nature landscape")
        full_prompt = f"{visual_prompt}, {PROTESTANT_DISCLAIMER}"

        image_url = _generate_image(client, full_prompt)

        dest = output_path / f"scene_{i:03d}.png"
        response = requests.get(image_url)
        response.raise_for_status()
        dest.write_bytes(response.content)

        image_paths.append(str(dest))

    return image_paths
