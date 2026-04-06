# Default AI Video Mix (Runway + Pexels) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the default video generation mode from BFL Flux static images (`--mode ai`) to a dynamic mix of Runway Gen-4.5 text-to-video + Pexels nature stock footage (`--mode runway`), adding `TYPE_VIDEO_RUNWAY` as a new visual source type.

**Architecture:** Add `TYPE_VIDEO_RUNWAY` dispatch in `VisualRouter` (routes to `generate_video_from_text`, falls back to Pexels stock). Pass `mode` to `create_scene_plan` / `_build_user_message` so the director uses the right types per mode. Add `--mode runway` CLI option (new default) that pipes through `VisualRouter` (same as mode=ai) but prefers Runway+Pexels over BFL.

**Tech Stack:** Python 3.11+, Click CLI, Runway Gen-4.5 (`generate_video_from_text`), Pexels API (`fetch_video_by_query`), Claude API (`create_scene_plan`), unittest.mock

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `musicvid/pipeline/visual_router.py` | Modify | Add `_route_runway_text_to_video()`, dispatch `TYPE_VIDEO_RUNWAY` in `route()` |
| `musicvid/pipeline/director.py` | Modify | Add `mode` param to `create_scene_plan`, `_build_user_message`, `_validate_scene_plan` |
| `musicvid/prompts/director_system.txt` | Modify | Add `TYPE_VIDEO_RUNWAY` description, motion_prompt examples, runway proportions |
| `musicvid/musicvid.py` | Modify | Add `--mode runway` (new default), pass mode to director, update startup summary, API key fallback |
| `tests/test_visual_router.py` | Modify | Add `TestVisualRouterRunway` class with routing tests |
| `tests/test_director.py` | Modify | Add tests for mode-aware defaults in `_validate_scene_plan` and `_build_user_message` |
| `tests/test_cli.py` | Modify | Add `test_mode_runway_calls_visual_router`, update default-mode tests |

---

## Task 1: Add TYPE_VIDEO_RUNWAY routing in visual_router.py

**Files:**
- Modify: `musicvid/pipeline/visual_router.py`
- Test: `tests/test_visual_router.py`

- [ ] **Step 1: Write failing tests for TYPE_VIDEO_RUNWAY**

Add a new test class at the bottom of `tests/test_visual_router.py`:

```python
import os
from unittest.mock import patch, MagicMock
from musicvid.pipeline.visual_router import VisualRouter

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
    """Tests for TYPE_VIDEO_RUNWAY routing."""

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_runway_calls_generate_video_from_text(self, tmp_path):
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")
        video_path = str(tmp_path / "runway_scene_004.mp4")

        with patch(
            "musicvid.pipeline.visual_router.generate_video_from_text",
            return_value=video_path,
        ) as mock_gen:
            result = router.route(SCENE_RUNWAY)

        expected_prompt = (
            "Person on hilltop arms raised, golden sunrise, wide shot "
            "slow camera rises revealing vast mountain landscape, golden light"
        )
        mock_gen.assert_called_once_with(
            expected_prompt,
            duration=5,
            output_path=video_path,
        )
        assert result == video_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_runway_uses_cache_if_exists(self, tmp_path):
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")
        video_path = tmp_path / "runway_scene_004.mp4"
        video_path.write_bytes(b"cached")

        with patch(
            "musicvid.pipeline.visual_router.generate_video_from_text"
        ) as mock_gen:
            result = router.route(SCENE_RUNWAY)

        mock_gen.assert_not_called()
        assert result == str(video_path)

    @patch.dict(os.environ, {}, clear=True)
    def test_route_runway_falls_back_to_pexels_when_no_api_key(self, tmp_path):
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")
        pexels_path = str(tmp_path / "scene_004.mp4")

        with patch(
            "musicvid.pipeline.visual_router.generate_video_from_text"
        ) as mock_gen, patch(
            "musicvid.pipeline.visual_router.fetch_video_by_query",
            return_value=pexels_path,
        ) as mock_fetch:
            result = router.route(SCENE_RUNWAY)

        mock_gen.assert_not_called()
        mock_fetch.assert_called()
        assert result == pexels_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_runway_falls_back_to_pexels_on_runway_failure(self, tmp_path):
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")
        pexels_path = str(tmp_path / "scene_004.mp4")

        with patch(
            "musicvid.pipeline.visual_router.generate_video_from_text",
            side_effect=RuntimeError("Runway error"),
        ), patch(
            "musicvid.pipeline.visual_router.fetch_video_by_query",
            return_value=pexels_path,
        ) as mock_fetch:
            result = router.route(SCENE_RUNWAY)

        mock_fetch.assert_called()
        assert result == pexels_path

    @patch.dict(os.environ, {"RUNWAY_API_KEY": "rw-key"})
    def test_route_runway_falls_back_to_nature_query_when_no_motion_prompt(self, tmp_path):
        scene = {**SCENE_RUNWAY, "motion_prompt": "", "visual_prompt": ""}
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")
        video_path = str(tmp_path / "runway_scene_004.mp4")

        with patch(
            "musicvid.pipeline.visual_router.generate_video_from_text",
            return_value=video_path,
        ) as mock_gen:
            result = router.route(scene)

        # When both prompts empty, use fallback prompt
        call_args = mock_gen.call_args[0][0]
        assert len(call_args) > 0  # some prompt was passed
        assert result == video_path
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_visual_router.py::TestVisualRouterRunway -v 2>&1 | head -40
```

