# Hybrid Visual Sourcing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-source Stage 3 asset pipeline with a per-scene visual router that picks between Pexels video, Unsplash photo, BFL AI image, or BFL+Runway animated based on the director's `visual_source` field.

**Architecture:** The director now outputs `visual_source` and `search_query` per scene. A new `VisualRouter` class in `visual_router.py` dispatches each scene to the correct API. The `musicvid.py` Stage 3 `mode=="ai"` path is replaced by a `VisualRouter` loop; `mode=="stock"` stays unchanged as a shortcut that overrides all scenes to `TYPE_VIDEO_STOCK`.

**Tech Stack:** Python 3.11+, requests, Pexels API, Unsplash API, BFL Flux, Runway Gen-4, unittest.mock

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `musicvid/pipeline/image_generator.py` | Add `generate_single_image()` helper |
| Modify | `musicvid/pipeline/stock_fetcher.py` | Add `fetch_video_by_query()` helper |
| Create | `musicvid/pipeline/visual_router.py` | `VisualRouter` class — per-scene dispatch + fallback |
| Create | `tests/test_visual_router.py` | Unit tests for all routes and fallbacks |
| Modify | `musicvid/prompts/director_system.txt` | Add `visual_source`/`search_query` to output format |
| Modify | `musicvid/pipeline/director.py` | `_validate_scene_plan` defaults new fields |
| Modify | `tests/test_director.py` | Tests for new field defaults |
| Modify | `musicvid/musicvid.py` | Replace Stage 3 `mode=="ai"` loop with `VisualRouter` |
| Modify | `tests/test_cli.py` | Update Stage 3 mocks for new code path |
| Modify | `.env.example` | Add `UNSPLASH_ACCESS_KEY` |

---

### Task 1: Add `generate_single_image()` to image_generator.py

**Files:**
- Modify: `musicvid/pipeline/image_generator.py`
- Test: `tests/test_image_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_image_generator.py, inside class TestGenerateImages (or new class)

class TestGenerateSingleImage:
    """Tests for the generate_single_image() helper."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.time")
    def test_generates_and_saves_image(self, mock_time, mock_requests, tmp_path):
        mock_time.monotonic.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()

        submit_resp = MagicMock()
        submit_resp.json.return_value = {
            "id": "task-001",
            "polling_url": "https://api.bfl.ai/v1/poll/task-001",
        }
        submit_resp.raise_for_status = MagicMock()

        poll_resp = MagicMock()
        poll_resp.json.return_value = {
            "status": "Ready",
            "result": {"sample": "https://cdn.bfl.ai/img/result.jpg"},
        }
        poll_resp.raise_for_status = MagicMock()

        download_resp = MagicMock()
        download_resp.content = b"fake-image-bytes"
        download_resp.raise_for_status = MagicMock()

        mock_requests.post.return_value = submit_resp
        mock_requests.get.side_effect = [poll_resp, download_resp]

        from musicvid.pipeline.image_generator import generate_single_image
        output = str(tmp_path / "scene_001.jpg")
        result = generate_single_image("mountain sunrise", output, provider="flux-pro")

        assert result == output
        assert Path(output).read_bytes() == b"fake-image-bytes"

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    def test_returns_cached_path_without_api_call(self, tmp_path):
        output = tmp_path / "scene_002.jpg"
        output.write_bytes(b"cached")

        from musicvid.pipeline.image_generator import generate_single_image
        with patch("musicvid.pipeline.image_generator.requests") as mock_req:
            result = generate_single_image("any prompt", str(output), provider="flux-pro")
        assert result == str(output)
        mock_req.post.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_image_generator.py::TestGenerateSingleImage -v
```
Expected: `ImportError` or `AttributeError: module has no attribute 'generate_single_image'`

- [ ] **Step 3: Add `generate_single_image()` to image_generator.py**

Add after the `generate_images()` function (around line 80):

```python
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
    task_id, polling_url = _submit_task(model_name, full_prompt)
    image_url = _poll_result(polling_url)
    _download_image(image_url, output_path)
    return str(output_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_image_generator.py::TestGenerateSingleImage -v
```
Expected: 2 PASSED

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
python3 -m pytest tests/test_image_generator.py -v
```
Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/image_generator.py tests/test_image_generator.py
git commit -m "feat(image_generator): add generate_single_image() helper for per-scene generation"
```

---

### Task 2: Add `fetch_video_by_query()` to stock_fetcher.py

