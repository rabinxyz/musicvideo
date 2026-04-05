# Animation Rules Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce animation placement rules (no adjacent animated scenes, max 25% animated, no outro/short-scene animation) on the director's scene plan before Runway Gen-4 runs.

**Architecture:** Add two helper functions (`get_section_priority`, `enforce_animation_rules`) to `musicvid/musicvid.py`, call `enforce_animation_rules` in the pipeline after the `--animate always/never` overrides and before the Runway animation loop (only when `animate_mode == "auto"`), and tighten the director system prompt to guide Claude toward producing compliant plans from the start.

**Tech Stack:** Python 3.11+, pytest, Click CLI (existing). No new dependencies.

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `musicvid/musicvid.py` | Add `get_section_priority()`, `enforce_animation_rules()`, call site |
| Modify | `musicvid/prompts/director_system.txt` | Update ANIMATION RULES section |
| Create | `tests/test_animation_rules.py` | Unit tests for both helper functions |

---

### Task 1: Write failing tests for `get_section_priority`

**Files:**
- Create: `tests/test_animation_rules.py`

- [ ] **Step 1: Write the failing test file**

```python
# tests/test_animation_rules.py
import pytest
from musicvid.musicvid import get_section_priority, enforce_animation_rules


class TestGetSectionPriority:
    def test_chorus_highest(self):
        assert get_section_priority("chorus") == 5

    def test_bridge(self):
        assert get_section_priority("bridge") == 4

    def test_verse(self):
        assert get_section_priority("verse") == 3

    def test_intro(self):
        assert get_section_priority("intro") == 2

    def test_outro_zero(self):
        assert get_section_priority("outro") == 0

    def test_unknown_section_default(self):
        assert get_section_priority("interlude") == 1

    def test_empty_string_default(self):
        assert get_section_priority("") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_animation_rules.py::TestGetSectionPriority -v`

Expected: `ImportError` or `FAILED` — `get_section_priority` not defined yet.

---

### Task 2: Implement `get_section_priority` and make its tests pass

**Files:**
- Modify: `musicvid/musicvid.py` — add functions before the `cli()` function

- [ ] **Step 1: Add `get_section_priority` to musicvid.py**

Find the line just before `def cli(` in `musicvid/musicvid.py` and insert:

```python
def get_section_priority(section: str) -> int:
    """Return animation priority for a section type. Higher = more important."""
    return {"chorus": 5, "bridge": 4, "verse": 3, "intro": 2, "outro": 0}.get(section, 1)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_animation_rules.py::TestGetSectionPriority -v`

Expected: `7 passed`

- [ ] **Step 3: Commit**

```bash
git add tests/test_animation_rules.py musicvid/musicvid.py
git commit -m "feat: add get_section_priority helper with tests"
```

---

### Task 3: Write failing tests for `enforce_animation_rules`

**Files:**
- Modify: `tests/test_animation_rules.py`

- [ ] **Step 1: Add tests for `enforce_animation_rules`**

Append to `tests/test_animation_rules.py`:

```python
def _make_scene(section, animate, start=0.0, end=10.0):
    return {"section": section, "animate": animate, "start": start, "end": end}


class TestEnforceAnimationRules:

    # ---- adjacency ----

    def test_adjacent_animated_lower_priority_disabled(self):
        scenes = [
            _make_scene("chorus", True, 0, 10),
            _make_scene("verse", True, 10, 20),
            _make_scene("verse", False, 20, 30),
            _make_scene("chorus", True, 30, 40),
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is True   # chorus keeps
        assert result[1]["animate"] is False  # verse loses to adjacent chorus
        assert result[2]["animate"] is False  # already false
        assert result[3]["animate"] is True   # chorus keeps

    def test_two_adjacent_same_priority_second_disabled(self):
        scenes = [
            _make_scene("verse", True, 0, 10),
            _make_scene("verse", True, 10, 20),
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is True
        assert result[1]["animate"] is False

    def test_non_adjacent_both_keep_animation(self):
        scenes = [
            _make_scene("chorus", True, 0, 10),
            _make_scene("verse", False, 10, 20),
            _make_scene("bridge", True, 20, 30),
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is True
        assert result[2]["animate"] is True

    # ---- max count ----

    def test_max_animated_25_percent(self):
        # 20 scenes, 8 animated → max 5 (20 // 4)
        scenes = []
        for i in range(20):
            animate = i < 8
            scenes.append(_make_scene("verse", animate, i * 10, (i + 1) * 10))
        result = enforce_animation_rules(scenes)
        animated = [s for s in result if s["animate"]]
        assert len(animated) <= 5

    def test_min_one_animated_allowed(self):
        # 3 scenes → max(1, 3//4) = max(1,0) = 1
        scenes = [
            _make_scene("chorus", True, 0, 10),
            _make_scene("verse", False, 10, 20),
            _make_scene("verse", False, 20, 30),
        ]
        result = enforce_animation_rules(scenes)
        assert sum(1 for s in result if s["animate"]) == 1

    def test_excess_animated_keeps_highest_priority(self):
        # 8 scenes, 3 animated (max 2) — keep the two with highest section priority
        scenes = [
            _make_scene("verse", True, 0, 10),    # priority 3 — should be dropped
            _make_scene("verse", False, 10, 20),
            _make_scene("chorus", True, 20, 30),  # priority 5 — keep
            _make_scene("verse", False, 30, 40),
            _make_scene("bridge", True, 40, 50),  # priority 4 — keep
            _make_scene("verse", False, 50, 60),
            _make_scene("verse", False, 60, 70),
            _make_scene("verse", False, 70, 80),
        ]
        result = enforce_animation_rules(scenes)
        animated = [s for s in result if s["animate"]]
        assert len(animated) == 2
        sections = {s["section"] for s in animated}
        assert "chorus" in sections
        assert "bridge" in sections

    # ---- short scenes ----

    def test_short_scene_disabled(self):
        scenes = [
            _make_scene("chorus", True, 0, 4),  # 4s < 6s
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is False

    def test_exactly_6s_allowed(self):
        scenes = [
            _make_scene("chorus", True, 0, 6),  # exactly 6s
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is True

    def test_short_scene_under_6s_disabled(self):
        scenes = [
            _make_scene("chorus", True, 0.0, 5.9),  # 5.9s < 6s
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is False

    # ---- outro ----

    def test_outro_never_animated(self):
        scenes = [
            _make_scene("outro", True, 0, 20),
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is False

    # ---- priority tie-breaking ----

    def test_priority_chorus_beats_verse_when_adjacent(self):
        scenes = [
            _make_scene("verse", True, 0, 10),
            _make_scene("chorus", True, 10, 20),
        ]
        result = enforce_animation_rules(scenes)
        assert result[0]["animate"] is False  # verse loses
        assert result[1]["animate"] is True   # chorus wins

    # ---- returns list ----

    def test_returns_list(self):
        scenes = [_make_scene("verse", False, 0, 10)]
        result = enforce_animation_rules(scenes)
        assert isinstance(result, list)

    # ---- log output ----

    def test_short_scene_prints_warning(self, capsys):
        scenes = [_make_scene("chorus", True, 0, 4)]
        enforce_animation_rules(scenes)
        captured = capsys.readouterr()
        assert "WARN" in captured.out or "za krótka" in captured.out

    def test_prints_animation_plan_summary(self, capsys):
        scenes = [
            _make_scene("chorus", True, 0, 10),
            _make_scene("verse", False, 10, 20),
        ]
        enforce_animation_rules(scenes)
        captured = capsys.readouterr()
        assert "Plan animacji Runway" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_animation_rules.py::TestEnforceAnimationRules -v`

Expected: `ImportError` or `FAILED` — `enforce_animation_rules` not defined yet.

---

### Task 4: Implement `enforce_animation_rules` and make all tests pass

**Files:**
- Modify: `musicvid/musicvid.py` — add `enforce_animation_rules` after `get_section_priority`

- [ ] **Step 1: Add `enforce_animation_rules` to musicvid.py right after `get_section_priority`**

```python
def enforce_animation_rules(scenes: list) -> list:
    """Enforce animation placement rules on director's scene plan.

    Rules applied in order:
    1. Disable short scenes (< 6s) — Runway minimum
    2. Disable outro scenes — should always be calm
    3. Fix adjacency — no two animated scenes side by side (lower priority loses)
    4. Enforce max 25% animated (max(1, total//4)), keeping highest priority
    5. Print animation plan summary
    """
    # Rule 1: short scenes and outro
    for scene in scenes:
        if scene.get("animate"):
            duration = scene["end"] - scene["start"]
            if duration < 6.0:
                scene["animate"] = False
                print(
                    f"WARN: Scena {scene['section']} za krótka"
                    f" ({duration:.1f}s) — Ken Burns fallback"
                )
            elif scene["section"] == "outro":
                scene["animate"] = False

    # Rule 2: adjacency — iterate forward, disable lower-priority neighbour
    for i in range(len(scenes) - 1):
        if scenes[i].get("animate") and scenes[i + 1].get("animate"):
            p_i = get_section_priority(scenes[i]["section"])
            p_next = get_section_priority(scenes[i + 1]["section"])
            if p_i >= p_next:
                scenes[i + 1]["animate"] = False
            else:
                scenes[i]["animate"] = False

    # Rule 3: max animated = max(1, total // 4)
    animated_indices = [i for i, s in enumerate(scenes) if s.get("animate")]
    max_animated = max(1, len(scenes) // 4)
    if len(animated_indices) > max_animated:
        # Sort by priority descending, keep top max_animated
        animated_indices.sort(key=lambda i: get_section_priority(scenes[i]["section"]), reverse=True)
        for idx in animated_indices[max_animated:]:
            scenes[idx]["animate"] = False

    # Rule 4: print summary
    animated = [i for i, s in enumerate(scenes) if s.get("animate")]
    print(f"Plan animacji Runway: {len(animated)} scen z {len(scenes)}")
    for i in animated:
        s = scenes[i]
        print(f"  Scena {i}: {s['section']} @ {s['start']:.1f}-{s['end']:.1f}s")

    return scenes
```