Expected: FAIL with `AttributeError: TYPE_VIDEO_RUNWAY not dispatched` or similar.

- [ ] **Step 3: Add `_route_runway_text_to_video()` to VisualRouter**

In `musicvid/pipeline/visual_router.py`, add after `_route_animated()`:

```python
def _route_runway_text_to_video(self, scene, idx, duration):
    """Route TYPE_VIDEO_RUNWAY → Runway text-to-video, fallback → Pexels stock."""
    output_path = str(self.cache_dir / f"runway_scene_{idx:03d}.mp4")
    if Path(output_path).exists():
        return output_path

    runway_key = os.environ.get("RUNWAY_API_KEY", "")
    if runway_key:
        visual = scene.get("visual_prompt", "")
        motion = scene.get("motion_prompt", "")
        if len(visual) > 500:
            visual = visual[:400]
        video_prompt = f"{visual} {motion}".strip() or "nature landscape slow camera movement"
        try:
            return generate_video_from_text(video_prompt, duration=5, output_path=output_path)
        except Exception as exc:
            print(f"  WARN: Runway text-to-video failed for scene {idx} — fallback Pexels ({exc})")

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

Also update the `route()` dispatch method — add before the `else: # TYPE_AI` branch:

```python
elif source == "TYPE_VIDEO_RUNWAY":
    return self._route_runway_text_to_video(scene, idx, duration)
```

The full updated `route()` should look like:

```python
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
        return self._route_runway_text_to_video(scene, idx, duration)
    else:  # TYPE_AI (default)
        return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_visual_router.py::TestVisualRouterRunway -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
python3 -m pytest tests/test_visual_router.py -v 2>&1 | tail -20
```

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/visual_router.py tests/test_visual_router.py
git commit -m "feat: add TYPE_VIDEO_RUNWAY routing in VisualRouter — Runway text-to-video with Pexels fallback"
```

---

## Task 2: Update director to support mode-aware defaults

**Files:**
- Modify: `musicvid/pipeline/director.py`
- Test: `tests/test_director.py`

- [ ] **Step 1: Write failing tests**

Add these tests to `tests/test_director.py` (after existing test classes):

```python
class TestValidateScenePlanModeDefaults:
    """Tests for mode-aware _validate_scene_plan defaults."""

    def test_default_visual_source_is_type_ai_when_no_mode(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {"section": "verse", "start": 0.0, "end": 5.0,
                 "visual_prompt": "test", "motion": "static",
                 "transition": "cut", "overlay": "none"},
            ]
        }
        result = _validate_scene_plan(plan, 5.0)
        assert result["scenes"][0]["visual_source"] == "TYPE_AI"

    def test_default_visual_source_is_type_video_runway_in_runway_mode(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {"section": "chorus", "start": 0.0, "end": 5.0,
                 "visual_prompt": "test", "motion": "static",
                 "transition": "cut", "overlay": "none"},
            ]
        }
        result = _validate_scene_plan(plan, 5.0, mode="runway")
        assert result["scenes"][0]["visual_source"] == "TYPE_VIDEO_RUNWAY"

    def test_explicit_visual_source_not_overridden_by_mode(self):
        from musicvid.pipeline.director import _validate_scene_plan
        plan = {
            "scenes": [
                {"section": "verse", "start": 0.0, "end": 5.0,
                 "visual_source": "TYPE_VIDEO_STOCK",
                 "visual_prompt": "", "motion": "static",
                 "transition": "cut", "overlay": "none"},
            ]
        }
        result = _validate_scene_plan(plan, 5.0, mode="runway")
        # Explicit choice preserved
        assert result["scenes"][0]["visual_source"] == "TYPE_VIDEO_STOCK"


class TestBuildUserMessageRunwayMode:
    """Tests for runway mode hint in _build_user_message."""

    def test_runway_mode_hint_in_message(self):
        from musicvid.pipeline.director import _build_user_message
        analysis = {
            "duration": 60.0, "bpm": 120.0, "beats": [0.0, 0.5, 1.0, 1.5],
            "lyrics": [], "sections": [],
        }
        msg = _build_user_message(analysis, mode="runway")
        assert "TYPE_VIDEO_RUNWAY" in msg
        assert "TYPE_VIDEO_STOCK" in msg

    def test_no_runway_hint_in_default_mode(self):
        from musicvid.pipeline.director import _build_user_message
        analysis = {
            "duration": 60.0, "bpm": 120.0, "beats": [0.0, 0.5, 1.0, 1.5],
            "lyrics": [], "sections": [],
        }
        msg = _build_user_message(analysis)
        # No runway-specific instructions appended
        assert "Use TYPE_VIDEO_RUNWAY" not in msg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_director.py::TestValidateScenePlanModeDefaults tests/test_director.py::TestBuildUserMessageRunwayMode -v 2>&1 | head -30
```

Expected: FAIL with `TypeError: _validate_scene_plan() got unexpected keyword argument 'mode'`.

- [ ] **Step 3: Update director.py — add mode parameter**

In `musicvid/pipeline/director.py`:

**Update `_validate_scene_plan` signature and default logic:**

```python
def _validate_scene_plan(plan, duration, mode=None):
    """Validate and fix the scene plan to ensure it covers the full duration."""
    if not plan.get("scenes"):
        raise ValueError("Scene plan has no scenes")

    if "master_style" not in plan:
        plan["master_style"] = ""

    default_visual_source = "TYPE_VIDEO_RUNWAY" if mode == "runway" else "TYPE_AI"

    for scene in plan["scenes"]:
        if "animate" not in scene:
            scene["animate"] = False
        if "motion_prompt" not in scene:
            scene["motion_prompt"] = ""
        if "lyrics_in_scene" not in scene:
            scene["lyrics_in_scene"] = []
        if "visual_source" not in scene:
            scene["visual_source"] = default_visual_source
        if "search_query" not in scene:
            scene["search_query"] = ""
        if "visual_prompt" not in scene:
            scene["visual_prompt"] = ""

    plan["scenes"].sort(key=lambda s: s["start"])
    plan["scenes"][0]["start"] = 0.0
    plan["scenes"][-1]["end"] = duration

    return plan
