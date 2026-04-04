"""Stage 3: Stock video fetching from Pexels API."""

import json
import os
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential


STYLE_QUERIES = {
    "contemplative": ["mountain sunrise", "calm water reflection", "forest light"],
    "joyful": ["sunlight meadow", "golden fields", "bright sky clouds"],
    "worship": ["hands raised light", "crowd worship", "candles warm"],
    "powerful": ["storm clouds dramatic", "ocean waves", "mountain peak"],
}

PEXELS_API_URL = "https://api.pexels.com/videos/search"


def _build_search_query(scene, overall_style):
    """Build a Pexels search query from scene data."""
    prompt = scene.get("visual_prompt", "").strip()
    if prompt:
        words = prompt.split()[:5]
        return " ".join(words)

    queries = STYLE_QUERIES.get(overall_style, STYLE_QUERIES["contemplative"])
    section = scene.get("section", "verse")
    idx = hash(section) % len(queries)
    return queries[idx]


def _get_best_video_file(video_files, min_width=1280):
    """Select the best quality video file from Pexels response."""
    hd_files = [f for f in video_files if f.get("width", 0) >= min_width]
    if hd_files:
        return max(hd_files, key=lambda f: f.get("width", 0))
    return max(video_files, key=lambda f: f.get("width", 0)) if video_files else None


def _create_placeholder_video(output_path, scene):
    """Create a placeholder black frame when video fetch fails."""
    from PIL import Image
    img = Image.new("RGB", (1920, 1080), color=(20, 20, 40))
    placeholder_path = output_path.with_suffix(".png")
    img.save(str(placeholder_path))
    return str(placeholder_path)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def _search_pexels(query, api_key):
    """Search Pexels for videos matching the query."""
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": "landscape",
        "size": "large",
        "per_page": 3,
    }
    response = requests.get(PEXELS_API_URL, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def _download_video(url, output_path, api_key):
    """Download a video file from URL."""
    headers = {"Authorization": api_key}
    response = requests.get(url, headers=headers, stream=True)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return str(output_path)


def fetch_videos(scene_plan, output_dir=None):
    """Fetch stock videos for each scene in the plan.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save downloaded videos.

    Returns:
        list of dicts with keys: scene_index, video_path, search_query
    """
    api_key = os.environ.get("PEXELS_API_KEY", "")
    overall_style = scene_plan.get("overall_style", "contemplative")
    scenes = scene_plan.get("scenes", [])

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        videos_dir = output_path / "videos"
        videos_dir.mkdir(exist_ok=True)
    else:
        videos_dir = Path(".")

    results = []

    for i, scene in enumerate(scenes):
        query = _build_search_query(scene, overall_style)
        video_path = None

        try:
            if api_key:
                search_result = _search_pexels(query, api_key)
                videos = search_result.get("videos", [])
                if videos:
                    video_data = videos[0]
                    video_file = _get_best_video_file(video_data.get("video_files", []))
                    if video_file:
                        dest = videos_dir / f"scene_{i:03d}.mp4"
                        video_path = _download_video(video_file["link"], dest, api_key)
        except Exception:
            pass

        if not video_path:
            dest = videos_dir / f"scene_{i:03d}"
            video_path = _create_placeholder_video(dest, scene)

        results.append({
            "scene_index": i,
            "video_path": video_path,
            "search_query": query,
        })

    if output_dir:
        manifest_path = Path(output_dir) / "fetch_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(results, f, indent=2)

    return results
