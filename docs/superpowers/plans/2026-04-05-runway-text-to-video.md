# Runway Text-to-Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two-step TYPE_ANIMATED pipeline (BFL image → Runway animate) with direct Runway text-to-video generation, saving ~$0.04/scene and ~30s/scene.

**Architecture:** Add `generate_video_from_text()` to `video_animator.py` that POSTs to Runway without `promptImage`. Update `visual_router.py` `_route_animated` to call this instead of BFL+animate. Update `director_system.txt` so `motion_prompt` describes the full scene (not just camera motion) for TYPE_ANIMATED.

**Tech Stack:** Python 3.14, requests, tenacity, unittest.mock, pytest

---

### Task 1: Add `generate_video_from_text()` to video_animator.py

**Files:**
- Modify: `musicvid/pipeline/video_animator.py`
- Modify: `tests/test_video_animator.py`

- [ ] **Step 1: Write failing tests for `generate_video_from_text`**

Add a new test class `TestGenerateVideoFromText` to `tests/test_video_animator.py`. Add these tests:

```python
class TestGenerateVideoFromText:
    """Tests for generate_video_from_text() — text-to-video without input image."""

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_returns_output_path(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import generate_video_from_text

        mock_time.monotonic.side_effect = [0.0, 1.0, 2.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-t2v")
        mock_requests.get.side_effect = [
            _make_poll_response("SUCCEEDED", "https://runway.ai/video.mp4"),
            _make_download_response(),
        ]

        out = tmp_path / "text_video_000.mp4"
        result = generate_video_from_text("Golden sunrise over mountains", output_path=str(out))

        assert result == str(out)
        assert out.exists()

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_payload_has_no_prompt_image(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import generate_video_from_text

        mock_time.monotonic.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-t2v")
        mock_requests.get.side_effect = [
            _make_poll_response("SUCCEEDED", "https://runway.ai/video.mp4"),
            _make_download_response(),
        ]

        out = tmp_path / "out.mp4"
        generate_video_from_text("Sunset over ocean", duration=5, output_path=str(out))

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["model"] == "gen4.5"
        assert payload["promptText"] == "Sunset over ocean"
        assert payload["duration"] == 5
        assert payload["ratio"] == "1280:720"
        assert "promptImage" not in payload

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_cache_hit_skips_api(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import generate_video_from_text

        out = tmp_path / "text_video_000.mp4"
        out.write_bytes(b"existing video")

        result = generate_video_from_text("Any prompt", output_path=str(out))

        assert result == str(out)
        mock_requests.post.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_when_no_api_key(self, tmp_path):
        from musicvid.pipeline.video_animator import generate_video_from_text

        out = tmp_path / "out.mp4"
        with pytest.raises(RuntimeError, match="RUNWAY_API_KEY"):
            generate_video_from_text("A prompt", output_path=str(out))

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_timeout_raises_timeout_error(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import generate_video_from_text

        mock_time.monotonic.side_effect = [0.0, 301.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-slow")
        mock_requests.get.return_value = _make_poll_response("PENDING")

        out = tmp_path / "out.mp4"
        with pytest.raises(TimeoutError):
            generate_video_from_text("A prompt", output_path=str(out))

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_failed_status_raises_runtime_error(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import generate_video_from_text

        mock_time.monotonic.side_effect = [0.0, 1.0, 2.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-fail")
        mock_requests.get.side_effect = [
            _make_poll_response("FAILED"),
        ]

        out = tmp_path / "out.mp4"
        with pytest.raises(RuntimeError, match="FAILED"):
            generate_video_from_text("A prompt", output_path=str(out))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_video_animator.py::TestGenerateVideoFromText -v`
Expected: FAIL — `ImportError: cannot import name 'generate_video_from_text'`

- [ ] **Step 3: Implement `_submit_text_to_video` and `generate_video_from_text`**

Add to `musicvid/pipeline/video_animator.py`, after the existing `_submit_animation` function:

```python
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_retryable),
)
def _submit_text_to_video(prompt, duration):
    """POST to Runway API to start text-to-video task (no input image). Returns task_id."""
    payload = {
        "model": "gen4.5",
        "promptText": prompt,
        "duration": duration,
        "ratio": "1280:720",
    }
    resp = requests.post(
        f"{RUNWAY_API_BASE}/v1/image_to_video",
        json=payload,
        headers=_get_headers(),
    )
    resp.raise_for_status()
    return resp.json()["id"]
```

Add at the end of the file, after `animate_image`:

```python
def generate_video_from_text(prompt, duration=5, output_path=None):
    """Generate video from text prompt using Runway Gen-4.5 (no input image).

    Args:
        prompt: Text describing the desired video scene.
        duration: Video duration in seconds (default 5).
        output_path: Path to write output .mp4. Required.

    Returns:
        str: Path to the generated .mp4 file.

    Raises:
        RuntimeError: If RUNWAY_API_KEY not set or Runway task fails.
        TimeoutError: If Runway API does not respond within 300s.
    """
    if not os.environ.get("RUNWAY_API_KEY"):
        raise RuntimeError(
            "RUNWAY_API_KEY not set. Get a key from app.runwayml.com → Settings → API Keys"
        )

    if output_path and Path(output_path).exists():
        return str(output_path)

    task_id = _submit_text_to_video(prompt, duration)
    video_url = _poll_animation(task_id)
    _download_video(video_url, output_path)
    return str(output_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_video_animator.py -v`