**Files:**
- Modify: `musicvid/pipeline/stock_fetcher.py`
- Test: `tests/test_stock_fetcher.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_stock_fetcher.py

class TestFetchVideoByQuery:
    """Tests for fetch_video_by_query() single-video helper."""

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_downloads_video_matching_min_duration(self, mock_requests, tmp_path):
        mock_search = MagicMock()
        mock_search.json.return_value = {
            "videos": [
                {
                    "duration": 10,
                    "video_files": [
                        {"id": 1, "width": 1920, "height": 1080,
                         "link": "https://example.com/video.mp4"},
                    ],
                }
            ]
        }
        mock_search.raise_for_status = MagicMock()
        mock_download = MagicMock()
        mock_download.raise_for_status = MagicMock()
        mock_download.iter_content = MagicMock(return_value=[b"video-data"])
        mock_requests.get.side_effect = [mock_search, mock_download]

        from musicvid.pipeline.stock_fetcher import fetch_video_by_query
        output = str(tmp_path / "scene_000.mp4")
        result = fetch_video_by_query("mountain sunrise", min_duration=5.0, output_path=output)

        assert result == output
        assert Path(output).exists()

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_returns_none_when_no_videos_found(self, mock_requests, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"videos": []}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        from musicvid.pipeline.stock_fetcher import fetch_video_by_query
        output = str(tmp_path / "scene_001.mp4")
        result = fetch_video_by_query("nothing matches", min_duration=5.0, output_path=output)

        assert result is None

    def test_returns_none_when_no_api_key(self, tmp_path):
        from musicvid.pipeline.stock_fetcher import fetch_video_by_query
        with patch.dict(os.environ, {}, clear=True):
            result = fetch_video_by_query("query", min_duration=5.0,
                                          output_path=str(tmp_path / "out.mp4"))
        assert result is None

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    def test_returns_cached_path_without_api_call(self, tmp_path):
        output = tmp_path / "scene_002.mp4"
        output.write_bytes(b"cached-video")

        from musicvid.pipeline.stock_fetcher import fetch_video_by_query
        with patch("musicvid.pipeline.stock_fetcher.requests") as mock_req:
            result = fetch_video_by_query("any query", 5.0, str(output))
        assert result == str(output)
        mock_req.get.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_stock_fetcher.py::TestFetchVideoByQuery -v
```
Expected: `ImportError` — `fetch_video_by_query` does not exist yet

- [ ] **Step 3: Add `fetch_video_by_query()` to stock_fetcher.py**

Add after the `_download_video()` function:

```python
def fetch_video_by_query(query, min_duration, output_path):
    """Fetch a single Pexels video by explicit query string.

    Unlike fetch_videos(), this takes a direct query instead of deriving
    one from scene style. Used by VisualRouter for TYPE_VIDEO_STOCK scenes.

    Args:
        query: Pexels search string (English, 3-5 words).
        min_duration: Minimum video duration in seconds.
        output_path: Destination path for the downloaded .mp4.

    Returns:
        str output_path if successful, None if not found or no API key.
    """
    api_key = os.environ.get("PEXELS_API_KEY", "")
    if not api_key:
        return None

    dest = Path(output_path)
    if dest.exists():
        return str(dest)

    try:
        search_result = _search_pexels(query, api_key)
        videos = search_result.get("videos", [])

        # Prefer videos long enough; fall back to first available
        candidate = next(
            (v for v in videos if v.get("duration", 0) >= min_duration),
            videos[0] if videos else None,
        )
        if candidate is None:
            return None

        video_file = _get_best_video_file(candidate.get("video_files", []))
        if video_file is None:
            return None

        return _download_video(video_file["link"], dest, api_key)
    except Exception:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_stock_fetcher.py::TestFetchVideoByQuery -v
```
Expected: 4 PASSED

- [ ] **Step 5: Run full stock_fetcher tests**

