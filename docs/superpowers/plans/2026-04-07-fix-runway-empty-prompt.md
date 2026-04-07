# Fix Runway Empty promptText Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Runway 400 errors caused by empty/None `motion_prompt` by adding fallback defaults at three layers: `video_animator.py`, `visual_router.py`, and `director_system.txt`.

**Architecture:** Defense-in-depth — the director prompt tells Claude to always provide motion_prompt; `visual_router.py` catches None/"" before calling animate; `video_animator.py` is the last-resort guard before the API call. Each layer has its own fallback string.

**Tech Stack:** Python, unittest.mock, Runway Gen-4 API

---

### Task 1: Guard empty promptText in video_animator.py

**Files:**
- Modify: `musicvid/pipeline/video_animator.py:43-51` (`_submit_animation`)
- Test: `tests/test_video_animator.py`

- [ ] **Step 1: Write failing tests for empty/None motion_prompt**

Add to `tests/test_video_animator.py`:

```python
class TestEmptyPromptFallback:
    """Ensure _submit_animation uses fallback when motion_prompt is empty or None."""

    @patch("musicvid.pipeline.video_animator.time")
    @patch("musicvid.pipeline.video_animator.requests")
    def test_empty_string_gets_fallback(self, mock_requests, mock_time):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "task123"}
        mock_requests.post.return_value = mock_resp
        mock_requests.exceptions = requests.exceptions

        from musicvid.pipeline.video_animator import _submit_animation
        _submit_animation("base64data", "", 5)

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["promptText"] == "Slow cinematic camera movement, natural light"

    @patch("musicvid.pipeline.video_animator.time")
    @patch("musicvid.pipeline.video_animator.requests")
    def test_none_gets_fallback(self, mock_requests, mock_time):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "task123"}
        mock_requests.post.return_value = mock_resp
        mock_requests.exceptions = requests.exceptions

        from musicvid.pipeline.video_animator import _submit_animation
        _submit_animation("base64data", None, 5)

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["promptText"] == "Slow cinematic camera movement, natural light"

    @patch("musicvid.pipeline.video_animator.time")
    @patch("musicvid.pipeline.video_animator.requests")
    def test_whitespace_only_gets_fallback(self, mock_requests, mock_time):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "task123"}
        mock_requests.post.return_value = mock_resp
        mock_requests.exceptions = requests.exceptions

        from musicvid.pipeline.video_animator import _submit_animation
        _submit_animation("base64data", "   ", 5)

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["promptText"] == "Slow cinematic camera movement, natural light"

    @patch("musicvid.pipeline.video_animator.time")
    @patch("musicvid.pipeline.video_animator.requests")
    def test_valid_prompt_passes_through_stripped(self, mock_requests, mock_time):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "task123"}
        mock_requests.post.return_value = mock_resp
        mock_requests.exceptions = requests.exceptions

        from musicvid.pipeline.video_animator import _submit_animation
        _submit_animation("base64data", "  zoom in slowly  ", 5)

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["promptText"] == "zoom in slowly"

    @patch("musicvid.pipeline.video_animator.time")
    @patch("musicvid.pipeline.video_animator.requests")
    def test_long_prompt_truncated_to_500(self, mock_requests, mock_time):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "task123"}
        mock_requests.post.return_value = mock_resp
        mock_requests.exceptions = requests.exceptions

        from musicvid.pipeline.video_animator import _submit_animation
        long_prompt = "a" * 600
        _submit_animation("base64data", long_prompt, 5)

        payload = mock_requests.post.call_args[1]["json"]
        assert len(payload["promptText"]) == 500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_video_animator.py::TestEmptyPromptFallback -v`
Expected: FAIL — empty/None prompts pass through unchanged, no truncation

- [ ] **Step 3: Implement fallback in _submit_animation**

In `musicvid/pipeline/video_animator.py`, modify `_submit_animation` (line 43-51):

```python
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_retryable),
)
def _submit_animation(image_b64, motion_prompt, duration):
    """POST to Runway API to start image-to-video task. Returns task_id."""
    if not motion_prompt or not motion_prompt.strip():
        motion_prompt = "Slow cinematic camera movement, natural light"

    payload = {
        "model": "gen4_turbo",
        "promptImage": image_b64,
        "promptText": motion_prompt.strip()[:500],
        "duration": duration,
        "ratio": "1280:720",
    }
    resp = requests.post(
        f"{RUNWAY_API_BASE}/v1/image_to_video",
        json=payload,
        headers=_get_headers(),
    )
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(f"Runway error {resp.status_code}: {resp.text}")
        raise
    return resp.json()["id"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_video_animator.py::TestEmptyPromptFallback -v`
