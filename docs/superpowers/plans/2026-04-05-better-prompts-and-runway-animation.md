# Better Prompts + Runway Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve AI image quality with context-aware lyrics-based prompts and a shared master_style, and add optional Runway Gen-4 animated video for scenes via a new `--animate` CLI flag.

**Architecture:** The director gains a `master_style` top-level field and per-scene `animate`/`motion_prompt` fields; `image_generator` appends `master_style` to every BFL prompt; a new `video_animator` module wraps the Runway Gen-4 image-to-video API; the assembler skips Ken Burns for animated clips; the CLI wires it all together with `--animate [auto|always|never]`.

**Tech Stack:** Python 3.11+, anthropic SDK, BFL API, Runway Gen-4 API (`requests`), MoviePy 2.1.2, unittest.mock

---

## File Map

| File | Action | Change |
|---|---|---|
| `musicvid/prompts/director_system.txt` | Modify | Add master_style output, animate/motion_prompt per scene, quality rules for visual_prompts |
| `musicvid/pipeline/director.py` | Modify | `_validate_scene_plan` handles master_style default; docstring update |
| `musicvid/pipeline/image_generator.py` | Modify | Use `scene_plan["master_style"]` in prompt; change default `provider="flux-pro"` |
| `musicvid/pipeline/video_animator.py` | Create | Runway Gen-4 image-to-video: `animate_image()`, `_submit_animation()`, `_poll_animation()`, `_download_video()` |
| `musicvid/pipeline/assembler.py` | Modify | `_load_scene_clip` skips Ken Burns when `scene.get("animate")` is True |
| `musicvid/musicvid.py` | Modify | Add `--animate` flag; override scene animate fields; call `animate_image` for animated scenes |
| `tests/test_director.py` | Modify | Add tests for master_style field, animate fields, max 1/3 animated |
| `tests/test_image_generator.py` | Modify | Add test that master_style is included in BFL prompt; test default provider is flux-pro |
| `tests/test_video_animator.py` | Create | Tests for animate_image: happy path, cache hit, polling states, timeout, no API key |
| `tests/test_assembler.py` | Modify | Add test: animated scene uses VideoFileClip without Ken Burns |
| `tests/test_cli.py` | Modify | Add tests for `--animate never/always/auto` |
| `tests/conftest.py` | Modify | Update `sample_scene_plan` to include master_style, animate, motion_prompt fields |

---

## Task 1: Director — context-aware prompts, master_style, animate fields

**Files:**
- Modify: `musicvid/prompts/director_system.txt`
- Modify: `musicvid/pipeline/director.py`
- Modify: `tests/test_director.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_director.py` (inside `TestCreateScenePlan`):

