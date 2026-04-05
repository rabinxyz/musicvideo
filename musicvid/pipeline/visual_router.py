"""Per-scene visual source routing for hybrid asset generation."""

import os
import requests
from pathlib import Path

from musicvid.pipeline.stock_fetcher import fetch_video_by_query
from musicvid.pipeline.image_generator import generate_single_image
from musicvid.pipeline.video_animator import animate_image


class VisualRouter:
    """Routes each scene to the appropriate visual source API.

    Dispatch order by visual_source:
      TYPE_VIDEO_STOCK  → Pexels video (fetch_video_by_query)
      TYPE_PHOTO_STOCK  → Unsplash photo (requests + UNSPLASH_ACCESS_KEY)
      TYPE_AI           → BFL Flux image (generate_single_image)
      TYPE_ANIMATED     → BFL image + Runway Gen-4 video (generate_single_image + animate_image)

    Fallback hierarchy:
      TYPE_VIDEO_STOCK failure → simplified query → TYPE_PHOTO_STOCK → TYPE_AI
      TYPE_PHOTO_STOCK no key  → TYPE_AI
      TYPE_ANIMATED no key     → static TYPE_AI image (Ken Burns in assembler)
    """

    def __init__(self, cache_dir, provider="flux-pro"):
        self.cache_dir = Path(cache_dir)
        self.provider = provider

    def route(self, scene):
        """Dispatch scene to the correct API. Returns asset path or None."""
        source = scene.get("visual_source", "TYPE_AI")
        idx = scene["index"]
        duration = scene["end"] - scene["start"]

        if source == "TYPE_VIDEO_STOCK":
            return self._route_video_stock(scene, idx, duration)
        elif source == "TYPE_PHOTO_STOCK":
            return self._route_photo_stock(scene, idx)
        elif source == "TYPE_ANIMATED":
            return self._route_animated(scene, idx, duration)
        else:  # TYPE_AI (default)
            return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)

    # ------------------------------------------------------------------
    # Private dispatch methods
    # ------------------------------------------------------------------

    def _route_video_stock(self, scene, idx, duration):
        query = scene.get("search_query", "nature landscape")
        output_path = str(self.cache_dir / f"scene_{idx:03d}.mp4")

        result = fetch_video_by_query(query, duration, output_path)
        if result:
            return result

        # Simplified query fallback (first 2 words)
        simplified = " ".join(query.split()[:2])
        if simplified and simplified != query:
            result = fetch_video_by_query(simplified, duration, output_path)
            if result:
                return result

        print(f"  Fallback: scene {idx} TYPE_VIDEO_STOCK → TYPE_PHOTO_STOCK")
        return self._route_photo_stock(scene, idx)

    def _route_photo_stock(self, scene, idx):
        output_path = str(self.cache_dir / f"scene_{idx:03d}.jpg")
        if Path(output_path).exists():
            return output_path

        unsplash_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
        if not unsplash_key:
            print(f"  Fallback: scene {idx} TYPE_PHOTO_STOCK → TYPE_AI (no UNSPLASH_ACCESS_KEY)")
            return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)

        query = scene.get("search_query", "nature landscape")
        try:
            resp = requests.get(
                "https://api.unsplash.com/photos/random",
                headers={"Authorization": f"Client-ID {unsplash_key}"},
                params={"query": query, "orientation": "landscape", "content_filter": "high"},
                timeout=10,
            )
            resp.raise_for_status()
            image_url = resp.json()["urls"]["regular"]
            img_resp = requests.get(image_url, timeout=30)
            img_resp.raise_for_status()
            Path(output_path).write_bytes(img_resp.content)
            return output_path
        except Exception as exc:
            print(f"  Fallback: scene {idx} TYPE_PHOTO_STOCK → TYPE_AI ({exc})")
            return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)

    def _route_animated(self, scene, idx, duration):
        image_path = self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)
        if image_path is None:
            return None

        output_path = str(self.cache_dir / f"animated_scene_{idx:03d}.mp4")
        if Path(output_path).exists():
            return output_path

        runway_key = os.environ.get("RUNWAY_API_KEY", "")
        if not runway_key:
            print(f"  Fallback: scene {idx} TYPE_ANIMATED → TYPE_AI (no RUNWAY_API_KEY)")
            return image_path  # assembler applies Ken Burns

        motion = scene.get("motion_prompt", "slow camera push forward")
        clip_dur = min(5, int(duration))
        return animate_image(image_path, motion, clip_dur, output_path)

    def _generate_bfl(self, prompt, idx):
        output_path = str(self.cache_dir / f"scene_{idx:03d}.jpg")
        if Path(output_path).exists():
            return output_path
        return generate_single_image(prompt, output_path, self.provider)