Expected: All 5 PASS

- [ ] **Step 5: Run full video_animator test suite**

Run: `python3 -m pytest tests/test_video_animator.py -v`
Expected: All tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/video_animator.py tests/test_video_animator.py
git commit -m "fix: guard empty promptText in _submit_animation with fallback and truncation"
```

---

### Task 2: Fix motion_prompt extraction in visual_router.py

**Files:**
- Modify: `musicvid/pipeline/visual_router.py:165-190` (`_route_animated`) and `musicvid/pipeline/visual_router.py:192-227` (`_route_runway`)
- Test: `tests/test_visual_router.py`

- [ ] **Step 1: Write failing tests for empty motion_prompt in both routes**

Add to `tests/test_visual_router.py`:

```python
class TestMotionPromptFallback:
    """Ensure _route_animated and _route_runway handle empty/None motion_prompt."""

    @patch("musicvid.pipeline.visual_router.animate_image")
    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key", "BFL_API_KEY": "test-key"})
    def test_route_animated_none_motion_prompt(self, mock_gen, mock_animate):
        mock_gen.return_value = "/tmp/scene_000.jpg"
        mock_animate.return_value = "/tmp/animated_scene_000.mp4"

        router = VisualRouter("/tmp/cache", provider="flux-dev")
        scene = {
            "index": 0, "start": 0, "end": 5,
            "visual_source": "TYPE_ANIMATED",
            "visual_prompt": "golden sunrise over hills",
            "motion_prompt": None,
        }
        router.route(scene)

        motion_arg = mock_animate.call_args[0][1]
        assert motion_arg is not None
        assert len(motion_arg.strip()) > 0

    @patch("musicvid.pipeline.visual_router.animate_image")
    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key", "BFL_API_KEY": "test-key"})
    def test_route_animated_empty_motion_prompt(self, mock_gen, mock_animate):
        mock_gen.return_value = "/tmp/scene_001.jpg"
        mock_animate.return_value = "/tmp/animated_scene_001.mp4"

        router = VisualRouter("/tmp/cache", provider="flux-dev")
        scene = {
            "index": 1, "start": 0, "end": 5,
            "visual_source": "TYPE_ANIMATED",
            "visual_prompt": "golden sunrise over hills",
            "motion_prompt": "",
        }
        router.route(scene)

        motion_arg = mock_animate.call_args[0][1]
        assert len(motion_arg.strip()) > 0

    @patch("musicvid.pipeline.visual_router.animate_image")
    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key", "BFL_API_KEY": "test-key"})
    def test_route_runway_none_motion_prompt(self, mock_gen, mock_animate):
        mock_gen.return_value = "/tmp/runway_img_002.jpg"
        mock_animate.return_value = "/tmp/runway_scene_002.mp4"

        router = VisualRouter("/tmp/cache", provider="flux-dev")
        scene = {
            "index": 2, "start": 0, "end": 5,
            "visual_source": "TYPE_VIDEO_RUNWAY",
            "visual_prompt": "peaceful ocean view",
            "search_query": "ocean waves",
            "motion_prompt": None,
        }
        router.route(scene)

        motion_arg = mock_animate.call_args[0][1]
        assert motion_arg is not None
        assert len(motion_arg.strip()) > 0

    @patch("musicvid.pipeline.visual_router.animate_image")
    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key", "BFL_API_KEY": "test-key"})
    def test_route_runway_empty_motion_prompt(self, mock_gen, mock_animate):
        mock_gen.return_value = "/tmp/runway_img_003.jpg"
        mock_animate.return_value = "/tmp/runway_scene_003.mp4"

        router = VisualRouter("/tmp/cache", provider="flux-dev")
        scene = {
            "index": 3, "start": 0, "end": 5,
            "visual_source": "TYPE_VIDEO_RUNWAY",
            "visual_prompt": "peaceful ocean view",
            "search_query": "ocean waves",
            "motion_prompt": "",
        }
        router.route(scene)

        motion_arg = mock_animate.call_args[0][1]
        assert len(motion_arg.strip()) > 0

    @patch("musicvid.pipeline.visual_router.animate_image")
    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key", "BFL_API_KEY": "test-key"})
    def test_route_runway_falls_back_to_visual_prompt(self, mock_gen, mock_animate):
        """When motion_prompt is empty, use visual_prompt as fallback before default."""
        mock_gen.return_value = "/tmp/runway_img_004.jpg"
        mock_animate.return_value = "/tmp/runway_scene_004.mp4"

        router = VisualRouter("/tmp/cache", provider="flux-dev")
        scene = {
            "index": 4, "start": 0, "end": 5,
            "visual_source": "TYPE_VIDEO_RUNWAY",
            "visual_prompt": "peaceful ocean view",
            "search_query": "ocean waves",
            "motion_prompt": "",
        }
        router.route(scene)

        motion_arg = mock_animate.call_args[0][1]
        # Should use visual_prompt as fallback or hardcoded default — not empty
        assert len(motion_arg.strip()) > 0

    @patch("musicvid.pipeline.visual_router.animate_image")
    @patch("musicvid.pipeline.visual_router.generate_single_image")
    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key", "BFL_API_KEY": "test-key"})
    def test_route_runway_motion_truncated_to_300(self, mock_gen, mock_animate):
        mock_gen.return_value = "/tmp/runway_img_005.jpg"
        mock_animate.return_value = "/tmp/runway_scene_005.mp4"

        router = VisualRouter("/tmp/cache", provider="flux-dev")
        scene = {
            "index": 5, "start": 0, "end": 5,
            "visual_source": "TYPE_VIDEO_RUNWAY",
            "visual_prompt": "nature",
            "search_query": "nature",
            "motion_prompt": "a" * 400,
        }
        router.route(scene)

        motion_arg = mock_animate.call_args[0][1]
        assert len(motion_arg) <= 300
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_visual_router.py::TestMotionPromptFallback -v`
Expected: FAIL — None/empty strings pass through, no truncation

- [ ] **Step 3: Implement fallback logic in _route_animated and _route_runway**

In `musicvid/pipeline/visual_router.py`, modify `_route_animated` (replace lines 185-187):

```python
        # Step 2: animate via Runway image-to-video
        motion = scene.get("motion_prompt") or scene.get("visual_prompt") or ""
        if not motion.strip():
            motion = "Slow cinematic camera push forward, natural golden light, peaceful atmosphere"
        motion = motion.strip()[:300]
        try:
            return animate_image(image_path, motion, duration=5, output_path=output_path)