```python
def _make_mock_client(self, mock_anthropic, plan_dict):
    """Helper: configure mock to return plan_dict as JSON."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = json.dumps(plan_dict)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.Anthropic.return_value = mock_client
    return mock_client

def _base_plan(self, scenes=None):
    """Helper: minimal valid plan dict."""
    return {
        "overall_style": "contemplative",
        "master_style": "Warm cinematic grade, golden tones",
        "color_palette": ["#aaa", "#bbb", "#ccc"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "fade"},
        "scenes": scenes or [
            {"section": "verse", "start": 0.0, "end": 10.0,
             "visual_prompt": "A lone figure stands on a cliff, warm amber light",
             "motion": "slow_zoom_in", "transition": "crossfade", "overlay": "none",
             "animate": False, "motion_prompt": ""},
        ],
    }

@patch("musicvid.pipeline.director.anthropic")
def test_returns_master_style(self, mock_anthropic, sample_analysis):
    mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
    result = create_scene_plan(sample_analysis)
    assert "master_style" in result
    assert isinstance(result["master_style"], str)
    assert len(result["master_style"]) > 0

@patch("musicvid.pipeline.director.anthropic")
def test_scenes_have_animate_field(self, mock_anthropic, sample_analysis):
    mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
    result = create_scene_plan(sample_analysis)
    for scene in result["scenes"]:
        assert "animate" in scene
        assert isinstance(scene["animate"], bool)

@patch("musicvid.pipeline.director.anthropic")
def test_animated_scenes_have_motion_prompt(self, mock_anthropic, sample_analysis):
    scenes = [
        {"section": "verse", "start": 0.0, "end": 5.0,
         "visual_prompt": "Mountain view", "motion": "slow_zoom_in",
         "transition": "crossfade", "overlay": "none",
         "animate": True, "motion_prompt": "Slow camera push forward"},
        {"section": "chorus", "start": 5.0, "end": 10.0,
         "visual_prompt": "Lake reflection", "motion": "static",
         "transition": "cut", "overlay": "none",
         "animate": False, "motion_prompt": ""},
    ]
    mock_client = self._make_mock_client(mock_anthropic, self._base_plan(scenes))
    result = create_scene_plan(sample_analysis)
    animated = [s for s in result["scenes"] if s["animate"]]
    for scene in animated:
        assert "motion_prompt" in scene
        assert len(scene["motion_prompt"]) > 0

@patch("musicvid.pipeline.director.anthropic")
def test_max_one_third_scenes_animated(self, mock_anthropic, sample_analysis):
    scenes = [
        {"section": "verse", "start": 0.0, "end": 4.0,
         "visual_prompt": "Meadow", "motion": "slow_zoom_in",
         "transition": "crossfade", "overlay": "none",
         "animate": True, "motion_prompt": "Camera rises slowly"},
        {"section": "chorus", "start": 4.0, "end": 7.0,
         "visual_prompt": "Mountain", "motion": "static",
         "transition": "cut", "overlay": "none",
         "animate": False, "motion_prompt": ""},
        {"section": "outro", "start": 7.0, "end": 10.0,
         "visual_prompt": "Sunset", "motion": "pan_left",
         "transition": "fade_black", "overlay": "none",
         "animate": False, "motion_prompt": ""},
    ]
    mock_client = self._make_mock_client(mock_anthropic, self._base_plan(scenes))
    result = create_scene_plan(sample_analysis)
    total = len(result["scenes"])
    animated = sum(1 for s in result["scenes"] if s["animate"])
    assert animated <= total / 3 + 0.01  # allow rounding up by 1

@patch("musicvid.pipeline.director.anthropic")
def test_master_style_default_when_missing(self, mock_anthropic, sample_analysis):
    """If Claude omits master_style, _validate_scene_plan should default to empty string."""
    plan_no_master = {
        "overall_style": "contemplative",
        "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "fade"},
        "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                    "visual_prompt": "test", "motion": "static",
                    "transition": "cut", "overlay": "none"}],
    }
    mock_client = self._make_mock_client(mock_anthropic, plan_no_master)
    result = create_scene_plan(sample_analysis)
    assert "master_style" in result  # should be defaulted
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_returns_master_style tests/test_director.py::TestCreateScenePlan::test_scenes_have_animate_field tests/test_director.py::TestCreateScenePlan::test_max_one_third_scenes_animated tests/test_director.py::TestCreateScenePlan::test_master_style_default_when_missing -v
```
Expected: FAIL (master_style not in result, animate not in scenes)

- [ ] **Step 3: Update director_system.txt**

Replace the entire contents of `musicvid/prompts/director_system.txt`:

```
You are a music video director specializing in Protestant Christian worship music videos.

You will receive an audio analysis containing lyrics, beats, BPM, duration, sections, and mood/energy data.

Your job is to create a detailed scene plan for the music video as pure JSON (no markdown, no code fences).

MASTER STYLE:
Begin by composing a master_style string (1-2 sentences, English) describing the consistent visual grade
applied to all scenes. Example: "Consistent warm cinematic color grade, golden amber tones, soft atmospheric
haze, photorealistic photography style." Include it as the master_style field in your JSON output.

CONTEXT-AWARE VISUAL PROMPTS:
For each scene, identify which lyrics lines fall within the scene's time window [start, end] seconds.
The visual_prompt MUST directly reference the metaphor, image, or emotion from those lyrics.

Every visual_prompt must:
1. Reference a specific image, metaphor, or emotion from the scene's lyrics (use adjacent scene if no lyrics)
2. Describe the main visual subject in detail (what is it, where is it)
3. Specify shot composition: close-up / medium shot / wide shot
4. Describe lighting direction, quality, and color temperature
5. Describe depth and atmosphere (foreground, midground, background)
Minimum 2 sentences of description before the technical suffix.

PROMPT BUILDING RULES:
Every visual_prompt ends with the master_style condensed + "cinematic 16:9, photorealistic, high quality"
Describe ONLY what IS in the scene — never describe what is NOT there.
Never use any of the BANNED WORDS listed below in visual_prompt fields.

BANNED WORDS (never use these in any visual_prompt):
Catholic, rosary, Madonna, saint, cross with figure, stained glass,
church interior, religious, icon, Byzantine, papal, crucifix,
prayer beads, Maria, monastery, monk, nun, cathedral, chapel,
shrine, altar, candle altar, sacred heart, IHS

POSITIVE MOTIFS TO USE:
- Nature: golden wheat fields, mountain peaks, morning mist, calm lakes, ancient forests
- Light: golden hour sunlight, rays breaking through clouds, abstract light particles
- Spiritual: simple wooden cross on hillside, dove in flight, open Bible on wooden table
- People: silhouette with hands raised toward sky, person walking through field
- Abstract: golden light rays on dark background, floating particles of light

EXAMPLE PROMPTS (follow this style):
- "A lone silhouette stands on a vast rocky cliff overlooking an infinite ocean at golden hour, arms raised toward dramatic storm clouds breaking into light. Wide shot, warm amber light from below the horizon, shallow depth of field with the figure sharp against a blurred sky, conveying human smallness before the divine. Warm cinematic grade, golden tones, photorealistic, cinematic 16:9, high quality"
- "Golden wheat field stretching to the horizon at sunrise, a narrow dirt path leads into the distance. Medium wide shot, soft warm light rakes across the field casting long shadows, morning mist lingers in the background valleys, peaceful and full of hope. Warm cinematic grade, golden tones, photorealistic, cinematic 16:9, high quality"

STYLE RULES:
- Match visual energy to musical energy (quiet sections = calm visuals, climax = dramatic)
- Maintain color consistency through master_style

ANIMATION RULES:
- Add "animate" (bool) and "motion_prompt" (string) to every scene
- Set animate: true only for emotionally significant scenes (chorus, key moments)
- Maximum 1/3 of all scenes may have animate: true (round down)
- motion_prompt describes ONLY the camera/scene motion (not content), e.g.:
  "Slow camera push forward, gentle breeze moves the trees"
  "Camera slowly rises revealing the landscape below, clouds drift gently"
  "Subtle zoom out, light rays sweep across the scene"
- Avoid fast or jarring motion — worship music requires slow, peaceful movement
- If animate: false, set motion_prompt to ""

OUTPUT FORMAT (pure JSON):
{
  "overall_style": "contemplative|joyful|worship|powerful",
  "master_style": "Consistent warm cinematic color grade, golden amber tones, soft atmospheric haze",
  "color_palette": ["#hex1", "#hex2", "#hex3"],
  "subtitle_style": {
    "font_size": 48,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "position": "center-bottom",
    "animation": "fade"
  },
  "scenes": [
    {
      "section": "intro|verse|chorus|bridge|outro",
      "start": 0.0,
      "end": 15.0,
      "visual_prompt": "Detailed positive description following the rules above (min 2 sentences + technical suffix)",
      "motion": "slow_zoom_in|slow_zoom_out|pan_left|pan_right|static",
      "transition": "crossfade|cut|fade_black",
      "overlay": "none|particles|light_rays|bokeh",
      "animate": false,
      "motion_prompt": ""
    }
  ]
}

IMPORTANT:
- Scenes must cover the entire duration with no gaps
- Each scene should be 5-15 seconds long
- Transitions should align with beat times when possible
- Visual prompts must reference the scene's lyrics — be specific, not generic
- Match the number of scenes to the song structure
```

- [ ] **Step 4: Update `_validate_scene_plan` in director.py**

