"""Tests for visual_router.VisualRouter."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

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

    def test_route_video_stock_falls_back_to_photo_then_ai(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        ai_path = str(tmp_path / "scene_000.jpg")

        with patch("musicvid.pipeline.visual_router.fetch_video_by_query", return_value=None), \
             patch.dict(os.environ, {}, clear=True), \
             patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=ai_path) as mock_gen:
            result = router.route(SCENE_VIDEO_STOCK)

        mock_gen.assert_called_once()
        assert result == ai_path

    def test_route_video_stock_fallback_uses_visual_prompt_for_bfl(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        scene = {
            "index": 0,
            "section": "verse",
            "start": 0.0,
            "end": 12.0,
            "visual_source": "TYPE_VIDEO_STOCK",
            "search_query": "mountain valley peaceful morning",
            "visual_prompt": "sunrise over misty mountain valley, wide angle",
            "motion_prompt": "",
            "animate": False,
        }
        ai_path = str(tmp_path / "scene_000.jpg")

        with patch("musicvid.pipeline.visual_router.fetch_video_by_query", return_value=None), \
             patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=ai_path) as mock_gen:
            result = router.route(scene)

        mock_gen.assert_called_once_with(
            "sunrise over misty mountain valley, wide angle",
            ai_path,
            "flux-pro",
        )
        assert result == ai_path

    def test_route_video_stock_fallback_uses_default_when_no_visual_prompt(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        ai_path = str(tmp_path / "scene_000.jpg")

        with patch("musicvid.pipeline.visual_router.fetch_video_by_query", return_value=None), \
             patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=ai_path) as mock_gen:
            result = router.route(SCENE_VIDEO_STOCK)  # SCENE_VIDEO_STOCK has visual_prompt=""

        mock_gen.assert_called_once_with(
            "nature landscape peaceful",
            ai_path,
            "flux-pro",
        )
        assert result == ai_path


class TestVisualRouterPhotoStock:
    @patch.dict(os.environ, {"UNSPLASH_ACCESS_KEY": "fake-key"})
    def test_route_photo_stock_calls_unsplash(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        output_path = str(tmp_path / "scene_001.jpg")

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "api.unsplash" in url:
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

    def test_route_photo_stock_no_unsplash_pexels_fallback(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        pexels_path = str(tmp_path / "scene_001.mp4")

        with patch.dict(os.environ, {"PEXELS_API_KEY": "pexels-key"}, clear=True), \
             patch("musicvid.pipeline.visual_router.fetch_video_by_query",
                   return_value=pexels_path) as mock_fetch, \
             patch("musicvid.pipeline.visual_router.generate_single_image") as mock_gen:
            result = router.route(SCENE_PHOTO_STOCK)

        mock_fetch.assert_called_once_with(
            SCENE_PHOTO_STOCK["search_query"],
            SCENE_PHOTO_STOCK["end"] - SCENE_PHOTO_STOCK["start"],
            str(tmp_path / "scene_001.mp4"),
        )
        mock_gen.assert_not_called()
        assert result == pexels_path


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

    def test_route_animated_no_runway_key_returns_static_image(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        image_path = str(tmp_path / "scene_003.jpg")

        with patch.dict(os.environ, {"BFL_API_KEY": "test-key", "RUNWAY_API_KEY": ""}, clear=False), \
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

        # Pre-create both cached files
        cached_video = tmp_path / "animated_scene_003.mp4"
        cached_video.write_bytes(b"cached-animation")
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
