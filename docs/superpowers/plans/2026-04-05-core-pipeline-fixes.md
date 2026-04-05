# Core Pipeline Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 core pipeline issues: subtitle pre-display offset, BPM-aware scene count, downbeat snapping, and lyrics-referenced visual prompts.

**Architecture:** Changes span `director.py` (BPM-aware prompt building, lyrics_in_scene field), `musicvid.py` (downbeat computation and snapping), `assembler.py` (subtitle timing offset), and `prompts/director_system.txt` (JSON schema update). Each fix is independent; tests accompany each change.

**Tech Stack:** Python 3.11+, MoviePy 2.1.2, anthropic SDK, pytest + unittest.mock

---

## File Map

| File | Change |
|------|--------|
| `musicvid/pipeline/assembler.py` | `_create_subtitle_clips`: subtract 0.1s from each segment start |
| `musicvid/pipeline/director.py` | `_build_user_message`: add BPM/bar_duration/downbeats/suggested_scene_count; `_validate_scene_plan`: default `lyrics_in_scene` |
| `musicvid/prompts/director_system.txt` | Add `lyrics_in_scene` to JSON output schema |
| `musicvid/musicvid.py` | Add `_compute_downbeats(beats)` helper; replace `_snap_to_nearest_beat` in `_apply_beat_sync` with window-based downbeat snap |
| `tests/test_assembler.py` | Test subtitle -0.1s offset |
| `tests/test_director.py` | Test BPM message fields; test `lyrics_in_scene` validation default |
| `tests/test_cli.py` | Test downbeat snapping logic |

---

## Task 1: Subtitle Pre-Display Offset

**Files:**
- Modify: `musicvid/pipeline/assembler.py:196-197`
- Test: `tests/test_assembler.py`

Context: `_create_subtitle_clips` builds TextClips from lyrics segments. Each clip gets
`txt_clip.with_start(segment["start"])`. The spec requires showing subtitles 0.1s before the
word. We subtract 0.1s from start (clamped to 0) and extend duration by 0.1s.

- [ ] **Step 1: Write failing test**

Add to `tests/test_assembler.py`:

```python
def test_subtitle_clips_predisplay_offset():
    """Subtitle clips start 0.1s before segment start."""
    from musicvid.pipeline.assembler import _create_subtitle_clips
    from unittest.mock import patch, MagicMock

    lyrics = [{"start": 5.0, "end": 6.5, "text": "Hello"}]
    subtitle_style = {"font_size": 48, "color": "#FFFFFF", "outline_color": "#000000"}
    size = (1920, 1080)

    mock_clip = MagicMock()
    mock_clip.with_duration.return_value = mock_clip
    mock_clip.with_start.return_value = mock_clip
    mock_clip.with_position.return_value = mock_clip
    mock_clip.with_effects.return_value = mock_clip

    with patch("musicvid.pipeline.assembler.TextClip", return_value=mock_clip):
        clips = _create_subtitle_clips(lyrics, subtitle_style, size)

    # Should start 0.1s earlier
    mock_clip.with_start.assert_called_once_with(4.9)
    # Duration should be 1.5 + 0.1 = 1.6s
    mock_clip.with_duration.assert_called_once_with(1.6)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_assembler.py::test_subtitle_clips_predisplay_offset -v
```

Expected: FAIL (current code calls `with_start(5.0)` and `with_duration(1.5)`)

- [ ] **Step 3: Implement the offset in assembler.py**

In `musicvid/pipeline/assembler.py`, find `_create_subtitle_clips` around line 196-197.
Replace:

```python
        txt_clip = txt_clip.with_duration(duration)
        txt_clip = txt_clip.with_start(segment["start"])
```

With:

```python
        offset_start = max(0.0, segment["start"] - 0.1)
        offset_duration = duration + (segment["start"] - offset_start)
        txt_clip = txt_clip.with_duration(offset_duration)
        txt_clip = txt_clip.with_start(offset_start)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_assembler.py::test_subtitle_clips_predisplay_offset -v
```

Expected: PASS

- [ ] **Step 5: Run full assembler tests to confirm no regressions**

```bash
python3 -m pytest tests/test_assembler.py -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "fix: show subtitles 0.1s before word for readability"
```

---

## Task 2: BPM-Aware Director Prompt

**Files:**
- Modify: `musicvid/pipeline/director.py:19-33` (`_build_user_message`)
- Modify: `musicvid/pipeline/director.py:59-79` (`_validate_scene_plan`)
- Modify: `musicvid/prompts/director_system.txt` (add `lyrics_in_scene` to JSON schema)
- Test: `tests/test_director.py`