```

**Update `_build_user_message` signature — add mode parameter at end:**

```python
def _build_user_message(analysis, style_override=None, mode=None):
    """Build the user message for Claude with analysis data."""
    # ... (keep all existing code unchanged until the end) ...

    if style_override and style_override != "auto":
        msg += f"\n\nIMPORTANT: Override the style to be '{style_override}' regardless of the mood detected in the audio."

    if mode == "runway":
        msg += (
            "\n\nMODE: runway — Use TYPE_VIDEO_RUNWAY for climactic scenes (chorus, bridge). "
            "Use TYPE_VIDEO_STOCK for intro, verse, outro. "
            "Minimum 40% of scenes must be TYPE_VIDEO_RUNWAY. "
            "TYPE_AI is NOT available in this mode — do not use it."
        )

    return msg
```

**Update `create_scene_plan` signature and calls:**

```python
def create_scene_plan(analysis, style_override=None, output_dir=None, mode=None):
    """Create a scene plan using Claude API.

    Args:
        analysis: Audio analysis dict from Stage 1.
        style_override: Optional style override.
        output_dir: Optional directory to save scene_plan.json.
        mode: Optional mode hint ('runway', 'ai', 'stock') for type defaults.

    Returns:
        dict with keys: overall_style, color_palette, subtitle_style, scenes
    """
    system_prompt = _load_system_prompt()
    user_message = _build_user_message(analysis, style_override, mode=mode)

    response_text = _call_claude(system_prompt, user_message)
    text = _strip_markdown(response_text)

    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        plan = None
        basic = _repair_truncated_json(text)
        if basic is not None:
            parsed = json.loads(basic)
            if parsed.get("scenes"):
                plan = parsed
        if plan is None:
            aggressive = _repair_truncated_json_aggressive(text)
            if aggressive is not None:
                plan = json.loads(aggressive)
        if plan is None:
            retry_message = user_message + "\n\nIMPORTANT: Your previous response was truncated. Be more concise: keep visual_prompt under 100 characters and limit to 8 scenes maximum."
            response_text = _call_claude(system_prompt, retry_message)
            text = _strip_markdown(response_text)
            plan = json.loads(text)

    plan = _validate_scene_plan(plan, analysis["duration"], mode=mode)

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        with open(output_path / "scene_plan.json", "w") as f:
            json.dump(plan, f, indent=2)

    return plan
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_director.py::TestValidateScenePlanModeDefaults tests/test_director.py::TestBuildUserMessageRunwayMode -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Run full director test suite**

```bash
python3 -m pytest tests/test_director.py -v 2>&1 | tail -20
```

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/director.py tests/test_director.py
git commit -m "feat: add mode param to create_scene_plan and _validate_scene_plan — runway mode defaults to TYPE_VIDEO_RUNWAY"
```

---

## Task 3: Update director_system.txt with TYPE_VIDEO_RUNWAY

**Files:**
- Modify: `musicvid/prompts/director_system.txt`

- [ ] **Step 1: Add TYPE_VIDEO_RUNWAY section to director_system.txt**

Find the `TYPE_ANIMATED` block in `musicvid/prompts/director_system.txt` and add `TYPE_VIDEO_RUNWAY` **before** it (it is the new primary Runway type):

Locate the line:
```
TYPE_ANIMATED — Runway Gen-4.5 text-to-video ($0.50, climactic)
```

Insert before it:
```
TYPE_VIDEO_RUNWAY — Runway Gen-4.5 text-to-video ($0.50, primary AI video)
  When: chorus and bridge ALWAYS. Verse when lyrics describe motion, emotion, action.
        Use when you want unique AI cinematography that stock cannot provide.
        Minimum 40% of scenes in runway mode.
  Fields: set motion_prompt (full scene description 2-3 sentences: action + camera + mood + style),
          set visual_prompt (optional descriptor), set search_query to ""
  motion_prompt must contain: what happens + camera movement + mood + style
  Style keywords: documentary, authentic, cinematic, natural light, film grain
  Example motion_prompts:
    Chorus: "Slow camera rise over misty mountain valley, person silhouette on ridge with
    arms open at dawn, documentary style, natural golden light, film grain"
    Verse: "Gentle push through morning mist in mountain valley, soft diffused light,
    peaceful atmosphere, no people, documentary nature cinematography, natural colors"
    Bridge: "Dramatic slow pull-back revealing endless ocean horizon, waves catching
    golden sunset light, emotional peak moment, cinematic documentary style, handheld feel"
    Intro: "Static wide shot of misty forest at dawn, light slowly breaking through
    trees, birds visible, nature documentary style, peaceful and contemplative"
