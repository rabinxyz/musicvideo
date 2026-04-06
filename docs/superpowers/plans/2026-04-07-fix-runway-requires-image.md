# Fix Runway — promptImage Required Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Runway API integration so both TYPE_VIDEO_RUNWAY and TYPE_ANIMATED use image-to-video (BFL image → Runway animate_image) instead of broken text-to-video.

**Architecture:** Remove `generate_video_from_text` and `_submit_text_to_video` (broken — Runway requires promptImage). Both TYPE_VIDEO_RUNWAY and TYPE_ANIMATED now generate a BFL flux-dev image first, then call `animate_image()`. Model changes from `gen4.5` to `gen4_turbo`.

**Tech Stack:** Python, Runway Gen-4 API, BFL Flux API, pytest, unittest.mock

---

### Task 1: Change Runway model to gen4_turbo and remove text-to-video functions

**Files:**
- Modify: `musicvid/pipeline/video_animator.py:46` (model change)
- Modify: `musicvid/pipeline/video_animator.py:70-88` (remove `_submit_text_to_video`)
- Modify: `musicvid/pipeline/video_animator.py:161-187` (remove `generate_video_from_text`)
- Test: `tests/test_video_animator.py`

- [ ] **Step 1: Write failing test for gen4_turbo model**

In `tests/test_video_animator.py`, update the existing payload test to expect `gen4_turbo`:

```python
# In TestAnimateImage.test_submit_called_with_correct_payload (line 165)
# Change line 184 from:
#   assert payload["model"] == "gen4.5"
# To:
#   assert payload["model"] == "gen4_turbo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_video_animator.py::TestAnimateImage::test_submit_called_with_correct_payload -v`
Expected: FAIL — `AssertionError: assert 'gen4.5' == 'gen4_turbo'`

- [ ] **Step 3: Change model to gen4_turbo in _submit_animation**

In `musicvid/pipeline/video_animator.py`, line 46, change:
```python
# Old:
        "model": "gen4.5",
# New:
        "model": "gen4_turbo",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_video_animator.py::TestAnimateImage::test_submit_called_with_correct_payload -v`
Expected: PASS

- [ ] **Step 5: Remove _submit_text_to_video and generate_video_from_text**

In `musicvid/pipeline/video_animator.py`:
- Delete the entire `_submit_text_to_video` function (lines 65-88, including the `@retry` decorator)
- Delete the entire `generate_video_from_text` function (lines 161-187)

- [ ] **Step 6: Remove TestGenerateVideoFromText test class and update error logging test**

In `tests/test_video_animator.py`:
- Delete the entire `TestGenerateVideoFromText` class (lines 237-340)
- Delete the `test_submit_text_to_video_logs_error_body` test from `TestRunwayErrorLogging` (lines 346-369) — the function it tests no longer exists
- Keep `test_submit_animation_logs_error_body` — it tests `_submit_animation` which still exists

- [ ] **Step 7: Run all video_animator tests**

Run: `python3 -m pytest tests/test_video_animator.py -v`
Expected: All tests PASS (TestAnimateImage: 6 tests, TestPollAnimationOutputFormats: 3 tests, TestRunwayErrorLogging: 1 test)

- [ ] **Step 8: Commit**

```bash
git add musicvid/pipeline/video_animator.py tests/test_video_animator.py
git commit -m "fix(runway): use gen4_turbo model, remove broken text-to-video functions

Runway API requires promptImage — text-to-video without image causes 400 error.
Remove _submit_text_to_video and generate_video_from_text entirely."
```

---

### Task 2: Rewrite visual_router to use BFL image → animate_image flow

**Files:**
- Modify: `musicvid/pipeline/visual_router.py:9` (import change)
- Modify: `musicvid/pipeline/visual_router.py:54-67` (docstring update)
- Modify: `musicvid/pipeline/visual_router.py:161-215` (_route_animated and _route_runway_text_to_video)
- Test: `tests/test_visual_router.py`

- [ ] **Step 1: Write failing tests for new _route_animated (BFL → animate_image)**

In `tests/test_visual_router.py`, replace the `TestVisualRouterAnimatedTextToVideo` class (lines 265-410) with:

```python
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

        # BFL called with visual_prompt and flux-dev provider (not self.provider)
        mock_gen_img.assert_called_once_with(
            SCENE_ANIMATED["visual_prompt"],
            image_path,
            "flux-dev",
        )
        # animate_image called with generated image and motion_prompt
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

        # Pre-create BFL image cache
        cached_img = tmp_path / "scene_003.jpg"
        cached_img.write_bytes(b"cached-bfl-image")
        video_path = str(tmp_path / "animated_scene_003.mp4")

        with patch("musicvid.pipeline.visual_router.generate_single_image") as mock_gen_img, \
             patch("musicvid.pipeline.visual_router.animate_image",
                   return_value=video_path) as mock_animate:
            result = router.route(SCENE_ANIMATED)

        # BFL NOT called — image already cached
        mock_gen_img.assert_not_called()
        # animate_image called with cached image path
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

        # BFL called twice: once for Runway input (flux-dev), once for fallback (self.provider)
        assert mock_gen_img.call_count == 2
        # Second call is fallback with self.provider
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
```

- [ ] **Step 2: Write failing tests for new _route_runway (BFL → animate_image)**

In `tests/test_visual_router.py`, replace the `TestVisualRouterRunway` class (lines 425-517) with:

```python
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

        # When visual_prompt is empty, BFL gets motion_prompt as fallback
        bfl_prompt = mock_gen_img.call_args[0][0]
        assert bfl_prompt == "nature landscape"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_visual_router.py::TestVisualRouterAnimatedImageToVideo tests/test_visual_router.py::TestVisualRouterRunway -v`
Expected: FAIL — `generate_video_from_text` is still imported/called

- [ ] **Step 4: Update visual_router.py import**

In `musicvid/pipeline/visual_router.py`, line 9, change:
```python
# Old:
from musicvid.pipeline.video_animator import animate_image, generate_video_from_text
# New:
from musicvid.pipeline.video_animator import animate_image
```

- [ ] **Step 5: Rewrite _route_animated method**

In `musicvid/pipeline/visual_router.py`, replace the `_route_animated` method (lines 161-181) with:

```python
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
        motion = scene.get("motion_prompt", "slow camera push forward, gentle movement")
        try:
            return animate_image(image_path, motion, duration=5, output_path=output_path)
        except Exception as exc:
            print(f"  WARN: Runway animate failed for scene {idx} — fallback TYPE_AI ({exc})")
            return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)
```

- [ ] **Step 6: Rewrite _route_runway_text_to_video method**

In `musicvid/pipeline/visual_router.py`, replace `_route_runway_text_to_video` (lines 183-215) with:

```python
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
            motion = scene.get("motion_prompt", "slow camera push forward, gentle movement")
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
```

- [ ] **Step 7: Update route() dispatch to call renamed method**

In `musicvid/pipeline/visual_router.py`, line 86, change:
```python
# Old:
            return self._route_runway_text_to_video(scene, idx, duration)
# New:
            return self._route_runway(scene, idx, duration)
```

- [ ] **Step 8: Update class docstring**

In `musicvid/pipeline/visual_router.py`, update the class docstring (lines 55-67) to reflect the new flow:

```python
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
```

- [ ] **Step 9: Run visual_router tests**

Run: `python3 -m pytest tests/test_visual_router.py -v`
Expected: All tests PASS

- [ ] **Step 10: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS. Watch for any other tests that import `generate_video_from_text`.

- [ ] **Step 11: Commit**

```bash
git add musicvid/pipeline/visual_router.py tests/test_visual_router.py
git commit -m "fix(router): use BFL image + Runway animate_image for TYPE_VIDEO_RUNWAY and TYPE_ANIMATED

Both routes now: 1) generate BFL flux-dev image, 2) animate via Runway image-to-video.
Fixes 400 Bad Request caused by missing promptImage in text-to-video calls."
```

---

### Task 3: Update director prompt to require visual_prompt for Runway types

**Files:**
- Modify: `musicvid/prompts/director_system.txt:41-62`

- [ ] **Step 1: Update TYPE_VIDEO_RUNWAY description**

In `musicvid/prompts/director_system.txt`, replace lines 41-57 with:

```
TYPE_VIDEO_RUNWAY — BFL image + Runway animate ($0.50, primary AI video)
  When: chorus and bridge ALWAYS. Verse when lyrics describe motion, emotion, action.
        Use when you want unique AI cinematography that stock cannot provide.
        Minimum 40% of scenes in runway mode.
  Fields: set visual_prompt (REQUIRED — BFL generates this image, min 3 sentences, documentary style),
          set motion_prompt (REQUIRED — Runway animates the image, 2-3 sentences: camera movement + mood),
          set search_query to ""
  visual_prompt describes WHAT the image shows (subject, composition, lighting).
  motion_prompt describes HOW the camera moves (pan, zoom, rise, push).
  Example:
    Chorus: visual_prompt: "Person silhouette on mountain ridge at dawn, arms open, golden light, wide shot, documentary style"
            motion_prompt: "Slow camera rise revealing vast landscape below, golden morning light, film grain"
    Verse:  visual_prompt: "Morning mist in mountain valley, soft diffused light, no people, nature documentary"
            motion_prompt: "Gentle push forward through mist, peaceful atmosphere, natural colors"
```

- [ ] **Step 2: Update TYPE_ANIMATED description**

In `musicvid/prompts/director_system.txt`, replace lines 59-62 with:

```
TYPE_ANIMATED — BFL image + Runway animate ($0.50, climactic)
  When: first chorus, last chorus, or bridge. Max 25% of scenes,
        never adjacent, min 3s scene. Also set animate: true.
  Fields: set visual_prompt (REQUIRED — BFL generates this image),
          set motion_prompt (REQUIRED — Runway animates: camera movement + mood),
          set search_query to ""
```

- [ ] **Step 3: Commit**

```bash
git add musicvid/prompts/director_system.txt
git commit -m "docs(director): update TYPE_VIDEO_RUNWAY and TYPE_ANIMATED to require visual_prompt + motion_prompt

Both types now use BFL image → Runway animate flow, so visual_prompt is required for BFL
and motion_prompt is required for Runway animation."
```

---

### Task 4: Fix any remaining references to generate_video_from_text across the codebase

**Files:**
- Search: all `.py` files for `generate_video_from_text`
- Modify: any files still referencing the removed function

- [ ] **Step 1: Search for remaining references**

Run: `grep -rn "generate_video_from_text" musicvid/ tests/`
Expected: No results. If any remain, fix them.

- [ ] **Step 2: Search for _submit_text_to_video references**

Run: `grep -rn "_submit_text_to_video" musicvid/ tests/`
Expected: No results.

- [ ] **Step 3: Search for _route_runway_text_to_video references**

Run: `grep -rn "_route_runway_text_to_video" musicvid/ tests/`
Expected: No results.

- [ ] **Step 4: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: remove remaining references to deleted text-to-video functions"
```