Context: `_build_user_message` currently tells Claude "Generate a maximum of N scenes" with N=10/12/15
based on fixed duration brackets. The spec requires passing BPM, bar_duration, downbeats list,
and `suggested_scene_count = int(duration / (bar_duration * 4))` so Claude generates the right number
of properly-timed scenes. Also adding `lyrics_in_scene` to the output JSON forces Claude to list
which lyrics are in each scene (improving visual prompt relevance).

- [ ] **Step 1: Write failing tests**

Add to `tests/test_director.py`:

```python
def test_build_user_message_includes_bpm_guidance():
    """User message contains BPM, bar_duration, and suggested_scene_count."""
    from musicvid.pipeline.director import _build_user_message

    analysis = {
        "duration": 240.0,
        "bpm": 84.0,
        "beats": [i * (60.0 / 84.0) for i in range(200)],  # synthetic beat list
        "lyrics": [],
        "sections": [],
        "mood_energy": "medium",
    }
    msg = _build_user_message(analysis)

    assert "BPM: 84" in msg
    # bar_duration = 4 * (60/84) ≈ 2.86s; suggested = int(240 / (2.86*4)) = 21
    assert "suggested" in msg.lower() or "scen" in msg.lower()
    assert "bar" in msg.lower() or "takt" in msg.lower()


def test_build_user_message_scene_count_based_on_bpm():
    """Suggested scene count is derived from BPM and duration, not fixed brackets."""
    from musicvid.pipeline.director import _build_user_message

    # 3-minute song at 120 BPM: bar = 2s, suggested = int(180/(2*4)) = 22
    analysis = {
        "duration": 180.0,
        "bpm": 120.0,
        "beats": [i * 0.5 for i in range(360)],
        "lyrics": [],
        "sections": [],
        "mood_energy": "high",
    }
    msg = _build_user_message(analysis)
    # suggested_scene_count = int(180 / (2.0 * 4)) = 22
    assert "22" in msg


def test_validate_scene_plan_defaults_lyrics_in_scene():
    """_validate_scene_plan adds lyrics_in_scene=[] when field is absent."""
    from musicvid.pipeline.director import _validate_scene_plan

    plan = {
        "overall_style": "worship",
        "master_style": "",
        "color_palette": [],
        "subtitle_style": {},
        "scenes": [
            {"start": 0.0, "end": 10.0, "visual_prompt": "test", "animate": False, "motion_prompt": ""},
        ],
    }
    validated = _validate_scene_plan(plan, 10.0)
    assert validated["scenes"][0]["lyrics_in_scene"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_director.py::test_build_user_message_includes_bpm_guidance tests/test_director.py::test_build_user_message_scene_count_based_on_bpm tests/test_director.py::test_validate_scene_plan_defaults_lyrics_in_scene -v
```

Expected: all 3 FAIL

- [ ] **Step 3: Implement BPM-aware _build_user_message in director.py**

Replace `_build_user_message` in `musicvid/pipeline/director.py`:

```python
def _build_user_message(analysis, style_override=None):
    """Build the user message for Claude with analysis data."""
    duration = analysis.get("duration", 0)
    bpm = analysis.get("bpm", 120.0)
    beats = analysis.get("beats", [])

    bar_duration = 4 * (60.0 / bpm)
    suggested_scene_count = max(4, int(duration / (bar_duration * 4)))

    # Downbeats: every 4th beat starting from index 0
    downbeats = beats[::4] if beats else []
    downbeats_preview = [round(d, 2) for d in downbeats[:20]]

    msg = f"Here is the audio analysis for the music video:\n\n{json.dumps(analysis, indent=2)}"
    msg += f"\n\nBPM: {bpm:.0f}"
    msg += f"\nBar duration (4 beats): {bar_duration:.2f}s"
    msg += f"\nOptimal scene duration (4 bars): {bar_duration * 4:.2f}s"
    msg += f"\nSuggested scene count for this song: {suggested_scene_count}"
    msg += f"\nDownbeats (every 4th beat, first 20): {downbeats_preview}"
    msg += f"\n\nSCENE LENGTH RULES:"
    msg += f"\n- Minimum scene: 2 bars = {bar_duration * 2:.2f}s"
    msg += f"\n- Optimal scene: 4 bars = {bar_duration * 4:.2f}s"
    msg += f"\n- Maximum scene: 8 bars = {bar_duration * 8:.2f}s"
    msg += f"\n- Target: {suggested_scene_count} scenes of ~{bar_duration * 4:.1f}s each"
    msg += f"\n- Each scene start/end should align with a downbeat from the list above"
    msg += f"\n\nGenerate approximately {suggested_scene_count} scenes (maximum {suggested_scene_count + 4})."
    if style_override and style_override != "auto":
        msg += f"\n\nIMPORTANT: Override the style to be '{style_override}' regardless of the mood detected in the audio."
    return msg
```

