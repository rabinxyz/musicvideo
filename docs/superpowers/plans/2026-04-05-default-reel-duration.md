# Default Reel Duration Change Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change default `--reel-duration` from 15s to 30s, add 45s/60s options, update social clip selector prompt to prioritize chorus fragments for 30s+ clips, and update the startup summary.

**Architecture:** Two files change: `musicvid/musicvid.py` for CLI option and startup summary, `musicvid/pipeline/social_clip_selector.py` for the Claude prompt. Test changes update hardcoded expected defaults and add coverage for new choices.

**Tech Stack:** Python 3.11+, Click CLI, Anthropic Claude API (social_clip_selector), pytest/unittest

---

### Task 1: Change `--reel-duration` CLI option — choices and default

**Files:**
- Modify: `musicvid/musicvid.py:296`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test — new choices (45, 60) accepted**

```python
# In tests/test_cli.py, inside TestPresetSocialReels (around line 1584)
def test_reel_duration_45_accepted(self, runner, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    result = runner.invoke(cli, [str(audio_file), "--reel-duration", "45", "--help"])
    assert result.exit_code == 0

def test_reel_duration_60_accepted(self, runner, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    result = runner.invoke(cli, [str(audio_file), "--reel-duration", "60", "--help"])
    assert result.exit_code == 0

def test_reel_duration_default_is_30(self, runner, tmp_path):
    """Verify --help output shows default=30."""
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    result = runner.invoke(cli, [str(audio_file), "--help"])
    assert result.exit_code == 0
    assert "default=30" in result.output or "[default: 30]" in result.output or "default: 30" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_cli.py::TestPresetSocialReels::test_reel_duration_45_accepted tests/test_cli.py::TestPresetSocialReels::test_reel_duration_60_accepted tests/test_cli.py::TestPresetSocialReels::test_reel_duration_default_is_30 -v
```

Expected: FAIL — choices `["15","20","30"]` doesn't include 45/60; default is "15" not "30"

- [ ] **Step 3: Update `--reel-duration` option in `musicvid/musicvid.py`**

Find line 296 (the `@click.option("--reel-duration", ...)` decorator) and change it to:

```python
@click.option("--reel-duration", type=click.Choice(["15", "20", "25", "30", "45", "60"]), default="30", help="Duration of social media reels in seconds.")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestPresetSocialReels::test_reel_duration_45_accepted tests/test_cli.py::TestPresetSocialReels::test_reel_duration_60_accepted tests/test_cli.py::TestPresetSocialReels::test_reel_duration_default_is_30 -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python3 -m pytest tests/test_cli.py -v --tb=short 2>&1 | tail -30
```

Expected: Previously passing tests still pass. If any test asserts `reel_duration == 15` as a default from CLI invocation without explicit `--reel-duration` flag, it must be updated to `30`.

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: change --reel-duration default to 30s, add 45s/60s choices"
```

---

### Task 2: Update `_print_startup_summary` to show reel duration

**Files:**
- Modify: `musicvid/musicvid.py:256-276`
- Test: `tests/test_cli.py`

The startup summary currently doesn't display `reel_duration`. The spec requires:
`"Rolki social:   3 × 30s z różnych fragmentów"` when preset includes social reels.

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_cli.py — add to TestStartupSummary class or near test_startup_summary_shown
@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_startup_summary_shows_reel_duration(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0], "bpm": 120.0, "duration": 60.0,
        "sections": [{"label": "verse", "start": 0.0, "end": 60.0}],
        "mood_energy": "contemplative", "language": "en",
    }
    mock_direct.return_value = {
        "overall_style": "contemplative", "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "fade"},
        "scenes": [{"section": "verse", "start": 0.0, "end": 60.0,
                    "visual_prompt": "t", "motion": "static", "transition": "cut",
                    "overlay": "none", "animate": False, "motion_prompt": ""}],
    }
    mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"}]
    result = runner.invoke(cli, [
        str(audio_file), "--preset", "full", "--mode", "stock",
        "--reel-duration", "30",
    ])
    assert result.exit_code == 0, result.output
    assert "30s" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_cli.py -k "test_startup_summary_shows_reel_duration" -v
```

Expected: FAIL — "30s" not found in output

- [ ] **Step 3: Update `_print_startup_summary` in `musicvid/musicvid.py`**

Find `_print_startup_summary` (lines 256–276). Add a line that shows reel duration when preset includes social:

```python
def _print_startup_summary(mode, provider, preset, effects, animate_mode, lut_style,
                            lut_intensity, subtitle_style_override, transitions_mode,
                            beat_sync, reel_duration):
    """Print a human-readable summary of the active generation settings."""
    images_desc = f"BFL {provider.upper()} (AI)" if mode == "ai" else "Pexels (stock)"
    animate_desc = "Runway Gen-4 (auto)" if animate_mode == "auto" else (
        "Runway Gen-4 (wszystkie)" if animate_mode == "always" else "wyłączone (Ken Burns)"
    )
    preset_desc = {"full": "Pełny teledysk", "social": "3 rolki", "all": "Pełny teledysk + 3 rolki"}.get(preset or "full", preset)
    lut_desc = f"LUT {lut_style} (intensity {lut_intensity})" if lut_style else "brak"
    click.echo("  MusicVid — tryb pełny")
    click.echo("  " + "━" * 38)
    click.echo(f"  Obrazy:      {images_desc}")
    click.echo(f"  Animacje:    {animate_desc}")
    click.echo(f"  Preset:      {preset_desc}")
    if preset in ("social", "all"):
        click.echo(f"  Rolki social:   3 × {reel_duration}s z różnych fragmentów")
    click.echo(f"  Efekty:      {effects}")
    click.echo(f"  Napisy:      {subtitle_style_override} style")
    click.echo(f"  Przejścia:   {transitions_mode}")
    click.echo(f"  Color grade: {lut_desc}")
    click.echo(f"  Beat sync:   {beat_sync}")
    click.echo("  " + "━" * 38)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_cli.py -k "test_startup_summary_shows_reel_duration" -v
```

Expected: PASS

- [ ] **Step 5: Run existing startup summary tests to check for regressions**

```bash
python3 -m pytest tests/test_cli.py -k "startup_summary" -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: show reel duration in startup summary for social/all presets"
```

---

### Task 3: Update social clip selector prompt for 30s+ durations

**Files:**
- Modify: `musicvid/pipeline/social_clip_selector.py:26-47`
- Test: `tests/test_social_clip_selector.py` (or wherever social clip selector tests live)

For clips ≥ 30s, the Claude prompt should prioritize: full refrain/chorus, clear melodic hook, complete thought (no mid-sentence cuts), phrase-aligned start/end.

- [ ] **Step 1: Locate existing tests for `select_social_clips`**

```bash
grep -n "select_social_clips\|social_clip_selector" /Users/s.rzytki/Documents/aiprojects/musicvideo/tests/*.py | head -20
```

- [ ] **Step 2: Write the failing test — 30s prompt includes chorus/refrain priority**

Find the test file for `social_clip_selector` (likely `tests/test_social_clip_selector.py` or `tests/test_pipeline.py`). Add:

```python
from unittest.mock import patch, MagicMock
from musicvid.pipeline.social_clip_selector import select_social_clips

@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_30s_prompt_mentions_chorus_priority(mock_anthropic):
    """For 30s clips the prompt should mention chorus/refrain as priority."""
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"clips": [{"id": "A", "start": 10.0, "end": 40.0, "section": "chorus", "reason": "test"}, {"id": "B", "start": 60.0, "end": 90.0, "section": "verse", "reason": "test"}, {"id": "C", "start": 120.0, "end": 150.0, "section": "bridge", "reason": "test"}]}')]
    mock_client.messages.create.return_value = mock_response

    analysis = {
        "lyrics": [{"start": 0.0, "end": 30.0, "text": "test lyric"}],
        "sections": [{"label": "chorus", "start": 0.0, "end": 30.0}],
        "duration": 180.0,
        "bpm": 120,
    }
    select_social_clips(analysis, 30)

    call_args = mock_client.messages.create.call_args
    user_message = call_args[1]["messages"][0]["content"]
    assert "refren" in user_message.lower() or "chorus" in user_message.lower()
    assert "pełny" in user_message.lower() or "full" in user_message.lower() or "complete" in user_message.lower()

@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_15s_prompt_does_not_add_chorus_rules(mock_anthropic):
    """For 15s clips the shorter rules apply (no chorus-priority block)."""
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"clips": [{"id": "A", "start": 10.0, "end": 25.0, "section": "verse", "reason": "test"}, {"id": "B", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "test"}, {"id": "C", "start": 120.0, "end": 135.0, "section": "bridge", "reason": "test"}]}')]
    mock_client.messages.create.return_value = mock_response

    analysis = {
        "lyrics": [{"start": 0.0, "end": 15.0, "text": "test lyric"}],
        "sections": [{"label": "verse", "start": 0.0, "end": 15.0}],
        "duration": 180.0,
        "bpm": 120,
    }
    select_social_clips(analysis, 15)

    call_args = mock_client.messages.create.call_args
    user_message = call_args[1]["messages"][0]["content"]
    # 15s prompt should NOT have the extended chorus-priority rules block
    assert "Pełny refren (priorytet najwyższy)" not in user_message
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python3 -m pytest tests/ -k "test_30s_prompt_mentions_chorus_priority or test_15s_prompt_does_not_add_chorus_rules" -v
```

Expected: FAIL (rule text not in prompt yet)

- [ ] **Step 4: Update `select_social_clips` in `social_clip_selector.py`**

Add conditional rules block for 30s+ durations in the `user_message` construction:

```python
def select_social_clips(analysis, clip_duration):
    """Ask Claude to select 3 non-overlapping clips from different song sections.

    Args:
        analysis: Audio analysis dict (lyrics, sections, duration, bpm).
        clip_duration: Desired clip duration in seconds (15, 20, 25, 30, 45, or 60).

    Returns:
        dict with key "clips": list of 3 dicts, each with id, start, end, section, reason.
    """
    client = anthropic.Anthropic()

    segments = [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
        for seg in analysis.get("lyrics", [])
    ]
    sections = analysis.get("sections", [])
    duration = analysis.get("duration", 0)

    long_clip_rules = ""
    if clip_duration >= 30:
        long_clip_rules = (
            f"- Pełny refren (priorytet najwyższy) — prefer a complete chorus if available\n"
            f"- Wyraźny hook melodyczny — include the main melodic hook\n"
            f"- Kompletną myśl tekstową — no mid-sentence cuts, full lyrical thought\n"
            f"- Zaczyna się na początku frazy muzycznej — start at a musical phrase boundary\n"
            f"- Kończy na naturalnej pauzie lub końcu frazy — end at a natural pause or phrase end\n"
        )

    user_message = (
        f"You are selecting 3 clips of {clip_duration} seconds each from a song for social media "
        f"(Instagram Reels, YouTube Shorts, TikTok).\n\n"
        f"Song duration: {duration:.1f}s\n"
        f"BPM: {analysis.get('bpm', 'unknown')}\n"
        f"Sections: {json.dumps(sections)}\n"
        f"Lyrics with timestamps:\n{json.dumps(segments, indent=2)}\n\n"
        f"Rules:\n"
        f"- Select exactly 3 clips, each {clip_duration}s long (end - start = {clip_duration} ±2s)\n"
        f"- Clips must NOT overlap and must have at least 5s gap between them\n"
        f"- Each clip must come from a DIFFERENT section (intro/verse/chorus/bridge/outro)\n"
        f"- Prefer fragments with strong lyrics and clear melody\n"
        f"- Each clip must start at the beginning of a phrase — not mid-word\n"
        f"- Each clip must end at the end of a lyric line\n"
        f"{long_clip_rules}"
        f"- Describe briefly why you chose each fragment\n\n"
        f"Return ONLY valid JSON (no markdown, no explanation):\n"
        f'{{"clips": [\n'
        f'  {{"id": "A", "start": <float>, "end": <float>, "section": "<section>", "reason": "<brief>"}},\n'
        f'  {{"id": "B", "start": <float>, "end": <float>, "section": "<section>", "reason": "<brief>"}},\n'
        f'  {{"id": "C", "start": <float>, "end": <float>, "section": "<section>", "reason": "<brief>"}}\n'
        f"]}}"
    )

    for _attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": user_message}],
            )
            result = json.loads(response.content[0].text.strip())
            if "clips" in result and len(result["clips"]) == 3:
                valid = all(
                    "start" in c and "end" in c and "id" in c
                    for c in result["clips"]
                )
                if valid:
                    return result
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

    # Fallback: 3 evenly spaced clips from the song
    spacing = duration / 4
    clips = []
    for i, clip_id in enumerate(["A", "B", "C"]):
        start = spacing * (i + 0.5)
        clips.append({
            "id": clip_id,
            "start": round(start, 1),
            "end": round(start + clip_duration, 1),
            "section": "unknown",
            "reason": "Fallback: evenly spaced",
        })
    return {"clips": clips}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/ -k "test_30s_prompt_mentions_chorus_priority or test_15s_prompt_does_not_add_chorus_rules" -v
```

Expected: PASS

- [ ] **Step 6: Run full test suite**

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All passing (322+)

- [ ] **Step 7: Commit**

```bash
git add musicvid/pipeline/social_clip_selector.py tests/
git commit -m "feat: add chorus/refrain priority rules in social clip selector for 30s+ reels"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ `--reel-duration` default changed from 15 → 30 (Task 1)
- ✅ New choices 45, 60 added (Task 1)
- ✅ Available options: 15, 20, 25, 30, 45, 60 (Task 1)
- ✅ Startup message shows correct reel duration (Task 2)
- ✅ Clip selection logic for 30s prioritizes full refrain/chorus (Task 3)
- ✅ `--help` shows `default=30` (Task 1 test covers this)

**Acceptance Criteria mapping:**
- `python3 -m musicvid.musicvid --help` shows default 30 → Task 1
- Generated reels ~30s → no code change needed (duration is passed through existing logic)
- Available options: 15, 20, 25, 30, 45, 60 → Task 1
- Startup summary shows correct duration → Task 2

**Placeholder scan:** No TBD/TODO/placeholders — all steps have complete code.

**Type consistency:** `reel_duration` is always `int` when passed to `_run_preset_mode` (CLI converts string choice via `int(reel_duration)` at line 548). `select_social_clips(analysis, clip_duration)` receives int. Consistent throughout.
