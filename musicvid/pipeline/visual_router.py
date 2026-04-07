"""Per-scene visual source routing for hybrid asset generation."""

import os
import requests
from pathlib import Path

from musicvid.pipeline.stock_fetcher import fetch_video_by_query
from musicvid.pipeline.image_generator import generate_single_image
from musicvid.pipeline.video_animator import animate_image

BLOCKED_WORDS = [
    # Non-Protestant religious imagery
    "muslim", "mosque", "islamic", "quran", "hindu",
    "buddha", "buddhist", "catholic", "cathedral",
    "shrine", "temple", "prayer rug", "hijab",
    "church interior", "altar", "rosary", "statue",
    "pope", "nun", "monk", "orthodox", "meditation",
    # Alcohol and intoxicants
    "alcohol", "beer", "wine", "whiskey", "vodka",
    "drinking", "bar", "pub", "cocktail", "champagne",
    "nightclub", "drunk",
    # Non-Protestant religious imagery (icons)
    "icon religious",
    # Other inappropriate content
    "gambling", "casino", "cigarette", "smoking",
    "drugs", "violence", "nightlife", "fight", "party",
]

SAFE_QUERY_MAP = {
    "worship hands raised": "people outdoor arms up sunset",
    "prayer hands": "person sitting quietly nature",
    "hands praying": "person peaceful outdoor sunrise",
    "praying hands": "person sitting peaceful morning",
    "prayer outdoor": "person sitting field morning light",
    "worship": "outdoor gathering people singing sunset",
    "spiritual": "peaceful nature landscape morning",
}


def sanitize_query(query):
    """Check query against blocked words and safe replacements."""
    if not query:
        return query
    query_lower = query.lower()
    for blocked in BLOCKED_WORDS:
        if blocked in query_lower:
            return "BLOCKED"
    for unsafe, safe in SAFE_QUERY_MAP.items():
        if unsafe in query_lower:
            return safe
    return query