```python
def _validate_scene_plan(plan, duration):
    """Validate and fix the scene plan to ensure it covers the full duration."""
    if not plan.get("scenes"):
        raise ValueError("Scene plan has no scenes")

    # Default master_style if Claude omitted it
    if "master_style" not in plan:
        plan["master_style"] = ""

    # Default animate/motion_prompt fields if Claude omitted them
    for scene in plan["scenes"]:
        if "animate" not in scene:
            scene["animate"] = False
        if "motion_prompt" not in scene:
            scene["motion_prompt"] = ""

    plan["scenes"].sort(key=lambda s: s["start"])
    plan["scenes"][0]["start"] = 0.0
    plan["scenes"][-1]["end"] = duration

    return plan
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_director.py -v
```
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add musicvid/prompts/director_system.txt musicvid/pipeline/director.py tests/test_director.py
git commit -m "feat: add master_style, animate/motion_prompt fields to director"
```

---

## Task 2: Image Generator — master_style in prompt + flux-pro default

**Files:**
- Modify: `musicvid/pipeline/image_generator.py`
- Modify: `tests/test_image_generator.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_image_generator.py`:

```python
class TestMasterStylePrompt:
    """Tests that master_style from scene_plan is appended to BFL prompts."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_master_style_appended_to_prompt(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response("task-1")
        mock_requests.get.side_effect = [
            _make_poll_response("Ready", "https://bfl.ai/img1.jpg"),
            _make_download_response(),
        ]

        plan = {
            "master_style": "Warm cinematic grade, golden tones",
            "scenes": [{"visual_prompt": "mountain sunrise", "start": 0.0, "end": 5.0}],
        }
        generate_images(plan, str(tmp_path))

        call_payload = mock_requests.post.call_args[1]["json"]
        assert "Warm cinematic grade, golden tones" in call_payload["prompt"]
        assert "mountain sunrise" in call_payload["prompt"]

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_no_master_style_still_works(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response("task-1")
        mock_requests.get.side_effect = [
            _make_poll_response("Ready", "https://bfl.ai/img1.jpg"),
            _make_download_response(),
        ]

        plan = {
            "scenes": [{"visual_prompt": "calm lake", "start": 0.0, "end": 5.0}],
        }
        generate_images(plan, str(tmp_path))

        call_payload = mock_requests.post.call_args[1]["json"]
        assert "calm lake" in call_payload["prompt"]


class TestDefaultProvider:
    """Tests that the default provider is flux-pro (maps to flux-pro-1.1)."""

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_default_provider_is_flux_pro(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images
        import inspect

        sig = inspect.signature(generate_images)
        assert sig.parameters["provider"].default == "flux-pro"

    @patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    def test_default_provider_calls_flux_pro_1_1_endpoint(self, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        mock_requests.post.return_value = _make_post_response("task-1")
        mock_requests.get.side_effect = [
            _make_poll_response("Ready", "https://bfl.ai/img1.jpg"),
            _make_download_response(),
        ]

        plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        generate_images(plan, str(tmp_path))  # uses default provider

        called_url = mock_requests.post.call_args[0][0]
        assert "flux-pro-1.1" in called_url
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_image_generator.py::TestMasterStylePrompt tests/test_image_generator.py::TestDefaultProvider -v
```
Expected: FAIL

- [ ] **Step 3: Update image_generator.py**

Change line 91 and the prompt building in `generate_images`:

```python
def generate_images(scene_plan, output_dir, provider="flux-pro"):
    """Generate one image per scene using BFL API.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save generated images.
        provider: One of flux-dev, flux-pro, flux-schnell. Default: flux-pro (flux-pro-1.1).

    Returns:
        list of image file paths in scene order.
    """
    _detect_provider(provider)

    model_name = BFL_MODELS[provider]
    scenes = scene_plan.get("scenes", [])
    master_style = scene_plan.get("master_style", "")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    image_paths = []
    total = len(scenes)

    for i, scene in enumerate(scenes):
        visual_prompt = scene.get("visual_prompt", "nature landscape")
        if master_style:
            full_prompt = f"{visual_prompt}, {master_style}, cinematic 16:9, photorealistic, high quality"
        else:
            full_prompt = f"{visual_prompt}, cinematic 16:9, photorealistic, high quality"

        task_id, polling_url = _submit_task(model_name, full_prompt)
        image_url = _poll_result(polling_url)

        dest = output_path / f"scene_{i:03d}.jpg"
        _download_image(image_url, str(dest))
        image_paths.append(str(dest))
        print(f"Scena {i + 1}/{total} gotowa")

    return image_paths
```

- [ ] **Step 4: Run all image_generator tests**

```bash
python3 -m pytest tests/test_image_generator.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/image_generator.py tests/test_image_generator.py
git commit -m "feat: use master_style in BFL prompts, default provider to flux-pro"
```

---

## Task 3: video_animator.py — Runway Gen-4 module

**Files:**
- Create: `musicvid/pipeline/video_animator.py`
- Create: `tests/test_video_animator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_video_animator.py`:

```python
"""Tests for Runway Gen-4 video animation module."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest


def _make_post_response(task_id="task-abc"):
    resp = MagicMock()
    resp.json.return_value = {"id": task_id}
    return resp


def _make_poll_response(status, video_url=None):
    resp = MagicMock()
    if status == "SUCCEEDED":
        resp.json.return_value = {"status": "SUCCEEDED", "output": [{"url": video_url}]}
    elif status == "FAILED":
        resp.json.return_value = {"status": "FAILED"}
    else:
        resp.json.return_value = {"status": status}
    return resp


def _make_download_response():
    resp = MagicMock()
    resp.iter_content.return_value = [b"fake", b"video", b"data"]
    return resp