```

- [ ] **Step 2: Update EXAMPLES section to include TYPE_VIDEO_RUNWAY**

Find the `EXAMPLES:` block and add:
```
  Refren (>6s, ruch/emocja) → TYPE_VIDEO_RUNWAY, motion_prompt: "slow camera rises..."
  Bridge (kulminacja) → TYPE_VIDEO_RUNWAY, motion_prompt: "dramatic pull-back..."
```

- [ ] **Step 3: Verify director_system.txt is valid**

```bash
python3 -c "
from pathlib import Path
txt = (Path('musicvid/prompts/director_system.txt')).read_text()
assert 'TYPE_VIDEO_RUNWAY' in txt
assert 'motion_prompt' in txt
print('OK — director_system.txt contains TYPE_VIDEO_RUNWAY')
print(f'File length: {len(txt)} chars')
"
```

Expected: `OK — director_system.txt contains TYPE_VIDEO_RUNWAY`

- [ ] **Step 4: Commit**

```bash
git add musicvid/prompts/director_system.txt
git commit -m "docs: add TYPE_VIDEO_RUNWAY to director system prompt with motion_prompt examples"
```

---

## Task 4: Add --mode runway to CLI

**Files:**
- Modify: `musicvid/musicvid.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add these tests to `tests/test_cli.py` in the `TestCLI` class:

```python
@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.VisualRouter")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_mode_runway_calls_visual_router(
    self, mock_analyze, mock_direct, mock_router_cls, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")

    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "chorus", "start": 0.0, "end": 10.0}],
        "mood_energy": "contemplative", "language": "pl",
    }
    scene = {
        "section": "chorus", "start": 0.0, "end": 10.0,
        "visual_source": "TYPE_VIDEO_RUNWAY", "search_query": "",
        "visual_prompt": "mountain sunrise", "motion_prompt": "slow rise",
        "motion": "static", "transition": "cut", "overlay": "none",
        "animate": False, "lyrics_in_scene": [],
    }
    mock_direct.return_value = {
        "overall_style": "worship",
        "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "karaoke"},
        "scenes": [scene],
    }
    fake_asset = str(tmp_path / "runway_scene_000.mp4")
    router_instance = MagicMock()
    router_instance.route.return_value = fake_asset
    mock_router_cls.return_value = router_instance

    output_dir = tmp_path / "output"
    result = runner.invoke(cli, [
        str(audio_file),
        "--output", str(output_dir),
        "--mode", "runway",
        "--preset", "full",
    ])

    assert result.exit_code == 0, result.output
    mock_router_cls.assert_called_once()
    router_instance.route.assert_called_once()
    mock_assemble.assert_called_once()

@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.VisualRouter")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_mode_runway_is_default(
    self, mock_analyze, mock_direct, mock_router_cls, mock_assemble, mock_font, runner, tmp_path
):
    """Invoking CLI without --mode should use VisualRouter (runway is default)."""
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")

    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
        "mood_energy": "contemplative", "language": "pl",
    }
    scene = {
        "section": "verse", "start": 0.0, "end": 10.0,
        "visual_source": "TYPE_VIDEO_RUNWAY", "search_query": "",
        "visual_prompt": "valley", "motion_prompt": "gentle push",
        "motion": "static", "transition": "cut", "overlay": "none",
        "animate": False, "lyrics_in_scene": [],
    }
    mock_direct.return_value = {
        "overall_style": "contemplative",
        "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "karaoke"},
        "scenes": [scene],
    }
    router_instance = MagicMock()
    router_instance.route.return_value = str(tmp_path / "runway_scene_000.mp4")
    mock_router_cls.return_value = router_instance

    output_dir = tmp_path / "output"
    result = runner.invoke(cli, [
        str(audio_file),
        "--output", str(output_dir),
        "--preset", "full",
        # NOTE: no --mode flag — should default to runway
    ])

    assert result.exit_code == 0, result.output
    # Default mode uses VisualRouter (runway path), not fetch_videos (stock path)
    mock_router_cls.assert_called_once()

@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.VisualRouter")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_mode_runway_passes_mode_to_director(
    self, mock_analyze, mock_direct, mock_router_cls, mock_assemble, mock_font, runner, tmp_path
):
    """--mode runway passes mode='runway' to create_scene_plan."""
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")

    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
        "mood_energy": "contemplative", "language": "pl",
    }
    scene = {
        "section": "verse", "start": 0.0, "end": 10.0,
        "visual_source": "TYPE_VIDEO_RUNWAY", "search_query": "",
        "visual_prompt": "", "motion_prompt": "",
        "motion": "static", "transition": "cut", "overlay": "none",
        "animate": False, "lyrics_in_scene": [],
    }
    mock_direct.return_value = {
        "overall_style": "contemplative",
        "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "karaoke"},
        "scenes": [scene],
    }
    router_instance = MagicMock()
    router_instance.route.return_value = str(tmp_path / "runway_scene_000.mp4")
    mock_router_cls.return_value = router_instance

    output_dir = tmp_path / "output"
    runner.invoke(cli, [
        str(audio_file), "--output", str(output_dir),
        "--mode", "runway", "--preset", "full",
    ])

    # Verify create_scene_plan was called with mode='runway'
    call_kwargs = mock_direct.call_args[1]
    assert call_kwargs.get("mode") == "runway"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_mode_runway_calls_visual_router tests/test_cli.py::TestCLI::test_mode_runway_is_default tests/test_cli.py::TestCLI::test_mode_runway_passes_mode_to_director -v 2>&1 | head -40
```