class VisualRouter:
    """Routes each scene to the appropriate visual source API.

    Dispatch order by visual_source:
      TYPE_VIDEO_STOCK  → Pexels video (fetch_video_by_query)
      TYPE_PHOTO_STOCK  → Unsplash photo (requests + UNSPLASH_ACCESS_KEY)
      TYPE_AI           → BFL Flux image (generate_single_image)
      TYPE_ANIMATED     → BFL flux-dev image + Runway animate_image (image-to-video)
      TYPE_VIDEO_RUNWAY → BFL flux-dev image + Runway animate_image (image-to-video)

    Fallback hierarchy:
      TYPE_VIDEO_STOCK failure → simplified query → BFL (visual_prompt or default)
      TYPE_PHOTO_STOCK         → Unsplash → Pexels → BFL
      TYPE_ANIMATED no key     → static TYPE_AI image (Ken Burns in assembler)
      TYPE_ANIMATED error      → static TYPE_AI image (Ken Burns in assembler)
      TYPE_VIDEO_RUNWAY no key → Pexels stock video
      TYPE_VIDEO_RUNWAY error  → Pexels stock video
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
        elif source == "TYPE_VIDEO_RUNWAY":
            return self._route_runway(scene, idx, duration)
        else:  # TYPE_AI (default)
            return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)

    # ------------------------------------------------------------------
    # Private dispatch methods
    # ------------------------------------------------------------------

    def _route_video_stock(self, scene, idx, duration):
        query = scene.get("search_query", "nature landscape")
        query = sanitize_query(query)
        if query == "BLOCKED":
            visual_prompt = scene.get("visual_prompt") or "nature landscape peaceful"
            print(f"  Fallback: scene {idx} TYPE_VIDEO_STOCK → TYPE_AI (query blocked)")
            return self._generate_bfl(visual_prompt, idx)
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

        # BFL fallback — use visual_prompt if available, else default
        visual_prompt = scene.get("visual_prompt") or ""
        fallback_prompt = visual_prompt if visual_prompt else "nature landscape peaceful"
        print(f"  Fallback: scene {idx} TYPE_VIDEO_STOCK → TYPE_AI (Pexels exhausted)")
        return self._generate_bfl(fallback_prompt, idx)

    def _route_photo_stock(self, scene, idx):
        output_path = str(self.cache_dir / f"scene_{idx:03d}.jpg")
        if Path(output_path).exists():
            return output_path

        query = scene.get("search_query", "nature landscape")
        query = sanitize_query(query)
        if query == "BLOCKED":
            print(f"  Fallback: scene {idx} TYPE_PHOTO_STOCK → TYPE_AI (query blocked)")
            return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)

        unsplash_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
        if unsplash_key:
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
                print(f"  Fallback: scene {idx} Unsplash failed ({exc}), trying Pexels")

        pexels_key = os.environ.get("PEXELS_API_KEY", "")
        if pexels_key:
            duration = scene["end"] - scene["start"]
            video_path = str(self.cache_dir / f"scene_{idx:03d}.mp4")
            result = fetch_video_by_query(query, duration, video_path)
            if result:
                return result
            print(f"  Fallback: scene {idx} Pexels failed, falling back to TYPE_AI")

        print(f"  WARN: Brak kluczy stock — fallback TYPE_AI dla sceny {idx}")
        return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)

    def _route_animated(self, scene, idx, duration):
        output_path = str(self.cache_dir / f"animated_scene_{idx:03d}.mp4")
        if Path(output_path).exists():
            return output_path

        runway_key = os.environ.get("RUNWAY_API_KEY", "")
        if not runway_key:
            print(f"  Fallback: scene {idx} TYPE_ANIMATED → TYPE_AI (no RUNWAY_API_KEY)")
            return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)

        # Step 1: generate BFL image (flux-dev — cheap)
        image_path = str(self.cache_dir / f"scene_{idx:03d}.jpg")
        if not Path(image_path).exists():
            image_path = generate_single_image(
                scene.get("visual_prompt", "nature landscape"),
                image_path,
                "flux-dev",
            )

        # Step 2: animate via Runway image-to-video
        motion = scene.get("motion_prompt") or scene.get("visual_prompt") or ""
        if not motion.strip():
            motion = "Slow cinematic camera push forward, natural golden light, peaceful atmosphere"
        motion = motion.strip()[:300]
        try:
            return animate_image(image_path, motion, duration=5, output_path=output_path)
        except Exception as exc:
            print(f"  WARN: Runway animate failed for scene {idx} — fallback TYPE_AI ({exc})")
            return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)

    def _route_runway(self, scene, idx, duration):
        """Route TYPE_VIDEO_RUNWAY → BFL image + Runway animate, fallback → Pexels stock."""
        output_path = str(self.cache_dir / f"runway_scene_{idx:03d}.mp4")
        if Path(output_path).exists():
            return output_path

        runway_key = os.environ.get("RUNWAY_API_KEY", "")
        if runway_key:
            # Step 1: generate BFL image (flux-dev — cheap)
            image_path = str(self.cache_dir / f"runway_img_{idx:03d}.jpg")
            if not Path(image_path).exists():
                bfl_prompt = scene.get("visual_prompt", "") or "nature landscape"
                image_path = generate_single_image(bfl_prompt, image_path, "flux-dev")

            # Step 2: animate via Runway image-to-video
            motion = scene.get("motion_prompt") or scene.get("visual_prompt") or ""
            if not motion.strip():
                motion = "Slow cinematic camera push forward, natural golden light, peaceful atmosphere"
            motion = motion.strip()[:300]
            try:
                return animate_image(image_path, motion, duration=5, output_path=output_path)
            except Exception as exc:
                print(f"  WARN: Runway animate failed for scene {idx} — fallback Pexels ({exc})")

        # Fallback: Pexels stock (no BFL — runway mode avoids AI images)
        query = scene.get("search_query", "") or "nature landscape peaceful"
        query = sanitize_query(query)
        if query == "BLOCKED":
            query = "nature landscape peaceful"
        stock_path = str(self.cache_dir / f"scene_{idx:03d}.mp4")
        result = fetch_video_by_query(query, duration, stock_path)
        if result:
            return result
        simplified = " ".join(query.split()[:2])
        if simplified and simplified != query:
            result = fetch_video_by_query(simplified, duration, stock_path)
            if result:
                return result
        return fetch_video_by_query("nature landscape", duration, stock_path)

    def _generate_bfl(self, prompt, idx):
        output_path = str(self.cache_dir / f"scene_{idx:03d}.jpg")
        if Path(output_path).exists():
            return output_path
        return generate_single_image(prompt, output_path, self.provider)
