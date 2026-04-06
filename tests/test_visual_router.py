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

    def test_route_video_stock_falls_back_to_bfl(self, tmp_path):
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


class TestVisualRouterAnimatedImageToVideo:
    """Tests for _route_animated using BFL image → Runway animate_image."""

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_generates_bfl_image_then_animates(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        image_path = str(tmp_path / "scene_003.jpg")
        video_path = str(tmp_path / "animated_scene_003.mp4")

        with patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path) as mock_gen_img, \
             patch("musicvid.pipeline.visual_router.animate_image",
                   return_value=video_path) as mock_animate:
            result = router.route(SCENE_ANIMATED)

        mock_gen_img.assert_called_once_with(
            SCENE_ANIMATED["visual_prompt"],
            image_path,
            "flux-dev",
        )
        mock_animate.assert_called_once_with(
            image_path,
            SCENE_ANIMATED["motion_prompt"],
            duration=5,
            output_path=video_path,
        )
        assert result == video_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_uses_cached_bfl_image(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        cached_img = tmp_path / "scene_003.jpg"
        cached_img.write_bytes(b"cached-bfl-image")
        video_path = str(tmp_path / "animated_scene_003.mp4")

        with patch("musicvid.pipeline.visual_router.generate_single_image") as mock_gen_img, \
             patch("musicvid.pipeline.visual_router.animate_image",
                   return_value=video_path) as mock_animate:
            result = router.route(SCENE_ANIMATED)

        mock_gen_img.assert_not_called()
        mock_animate.assert_called_once_with(
            str(cached_img),
            SCENE_ANIMATED["motion_prompt"],
            duration=5,
            output_path=video_path,
        )
        assert result == video_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_returns_cached_video(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        cached_video = tmp_path / "animated_scene_003.mp4"
        cached_video.write_bytes(b"cached-animation")

        with patch("musicvid.pipeline.visual_router.generate_single_image") as mock_gen_img, \
             patch("musicvid.pipeline.visual_router.animate_image") as mock_animate:
            result = router.route(SCENE_ANIMATED)

        mock_gen_img.assert_not_called()
        mock_animate.assert_not_called()
        assert result == str(cached_video)

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_fallback_to_type_ai_on_runway_error(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        image_path = str(tmp_path / "scene_003.jpg")

        with patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path) as mock_gen_img, \
             patch("musicvid.pipeline.visual_router.animate_image",
                   side_effect=RuntimeError("Runway failed")):
            result = router.route(SCENE_ANIMATED)

        assert mock_gen_img.call_count == 2
        # First call: BFL for Runway input (flux-dev)
        assert mock_gen_img.call_args_list[0] == (
            (SCENE_ANIMATED["visual_prompt"], image_path, "flux-dev"),
        )
        # Second call: fallback with self.provider
        assert mock_gen_img.call_args_list[1] == (
            (SCENE_ANIMATED["visual_prompt"], image_path, "flux-pro"),
        )
        assert result == image_path

    def test_route_animated_no_runway_key_falls_back_to_type_ai(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        image_path = str(tmp_path / "scene_003.jpg")

        with patch.dict(os.environ, {"RUNWAY_API_KEY": ""}, clear=False), \
             patch("musicvid.pipeline.visual_router.animate_image") as mock_animate, \
             patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path) as mock_gen_img:
            result = router.route(SCENE_ANIMATED)

        mock_animate.assert_not_called()
        mock_gen_img.assert_called_once()
        assert result == image_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_uses_default_motion_when_missing(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        scene = {
            "index": 0,
            "visual_source": "TYPE_ANIMATED",
            "visual_prompt": "Mountain scene",
            "start": 0.0,
            "end": 10.0,
            "animate": True,
        }
        image_path = str(tmp_path / "scene_000.jpg")
        video_path = str(tmp_path / "animated_scene_000.mp4")

        with patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path), \
             patch("musicvid.pipeline.visual_router.animate_image",
                   return_value=video_path) as mock_animate:
            router.route(scene)

        called_motion = mock_animate.call_args[0][1]
        assert called_motion == "slow camera push forward, gentle movement"


SCENE_RUNWAY = {
    "index": 4,
    "section": "chorus",
    "start": 48.0,
    "end": 60.0,
    "visual_source": "TYPE_VIDEO_RUNWAY",
    "search_query": "",
    "visual_prompt": "Person on hilltop arms raised, golden sunrise, wide shot",
    "motion_prompt": "slow camera rises revealing vast mountain landscape, golden light",
    "animate": False,
}


class TestVisualRouterRunway:
    """Tests for TYPE_VIDEO_RUNWAY routing — BFL image → Runway animate_image."""

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_runway_generates_bfl_image_then_animates(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        image_path = str(tmp_path / "runway_img_004.jpg")
        video_path = str(tmp_path / "runway_scene_004.mp4")

        with patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path) as mock_gen_img, \
             patch("musicvid.pipeline.visual_router.animate_image",
                   return_value=video_path) as mock_animate:
            result = router.route(SCENE_RUNWAY)

        mock_gen_img.assert_called_once_with(
            SCENE_RUNWAY["visual_prompt"],
            image_path,
            "flux-dev",
        )
        mock_animate.assert_called_once_with(
            image_path,
            SCENE_RUNWAY["motion_prompt"],
            duration=5,
            output_path=video_path,
        )
        assert result == video_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_runway_uses_cache_if_video_exists(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")
        video_path = tmp_path / "runway_scene_004.mp4"
        video_path.write_bytes(b"cached")

        with patch("musicvid.pipeline.visual_router.generate_single_image") as mock_gen_img, \
             patch("musicvid.pipeline.visual_router.animate_image") as mock_animate:
            result = router.route(SCENE_RUNWAY)

        mock_gen_img.assert_not_called()
        mock_animate.assert_not_called()
        assert result == str(video_path)

    @patch.dict(os.environ, {}, clear=True)
    def test_route_runway_falls_back_to_pexels_when_no_api_key(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")
        pexels_path = str(tmp_path / "scene_004.mp4")

        with patch("musicvid.pipeline.visual_router.animate_image") as mock_animate, \
             patch("musicvid.pipeline.visual_router.fetch_video_by_query",
                   return_value=pexels_path) as mock_fetch:
            result = router.route(SCENE_RUNWAY)

        mock_animate.assert_not_called()
        mock_fetch.assert_called()
        assert result == pexels_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_runway_falls_back_to_pexels_on_runway_failure(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")
        pexels_path = str(tmp_path / "scene_004.mp4")
        image_path = str(tmp_path / "runway_img_004.jpg")

        with patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path), \
             patch("musicvid.pipeline.visual_router.animate_image",
                   side_effect=RuntimeError("Runway error")), \
             patch("musicvid.pipeline.visual_router.fetch_video_by_query",
                   return_value=pexels_path) as mock_fetch:
            result = router.route(SCENE_RUNWAY)

        mock_fetch.assert_called()
        assert result == pexels_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_runway_uses_visual_prompt_fallback_for_bfl(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        scene = {**SCENE_RUNWAY, "visual_prompt": "", "motion_prompt": "slow pan"}
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")
        image_path = str(tmp_path / "runway_img_004.jpg")
        video_path = str(tmp_path / "runway_scene_004.mp4")

        with patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path) as mock_gen_img, \
             patch("musicvid.pipeline.visual_router.animate_image",
                   return_value=video_path):
            router.route(scene)

        bfl_prompt = mock_gen_img.call_args[0][0]
        assert bfl_prompt == "nature landscape"


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