- [ ] **Step 4: Default lyrics_in_scene in _validate_scene_plan**

In `_validate_scene_plan`, in the loop over scenes, add after `motion_prompt` defaulting:

```python
        if "lyrics_in_scene" not in scene:
            scene["lyrics_in_scene"] = []
```

Full updated loop in `_validate_scene_plan`:

```python
    for scene in plan["scenes"]:
        if "animate" not in scene:
            scene["animate"] = False
        if "motion_prompt" not in scene:
            scene["motion_prompt"] = ""
        if "lyrics_in_scene" not in scene:
            scene["lyrics_in_scene"] = []
```

- [ ] **Step 5: Add lyrics_in_scene to director_system.txt JSON schema**

In `musicvid/prompts/director_system.txt`, find the scenes array in OUTPUT FORMAT and add
`lyrics_in_scene` field. The scene object should become:

```json
    {
      "section": "intro|verse|chorus|bridge|outro",
      "start": 0.0,
      "end": 15.0,
      "lyrics_in_scene": ["line 1 of lyrics that appear in this scene", "line 2"],
      "visual_prompt": "Detailed positive description following the rules above (min 3 sentences + technical suffix)",
      "motion": "slow_zoom_in|slow_zoom_out|pan_left|pan_right|static",
      "transition": "crossfade|cut|fade_black",
      "overlay": "none|particles|light_rays|bokeh",
      "animate": false,
      "motion_prompt": ""
    }
```

Also add after CONTEXT-AWARE VISUAL PROMPTS section:

```
For each scene, you MUST populate "lyrics_in_scene" with the lyrics lines that fall within
[start, end] seconds. This forces you to identify the exact words before writing the visual_prompt.
The visual_prompt must illustrate those specific words — not generic landscape filler.
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_director.py::test_build_user_message_includes_bpm_guidance tests/test_director.py::test_build_user_message_scene_count_based_on_bpm tests/test_director.py::test_validate_scene_plan_defaults_lyrics_in_scene -v
```

Expected: all 3 PASS

- [ ] **Step 7: Run full director tests for regressions**

```bash
python3 -m pytest tests/test_director.py -v
```

Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add musicvid/pipeline/director.py musicvid/prompts/director_system.txt tests/test_director.py
git commit -m "feat: BPM-aware scene count and lyrics_in_scene field in director"
```

---

## Task 3: Downbeat-Based Beat Snapping

**Files:**
- Modify: `musicvid/musicvid.py:154-174` (replace `_snap_to_nearest_beat`, update `_apply_beat_sync`)
- Test: `tests/test_cli.py`

Context: `_apply_beat_sync` currently snaps scene boundaries to the globally nearest beat.
The spec requires snapping to **downbeats** (every 4th beat) within a ±0.5s window.
If no downbeat is within 0.5s, the boundary stays unchanged.
We add `_compute_downbeats(beats)` and `_snap_to_downbeat(t, downbeats, window=0.5)` helpers,
then update `_apply_beat_sync` to use them.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_cli.py` (or a new `tests/test_beat_sync.py`):