Expected: FAIL with `Error: Invalid value for '--mode': 'runway' is not 'stock', 'ai', 'hybrid'.`

- [ ] **Step 3: Add --mode runway to CLI options in musicvid.py**

Find the `--mode` option definition in `musicvid/musicvid.py` (around line 404):

```python
@click.option("--mode", type=click.Choice(["stock", "ai", "hybrid"]), default="ai", help="Video source mode.")
```

Change to:
```python
@click.option("--mode", type=click.Choice(["stock", "ai", "runway", "hybrid"]), default="runway", help="Video source mode.")
```

- [ ] **Step 4: Update Stage 3 routing for runway mode**

Find the Stage 3 block (around line 609) where mode handling occurs:

```python
if mode == "ai":
    ...
else:  # mode == "stock"
    ...
```

Change to:

```python
if mode in ("ai", "runway"):
    router = VisualRouter(cache_dir=str(cache_dir), provider=provider)
    fetch_manifest = []
    for i, scene in enumerate(scene_plan["scenes"]):
        scene["index"] = i
        src = scene.get("visual_source", "TYPE_AI")
        asset_path = router.route(scene)
        fetch_manifest.append({
            "scene_index": i,
            "video_path": asset_path,
            "start": scene["start"],
            "end": scene["end"],
            "source": src,
        })
    save_cache(cache_dir, "image_manifest.json", fetch_manifest)
elif mode == "stock":
    fetch_manifest = fetch_videos(scene_plan, output_dir=str(cache_dir))
else:  # hybrid
    fetch_manifest = fetch_videos(scene_plan, output_dir=str(cache_dir))
```

- [ ] **Step 5: Pass mode to create_scene_plan**

Find the `create_scene_plan(...)` call in the CLI (Stage 2, around line 572). Update it to pass `mode`:

```python
scene_plan = create_scene_plan(
    audio_analysis,
    style_override=style,
    output_dir=str(cache_dir),
    mode=mode,
)
```