- [ ] **Step 2: Run all animation rule tests**

Run: `python3 -m pytest tests/test_animation_rules.py -v`

Expected: All tests pass.

- [ ] **Step 3: Run full test suite to check for regressions**

Run: `python3 -m pytest tests/ -v 2>&1 | tail -20`

Expected: No new failures (existing count ~341 tests).

- [ ] **Step 4: Commit**

```bash
git add musicvid/musicvid.py tests/test_animation_rules.py
git commit -m "feat: implement enforce_animation_rules with full test coverage"
```

---

### Task 5: Wire `enforce_animation_rules` into the pipeline

**Files:**
- Modify: `musicvid/musicvid.py` — add call site after the animate overrides, before animation loop

- [ ] **Step 1: Locate insertion point**

In `musicvid/musicvid.py`, find this block (around line 503–506):

```python
        elif animate_mode == "never":
            for scene in scene_plan["scenes"]:
                scene["animate"] = False

        # Stage 3.5: Animate scenes with Runway Gen-4
```

- [ ] **Step 2: Insert the call for `auto` mode only**

After the `elif animate_mode == "never":` block and before the `# Stage 3.5:` comment, add:

```python
        # Enforce animation placement rules (auto mode only — always/never are explicit overrides)
        if animate_mode == "auto":
            scene_plan["scenes"] = enforce_animation_rules(scene_plan["scenes"])
```

The block should now read:

```python
        elif animate_mode == "never":
            for scene in scene_plan["scenes"]:
                scene["animate"] = False

        # Enforce animation placement rules (auto mode only — always/never are explicit overrides)
        if animate_mode == "auto":
            scene_plan["scenes"] = enforce_animation_rules(scene_plan["scenes"])

        # Stage 3.5: Animate scenes with Runway Gen-4
        if animate_mode != "never":
```

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ -v 2>&1 | tail -20`

Expected: No new failures.

- [ ] **Step 4: Commit**

```bash
git add musicvid/musicvid.py
git commit -m "feat: wire enforce_animation_rules into pipeline for auto animate mode"
```

---

### Task 6: Update director system prompt

**Files:**
- Modify: `musicvid/prompts/director_system.txt`

- [ ] **Step 1: Replace the ANIMATION RULES section**

Find this block in `musicvid/prompts/director_system.txt`:

```
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
```

Replace it with:

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

- [ ] **Step 2: Verify the file looks correct**

Run: `python3 -c "open('musicvid/prompts/director_system.txt').read()"`

Expected: No errors (file is valid text).

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ -v 2>&1 | tail -20`

Expected: No new failures.

- [ ] **Step 4: Commit**

```bash
git add musicvid/prompts/director_system.txt
git commit -m "docs: update director prompt with stricter animation placement rules"
```

---

## Self-Review Against Spec

| Spec Requirement | Task Covering It |
|-----------------|-----------------|
| No adjacent animated scenes | Task 3 test + Task 4 impl (Rule 2) |
| Max 25% animated (max(1, total//4)) | Task 3 test + Task 4 impl (Rule 3) |
| Outro never animated | Task 3 test + Task 4 impl (Rule 1) |
| Scenes < 6s never animated | Task 3 test + Task 4 impl (Rule 1) |
| Log shows animation plan | Task 3 test + Task 4 impl (Rule 4) |
| Priority: chorus > bridge > verse > intro > outro | Task 1+2 (get_section_priority) |
| Call before animation loop | Task 5 |
| Update director prompt | Task 6 |
| `python3 -m pytest tests/test_animation_rules.py -v` passes | Tasks 2+4 |