```bash
python3 -m pytest tests/test_stock_fetcher.py -v
```
Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/stock_fetcher.py tests/test_stock_fetcher.py
git commit -m "feat(stock_fetcher): add fetch_video_by_query() for direct query fetching"
```

---

### Task 3: Create VisualRouter + tests

**Files:**
- Create: `musicvid/pipeline/visual_router.py`
- Create: `tests/test_visual_router.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_visual_router.py`:

```python
"""Tests for visual_router.VisualRouter."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest


SCENE_VIDEO_STOCK = {
    "index": 0,
    "section": "verse",
    "start": 0.0,
    "end": 12.0,
    "visual_source": "TYPE_VIDEO_STOCK",
    "search_query": "mountain valley peaceful morning",
    "visual_prompt": "",
    "motion_prompt": "",
    "animate": False,
}

SCENE_PHOTO_STOCK = {
    "index": 1,
    "section": "verse",
    "start": 12.0,
    "end": 24.0,
    "visual_source": "TYPE_PHOTO_STOCK",
    "search_query": "open bible morning light wooden table",
    "visual_prompt": "",
    "motion_prompt": "",
    "animate": False,
}

SCENE_AI = {
    "index": 2,
    "section": "chorus",
    "start": 24.0,
    "end": 36.0,
    "visual_source": "TYPE_AI",
    "search_query": "",
    "visual_prompt": "Cathedral of light above clouds, documentary aerial photography style",
    "motion_prompt": "",
    "animate": False,
}

SCENE_ANIMATED = {
    "index": 3,
    "section": "chorus",
    "start": 36.0,
    "end": 48.0,
    "visual_source": "TYPE_ANIMATED",
    "search_query": "",
    "visual_prompt": "Person on hilltop arms raised, golden sunrise, wide shot",
    "motion_prompt": "slow camera rises revealing vast landscape",
    "animate": True,
}


class TestVisualRouterVideoStock:
    def test_route_calls_fetch_pexels(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        expected_path = str(tmp_path / "scene_000.mp4")
        with patch("musicvid.pipeline.visual_router.fetch_video_by_query",
                   return_value=expected_path) as mock_fetch:
            result = router.route(SCENE_VIDEO_STOCK)

        mock_fetch.assert_called_once_with(
            "mountain valley peaceful morning",
            12.0,
            expected_path,
        )
        assert result == expected_path

    def test_route_video_stock_simplified_query_fallback(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        video_path = str(tmp_path / "scene_000.mp4")

        def side_effect(query, min_dur, out_path):
            if query == "mountain valley peaceful morning":
                return None
            if query == "mountain valley":
                return video_path
            return None

        with patch("musicvid.pipeline.visual_router.fetch_video_by_query",
                   side_effect=side_effect):
            result = router.route(SCENE_VIDEO_STOCK)

        assert result == video_path

    def test_route_video_stock_falls_back_to_photo_stock(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        # Pexels returns nothing, Unsplash succeeds
        photo_path = str(tmp_path / "scene_000.jpg")
        Path(photo_path).write_bytes(b"photo")

        with patch("musicvid.pipeline.visual_router.fetch_video_by_query", return_value=None), \
             patch.dict(os.environ, {"UNSPLASH_ACCESS_KEY": "fake-key"}):
            # Unsplash mock: write the photo file
            def fake_unsplash_get(url, **kwargs):
                resp = MagicMock()
                resp.raise_for_status = MagicMock()
                if "unsplash" in url:
                    resp.json.return_value = {"urls": {"regular": "https://img.unsplash.com/photo.jpg"}}
                else:
                    resp.content = b"photo-bytes"
                return resp

            with patch("musicvid.pipeline.visual_router.requests.get",
                       side_effect=fake_unsplash_get):
                result = router.route(SCENE_VIDEO_STOCK)

        assert result is not None


class TestVisualRouterPhotoStock:
    @patch.dict(os.environ, {"UNSPLASH_ACCESS_KEY": "fake-key"})
    def test_route_photo_stock_calls_unsplash(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        output_path = str(tmp_path / "scene_001.jpg")

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "unsplash" in url:
                resp.json.return_value = {
                    "urls": {"regular": "https://img.unsplash.com/photo.jpg"}
                }
            else:
                resp.content = b"photo-data"
            return resp

        with patch("musicvid.pipeline.visual_router.requests.get", side_effect=fake_get):
            result = router.route(SCENE_PHOTO_STOCK)

        assert result == output_path
        assert Path(output_path).read_bytes() == b"photo-data"

    def test_route_photo_stock_no_key_falls_back_to_type_ai(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        ai_path = str(tmp_path / "scene_001.jpg")

        with patch.dict(os.environ, {}, clear=True), \
             patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=ai_path) as mock_gen:
            result = router.route(SCENE_PHOTO_STOCK)

        mock_gen.assert_called_once()
        assert result == ai_path

    @patch.dict(os.environ, {"UNSPLASH_ACCESS_KEY": "fake-key"})
    def test_route_photo_stock_returns_cached(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        cached = tmp_path / "scene_001.jpg"
        cached.write_bytes(b"cached-photo")

        with patch("musicvid.pipeline.visual_router.requests.get") as mock_get:
            result = router.route(SCENE_PHOTO_STOCK)

        mock_get.assert_not_called()
        assert result == str(cached)


class TestVisualRouterAI:
    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    def test_route_ai_calls_generate_single_image(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        ai_path = str(tmp_path / "scene_002.jpg")
        with patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=ai_path) as mock_gen:
            result = router.route(SCENE_AI)

        mock_gen.assert_called_once_with(
            SCENE_AI["visual_prompt"],
            ai_path,
            "flux-pro",
        )
        assert result == ai_path

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    def test_route_ai_returns_cached(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        cached = tmp_path / "scene_002.jpg"
        cached.write_bytes(b"cached-ai")

        with patch("musicvid.pipeline.visual_router.generate_single_image") as mock_gen:
            result = router.route(SCENE_AI)

        mock_gen.assert_not_called()
        assert result == str(cached)


class TestVisualRouterAnimated:
    @patch.dict(os.environ, {"BFL_API_KEY": "test-key", "RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_calls_generate_and_animate(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        image_path = str(tmp_path / "scene_003.jpg")
        video_path = str(tmp_path / "animated_scene_003.mp4")

        with patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path) as mock_gen, \
             patch("musicvid.pipeline.visual_router.animate_image",
                   return_value=video_path) as mock_anim:
            result = router.route(SCENE_ANIMATED)

        mock_gen.assert_called_once_with(
            SCENE_ANIMATED["visual_prompt"],
            image_path,
            "flux-pro",
        )
        mock_anim.assert_called_once_with(
            image_path,
            SCENE_ANIMATED["motion_prompt"],
            5,  # min(5, int(48.0 - 36.0)) = 5
            video_path,
        )
        assert result == video_path

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    def test_route_animated_no_runway_key_returns_static_image(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        image_path = str(tmp_path / "scene_003.jpg")

        with patch.dict(os.environ, {"RUNWAY_API_KEY": ""}, clear=False), \
             patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path) as mock_gen, \
             patch("musicvid.pipeline.visual_router.animate_image") as mock_anim:
            result = router.route(SCENE_ANIMATED)

        mock_anim.assert_not_called()
        assert result == image_path

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key", "RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_returns_cached_video(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        # Pre-create the animated video
        cached_video = tmp_path / "animated_scene_003.mp4"
        cached_video.write_bytes(b"cached-animation")

        # image also cached
        cached_image = tmp_path / "scene_003.jpg"
        cached_image.write_bytes(b"cached-image")

        with patch("musicvid.pipeline.visual_router.generate_single_image") as mock_gen, \
             patch("musicvid.pipeline.visual_router.animate_image") as mock_anim:
            result = router.route(SCENE_ANIMATED)

        mock_gen.assert_not_called()
        mock_anim.assert_not_called()
        assert result == str(cached_video)


class TestVisualRouterDefaultSource:
    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    def test_route_missing_visual_source_defaults_to_type_ai(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-dev")

        scene = {
            "index": 5,
            "section": "verse",
            "start": 0.0,
            "end": 10.0,
            "visual_prompt": "Calm lake at dawn",
            "motion_prompt": "",
            "animate": False,
            # visual_source intentionally omitted
        }
        ai_path = str(tmp_path / "scene_005.jpg")

        with patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=ai_path) as mock_gen:
            result = router.route(scene)

        mock_gen.assert_called_once_with("Calm lake at dawn", ai_path, "flux-dev")
        assert result == ai_path
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_visual_router.py -v
```
Expected: `ImportError` — module `visual_router` does not exist yet

- [ ] **Step 3: Create `musicvid/pipeline/visual_router.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_visual_router.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/visual_router.py tests/test_visual_router.py
git commit -m "feat(visual_router): add VisualRouter for per-scene hybrid asset sourcing"
```

---

### Task 4: Update director prompt + validate defaults

**Files:**
- Modify: `musicvid/prompts/director_system.txt`
- Modify: `musicvid/pipeline/director.py`
- Test: `tests/test_director.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_director.py — in TestValidateScenePlan or new class

class TestValidateScenePlanNewFields:
    """Tests that _validate_scene_plan defaults new hybrid sourcing fields."""

    def test_defaults_visual_source_to_type_ai(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {"start": 0.0, "end": 10.0, "section": "verse"},
            ]
        }
        result = _validate_scene_plan(plan, duration=10.0)
        assert result["scenes"][0]["visual_source"] == "TYPE_AI"

    def test_defaults_search_query_to_empty_string(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {"start": 0.0, "end": 10.0, "section": "verse"},
            ]
        }
        result = _validate_scene_plan(plan, duration=10.0)
        assert result["scenes"][0]["search_query"] == ""

    def test_preserves_existing_visual_source(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {
                    "start": 0.0,
                    "end": 10.0,
                    "section": "verse",
                    "visual_source": "TYPE_VIDEO_STOCK",
                    "search_query": "mountain sunrise",
                },
            ]
        }
        result = _validate_scene_plan(plan, duration=10.0)
        assert result["scenes"][0]["visual_source"] == "TYPE_VIDEO_STOCK"
        assert result["scenes"][0]["search_query"] == "mountain sunrise"

    def test_defaults_visual_prompt_to_empty_string_when_missing(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {
                    "start": 0.0,
                    "end": 10.0,
                    "section": "verse",
                    "visual_source": "TYPE_VIDEO_STOCK",
                    "search_query": "mountain sunrise",
                    # visual_prompt intentionally omitted
                },
            ]
        }
        result = _validate_scene_plan(plan, duration=10.0)
        assert result["scenes"][0]["visual_prompt"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_director.py::TestValidateScenePlanNewFields -v
```
Expected: FAIL — `visual_source` and `search_query` not yet defaulted

- [ ] **Step 3: Update `_validate_scene_plan` in director.py**

In `_validate_scene_plan`, extend the per-scene defaults block (after the existing defaults, around line 108):

```python
    # Default animate/motion_prompt/lyrics_in_scene fields if Claude omitted them
    for scene in plan["scenes"]:
        if "animate" not in scene:
            scene["animate"] = False
        if "motion_prompt" not in scene:
            scene["motion_prompt"] = ""
        if "lyrics_in_scene" not in scene:
            scene["lyrics_in_scene"] = []
        # Hybrid visual sourcing fields (Spec 5)
        if "visual_source" not in scene:
            scene["visual_source"] = "TYPE_AI"
        if "search_query" not in scene:
            scene["search_query"] = ""
        if "visual_prompt" not in scene:
            scene["visual_prompt"] = ""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_director.py::TestValidateScenePlanNewFields -v
```
Expected: 4 PASSED

- [ ] **Step 5: Update director_system.txt — add VISUAL SOURCE SELECTION section**

Add the following block immediately after the `MASTER STYLE:` section (after line 9), before `CONTEXT-AWARE VISUAL PROMPTS:`:

```
VISUAL SOURCE SELECTION:
For each scene choose "visual_source" (required field) based on lyrics content:

TYPE_VIDEO_STOCK — Pexels video (free, realistic)
  When: concrete filmable elements — nature (mountains, water, sky, fields), people (worship,
        prayer, walking), community activities. NOT for abstract spiritual concepts.
  Fields: set search_query (English, 3-5 words describing what to film), set visual_prompt to ""

TYPE_PHOTO_STOCK — Unsplash photo (free, documentary)
  When: still/contemplative moments, specific objects (open Bible, wooden cross, candle),
        landscapes to be shown as static Ken Burns pan.
  Fields: set search_query (English, 3-5 words), set visual_prompt to ""

TYPE_AI — BFL Flux image generation ($0.04, unique)
  When: abstract spiritual concepts impossible to photograph — glory of God, eternity, throne,
        river of life, spiritual light (as theological concept not physical light).
  Fields: set visual_prompt (detailed, min 3 sentences, documentary style), set search_query to ""

TYPE_ANIMATED — BFL image + Runway Gen-4 video ($0.54, climactic)
  When: TYPE_AI scene that is also: first chorus, last chorus before outro, or bridge.
        Maximum 25% of all scenes; never two adjacent; minimum scene duration 6s.
  Fields: set visual_prompt (detailed), set motion_prompt (camera motion 3-8 words),
          set search_query to "", set animate: true

EXAMPLES:
  "góry, dolina, chodzę" → TYPE_VIDEO_STOCK, search_query: "person walking mountain valley path"
  "otwarta Biblia" → TYPE_PHOTO_STOCK, search_query: "open bible morning light wooden table"
  "Chwała Bogu na wysokościach" → TYPE_AI, visual_prompt: "Vast cathedral of light above cloud layer..."
  First refrain (kulminacja, >6s) → TYPE_ANIMATED, visual_prompt: "...", motion_prompt: "slow camera rises"

```

Also update the OUTPUT FORMAT JSON template in director_system.txt to include the new fields in the scenes array. Find the scenes array template and update it:

Change the scene object template from:
```json
    {
      "section": "intro|verse|chorus|bridge|outro",
      "start": 0.0,
      "end": 15.0,
      "lyrics_in_scene": ["lyrics line 1 that appears in this scene", "lyrics line 2"],
      "visual_prompt": "Detailed positive description following the rules above (min 3 sentences + technical suffix)",
      "motion": "slow_zoom_in|slow_zoom_out|pan_left|pan_right|static|diagonal_drift|cut_zoom",
      "transition": "crossfade|cut|fade_black",
      "overlay": "none|particles|light_rays|bokeh",
      "animate": false,
      "motion_prompt": ""
    }
```

To:
```json
    {
      "section": "intro|verse|chorus|bridge|outro",
      "start": 0.0,
      "end": 15.0,
      "lyrics_in_scene": ["lyrics line 1 that appears in this scene", "lyrics line 2"],
      "visual_source": "TYPE_VIDEO_STOCK|TYPE_PHOTO_STOCK|TYPE_AI|TYPE_ANIMATED",
      "search_query": "english search terms for stock (3-5 words) or empty string for AI",
      "visual_prompt": "Detailed description for AI generation — empty string for STOCK types",
      "motion": "slow_zoom_in|slow_zoom_out|pan_left|pan_right|static|diagonal_drift|cut_zoom",
      "transition": "crossfade|cut|fade_black",
      "overlay": "none|particles|light_rays|bokeh",
      "animate": false,
      "motion_prompt": ""
    }
```

- [ ] **Step 6: Run full director tests + visual_router tests**

```bash
python3 -m pytest tests/test_director.py tests/test_visual_router.py -v
```
Expected: all PASSED

- [ ] **Step 7: Commit**

```bash
git add musicvid/prompts/director_system.txt musicvid/pipeline/director.py tests/test_director.py
git commit -m "feat(director): add visual_source/search_query fields to scene plan for hybrid sourcing"
```

---

### Task 5: Wire VisualRouter into musicvid.py Stage 3

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `.env.example`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

```python
# Add to tests/test_cli.py — a new class for hybrid routing

class TestHybridVisualRouting:
    """Tests that mode=ai uses VisualRouter instead of generate_images."""

    def _make_scene_plan(self):
        return {
            "overall_style": "contemplative",
            "master_style": "Documentary style",
            "color_palette": ["#FFFFFF"],
            "subtitle_style": {"font_size": 48, "color": "#FFFFFF",
                               "outline_color": "#000000", "position": "center-bottom",
                               "animation": "karaoke"},
            "scenes": [
                {
                    "section": "verse",
                    "start": 0.0,
                    "end": 12.0,
                    "lyrics_in_scene": ["Tylko w Bogu"],
                    "visual_source": "TYPE_VIDEO_STOCK",
                    "search_query": "mountain valley morning",
                    "visual_prompt": "",
                    "motion": "slow_zoom_in",
                    "transition_to_next": "cut",
                    "overlay": "none",
                    "animate": False,
                    "motion_prompt": "",
                },
                {
                    "section": "chorus",
                    "start": 12.0,
                    "end": 24.0,
                    "lyrics_in_scene": ["Chwała"],
                    "visual_source": "TYPE_AI",
                    "search_query": "",
                    "visual_prompt": "Cathedral of light",
                    "motion": "static",
                    "transition_to_next": "cut",
                    "overlay": "none",
                    "animate": False,
                    "motion_prompt": "",
                },
            ],
        }

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.VisualRouter")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_mode_ai_uses_visual_router(
        self, mock_analyze, mock_director, mock_router_cls,
        mock_assemble, mock_font, tmp_path, audio_file
    ):
        mock_analyze.return_value = {
            "duration": 24.0, "bpm": 120.0, "beats": [0.5 * i for i in range(48)],
            "sections": [], "lyrics": [],
        }
        mock_director.return_value = self._make_scene_plan()

        router_instance = MagicMock()
        router_instance.route.side_effect = [
            str(tmp_path / "scene_000.mp4"),
            str(tmp_path / "scene_001.jpg"),
        ]
        mock_router_cls.return_value = router_instance
        mock_assemble.return_value = str(tmp_path / "output.mp4")

        from click.testing import CliRunner
        from musicvid.musicvid import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            str(audio_file), "--mode", "ai", "--preset", "full",
            "--animate", "never", "--output-dir", str(tmp_path),
        ])

        assert mock_router_cls.called
        assert router_instance.route.call_count == 2

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_mode_stock_still_uses_fetch_videos(
        self, mock_analyze, mock_director, mock_fetch,
        mock_assemble, mock_font, tmp_path, audio_file
    ):
        mock_analyze.return_value = {
            "duration": 24.0, "bpm": 120.0, "beats": [0.5 * i for i in range(48)],
            "sections": [], "lyrics": [],
        }
        mock_director.return_value = self._make_scene_plan()
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": str(tmp_path / "s0.mp4"),
             "search_query": "q", "start": 0.0, "end": 12.0},
            {"scene_index": 1, "video_path": str(tmp_path / "s1.mp4"),
             "search_query": "q", "start": 12.0, "end": 24.0},
        ]
        mock_assemble.return_value = str(tmp_path / "output.mp4")

        from click.testing import CliRunner
        from musicvid.musicvid import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            str(audio_file), "--mode", "stock", "--preset", "full",
            "--output-dir", str(tmp_path),
        ])

        mock_fetch.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::TestHybridVisualRouting -v
```
Expected: FAIL — `VisualRouter` not imported in musicvid.py, `mock_router_cls` never called

- [ ] **Step 3: Update musicvid.py — add import and replace Stage 3 mode==ai block**

**3a. Add import at top of musicvid.py** (after the existing imports, around line 20):

```python
from musicvid.pipeline.visual_router import VisualRouter
```

**3b. Replace Stage 3 `mode == "ai"` block** (lines 598–666 in the original file).

Find this block:
```python
    if mode == "ai":
        image_cache_name = f"image_manifest{manifest_suffix}.json"
        image_manifest = load_cache(str(cache_dir), image_cache_name) if not new else None
        if image_manifest and _image_files_exist(image_manifest):
            click.echo("[3/4] Generating images... CACHED (skipped)")
            fetch_manifest = image_manifest
        else:
            click.echo(f"[3/4] Generating images (provider: {provider})...")
            gen_platform = "reels" if preset == "social" else None
            image_paths = generate_images(scene_plan, str(cache_dir), provider=provider, platform=gen_platform)
            fetch_manifest = [
                {"scene_index": i, "video_path": path, "search_query": scene["visual_prompt"]}
                for i, (path, scene) in enumerate(zip(image_paths, scene_plan["scenes"]))
            ]
            save_cache(str(cache_dir), image_cache_name, fetch_manifest)
        click.echo(f"  Generated: {len(fetch_manifest)} images")

        # Apply --animate overrides to scene plan
        if animate_mode == "always":
            for scene in scene_plan["scenes"]:
                scene["animate"] = True
                if not scene.get("motion_prompt"):
                    scene["motion_prompt"] = "Slow camera push forward, gentle atmospheric movement"
        elif animate_mode == "never":
            for scene in scene_plan["scenes"]:
                scene["animate"] = False

        # Enforce animation placement rules (auto mode only — always/never are explicit overrides)
        if animate_mode == "auto":
            scene_plan["scenes"] = enforce_animation_rules(scene_plan["scenes"])

        # Stage 3.5: Animate scenes with Runway Gen-4
        if animate_mode != "never":
            runway_key = os.environ.get("RUNWAY_API_KEY")
            for entry in fetch_manifest:
                idx = entry["scene_index"]
                scene = scene_plan["scenes"][idx]
                if not scene.get("animate", False):
                    continue
                if not runway_key:
                    click.echo(f"  ⚠ RUNWAY_API_KEY not set — Ken Burns fallback for scene {idx + 1}")
                    scene["animate"] = False
                    continue
                animated_path = str(cache_dir / f"animated_scene_{idx:03d}.mp4")
                click.echo(f"  Animating scene {idx + 1}/{len(scene_plan['scenes'])}...")
                try:
                    result_path = animate_image(
                        entry["video_path"],
                        scene.get("motion_prompt", "Slow camera push forward"),
                        duration=5,
                        output_path=animated_path,
                    )
                    entry["video_path"] = result_path
                except Exception as exc:
                    if hasattr(exc, 'response') and exc.response is not None:
                        click.echo(f"  Runway error: {exc.response.status_code} {exc.response.text[:300]}")
                    click.echo(f"  ⚠ Animation failed for scene {idx + 1}: {exc} — Ken Burns fallback")
                    scene["animate"] = False
```

Replace with:
```python
    if mode == "ai":
        image_cache_name = f"image_manifest{manifest_suffix}.json"
        image_manifest = load_cache(str(cache_dir), image_cache_name) if not new else None
        if image_manifest and _image_files_exist(image_manifest):
            click.echo("[3/4] Generating assets... CACHED (skipped)")
            fetch_manifest = image_manifest
        else:
            # Apply --animate overrides to visual_source before routing
            scenes = scene_plan["scenes"]
            if animate_mode == "always":
                for scene in scenes:
                    if scene.get("visual_source") in ("TYPE_AI", "TYPE_VIDEO_STOCK", "TYPE_PHOTO_STOCK"):
                        scene["visual_source"] = "TYPE_ANIMATED"
                    if not scene.get("motion_prompt"):
                        scene["motion_prompt"] = "Slow camera push forward, gentle atmospheric movement"
                scenes = enforce_animation_rules(scenes)
            elif animate_mode == "never":
                for scene in scenes:
                    if scene.get("visual_source") == "TYPE_ANIMATED":
                        scene["visual_source"] = "TYPE_AI"
            elif animate_mode == "auto":
                scenes = enforce_animation_rules(scenes)
            scene_plan["scenes"] = scenes

            click.echo(f"[3/4] Generating assets (provider: {provider})...")
            router = VisualRouter(cache_dir=str(cache_dir), provider=provider)
            fetch_manifest = []
            for i, scene in enumerate(scene_plan["scenes"]):
                scene["index"] = i
                src = scene.get("visual_source", "TYPE_AI")
                label = scene.get("search_query") or scene.get("visual_prompt", "")
                click.echo(f"  [{i + 1}/{len(scene_plan['scenes'])}] "
                           f"{scene['section']}: {src} — '{label[:40]}'")
                asset_path = router.route(scene)
                if asset_path is None:
                    from musicvid.pipeline.stock_fetcher import _create_placeholder_video
                    placeholder_dest = cache_dir / f"scene_{i:03d}"
                    asset_path = _create_placeholder_video(placeholder_dest, scene)
                fetch_manifest.append({
                    "scene_index": i,
                    "video_path": asset_path,
                    "start": scene["start"],
                    "end": scene["end"],
                    "source": src,
                })
            save_cache(str(cache_dir), image_cache_name, fetch_manifest)
        click.echo(f"  Assets: {len(fetch_manifest)} scenes")
```

- [ ] **Step 4: Update `.env.example`**

```
ANTHROPIC_API_KEY=...      # required
PEXELS_API_KEY=...         # required for --mode stock and TYPE_VIDEO_STOCK scenes
BFL_API_KEY=...            # bfl.ai — required for --mode ai (flux models)
RUNWAY_API_KEY=...         # optional, for --animate / TYPE_ANIMATED scenes
UNSPLASH_ACCESS_KEY=...    # optional, for TYPE_PHOTO_STOCK scenes (free at unsplash.com/developers)
```

- [ ] **Step 5: Run the new CLI tests**

```bash
python3 -m pytest tests/test_cli.py::TestHybridVisualRouting -v
```
Expected: 2 PASSED

- [ ] **Step 6: Run full test suite**

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -40
```
Expected: all PASSED (or only pre-existing failures)

If any existing CLI tests fail because they still mock `generate_images`, update them to mock `VisualRouter` instead. Look for tests using `@patch("musicvid.musicvid.generate_images")` and replace with:

```python
@patch("musicvid.musicvid.VisualRouter")
```

with the router mock returning a manifest like:
```python
router_instance = MagicMock()
router_instance.route.return_value = str(tmp_path / "scene_000.jpg")
mock_router_cls.return_value = router_instance
```

- [ ] **Step 7: Commit**

```bash
git add musicvid/musicvid.py .env.example tests/test_cli.py
git commit -m "feat(musicvid): replace Stage 3 ai-mode loop with VisualRouter for hybrid sourcing"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `visual_source` field per scene | Task 4 (director defaults) + Task 5 (router loop) |
| `search_query` field per scene | Task 4 + Task 5 |
| TYPE_VIDEO_STOCK → Pexels | Task 2 (`fetch_video_by_query`) + Task 3 (router `_route_video_stock`) |
| TYPE_PHOTO_STOCK → Unsplash | Task 3 (router `_route_photo_stock`) |
| TYPE_AI → BFL Flux | Task 1 (`generate_single_image`) + Task 3 (router `_generate_bfl`) |
| TYPE_ANIMATED → BFL + Runway | Task 3 (router `_route_animated`) |
| Fallback: Pexels → simplified query → Unsplash → AI | Task 3 (`_route_video_stock`) |
| Fallback: no UNSPLASH key → AI | Task 3 (`_route_photo_stock`) |
| Fallback: no RUNWAY key → static image | Task 3 (`_route_animated`) |
| Cache check (no re-download) | Task 3 (each `_route_*` checks `Path.exists()`) |
| Log line per scene: `[1/20] verse: TYPE_VIDEO_STOCK — 'mountain valley'` | Task 5 (`click.echo` loop) |
| `animate_mode` flag respected (never/always/auto) | Task 5 (visual_source override logic) |
| `UNSPLASH_ACCESS_KEY` in `.env.example` | Task 5 |
| Tests: `test_route_*`, `test_fallback_*`, `test_cache_respected` | Task 3 |
| `--mode stock` unchanged | Task 5 (`else` branch untouched) |

**Placeholder scan:** No TBD or placeholder text found.

**Type consistency:** `generate_single_image(prompt, output_path, provider)` defined in Task 1 and called in Task 3 with same signature. `fetch_video_by_query(query, min_duration, output_path)` defined in Task 2 and called in Task 3 with same signature. `animate_image(image_path, motion_prompt, duration, output_path)` already exists in `video_animator.py` and is called in Task 3 correctly.