- [ ] **Step 6: Update _print_startup_summary() for runway mode**

Find `_print_startup_summary()` (around line 267). Update `images_desc`:

```python
if mode == "runway":
    images_desc = "Runway Gen-4.5 AI video + Pexels przyroda"
elif mode == "ai":
    images_desc = f"BFL {provider.upper()} (AI)"
else:
    images_desc = "Pexels (stock)"
```

- [ ] **Step 7: Update API key fallback for runway mode**

Find the API key fallback block (around line 462). The existing check `if mode == "ai" and not BFL_API_KEY` should stay. Add for runway mode: runway without RUNWAY_API_KEY just keeps going (VisualRouter handles fallback to Pexels internally). No CLI-level switch needed.

Verify the existing block is correct:
```python
if mode == "ai" and not os.environ.get("BFL_API_KEY"):
    click.echo("Brak BFL_API_KEY — przełączam na tryb stock (Pexels)...")
    mode = "stock"
# runway mode: no key check at CLI level — VisualRouter falls back to Pexels internally
```

- [ ] **Step 8: Update --economy shortcut (still mode=ai, correct)**

Verify `--economy` still sets `mode="ai"` (for BFL Flux — intentional). No change needed.

- [ ] **Step 9: Run new CLI tests**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_mode_runway_calls_visual_router tests/test_cli.py::TestCLI::test_mode_runway_is_default tests/test_cli.py::TestCLI::test_mode_runway_passes_mode_to_director -v
```

Expected: All 3 tests PASS.

- [ ] **Step 10: Run full test suite**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests pass. If `test_mode_option_values` fails because it only checks `["stock", "ai", "hybrid"]`, update it to also accept `"runway"`.

Fix in `test_cli.py` if needed:
```python
def test_mode_option_values(self, runner, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake")
    for mode in ["stock", "ai", "runway", "hybrid"]:
        result = runner.invoke(cli, [str(audio_file), "--mode", mode, "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 11: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add --mode runway as new default — Runway text-to-video + Pexels nature mix"
```

---

## Self-Review

### Spec Coverage Check

| Spec Requirement | Task |
|----------------|------|
| TYPE_VIDEO_RUNWAY → Runway Gen-4.5 text-to-video | Task 1 |
| Fallback gdy brak RUNWAY_API_KEY → TYPE_VIDEO_STOCK | Task 1, `_route_runway_text_to_video` |
| TYPE_ANIMATED deprecated/replaced for runway mode | Task 1 (TYPE_VIDEO_RUNWAY is new primary type) |
| director_system.txt: new TYPE_VIDEO_RUNWAY guidance | Task 3 |
| director_system.txt: motion_prompt examples | Task 3 |
| --mode runway as new CLI option | Task 4 |
| --mode runway as new default | Task 4, Step 3 |
| _validate_scene_plan defaults TYPE_VIDEO_RUNWAY in runway mode | Task 2 |
| _print_startup_summary shows Runway mix | Task 4, Step 6 |
| Tests for TYPE_VIDEO_RUNWAY routing | Task 1 |
| Tests for director mode-aware defaults | Task 2 |
| Tests for --mode runway CLI | Task 4 |
| --mode ai still works (backward compat) | Unchanged — VisualRouter handles TYPE_AI |
| --mode stock still works | Unchanged |
| python3 -m pytest tests/ -v passes | Task 4, Step 10 |

### Gaps / Notes
- `TYPE_ANIMATED` is kept as-is for backward compatibility (existing scene plans that use it still work). In runway mode, director uses `TYPE_VIDEO_RUNWAY` instead. Both route to `generate_video_from_text()`.
- `--mode hybrid` is not changed — out of spec scope.
- `enforce_animation_rules` is only called for `animate_mode` logic, not for TYPE_VIDEO_RUNWAY scenes — this is intentional (TYPE_VIDEO_RUNWAY has no 25% cap).
- The `--animate` flag still controls TYPE_ANIMATED scenes only; TYPE_VIDEO_RUNWAY is unaffected.
