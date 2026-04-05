# Fix Animation Duration Threshold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lower the minimum scene duration threshold for Runway animation from 6s to 3s, and always send duration=5 to Runway API regardless of scene length.

**Architecture:** Two surgical changes: (1) `enforce_animation_rules()` in `musicvid/musicvid.py` threshold 6.0→3.0, (2) `_route_animated()` in `musicvid/pipeline/visual_router.py` always passes duration=5 to `animate_image()`. Existing tests updated to match new threshold. Assembler already trims via `subclipped()`.

**Tech Stack:** Python, pytest, unittest.mock

---

### Task 1: Update tests for new 3s threshold in `enforce_animation_rules`

**Files:**
- Modify: `tests/test_animation_rules.py:123-142` (short scene tests)

- [ ] **Step 1: Update `test_short_scene_disabled` — 4s scene should now PASS animation (>= 3s)**

Change the test: a 4s scene is now long enough for animation, so we need a scene < 3s to test the disable path.

```python
    def test_short_scene_disabled(self):
        scenes = [
            _make_scene("chorus", True, 0, 2),  # 2s < 3s
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is False
```

- [ ] **Step 2: Update `test_exactly_6s_allowed` → `test_exactly_3s_allowed`**

```python
    def test_exactly_3s_allowed(self):
        scenes = [
            _make_scene("chorus", True, 0, 3),  # exactly 3s
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is True
```

- [ ] **Step 3: Update `test_short_scene_under_6s_disabled` → `test_short_scene_under_3s_disabled`**

```python
    def test_short_scene_under_3s_disabled(self):
        scenes = [
            _make_scene("chorus", True, 0.0, 2.9),  # 2.9s < 3s
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is False
```

- [ ] **Step 4: Add new test — 4s chorus scene IS animated (the core fix)**

```python
    def test_4s_chorus_scene_animated(self):
        """Regression: 4-5s chorus scenes must be animated, not Ken Burns fallback."""
        scenes = [
            _make_scene("chorus", True, 0, 4.5),  # 4.5s >= 3s — should animate
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is True
```

- [ ] **Step 5: Run tests — expect failures on threshold tests (still 6.0 in code)**

Run: `python3 -m pytest tests/test_animation_rules.py -v`
Expected: `test_exactly_3s_allowed` FAILS (code still checks `< 6.0`), `test_4s_chorus_scene_animated` FAILS.

- [ ] **Step 6: Commit test changes**

```bash
git add tests/test_animation_rules.py
git commit -m "test: update animation rules tests for 3s threshold (red phase)"
```

---

### Task 2: Lower threshold from 6.0 to 3.0 in `enforce_animation_rules`

**Files:**
- Modify: `musicvid/musicvid.py:301` — change `duration < 6.0` to `duration < 3.0`

- [ ] **Step 1: Change the threshold**

In `musicvid/musicvid.py`, in `enforce_animation_rules`, change line 301:

Old:
```python
            if duration < 6.0:
```

New:
```python
            if duration < 3.0:
```

- [ ] **Step 2: Run animation rules tests — all should pass**

Run: `python3 -m pytest tests/test_animation_rules.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add musicvid/musicvid.py
git commit -m "fix: lower animation min duration threshold from 6s to 3s"
```

---

### Task 3: Always pass duration=5 to Runway in `_route_animated`

**Files:**
- Modify: `musicvid/pipeline/visual_router.py:123` — replace `clip_dur = min(5, int(duration))` with `runway_duration = 5`
- Modify: `tests/test_visual_router.py` — update/add test for fixed duration

- [ ] **Step 1: Find and read the existing test for `_route_animated` duration**

Run: `python3 -m pytest tests/test_visual_router.py -v -k animated 2>&1 | head -40`

Review the existing test to understand current assertions about duration.

- [ ] **Step 2: Add/update test asserting duration=5 is always passed to `animate_image`**

In `tests/test_visual_router.py`, add a test that verifies `animate_image` is called with `duration=5` regardless of scene duration:

```python
    def test_route_animated_always_sends_duration_5(self, tmp_path):
        """Runway always receives duration=5, assembler trims to scene length."""
        router = VisualRouter(str(tmp_path), provider="flux-pro")
        scene = {
            "index": 0,
            "visual_source": "TYPE_ANIMATED",
            "visual_prompt": "sunset",
            "motion_prompt": "slow pan",
            "start": 0,
            "end": 3.5,  # 3.5s scene — should still send 5 to Runway
        }
        with patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key", "BFL_API_KEY": "test-key"}):
            with patch.object(router, "_generate_bfl", return_value=str(tmp_path / "img.jpg")):
                with patch("musicvid.pipeline.visual_router.animate_image") as mock_animate:
                    mock_animate.return_value = str(tmp_path / "animated_scene_000.mp4")
                    router.route(scene)
                    mock_animate.assert_called_once()
                    call_args = mock_animate.call_args
                    assert call_args[0][2] == 5 or call_args[1].get("duration") == 5
```

- [ ] **Step 3: Run test — expect FAIL (code passes `min(5, 3)` = 3)**

Run: `python3 -m pytest tests/test_visual_router.py -v -k "duration_5"`
Expected: FAIL — animate_image called with duration=3

- [ ] **Step 4: Fix `_route_animated` to always use duration=5**

In `musicvid/pipeline/visual_router.py`, change `_route_animated` (line 123-124):

Old:
```python
        motion = scene.get("motion_prompt", "slow camera push forward")
        clip_dur = min(5, int(duration))
        return animate_image(image_path, motion, clip_dur, output_path)
```

New:
```python
        motion = scene.get("motion_prompt", "slow camera push forward")
        return animate_image(image_path, motion, 5, output_path)
```

- [ ] **Step 5: Run all visual router tests — all should pass**

Run: `python3 -m pytest tests/test_visual_router.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add musicvid/pipeline/visual_router.py tests/test_visual_router.py
git commit -m "fix: always send duration=5 to Runway API regardless of scene length"
```