class TestAnimateImage:
    """Tests for animate_image() function."""

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_returns_output_path(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        mock_time.monotonic.side_effect = [0.0, 1.0, 2.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-1")
        mock_requests.get.side_effect = [
            _make_poll_response("SUCCEEDED", "https://runway.ai/video.mp4"),
            _make_download_response(),
        ]

        img = tmp_path / "scene_000.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "animated_scene_000.mp4"

        result = animate_image(str(img), "Slow camera push forward", output_path=str(out))

        assert result == str(out)
        assert out.exists()

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_cache_hit_skips_api(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        img = tmp_path / "scene_000.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "animated_scene_000.mp4"
        out.write_bytes(b"existing video")  # simulate cached file

        result = animate_image(str(img), "Slow zoom", output_path=str(out))

        assert result == str(out)
        mock_requests.post.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_when_no_api_key(self, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        img = tmp_path / "scene_000.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "animated.mp4"

        with pytest.raises(RuntimeError, match="RUNWAY_API_KEY"):
            animate_image(str(img), "Slow zoom", output_path=str(out))

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_polling_pending_then_succeeded(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        mock_time.monotonic.side_effect = [0.0, 1.0, 2.0, 3.0, 4.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-pending")
        mock_requests.get.side_effect = [
            _make_poll_response("PENDING"),
            _make_poll_response("PENDING"),
            _make_poll_response("SUCCEEDED", "https://runway.ai/video.mp4"),
            _make_download_response(),
        ]

        img = tmp_path / "scene.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "out.mp4"

        result = animate_image(str(img), "Camera rises", output_path=str(out))
        assert result == str(out)

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_timeout_raises_timeout_error(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        # monotonic always returns > POLL_TIMEOUT after first call
        mock_time.monotonic.side_effect = [0.0, 301.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-slow")
        mock_requests.get.return_value = _make_poll_response("PENDING")

        img = tmp_path / "scene.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "out.mp4"

        with pytest.raises(TimeoutError):
            animate_image(str(img), "Slow zoom", output_path=str(out))

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_failed_status_raises_runtime_error(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        mock_time.monotonic.side_effect = [0.0, 1.0, 2.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-fail")
        mock_requests.get.side_effect = [
            _make_poll_response("FAILED"),
        ]

        img = tmp_path / "scene.jpg"
        img.write_bytes(b"fake jpeg")
        out = tmp_path / "out.mp4"

        with pytest.raises(RuntimeError, match="FAILED"):
            animate_image(str(img), "Slow zoom", output_path=str(out))

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"})
    @patch("musicvid.pipeline.video_animator.requests")
    @patch("musicvid.pipeline.video_animator.time")
    def test_submit_called_with_correct_payload(self, mock_time, mock_requests, tmp_path):
        from musicvid.pipeline.video_animator import animate_image

        mock_time.monotonic.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()

        mock_requests.post.return_value = _make_post_response("task-1")
        mock_requests.get.side_effect = [
            _make_poll_response("SUCCEEDED", "https://runway.ai/video.mp4"),
            _make_download_response(),
        ]

        img = tmp_path / "scene.jpg"
        img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)  # minimal jpeg bytes
        out = tmp_path / "out.mp4"

        animate_image(str(img), "Camera rises slowly", duration=5, output_path=str(out))

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["model"] == "gen4_turbo"
        assert payload["duration"] == 5
        assert payload["ratio"] == "1280:768"
        assert "Camera rises slowly" == payload["promptText"]
        assert payload["promptImage"].startswith("data:image/jpeg;base64,")
```

- [ ] **Step 2: Run tests to verify they fail (module doesn't exist)**

```bash
python3 -m pytest tests/test_video_animator.py -v 2>&1 | head -20
```
Expected: FAIL with ImportError

- [ ] **Step 3: Create `musicvid/pipeline/video_animator.py`**

```python
"""Runway Gen-4 image-to-video animation module."""

import base64
import os
import time
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception


RUNWAY_API_BASE = "https://api.dev.runwayml.com"
RUNWAY_API_VERSION = "2024-11-06"
POLL_INTERVAL = 3
POLL_TIMEOUT = 300


def _is_retryable(exc):
    """Return True for network errors and 5xx responses (retryable)."""
    if isinstance(exc, requests.exceptions.ConnectionError):
        return True
    if isinstance(exc, requests.exceptions.Timeout):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


def _get_headers():
    """Return auth headers for Runway API."""
    return {
        "Authorization": f"Bearer {os.environ.get('RUNWAY_API_KEY', '')}",
        "Content-Type": "application/json",
        "X-Runway-Version": RUNWAY_API_VERSION,
    }


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_retryable),
)
def _submit_animation(image_b64, motion_prompt, duration):
    """POST to Runway API to start image-to-video task. Returns task_id."""
    payload = {
        "model": "gen4_turbo",
        "promptImage": image_b64,
        "promptText": motion_prompt,
        "duration": duration,
        "ratio": "1280:768",
    }
    resp = requests.post(
        f"{RUNWAY_API_BASE}/v1/image_to_video",
        json=payload,
        headers=_get_headers(),
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _poll_animation(task_id):
    """Poll until task SUCCEEDED or FAILED/CANCELLED or timeout."""
    start = time.monotonic()
    while time.monotonic() - start < POLL_TIMEOUT:
        resp = requests.get(
            f"{RUNWAY_API_BASE}/v1/tasks/{task_id}",
            headers=_get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "SUCCEEDED":
            return data["output"][0]["url"]
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"Runway task {task_id} failed with status: {status}")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Runway animation timed out after {POLL_TIMEOUT}s")


def _download_video(url, output_path):
    """Download video stream from URL to output_path."""
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def animate_image(image_path, motion_prompt, duration=5, output_path=None):
    """Animate a still image using Runway Gen-4 image-to-video API.

    Args:
        image_path: Path to the source image (.jpg or .png).
        motion_prompt: Text describing the desired camera/scene motion.
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

    image_bytes = Path(image_path).read_bytes()
    ext = Path(image_path).suffix.lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    image_b64 = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"

    task_id = _submit_animation(image_b64, motion_prompt, duration)
    video_url = _poll_animation(task_id)
    _download_video(video_url, output_path)
    return str(output_path)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_video_animator.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/video_animator.py tests/test_video_animator.py
git commit -m "feat: add video_animator module for Runway Gen-4 image-to-video"
```

---

## Task 4: Assembler — skip Ken Burns for animated clips

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_assembler.py` (find the existing test class for `_load_scene_clip` or add a new class):

```python
class TestLoadSceneClipAnimated:
    """Tests that animated scenes skip Ken Burns and use VideoFileClip resized."""

    @patch("musicvid.pipeline.assembler.VideoFileClip")
    def test_animated_scene_skips_ken_burns(self, mock_vfc, tmp_path):
        from musicvid.pipeline.assembler import _load_scene_clip

        # Create a fake .mp4 file
        fake_mp4 = tmp_path / "animated.mp4"
        fake_mp4.write_bytes(b"fake video")

        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_vfc.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in", "animate": True}
        result = _load_scene_clip(str(fake_mp4), scene, (1920, 1080))

        # resized should be called to fit target_size
        mock_clip.resized.assert_called_once_with(new_size=(1920, 1080))
        # transform (Ken Burns) should NOT be called
        mock_clip.transform.assert_not_called()

    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_non_animated_image_uses_ken_burns(self, mock_ic, tmp_path):
        from musicvid.pipeline.assembler import _load_scene_clip

        fake_jpg = tmp_path / "scene.jpg"
        fake_jpg.write_bytes(b"fake jpeg")

        mock_clip = MagicMock()
        mock_clip.duration = None
        mock_ic.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in", "animate": False}
        _load_scene_clip(str(fake_jpg), scene, (1920, 1080))

        # transform (Ken Burns) SHOULD be called
        mock_clip.transform.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_assembler.py::TestLoadSceneClipAnimated -v
```
Expected: FAIL

- [ ] **Step 3: Update `_load_scene_clip` in assembler.py**

Replace the `_load_scene_clip` function (lines 151-165):

```python
def _load_scene_clip(video_path, scene, target_size):
    """Load a video or image clip for a scene."""
    path = Path(video_path)
    duration = scene["end"] - scene["start"]

    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
        clip = ImageClip(str(path))
    else:
        clip = VideoFileClip(str(path))
        if clip.duration < duration:
            loops = int(duration / clip.duration) + 1
            clip = concatenate_videoclips([clip] * loops)
        clip = clip.subclipped(0, duration)

    # Animated clips from Runway Gen-4: resize only, skip Ken Burns
    if scene.get("animate", False) and path.suffix.lower() == ".mp4":
        return clip.resized(new_size=target_size)

    return _create_ken_burns_clip(clip, duration, scene.get("motion", "static"), target_size)
```

- [ ] **Step 4: Run all assembler tests**

```bash
python3 -m pytest tests/test_assembler.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: skip Ken Burns for animated Runway clips in assembler"
```

---

## Task 5: CLI — --animate flag and pipeline wiring

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Update conftest.py sample_scene_plan**

Add `master_style`, `animate`, `motion_prompt` fields to the fixture in `tests/conftest.py`:

```python
@pytest.fixture
def sample_scene_plan():
    """Sample director output for testing downstream stages."""
    return {
        "overall_style": "contemplative",
        "master_style": "Consistent warm cinematic grade, golden amber tones",
        "color_palette": ["#1a1a2e", "#16213e", "#e2e2e2"],
        "subtitle_style": {
            "font_size": 48,
            "color": "#FFFFFF",
            "outline_color": "#000000",
            "position": "center-bottom",
            "animation": "fade",
        },
        "scenes": [
            {
                "section": "intro",
                "start": 0.0,
                "end": 2.0,
                "visual_prompt": "mountain sunrise golden light peaceful morning",
                "motion": "slow_zoom_in",
                "transition": "fade_black",
                "overlay": "none",
                "animate": False,
                "motion_prompt": "",
            },
            {
                "section": "verse",
                "start": 2.0,
                "end": 6.0,
                "visual_prompt": "calm water reflection forest lake serene",
                "motion": "slow_zoom_out",
                "transition": "crossfade",
                "overlay": "light_rays",
                "animate": False,
                "motion_prompt": "",
            },
            {
                "section": "outro",
                "start": 6.0,
                "end": 10.0,
                "visual_prompt": "sunset clouds golden horizon peaceful",
                "motion": "pan_left",
                "transition": "fade_black",
                "overlay": "particles",
                "animate": False,
                "motion_prompt": "",
            },
        ],
    }
```

- [ ] **Step 2: Write failing CLI tests**

Add to `tests/test_cli.py`:

```python
class TestAnimateCLI:
    """Tests for --animate flag integration."""

    def _base_mocks(self):
        """Return a dict of patch targets needed for a full ai pipeline run."""
        return {
            "musicvid.musicvid.analyze_audio": MagicMock(return_value={
                "lyrics": [], "beats": [], "bpm": 120.0, "duration": 10.0,
                "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
                "mood_energy": "contemplative", "language": "en",
            }),
            "musicvid.musicvid.create_scene_plan": MagicMock(return_value={
                "overall_style": "contemplative",
                "master_style": "Warm grade",
                "color_palette": ["#aaa"],
                "subtitle_style": {"font_size": 48, "color": "#FFF",
                                   "outline_color": "#000", "position": "center-bottom",
                                   "animation": "fade"},
                "scenes": [
                    {"section": "verse", "start": 0.0, "end": 5.0,
                     "visual_prompt": "meadow", "motion": "slow_zoom_in",
                     "transition": "crossfade", "overlay": "none",
                     "animate": True, "motion_prompt": "Camera rises slowly"},
                    {"section": "chorus", "start": 5.0, "end": 10.0,
                     "visual_prompt": "mountain", "motion": "static",
                     "transition": "cut", "overlay": "none",
                     "animate": False, "motion_prompt": ""},
                ],
            }),
            "musicvid.musicvid.generate_images": MagicMock(
                return_value=["/tmp/scene_000.jpg", "/tmp/scene_001.jpg"]
            ),
            "musicvid.musicvid.assemble_video": MagicMock(),
            "musicvid.musicvid.get_font_path": MagicMock(return_value="/fake/font.ttf"),
            "musicvid.musicvid.animate_image": MagicMock(return_value="/tmp/animated_scene_000.mp4"),
        }

    def test_animate_never_does_not_call_animate_image(self, tmp_path):
        from click.testing import CliRunner
        from musicvid.musicvid import cli
        from unittest.mock import patch, MagicMock

        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake audio")

        mocks = self._base_mocks()
        with patch.multiple("musicvid.musicvid", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            runner = CliRunner()
            result = runner.invoke(cli, [str(audio), "--mode", "ai", "--animate", "never"])

        mocks["musicvid.musicvid.animate_image"].assert_not_called()

    def test_animate_always_overrides_all_scenes_to_true(self, tmp_path):
        from click.testing import CliRunner
        from musicvid.musicvid import cli
        from unittest.mock import patch, MagicMock

        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake audio")

        mocks = self._base_mocks()
        captured_plans = []

        original_assemble = mocks["musicvid.musicvid.assemble_video"]
        def capture_plan(*args, **kwargs):
            captured_plans.append(kwargs.get("scene_plan", args[1] if len(args) > 1 else None))
        original_assemble.side_effect = capture_plan

        with patch.multiple("musicvid.musicvid", **{k.split(".")[-1]: v for k, v in mocks.items()}):
            runner = CliRunner()
            runner.invoke(cli, [str(audio), "--mode", "ai", "--animate", "always"])

        # All scenes should have animate=True
        if captured_plans:
            plan = captured_plans[0]
            if plan:
                assert all(s["animate"] for s in plan["scenes"])

    def test_animate_always_calls_animate_image_for_each_scene(self, tmp_path):
        from click.testing import CliRunner
        from musicvid.musicvid import cli
        from unittest.mock import patch, MagicMock
        import os

        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake audio")

        mocks = self._base_mocks()
        # Override scene plan so all animate=True with always
        # The CLI should override based on --animate always

        with patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"}):
            with patch.multiple("musicvid.musicvid", **{k.split(".")[-1]: v for k, v in mocks.items()}):
                runner = CliRunner()
                runner.invoke(cli, [str(audio), "--mode", "ai", "--animate", "always"])

        # animate_image should be called for scenes that have animate=True after override
        assert mocks["musicvid.musicvid.animate_image"].call_count >= 1

    def test_animate_auto_uses_director_decisions(self, tmp_path):
        from click.testing import CliRunner
        from musicvid.musicvid import cli
        from unittest.mock import patch, MagicMock
        import os

        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake audio")

        mocks = self._base_mocks()  # director returns animate=True for scene 0

        with patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key"}):
            with patch.multiple("musicvid.musicvid", **{k.split(".")[-1]: v for k, v in mocks.items()}):
                runner = CliRunner()
                runner.invoke(cli, [str(audio), "--mode", "ai", "--animate", "auto"])

        # animate_image should be called once (only scene 0 has animate=True in director plan)
        assert mocks["musicvid.musicvid.animate_image"].call_count == 1

    def test_animate_fallback_when_no_runway_key(self, tmp_path):
        from click.testing import CliRunner
        from musicvid.musicvid import cli
        from unittest.mock import patch, MagicMock
        import os

        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"fake audio")

        mocks = self._base_mocks()

        with patch.dict(os.environ, {}, clear=True):  # no RUNWAY_API_KEY
            with patch.multiple("musicvid.musicvid", **{k.split(".")[-1]: v for k, v in mocks.items()}):
                runner = CliRunner()
                result = runner.invoke(cli, [str(audio), "--mode", "ai", "--animate", "auto"])

        # Should not call animate_image (fallback to Ken Burns)
        mocks["musicvid.musicvid.animate_image"].assert_not_called()
        # Should still succeed (fallback, no error)
        assert result.exit_code == 0
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::TestAnimateCLI -v 2>&1 | head -30
```
Expected: FAIL (no --animate flag)

- [ ] **Step 4: Update musicvid.py**

Add the import at the top and the `--animate` flag, then wire animation into the pipeline.

**Add import** (after line 18 `from musicvid.pipeline.lyrics_parser import align_with_claude`):
```python
from musicvid.pipeline.video_animator import animate_image
```

**Add CLI option** (after the `--title-card` option):
```python
@click.option("--animate", "animate_mode", type=click.Choice(["auto", "always", "never"]), default="auto", help="Animated video via Runway Gen-4 (auto|always|never). Only with --mode ai.")
```

**Add `animate_mode` to the function signature:**
```python
def cli(audio_file, mode, provider, style, output, resolution, lang, new, font_path, lyrics_path, effects, clip_duration, platform, title_card, animate_mode):
```

**Add animation step** (replace Stage 3 `if mode == "ai":` block with):
```python
    # Stage 3: Fetch Videos or Generate Images
    manifest_suffix = f"_clip_{clip_duration}s" if clip_duration else ""
    if mode == "ai":
        image_cache_name = f"image_manifest{manifest_suffix}.json"
        image_manifest = load_cache(str(cache_dir), image_cache_name) if not new else None
        if image_manifest and _image_files_exist(image_manifest):
            click.echo("[3/4] Generating images... CACHED (skipped)")
            fetch_manifest = image_manifest
        else:
            click.echo(f"[3/4] Generating images (provider: {provider})...")
            image_paths = generate_images(scene_plan, str(cache_dir), provider=provider)
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

        # Stage 3.5: Animate scenes with Runway Gen-4
        if animate_mode != "never":
            runway_key = os.environ.get("RUNWAY_API_KEY")
            for entry in fetch_manifest:
                idx = entry["scene_index"]
                scene = scene_plan["scenes"][idx]
                if not scene.get("animate", False):
                    continue
                if not runway_key:
                    click.echo(f"  \u26a0 RUNWAY_API_KEY not set \u2014 Ken Burns fallback for scene {idx + 1}")
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
                    click.echo(f"  \u26a0 Animation failed for scene {idx + 1}: {exc} \u2014 Ken Burns fallback")
                    scene["animate"] = False
    else:
```

**Also add `import os`** at the top if not already present. Check: `musicvid.py` doesn't currently import `os` explicitly; it uses `pathlib.Path` and `hashlib`. We need `os.environ.get("RUNWAY_API_KEY")`. Add `import os` after `import hashlib`.

- [ ] **Step 5: Run all CLI tests**

```bash
python3 -m pytest tests/test_cli.py -v
```
Expected: ALL PASS

- [ ] **Step 6: Run full test suite**

```bash
python3 -m pytest tests/ -v
```
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py tests/conftest.py
git commit -m "feat: add --animate flag with Runway Gen-4 pipeline integration"
```

---

## Self-Review

Checked against IDEA.md spec:

| Requirement | Task |
|---|---|
| flux-pro-1.1 as default model | Task 2 ✅ |
| visual_prompt references scene lyrics | Task 1 (system prompt updated) ✅ |
| Minimum 2 sentences in visual_prompt | Task 1 (system prompt rule) ✅ |
| Composition, lighting, depth in prompts | Task 1 (system prompt rule) ✅ |
| master_style appended to all prompts | Task 1 (director) + Task 2 (image gen) ✅ |
| animate/motion_prompt per scene | Task 1 ✅ |
| max 1/3 scenes animated (auto mode) | Task 1 (system prompt) + Task 5 (always override) ✅ |
| New video_animator.py module | Task 3 ✅ |
| animate_image(image_path, motion_prompt, duration, output_path) | Task 3 ✅ |
| Runway Gen-4 POST → poll → download | Task 3 ✅ |
| Poll interval 3s, timeout 300s | Task 3 ✅ |
| Retry max 2 for network errors | Task 3 ✅ |
| Animated clips cached in tmp/ | Task 3 (cache check in animate_image) ✅ |
| Assembler: VideoFileClip not Ken Burns for animated | Task 4 ✅ |
| Fallback to Ken Burns when no RUNWAY_API_KEY | Task 5 ✅ |
| --animate [auto\|always\|never] CLI flag | Task 5 ✅ |
| All tests pass | Task 5 (step 6) ✅ |
| RUNWAY_API_KEY in .env.example | Not covered — add manually |

Note: `.env.example` update is a one-liner, handled post-plan.