Expected: ALL PASS (existing tests + 6 new tests)

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/video_animator.py tests/test_video_animator.py
git commit -m "feat: add generate_video_from_text() for Runway text-to-video"
```

---

### Task 2: Update `_route_animated` in visual_router.py to use text-to-video

**Files:**
- Modify: `musicvid/pipeline/visual_router.py`
- Modify: `tests/test_visual_router.py`

- [ ] **Step 1: Write failing tests for new `_route_animated` behavior**

Replace the existing `TestVisualRouterAnimated` class and add new tests in `tests/test_visual_router.py`.

First, update the import at top of `visual_router.py` — the test will verify the new import exists:

Add a new test class after the existing `TestVisualRouterAnimated`:

```python
class TestVisualRouterAnimatedTextToVideo:
    """Tests for _route_animated using text-to-video (no BFL image step)."""

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_calls_generate_video_from_text(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        video_path = str(tmp_path / "animated_scene_003.mp4")

        with patch("musicvid.pipeline.visual_router.generate_video_from_text",
                   return_value=video_path) as mock_gen_video, \
             patch("musicvid.pipeline.visual_router.generate_single_image") as mock_gen_img:
            result = router.route(SCENE_ANIMATED)

        mock_gen_img.assert_not_called()
        mock_gen_video.assert_called_once_with(
            "Person on hilltop arms raised, golden sunrise, wide shot slow camera rises revealing vast landscape",
            duration=5,
            output_path=video_path,
        )
        assert result == video_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_builds_video_prompt_from_visual_and_motion(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        scene = {
            "index": 0,
            "visual_source": "TYPE_ANIMATED",
            "visual_prompt": "Golden light over valley",
            "motion_prompt": "slow camera rise",
            "start": 0.0,
            "end": 10.0,
            "animate": True,
        }
        video_path = str(tmp_path / "animated_scene_000.mp4")

        with patch("musicvid.pipeline.visual_router.generate_video_from_text",
                   return_value=video_path) as mock_gen:
            router.route(scene)

        called_prompt = mock_gen.call_args[0][0]
        assert called_prompt == "Golden light over valley slow camera rise"

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_truncates_long_visual_prompt(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        long_visual = "A" * 500
        scene = {
            "index": 0,
            "visual_source": "TYPE_ANIMATED",
            "visual_prompt": long_visual,
            "motion_prompt": "slow pan left",
            "start": 0.0,
            "end": 10.0,
            "animate": True,
        }
        video_path = str(tmp_path / "animated_scene_000.mp4")

        with patch("musicvid.pipeline.visual_router.generate_video_from_text",
                   return_value=video_path) as mock_gen:
            router.route(scene)

        called_prompt = mock_gen.call_args[0][0]
        # visual truncated to 400 + space + motion_prompt
        assert called_prompt == "A" * 400 + " slow pan left"
        assert len(called_prompt) <= 400 + 1 + len("slow pan left")

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_fallback_to_type_ai_on_error(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        image_path = str(tmp_path / "scene_003.jpg")

        with patch("musicvid.pipeline.visual_router.generate_video_from_text",
                   side_effect=RuntimeError("Runway failed")) as mock_gen_video, \
             patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path) as mock_gen_img:
            result = router.route(SCENE_ANIMATED)

        mock_gen_video.assert_called_once()
        mock_gen_img.assert_called_once_with(
            SCENE_ANIMATED["visual_prompt"],
            image_path,
            "flux-pro",
        )
        assert result == image_path

    def test_route_animated_no_runway_key_falls_back_to_type_ai(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        image_path = str(tmp_path / "scene_003.jpg")

        with patch.dict(os.environ, {"RUNWAY_API_KEY": ""}, clear=False), \
             patch("musicvid.pipeline.visual_router.generate_video_from_text") as mock_gen_video, \
             patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=image_path) as mock_gen_img:
            result = router.route(SCENE_ANIMATED)

        mock_gen_video.assert_not_called()
        mock_gen_img.assert_called_once()
        assert result == image_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_animated_returns_cached_video(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        cached_video = tmp_path / "animated_scene_003.mp4"
        cached_video.write_bytes(b"cached-animation")

        with patch("musicvid.pipeline.visual_router.generate_video_from_text") as mock_gen_video, \
             patch("musicvid.pipeline.visual_router.generate_single_image") as mock_gen_img:
            result = router.route(SCENE_ANIMATED)

        mock_gen_video.assert_not_called()
        mock_gen_img.assert_not_called()
        assert result == str(cached_video)

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
            # motion_prompt intentionally omitted
        }
        video_path = str(tmp_path / "animated_scene_000.mp4")

        with patch("musicvid.pipeline.visual_router.generate_video_from_text",
                   return_value=video_path) as mock_gen:
            router.route(scene)

        called_prompt = mock_gen.call_args[0][0]
        assert called_prompt == "Mountain scene slow camera push forward"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_visual_router.py::TestVisualRouterAnimatedTextToVideo -v`
Expected: FAIL — `ImportError` or assertion errors since `_route_animated` still calls BFL + animate_image

- [ ] **Step 3: Update `_route_animated` in visual_router.py**

Replace the import line and `_route_animated` method in `musicvid/pipeline/visual_router.py`.

Change the import from:
```python
from musicvid.pipeline.video_animator import animate_image
```
to:
```python
from musicvid.pipeline.video_animator import animate_image, generate_video_from_text
```

Replace the `_route_animated` method:
```python
    def _route_animated(self, scene, idx, duration):
        output_path = str(self.cache_dir / f"animated_scene_{idx:03d}.mp4")
        if Path(output_path).exists():
            return output_path

        runway_key = os.environ.get("RUNWAY_API_KEY", "")
        if not runway_key:
            print(f"  Fallback: scene {idx} TYPE_ANIMATED → TYPE_AI (no RUNWAY_API_KEY)")
            return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)

        visual = scene.get("visual_prompt", "")
        motion = scene.get("motion_prompt", "slow camera push forward")
        if len(visual) > 500:
            visual = visual[:400]
        video_prompt = f"{visual} {motion}".strip()

        try:
            return generate_video_from_text(video_prompt, duration=5, output_path=output_path)
        except Exception as exc:
            print(f"  WARN: Runway text-to-video failed for scene {idx} — fallback TYPE_AI ({exc})")
            return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)
```

- [ ] **Step 4: Remove old `TestVisualRouterAnimated` tests that expect BFL+animate behavior**

Delete the entire `TestVisualRouterAnimated` class (lines 265-325 in `tests/test_visual_router.py`) and the `TestVisualRouterAnimatedDuration` class (lines 328-349). These tested the old two-step flow. The new `TestVisualRouterAnimatedTextToVideo` class covers all the same scenarios.

- [ ] **Step 5: Run all tests to verify they pass**

Run: `python3 -m pytest tests/test_visual_router.py -v`
Expected: ALL PASS

Then run full suite:
Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS (total count changes due to removed old tests + added new tests)

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/visual_router.py tests/test_visual_router.py
git commit -m "feat: switch TYPE_ANIMATED from BFL+animate to Runway text-to-video"
```

---

### Task 3: Update director_system.txt for text-to-video motion_prompt guidance

**Files:**
- Modify: `musicvid/prompts/director_system.txt`
- Modify: `tests/test_visual_router.py` (no new tests needed — prompt changes are in the director system prompt, not in code logic)

- [ ] **Step 1: Update TYPE_ANIMATED description in director_system.txt**

In `musicvid/prompts/director_system.txt`, replace the TYPE_ANIMATED section under VISUAL SOURCE SELECTION (around line 29-32):

Old:
```
TYPE_ANIMATED — BFL image + Runway Gen-4 video ($0.54, climactic)
  When: TYPE_AI scene that is first chorus, last chorus, or bridge. Max 25% of scenes,
        never adjacent, min 6s scene. Also set animate: true.
  Fields: set visual_prompt, motion_prompt, set search_query to ""
```

New:
```
TYPE_ANIMATED — Runway Gen-4.5 text-to-video ($0.50, climactic)
  When: first chorus, last chorus, or bridge. Max 25% of scenes,
        never adjacent, min 3s scene. Also set animate: true.
  Fields: set visual_prompt (can be empty), motion_prompt (FULL scene description), set search_query to ""
```

- [ ] **Step 2: Update ANIMATION RULES section**

Replace the ANIMATION RULES section (around lines 90-101):

Old:
```
ANIMATION RULES:
- Add "animate" (bool) and "motion_prompt" (string) to every scene
- Set animate: true ONLY for: first chorus, bridge, last chorus before outro
- NEVER set animate: true for: outro, any scene shorter than 6 seconds, two adjacent scenes
- Maximum 1 animated scene per 4 scenes (25% cap, round down; minimum 1 allowed)
- Two scenes with animate: true must NEVER be adjacent — always have at least 1 static scene between them
- motion_prompt describes ONLY the camera/scene motion (not content), e.g.:
  "Slow camera push forward, gentle breeze moves the trees"
  "Camera slowly rises revealing the landscape below, clouds drift gently"
  "Subtle zoom out, light rays sweep across the scene"
- Avoid fast or jarring motion — worship music requires slow, peaceful movement
- If animate: false, set motion_prompt to ""
```

New:
```
ANIMATION RULES:
- Add "animate" (bool) and "motion_prompt" (string) to every scene
- Set animate: true ONLY for: first chorus, bridge, last chorus before outro
- NEVER set animate: true for: outro, any scene shorter than 3 seconds, two adjacent scenes
- Maximum 1 animated scene per 4 scenes (25% cap, round down; minimum 1 allowed)
- Two scenes with animate: true must NEVER be adjacent — always have at least 1 static scene between them
- For TYPE_ANIMATED scenes, motion_prompt describes the FULL video scene (Runway generates video from text):
  - What happens in frame (subject + action + mood)
  - Camera movement
  - Lighting and atmosphere
  - Maximum 2-3 sentences, concrete and specific
  Examples:
  "Slow camera rise over misty mountain valley at dawn, golden light breaking through clouds, person silhouette on ridge, documentary cinematic style, natural colors"
  "Gentle push forward through outdoor worship gathering, people with hands raised at sunset, warm golden backlight, authentic documentary feel, real emotion"
  "Camera slowly pulls back revealing vast ocean horizon, waves in foreground, light dancing on water surface, contemplative mood, film grain aesthetic"
- For non-animated scenes (animate: false), set motion_prompt to ""
- Avoid fast or jarring motion — worship music requires slow, peaceful movement
```

- [ ] **Step 3: Run tests to verify nothing broke**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS (prompt text changes don't affect code logic tests)

- [ ] **Step 4: Commit**

```bash
git add musicvid/prompts/director_system.txt
git commit -m "docs: update director prompt for Runway text-to-video motion_prompt"
```