```

In `musicvid/pipeline/visual_router.py`, modify `_route_runway` (replace lines 207-209):

```python
            # Step 2: animate via Runway image-to-video
            motion = scene.get("motion_prompt") or scene.get("visual_prompt") or ""
            if not motion.strip():
                motion = "Slow cinematic camera push forward, natural golden light, peaceful atmosphere"
            motion = motion.strip()[:300]
            try:
                return animate_image(image_path, motion, duration=5, output_path=output_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_visual_router.py::TestMotionPromptFallback -v`
Expected: All 6 PASS

- [ ] **Step 5: Run full visual_router test suite**

Run: `python3 -m pytest tests/test_visual_router.py -v`
Expected: All tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/visual_router.py tests/test_visual_router.py
git commit -m "fix: add motion_prompt fallback and truncation in visual_router routes"
```

---

### Task 3: Add motion_prompt requirement to director prompt

**Files:**
- Modify: `musicvid/prompts/director_system.txt:131-145`
- Test: `tests/test_director.py`

- [ ] **Step 1: Write failing test for non-empty motion_prompt requirement in prompt**

Add to `tests/test_director.py`:

```python
class TestDirectorPromptMotionRequirement:
    """Ensure director system prompt requires non-empty motion_prompt."""

    def test_system_prompt_requires_nonempty_motion_prompt(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        content = prompt_path.read_text()
        # Must mention that motion_prompt must be non-empty for RUNWAY/ANIMATED
        assert "MUST be a non-empty string" in content or "MUSI być niepustym" in content or "must not be empty" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_director.py::TestDirectorPromptMotionRequirement -v`
Expected: FAIL — current prompt doesn't contain this phrase

- [ ] **Step 3: Update director_system.txt**

In `musicvid/prompts/director_system.txt`, after line 145 (`- For non-animated scenes (animate: false), set motion_prompt to ""`), add:

```
- IMPORTANT: motion_prompt for TYPE_VIDEO_RUNWAY and TYPE_ANIMATED MUST be a non-empty string of at least 5 words describing camera movement and mood. If unsure, use: "Slow cinematic camera push forward, natural golden light"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_director.py::TestDirectorPromptMotionRequirement -v`
Expected: PASS

- [ ] **Step 5: Run full director test suite**

Run: `python3 -m pytest tests/test_director.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add musicvid/prompts/director_system.txt tests/test_director.py
git commit -m "fix: add non-empty motion_prompt requirement to director system prompt"
```

---

### Task 4: Run full test suite

- [ ] **Step 1: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All ~728+ tests PASS

- [ ] **Step 2: Fix any regressions if found**

- [ ] **Step 3: Final commit if any fixes needed**