```python
def test_snap_to_downbeat_within_window():
    """Snaps to closest downbeat when within 0.5s window."""
    from musicvid.musicvid import _snap_to_downbeat
    downbeats = [0.0, 2.86, 5.71, 8.57]
    # t=2.9 is 0.04s from 2.86 — within window
    assert abs(_snap_to_downbeat(2.9, downbeats) - 2.86) < 0.01


def test_snap_to_downbeat_outside_window():
    """Returns t unchanged when no downbeat is within 0.5s."""
    from musicvid.musicvid import _snap_to_downbeat
    downbeats = [0.0, 2.86, 5.71]
    # t=4.0 is 1.14s from 2.86 and 1.71s from 5.71 — both outside window
    assert _snap_to_downbeat(4.0, downbeats) == 4.0


def test_compute_downbeats_every_4th():
    """Returns every 4th beat starting at index 0."""
    from musicvid.musicvid import _compute_downbeats
    beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    assert _compute_downbeats(beats) == [0.0, 2.0, 4.0]


def test_apply_beat_sync_uses_downbeats():
    """_apply_beat_sync snaps boundaries to downbeats, not all beats."""
    from musicvid.musicvid import _apply_beat_sync
    # Beats at every 0.5s; downbeats at 0, 2.0, 4.0, 6.0, ...
    beats = [i * 0.5 for i in range(20)]
    scene_plan = {
        "scenes": [
            {"start": 0.0, "end": 4.1},   # 4.1 → should snap to downbeat 4.0
            {"start": 4.1, "end": 8.0},
        ]
    }
    result = _apply_beat_sync(scene_plan, beats)
    assert result["scenes"][0]["end"] == pytest.approx(4.0, abs=0.01)
    assert result["scenes"][1]["start"] == pytest.approx(4.0, abs=0.01)


def test_apply_beat_sync_no_snap_outside_window():
    """Boundary outside ±0.5s of any downbeat is not snapped."""
    from musicvid.musicvid import _apply_beat_sync
    beats = [i * 0.5 for i in range(20)]  # downbeats at 0, 2.0, 4.0, 6.0...
    scene_plan = {
        "scenes": [
            {"start": 0.0, "end": 3.2},   # 3.2 is 0.8s from downbeat 4.0 → no snap
            {"start": 3.2, "end": 8.0},
        ]
    }
    result = _apply_beat_sync(scene_plan, beats)
    assert result["scenes"][0]["end"] == pytest.approx(3.2, abs=0.01)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::test_snap_to_downbeat_within_window tests/test_cli.py::test_snap_to_downbeat_outside_window tests/test_cli.py::test_compute_downbeats_every_4th tests/test_cli.py::test_apply_beat_sync_uses_downbeats tests/test_cli.py::test_apply_beat_sync_no_snap_outside_window -v
```

Expected: all FAIL (`_snap_to_downbeat` and `_compute_downbeats` don't exist yet)

- [ ] **Step 3: Implement helpers and update _apply_beat_sync in musicvid.py**

In `musicvid/musicvid.py`, replace the existing `_snap_to_nearest_beat` and `_apply_beat_sync`
functions (around lines 154-174):

```python
def _compute_downbeats(beats):
    """Return every 4th beat (downbeat) from the beats list."""
    return beats[::4]


def _snap_to_downbeat(t, downbeats, window=0.5):
    """Snap t to the nearest downbeat within window seconds; return t unchanged if none qualifies."""
    candidates = [d for d in downbeats if abs(d - t) <= window]
    if not candidates:
        return t
    return min(candidates, key=lambda d: abs(d - t))


def _snap_to_nearest_beat(t, beats):
    """Return the beat timestamp closest to t (kept for backward compat)."""
    if not beats:
        return t
    return min(beats, key=lambda b: abs(b - t))


def _apply_beat_sync(scene_plan, beats):
    """Snap interior scene boundaries to nearest downbeat within ±0.5s.

    First scene start stays 0.0; last scene end stays as-is.
    Adjacent scenes share the same snapped boundary (no gaps).
    Falls back to unsnapped boundary if no downbeat is within 0.5s.
    """
    scenes = scene_plan["scenes"]
    if not scenes or not beats:
        return scene_plan
    downbeats = _compute_downbeats(beats)
    for i in range(len(scenes) - 1):
        snapped = _snap_to_downbeat(scenes[i]["end"], downbeats)
        scenes[i]["end"] = snapped
        scenes[i + 1]["start"] = snapped
    return scene_plan
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::test_snap_to_downbeat_within_window tests/test_cli.py::test_snap_to_downbeat_outside_window tests/test_cli.py::test_compute_downbeats_every_4th tests/test_cli.py::test_apply_beat_sync_uses_downbeats tests/test_cli.py::test_apply_beat_sync_no_snap_outside_window -v
```

Expected: all PASS

- [ ] **Step 5: Run full test suite for regressions**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all existing tests pass

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: snap scene boundaries to downbeats (every 4th beat) within ±0.5s window"
```

---

## Spec Coverage Check

| Spec requirement | Task |
|-----------------|------|
| --new clears all cache files | Already implemented via `shutil.rmtree(cache_dir)` — no change needed |
| Subtitles 0.1s before word | Task 1 |
| Pass BPM/bar_duration/downbeats to director | Task 2 |
| Suggested scene count from BPM | Task 2 |
| lyrics_in_scene field per scene | Task 2 |
| Visual prompt references lyrics | Task 2 (system prompt update) |
| snap_to_downbeat within ±0.5s | Task 3 |
| Scenes 8-15s long | Task 2 (director prompt guidance) |
| All tests pass | Each task runs full test suite |
