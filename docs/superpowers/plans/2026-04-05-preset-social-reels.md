# Preset Mode: Full + Social Reels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--preset [full|social|all]` flag that generates a full YouTube video and/or 3 social media reels (9:16) from different song fragments in a single run, sharing stages 1-3.

**Architecture:** New `select_social_clips()` function asks Claude to pick 3 non-overlapping clips from different sections. New helpers filter the shared scene plan and manifest to each clip window. Assembler gains social-mode parameters (subtitle margin, fade durations, no cinematic bars). CLI orchestrates stage 4 in a loop.

**Tech Stack:** Python 3.11+, Click CLI, MoviePy 2.x, Claude API (anthropic), PIL/Pillow for smart crop blur

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `musicvid/pipeline/social_clip_selector.py` | Create | `select_social_clips()` — asks Claude for 3 non-overlapping clips |
| `tests/test_social_clip_selector.py` | Create | Tests for social clip selection |
| `musicvid/musicvid.py` | Modify | `--preset`, `--reel-duration` flags, stage 4 loop, output folders |
| `musicvid/pipeline/assembler.py` | Modify | `subtitle_margin_bottom`, `audio_fade_out`, social-mode params, portrait smart crop, Ken Burns portrait restriction |
| `tests/test_assembler.py` | Modify | Tests for social-mode assembler params and portrait smart crop |
| `tests/test_cli.py` | Modify | Tests for `--preset` and `--reel-duration` CLI flags |

---

### Task 1: Social Clip Selector

**Files:**
- Create: `musicvid/pipeline/social_clip_selector.py`
- Create: `tests/test_social_clip_selector.py`

- [ ] **Step 1: Write the failing test — returns 3 clips with required fields**

```python
# tests/test_social_clip_selector.py
"""Tests for social_clip_selector module."""
import json
from unittest.mock import patch, MagicMock

import pytest

from musicvid.pipeline.social_clip_selector import select_social_clips


def _make_analysis(duration=180.0):
    return {
        "duration": duration,
        "bpm": 120,
        "sections": [
            {"label": "intro", "start": 0.0, "end": 20.0},
            {"label": "verse", "start": 20.0, "end": 60.0},
            {"label": "chorus", "start": 60.0, "end": 90.0},
            {"label": "bridge", "start": 90.0, "end": 120.0},
            {"label": "outro", "start": 120.0, "end": 180.0},
        ],
        "lyrics": [
            {"start": 20.0, "end": 24.0, "text": "First verse line"},
            {"start": 60.0, "end": 64.0, "text": "Chorus line one"},
            {"start": 90.0, "end": 94.0, "text": "Bridge moment"},
        ],
    }


def _mock_claude_response(clips):
    """Helper to create a mock Claude API response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({"clips": clips}))]
    return mock_response


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_returns_three_clips_with_required_fields(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    clips = [
        {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Best hook"},
        {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Opening"},
        {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Emotional peak"},
    ]
    mock_client.messages.create.return_value = _mock_claude_response(clips)

    result = select_social_clips(_make_analysis(), 15)

    assert len(result["clips"]) == 3
    for clip in result["clips"]:
        assert "id" in clip
        assert "start" in clip
        assert "end" in clip
        assert "section" in clip
        assert "reason" in clip
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_social_clip_selector.py::test_returns_three_clips_with_required_fields -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'musicvid.pipeline.social_clip_selector'"

- [ ] **Step 3: Write minimal implementation**

```python
# musicvid/pipeline/social_clip_selector.py
"""Select 3 non-overlapping clips from different song sections for social media reels."""
import json

import anthropic


def select_social_clips(analysis, clip_duration):
    """Ask Claude to select 3 non-overlapping clips from different song sections.

    Args:
        analysis: Audio analysis dict (lyrics, sections, duration, bpm).
        clip_duration: Desired clip duration in seconds (15, 20, or 30).

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

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_social_clip_selector.py::test_returns_three_clips_with_required_fields -v`
Expected: PASS

- [ ] **Step 5: Write additional tests — retry, prompt content, fallback**

Add to `tests/test_social_clip_selector.py`:

```python
@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_retries_on_invalid_json(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    invalid_response = MagicMock()
    invalid_response.content = [MagicMock(text="not valid json")]
    valid_clips = [
        {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
        {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Verse"},
        {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Bridge"},
    ]
    valid_response = _mock_claude_response(valid_clips)
    mock_client.messages.create.side_effect = [invalid_response, valid_response]

    result = select_social_clips(_make_analysis(), 15)

    assert mock_client.messages.create.call_count == 2
    assert len(result["clips"]) == 3


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_passes_clip_duration_in_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    clips = [
        {"id": "A", "start": 60.0, "end": 90.0, "section": "chorus", "reason": "Hook"},
        {"id": "B", "start": 20.0, "end": 50.0, "section": "verse", "reason": "Verse"},
        {"id": "C", "start": 90.0, "end": 120.0, "section": "bridge", "reason": "Bridge"},
    ]
    mock_client.messages.create.return_value = _mock_claude_response(clips)

    select_social_clips(_make_analysis(), 30)

    call_kwargs = mock_client.messages.create.call_args[1]
    user_content = call_kwargs["messages"][0]["content"]
    assert "30 seconds" in user_content


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_fallback_on_all_attempts_fail(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="bad json")]
    mock_client.messages.create.return_value = mock_response

    result = select_social_clips(_make_analysis(duration=180.0), 15)

    assert len(result["clips"]) == 3
    # Fallback clips should be evenly spaced and non-overlapping
    starts = sorted(c["start"] for c in result["clips"])
    for i in range(len(starts) - 1):
        end_i = starts[i] + 15
        assert starts[i + 1] >= end_i  # no overlap


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_rejects_response_with_wrong_clip_count(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    # First response: only 2 clips (wrong)
    two_clips_response = MagicMock()
    two_clips_response.content = [MagicMock(text=json.dumps({"clips": [
        {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
        {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Verse"},
    ]}))]

    # Second response: 3 clips (correct)
    valid_clips = [
        {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
        {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Verse"},
        {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Bridge"},
    ]
    mock_client.messages.create.side_effect = [two_clips_response, _mock_claude_response(valid_clips)]

    result = select_social_clips(_make_analysis(), 15)

    assert mock_client.messages.create.call_count == 2
    assert len(result["clips"]) == 3
```

- [ ] **Step 6: Run all social clip selector tests**

Run: `python3 -m pytest tests/test_social_clip_selector.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add musicvid/pipeline/social_clip_selector.py tests/test_social_clip_selector.py
git commit -m "feat: add select_social_clips for 3-clip social media selection"
```

---

### Task 2: Scene Plan and Manifest Filtering for Clip Windows

**Files:**
- Modify: `musicvid/musicvid.py` (add `_filter_scene_plan_to_clip`, `_filter_manifest_to_clip`)
- Modify: `tests/test_cli.py` (add filter tests)

- [ ] **Step 1: Write the failing test — scene plan filtering**

Add to `tests/test_cli.py`:

```python
class TestFilterScenePlanToClip:
    """Tests for _filter_scene_plan_to_clip helper."""

    def test_returns_only_overlapping_scenes(self):
        from musicvid.musicvid import _filter_scene_plan_to_clip

        scene_plan = {
            "overall_style": "contemplative",
            "master_style": "warm tones",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48},
            "scenes": [
                {"section": "intro", "start": 0.0, "end": 15.0, "visual_prompt": "sunrise",
                 "motion": "slow_zoom_in", "transition": "cut", "overlay": "none"},
                {"section": "verse", "start": 15.0, "end": 45.0, "visual_prompt": "lake",
                 "motion": "pan_left", "transition": "crossfade", "overlay": "none"},
                {"section": "chorus", "start": 45.0, "end": 75.0, "visual_prompt": "mountain",
                 "motion": "slow_zoom_out", "transition": "cut", "overlay": "none"},
                {"section": "outro", "start": 75.0, "end": 100.0, "visual_prompt": "sunset",
                 "motion": "static", "transition": "fade_black", "overlay": "none"},
            ],
        }

        result = _filter_scene_plan_to_clip(scene_plan, 45.0, 60.0)

        # Only the chorus scene overlaps [45, 60]
        assert len(result["scenes"]) == 1
        assert result["scenes"][0]["section"] == "chorus"

    def test_offsets_scene_times_to_zero(self):
        from musicvid.musicvid import _filter_scene_plan_to_clip

        scene_plan = {
            "overall_style": "contemplative",
            "master_style": "",
            "color_palette": [],
            "subtitle_style": {},
            "scenes": [
                {"section": "chorus", "start": 45.0, "end": 75.0, "visual_prompt": "mountain",
                 "motion": "slow_zoom_out", "transition": "cut", "overlay": "none"},
            ],
        }

        result = _filter_scene_plan_to_clip(scene_plan, 45.0, 60.0)

        assert result["scenes"][0]["start"] == 0.0
        assert result["scenes"][0]["end"] == 15.0

    def test_trims_partially_overlapping_scenes(self):
        from musicvid.musicvid import _filter_scene_plan_to_clip

        scene_plan = {
            "overall_style": "contemplative",
            "master_style": "",
            "color_palette": [],
            "subtitle_style": {},
            "scenes": [
                {"section": "verse", "start": 10.0, "end": 30.0, "visual_prompt": "lake",
                 "motion": "pan_left", "transition": "cut", "overlay": "none"},
                {"section": "chorus", "start": 30.0, "end": 50.0, "visual_prompt": "mountain",
                 "motion": "slow_zoom_out", "transition": "cut", "overlay": "none"},
            ],
        }

        # Clip window [25, 40] overlaps both scenes
        result = _filter_scene_plan_to_clip(scene_plan, 25.0, 40.0)

        assert len(result["scenes"]) == 2
        # Verse: [10,30] clipped to [25,30] → offset → [0, 5]
        assert result["scenes"][0]["start"] == 0.0
        assert result["scenes"][0]["end"] == 5.0
        # Chorus: [30,50] clipped to [30,40] → offset → [5, 10]
        assert result["scenes"][1]["start"] == 5.0
        assert result["scenes"][1]["end"] == 10.0

    def test_preserves_non_scene_fields(self):
        from musicvid.musicvid import _filter_scene_plan_to_clip

        scene_plan = {
            "overall_style": "joyful",
            "master_style": "golden tones",
            "color_palette": ["#fff"],
            "subtitle_style": {"font_size": 48},
            "scenes": [
                {"section": "chorus", "start": 0.0, "end": 30.0, "visual_prompt": "test",
                 "motion": "static", "transition": "cut", "overlay": "none"},
            ],
        }

        result = _filter_scene_plan_to_clip(scene_plan, 0.0, 15.0)

        assert result["overall_style"] == "joyful"
        assert result["master_style"] == "golden tones"
        assert result["color_palette"] == ["#fff"]
        assert result["subtitle_style"] == {"font_size": 48}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py::TestFilterScenePlanToClip -v`
Expected: FAIL with "cannot import name '_filter_scene_plan_to_clip'"

- [ ] **Step 3: Implement `_filter_scene_plan_to_clip`**

Add to `musicvid/musicvid.py` after the existing `_filter_analysis_to_clip` function (after line 71):

```python
def _filter_scene_plan_to_clip(scene_plan, clip_start, clip_end):
    """Return a copy of scene_plan with scenes filtered and offset to the clip window.

    Scenes that don't overlap [clip_start, clip_end] are dropped.
    Overlapping scenes are trimmed to the window and offset so clip_start → t=0.
    """
    filtered_scenes = []
    for scene in scene_plan["scenes"]:
        if scene["end"] <= clip_start or scene["start"] >= clip_end:
            continue
        trimmed = {
            **scene,
            "start": max(0.0, scene["start"] - clip_start),
            "end": min(clip_end - clip_start, scene["end"] - clip_start),
        }
        filtered_scenes.append(trimmed)

    return {**scene_plan, "scenes": filtered_scenes}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py::TestFilterScenePlanToClip -v`
Expected: All PASS

- [ ] **Step 5: Write the failing test — manifest filtering**

Add to `tests/test_cli.py`:

```python
class TestFilterManifestToClip:
    """Tests for _filter_manifest_to_clip helper."""

    def test_returns_only_matching_entries(self):
        from musicvid.musicvid import _filter_manifest_to_clip

        scenes = [
            {"section": "intro", "start": 0.0, "end": 15.0},
            {"section": "verse", "start": 15.0, "end": 45.0},
            {"section": "chorus", "start": 45.0, "end": 75.0},
        ]
        manifest = [
            {"scene_index": 0, "video_path": "/a.jpg", "search_query": "intro"},
            {"scene_index": 1, "video_path": "/b.jpg", "search_query": "verse"},
            {"scene_index": 2, "video_path": "/c.jpg", "search_query": "chorus"},
        ]

        result = _filter_manifest_to_clip(manifest, scenes, 45.0, 60.0)

        assert len(result) == 1
        assert result[0]["video_path"] == "/c.jpg"

    def test_reindexes_scene_indices(self):
        from musicvid.musicvid import _filter_manifest_to_clip

        scenes = [
            {"section": "verse", "start": 15.0, "end": 45.0},
            {"section": "chorus", "start": 45.0, "end": 75.0},
        ]
        manifest = [
            {"scene_index": 0, "video_path": "/a.jpg", "search_query": "verse"},
            {"scene_index": 1, "video_path": "/b.jpg", "search_query": "chorus"},
        ]

        # Clip [40, 55] overlaps both scenes
        result = _filter_manifest_to_clip(manifest, scenes, 40.0, 55.0)

        assert len(result) == 2
        assert result[0]["scene_index"] == 0
        assert result[1]["scene_index"] == 1
```

- [ ] **Step 6: Implement `_filter_manifest_to_clip`**

Add to `musicvid/musicvid.py` after `_filter_scene_plan_to_clip`:

```python
def _filter_manifest_to_clip(manifest, scenes, clip_start, clip_end):
    """Return manifest entries for scenes that overlap the clip window, with reindexed scene_index."""
    overlapping_indices = set()
    for i, scene in enumerate(scenes):
        if scene["end"] > clip_start and scene["start"] < clip_end:
            overlapping_indices.add(i)

    filtered = []
    new_idx = 0
    for entry in manifest:
        if entry["scene_index"] in overlapping_indices:
            filtered.append({**entry, "scene_index": new_idx})
            new_idx += 1

    return filtered
```

- [ ] **Step 7: Run all filter tests**

Run: `python3 -m pytest tests/test_cli.py::TestFilterScenePlanToClip tests/test_cli.py::TestFilterManifestToClip -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add scene plan and manifest filtering for clip windows"
```

---

### Task 3: Assembler Social Mode Parameters

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write the failing test — subtitle margin bottom parameter**

Add to `tests/test_assembler.py`:

```python
class TestSubtitleMarginBottom:
    """Tests for configurable subtitle margin bottom in assembler."""

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_default_margin_is_80(self, mock_vfx, mock_text_clip, mock_effects, mock_bars,
                                   sample_analysis, sample_scene_plan):
        mock_effects.side_effect = lambda clip, level: clip
        mock_bars.return_value = []
        mock_txt = MagicMock()
        mock_text_clip.return_value = mock_txt
        mock_txt.with_duration.return_value = mock_txt
        mock_txt.with_start.return_value = mock_txt
        mock_txt.with_position.return_value = mock_txt
        mock_txt.with_effects.return_value = mock_txt
        mock_vfx.CrossFadeIn.return_value = MagicMock()
        mock_vfx.CrossFadeOut.return_value = MagicMock()

        _create_subtitle_clips = __import__(
            "musicvid.pipeline.assembler", fromlist=["_create_subtitle_clips"]
        )._create_subtitle_clips

        _create_subtitle_clips(
            sample_analysis["lyrics"],
            sample_scene_plan["subtitle_style"],
            (1920, 1080),
        )

        # Default margin_bottom = 80
        pos_call = mock_txt.with_position.call_args[0][0]
        assert pos_call[1] == 1080 - 80 - 48  # height - margin - font_size

    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.vfx")
    def test_custom_margin_200_for_social(self, mock_vfx, mock_text_clip, sample_analysis, sample_scene_plan):
        mock_txt = MagicMock()
        mock_text_clip.return_value = mock_txt
        mock_txt.with_duration.return_value = mock_txt
        mock_txt.with_start.return_value = mock_txt
        mock_txt.with_position.return_value = mock_txt
        mock_txt.with_effects.return_value = mock_txt
        mock_vfx.CrossFadeIn.return_value = MagicMock()
        mock_vfx.CrossFadeOut.return_value = MagicMock()

        from musicvid.pipeline.assembler import _create_subtitle_clips

        _create_subtitle_clips(
            sample_analysis["lyrics"],
            sample_scene_plan["subtitle_style"],
            (1080, 1920),
            subtitle_margin_bottom=200,
        )

        pos_call = mock_txt.with_position.call_args[0][0]
        assert pos_call[1] == 1920 - 200 - 48  # height - 200 - font_size
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assembler.py::TestSubtitleMarginBottom -v`
Expected: FAIL (TypeError: unexpected keyword argument 'subtitle_margin_bottom')

- [ ] **Step 3: Add `subtitle_margin_bottom` parameter to `_create_subtitle_clips`**

Modify `musicvid/pipeline/assembler.py` — change `_create_subtitle_clips` signature from:

```python
def _create_subtitle_clips(lyrics, subtitle_style, size, font_path=None):
```

to:

```python
def _create_subtitle_clips(lyrics, subtitle_style, size, font_path=None, subtitle_margin_bottom=80):
```

And change the line:

```python
    margin_bottom = 80
```

to:

```python
    margin_bottom = subtitle_margin_bottom
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_assembler.py::TestSubtitleMarginBottom -v`
Expected: PASS

- [ ] **Step 5: Write the failing test — configurable audio fade out**

Add to `tests/test_assembler.py`:

```python
class TestSocialFadeDurations:
    """Tests for configurable audio_fade_out in assembler."""

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_default_audio_fade_out_is_1(
        self, mock_img, mock_concat, mock_comp, mock_vfx, mock_afx,
        mock_audio, mock_effects, mock_bars, sample_analysis, sample_scene_plan
    ):
        mock_effects.side_effect = lambda clip, level: clip
        mock_bars.return_value = []
        mock_clip = MagicMock()
        mock_img.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        mock_video = MagicMock()
        mock_video.duration = 10.0
        mock_concat.return_value = mock_video
        mock_comp.return_value = mock_video
        mock_video.with_effects.return_value = mock_video
        mock_video.with_audio.return_value = mock_video
        mock_video.with_duration.return_value = mock_video

        mock_audio_clip = MagicMock()
        mock_audio_clip.duration = 10.0
        mock_audio.return_value = mock_audio_clip
        mock_audio_clip.subclipped.return_value = mock_audio_clip
        mock_audio_clip.with_effects.return_value = mock_audio_clip

        manifest = [{"scene_index": 0, "video_path": "/fake/img.jpg", "search_query": "test"}]

        assemble_video(
            analysis=sample_analysis,
            scene_plan={"scenes": [sample_scene_plan["scenes"][0]], **{k: v for k, v in sample_scene_plan.items() if k != "scenes"}},
            fetch_manifest=manifest,
            audio_path="/fake/audio.mp3",
            output_path="/fake/out.mp4",
            clip_start=0.0,
            clip_end=10.0,
        )

        # Default: AudioFadeOut(1.0)
        mock_afx.AudioFadeOut.assert_called_with(1.0)

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_custom_audio_fade_out_1_5(
        self, mock_img, mock_concat, mock_comp, mock_vfx, mock_afx,
        mock_audio, mock_effects, mock_bars, sample_analysis, sample_scene_plan
    ):
        mock_effects.side_effect = lambda clip, level: clip
        mock_bars.return_value = []
        mock_clip = MagicMock()
        mock_img.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        mock_video = MagicMock()
        mock_video.duration = 10.0
        mock_concat.return_value = mock_video
        mock_comp.return_value = mock_video
        mock_video.with_effects.return_value = mock_video
        mock_video.with_audio.return_value = mock_video
        mock_video.with_duration.return_value = mock_video

        mock_audio_clip = MagicMock()
        mock_audio_clip.duration = 10.0
        mock_audio.return_value = mock_audio_clip
        mock_audio_clip.subclipped.return_value = mock_audio_clip
        mock_audio_clip.with_effects.return_value = mock_audio_clip

        manifest = [{"scene_index": 0, "video_path": "/fake/img.jpg", "search_query": "test"}]

        assemble_video(
            analysis=sample_analysis,
            scene_plan={"scenes": [sample_scene_plan["scenes"][0]], **{k: v for k, v in sample_scene_plan.items() if k != "scenes"}},
            fetch_manifest=manifest,
            audio_path="/fake/audio.mp3",
            output_path="/fake/out.mp4",
            clip_start=0.0,
            clip_end=10.0,
            audio_fade_out=1.5,
        )

        mock_afx.AudioFadeOut.assert_called_with(1.5)
```

- [ ] **Step 6: Add `audio_fade_out` and `subtitle_margin_bottom` to `assemble_video`**

Modify `assemble_video` signature in `musicvid/pipeline/assembler.py`:

```python
def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path,
                   resolution="1080p", font_path=None, effects_level="minimal",
                   clip_start=None, clip_end=None, title_card_text=None,
                   audio_fade_out=1.0, subtitle_margin_bottom=80, cinematic_bars=True):
```

Pass `subtitle_margin_bottom` to `_create_subtitle_clips`:

```python
    subtitle_clips = _create_subtitle_clips(
        analysis.get("lyrics", []),
        scene_plan.get("subtitle_style", {}),
        target_size,
        font_path=font_path,
        subtitle_margin_bottom=subtitle_margin_bottom,
    )
```

Use `audio_fade_out` instead of hardcoded `1.0`:

```python
        audio = audio.with_effects([afx.AudioFadeIn(0.5), afx.AudioFadeOut(audio_fade_out)])
```

Gate cinematic bars with the `cinematic_bars` flag:

```python
    if cinematic_bars and effects_level in ("minimal", "full"):
        bars = create_cinematic_bars(target_size[0], target_size[1], video.duration)
        layers.extend(bars)
```

- [ ] **Step 7: Run tests**

Run: `python3 -m pytest tests/test_assembler.py::TestSocialFadeDurations tests/test_assembler.py::TestSubtitleMarginBottom -v`
Expected: All PASS

- [ ] **Step 8: Run full test suite to ensure no regressions**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS (existing tests unaffected since defaults match old behavior)

- [ ] **Step 9: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: add social mode params to assembler (subtitle margin, fade, cinematic bars)"
```

---

### Task 4: Portrait Ken Burns Restriction

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Modify: `tests/test_assembler.py`

The spec says for 9:16 reels: "Ken Burns: tylko zoom in/out i pan_up/pan_down (bez poziomego)". We need to:
1. Remap horizontal pans (`pan_left`/`pan_right`) to vertical (`pan_up`/`pan_down`) when in portrait mode
2. Add `pan_up` and `pan_down` Ken Burns motions

- [ ] **Step 1: Write the failing test — pan_up motion type**

Add to `tests/test_assembler.py`:

```python
class TestPortraitKenBurns:
    """Tests for portrait-mode Ken Burns restrictions."""

    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_pan_up_creates_vertical_pan(self, mock_image_clip):
        from musicvid.pipeline.assembler import _create_ken_burns_clip

        mock_clip = MagicMock()
        mock_image_clip.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        result = _create_ken_burns_clip(mock_clip, 5.0, "pan_up", (1080, 1920))

        mock_clip.transform.assert_called_once()

    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_pan_down_creates_vertical_pan(self, mock_image_clip):
        from musicvid.pipeline.assembler import _create_ken_burns_clip

        mock_clip = MagicMock()
        mock_image_clip.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        result = _create_ken_burns_clip(mock_clip, 5.0, "pan_down", (1080, 1920))

        mock_clip.transform.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assembler.py::TestPortraitKenBurns -v`
Expected: FAIL (pan_up falls through to static, no transform call)

- [ ] **Step 3: Add pan_up and pan_down to Ken Burns**

Add to `_create_ken_burns_clip` in `musicvid/pipeline/assembler.py`, before the `else: # static` branch:

```python
    elif motion == "pan_up":
        def pan_u(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_offset = fh - h
            y = int(max_offset * (1 - progress))
            cropped = frame[y:y + h, 0:w]
            return cropped
        return clip.transform(pan_u)

    elif motion == "pan_down":
        def pan_d(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_offset = fh - h
            y = int(max_offset * progress)
            cropped = frame[y:y + h, 0:w]
            return cropped
        return clip.transform(pan_d)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestPortraitKenBurns -v`
Expected: PASS

- [ ] **Step 5: Write test — remap_motion_for_portrait helper**

Add to `tests/test_assembler.py`:

```python
    def test_remap_motion_for_portrait_replaces_horizontal(self):
        from musicvid.pipeline.assembler import _remap_motion_for_portrait

        assert _remap_motion_for_portrait("pan_left") == "pan_up"
        assert _remap_motion_for_portrait("pan_right") == "pan_down"
        assert _remap_motion_for_portrait("slow_zoom_in") == "slow_zoom_in"
        assert _remap_motion_for_portrait("static") == "static"
```

- [ ] **Step 6: Implement `_remap_motion_for_portrait`**

Add to `musicvid/pipeline/assembler.py`:

```python
def _remap_motion_for_portrait(motion):
    """Remap horizontal pans to vertical for portrait (9:16) format."""
    remap = {"pan_left": "pan_up", "pan_right": "pan_down"}
    return remap.get(motion, motion)
```

- [ ] **Step 7: Run test to verify**

Run: `python3 -m pytest tests/test_assembler.py::TestPortraitKenBurns::test_remap_motion_for_portrait_replaces_horizontal -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: add pan_up/pan_down Ken Burns and portrait motion remapping"
```

---

### Task 5: CLI Flags and Preset Routing

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test — flags accepted**

Add to `tests/test_cli.py`:

```python
class TestPresetMode:
    """Tests for --preset and --reel-duration CLI flags."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_preset_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--preset", "all", "--help"])
        assert result.exit_code == 0

    def test_reel_duration_flag_accepted(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--reel-duration", "30", "--help"])
        assert result.exit_code == 0

    def test_preset_invalid_value_rejected(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--preset", "invalid"])
        assert result.exit_code != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::TestPresetMode::test_preset_flag_accepted -v`
Expected: FAIL (no such option: --preset)

- [ ] **Step 3: Add --preset and --reel-duration options to CLI**

Add to `musicvid/musicvid.py` click options (after `--animate`):

```python
@click.option("--preset", type=click.Choice(["full", "social", "all"]), default=None, help="Preset mode: full (YouTube), social (3 reels), all (both).")
@click.option("--reel-duration", type=click.Choice(["15", "20", "30"]), default="15", help="Duration of social media reels in seconds.")
```

Add `preset` and `reel_duration` to the `cli` function signature.

- [ ] **Step 4: Run flag acceptance tests**

Run: `python3 -m pytest tests/test_cli.py::TestPresetMode -v`
Expected: All PASS

- [ ] **Step 5: Write the failing test — preset full calls assemble once**

Add to `tests/test_cli.py::TestPresetMode`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_preset_full_assembles_one_video(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 0.5, "end": 2.0, "text": "Test"}],
            "beats": [0.0, 0.5, 1.0],
            "bpm": 120.0,
            "duration": 60.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 60.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 60.0,
                        "visual_prompt": "test", "motion": "static",
                        "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--preset", "full",
        ])

        assert result.exit_code == 0, result.output
        assert mock_assemble.call_count == 1
        call_kwargs = mock_assemble.call_args[1]
        assert "pelny" in call_kwargs["output_path"]
        assert call_kwargs["output_path"].endswith("_youtube.mp4")
```

- [ ] **Step 6: Write the failing test — preset social selects clips and assembles 3 times**

Add to `tests/test_cli.py::TestPresetMode`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_preset_social_assembles_three_reels(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 20.0, "end": 24.0, "text": "Verse line"},
                {"start": 60.0, "end": 64.0, "text": "Chorus line"},
                {"start": 90.0, "end": 94.0, "text": "Bridge line"},
            ],
            "beats": [0.0, 0.5, 1.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [
                {"label": "verse", "start": 0.0, "end": 60.0},
                {"label": "chorus", "start": 60.0, "end": 90.0},
                {"label": "bridge", "start": 90.0, "end": 120.0},
            ],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
                {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Opening"},
                {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Peak"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [
                {"section": "verse", "start": 0.0, "end": 60.0,
                 "visual_prompt": "test1", "motion": "static", "transition": "cut", "overlay": "none"},
                {"section": "chorus", "start": 60.0, "end": 90.0,
                 "visual_prompt": "test2", "motion": "slow_zoom_in", "transition": "cut", "overlay": "none"},
                {"section": "bridge", "start": 90.0, "end": 120.0,
                 "visual_prompt": "test3", "motion": "pan_left", "transition": "cut", "overlay": "none"},
            ],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v1.mp4", "search_query": "test1"},
            {"scene_index": 1, "video_path": "/fake/v2.mp4", "search_query": "test2"},
            {"scene_index": 2, "video_path": "/fake/v3.mp4", "search_query": "test3"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--preset", "social",
        ])

        assert result.exit_code == 0, result.output
        assert mock_assemble.call_count == 3
        mock_social.assert_called_once()

        # All 3 calls should use portrait resolution
        for call in mock_assemble.call_args_list:
            assert call[1]["resolution"] == "portrait"

        # Check output paths are in social/ subfolder
        paths = [call[1]["output_path"] for call in mock_assemble.call_args_list]
        assert all("social" in p for p in paths)
        assert any("rolka_A" in p for p in paths)
        assert any("rolka_B" in p for p in paths)
        assert any("rolka_C" in p for p in paths)
```

- [ ] **Step 7: Write the failing test — preset all assembles 4 times (1 full + 3 reels)**

Add to `tests/test_cli.py::TestPresetMode`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_preset_all_assembles_four_videos(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 20.0, "end": 24.0, "text": "Test"}],
            "beats": [0.0, 0.5],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [
                {"label": "verse", "start": 0.0, "end": 60.0},
                {"label": "chorus", "start": 60.0, "end": 90.0},
                {"label": "bridge", "start": 90.0, "end": 120.0},
            ],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
                {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Opening"},
                {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Peak"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [
                {"section": "verse", "start": 0.0, "end": 60.0,
                 "visual_prompt": "test", "motion": "static", "transition": "cut", "overlay": "none"},
                {"section": "chorus", "start": 60.0, "end": 90.0,
                 "visual_prompt": "test", "motion": "static", "transition": "cut", "overlay": "none"},
                {"section": "bridge", "start": 90.0, "end": 120.0,
                 "visual_prompt": "test", "motion": "static", "transition": "cut", "overlay": "none"},
            ],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v1.mp4", "search_query": "test"},
            {"scene_index": 1, "video_path": "/fake/v2.mp4", "search_query": "test"},
            {"scene_index": 2, "video_path": "/fake/v3.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--preset", "all",
        ])

        assert result.exit_code == 0, result.output
        assert mock_assemble.call_count == 4

        # First call is full YouTube video
        first_call = mock_assemble.call_args_list[0][1]
        assert "pelny" in first_call["output_path"]

        # Remaining 3 calls are social reels
        for call in mock_assemble.call_args_list[1:]:
            assert call[1]["resolution"] == "portrait"
            assert "social" in call[1]["output_path"]
```

- [ ] **Step 8: Write the failing test — stages 1-3 run only once with preset all**

Add to `tests/test_cli.py::TestPresetMode`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_preset_all_stages_1_to_3_run_once(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 20.0, "end": 24.0, "text": "Test"}],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [
                {"label": "verse", "start": 0.0, "end": 60.0},
                {"label": "chorus", "start": 60.0, "end": 90.0},
                {"label": "bridge", "start": 90.0, "end": 120.0},
            ],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
                {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Opening"},
                {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Peak"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [
                {"section": "verse", "start": 0.0, "end": 60.0,
                 "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"},
            ],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--preset", "all",
        ])

        assert result.exit_code == 0, result.output
        # Stages 1-3 called only once each
        mock_analyze.assert_called_once()
        mock_direct.assert_called_once()
        mock_fetch.assert_called_once()
        # Stage 4 called 4 times
        assert mock_assemble.call_count == 4
```

- [ ] **Step 9: Write the failing test — reel duration flag changes clip duration**

Add to `tests/test_cli.py::TestPresetMode`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_reel_duration_changes_clip_length(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 180.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 10.0, "end": 40.0, "section": "verse", "reason": "A"},
                {"id": "B", "start": 60.0, "end": 90.0, "section": "verse", "reason": "B"},
                {"id": "C", "start": 120.0, "end": 150.0, "section": "verse", "reason": "C"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 180.0,
                        "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--preset", "social",
            "--reel-duration", "30",
        ])

        assert result.exit_code == 0, result.output
        # select_social_clips called with duration=30
        mock_social.assert_called_once()
        assert mock_social.call_args[0][1] == 30

        # Output filenames contain 30s
        paths = [call[1]["output_path"] for call in mock_assemble.call_args_list]
        assert all("30s" in p for p in paths)
```

- [ ] **Step 10: Implement preset routing in CLI**

Modify `musicvid/musicvid.py`:

1. Add import at top:
```python
from musicvid.pipeline.social_clip_selector import select_social_clips
```

2. Add the two new click options before the `cli` function definition.

3. Modify the `cli` function body. After stage 3 and font resolution (after line 251), replace the current output/assembly logic (lines 253-281) with:

```python
    # === Preset mode routing ===
    if preset is not None:
        _run_preset_mode(
            preset=preset,
            reel_duration=int(reel_duration),
            analysis=full_analysis,  # original unfiltered analysis
            scene_plan=scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path=str(audio_path),
            output_dir=output_dir,
            stem=audio_path.stem,
            font=font,
            effects=effects,
            cache_dir=cache_dir,
            new=new,
        )
        return

    # === Original single-output mode (unchanged) ===
    # ... existing code for clip_duration / normal mode ...
```

4. Add `_run_preset_mode` function:

```python
def _run_preset_mode(preset, reel_duration, analysis, scene_plan, fetch_manifest,
                     audio_path, output_dir, stem, font, effects, cache_dir, new):
    """Handle --preset flag: generate full video and/or social reels."""
    generate_full = preset in ("full", "all")
    generate_social = preset in ("social", "all")

    # Social clip selection
    social_clips = None
    if generate_social:
        social_cache_name = f"social_clips_{reel_duration}s.json"
        social_clips = load_cache(str(cache_dir), social_cache_name) if not new else None
        if social_clips:
            click.echo(f"[social] Social clip selection ({reel_duration}s)... CACHED (skipped)")
        else:
            click.echo(f"[social] Selecting 3 × {reel_duration}s fragments...")
            social_clips = select_social_clips(analysis, reel_duration)
            save_cache(str(cache_dir), social_cache_name, social_clips)
        for clip in social_clips["clips"]:
            click.echo(f"  Clip {clip['id']}: {clip['start']:.1f}s–{clip['end']:.1f}s "
                       f"({clip.get('section', '?')}) — {clip.get('reason', '')}")

    # Count total assemblies for progress
    total = (1 if generate_full else 0) + (3 if generate_social else 0)
    assembly_num = 0

    # Stage 4a: Full YouTube video
    if generate_full:
        assembly_num += 1
        pelny_dir = output_dir / "pelny"
        pelny_dir.mkdir(parents=True, exist_ok=True)
        full_output = str(pelny_dir / f"{stem}_youtube.mp4")
        click.echo(f"[4/4] Montaż:\n  → Pełny teledysk YouTube ({assembly_num}/{total})...")
        assemble_video(
            analysis=analysis,
            scene_plan=scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path=audio_path,
            output_path=full_output,
            resolution="1080p",
            font_path=font,
            effects_level=effects,
        )
        click.echo(f"  → Pełny teledysk YouTube ({assembly_num}/{total})... ✅")

    # Stage 4b-d: Social reels
    if generate_social:
        social_dir = output_dir / "social"
        social_dir.mkdir(parents=True, exist_ok=True)

        if not generate_full:
            click.echo("[4/4] Montaż:")

        for clip_info in social_clips["clips"]:
            assembly_num += 1
            clip_id = clip_info["id"]
            clip_start = clip_info["start"]
            clip_end = clip_info["end"]
            section = clip_info.get("section", "unknown")

            reel_output = str(social_dir / f"{stem}_rolka_{clip_id}_{reel_duration}s.mp4")

            click.echo(f"  → Rolka {clip_id} — {section} ({assembly_num}/{total})...")

            # Filter analysis, scene plan, and manifest to clip window
            clip_analysis = _filter_analysis_to_clip(analysis, clip_start, clip_end)
            clip_scene_plan = _filter_scene_plan_to_clip(scene_plan, clip_start, clip_end)

            # Remap horizontal pans to vertical for portrait
            from musicvid.pipeline.assembler import _remap_motion_for_portrait
            for scene in clip_scene_plan["scenes"]:
                scene["motion"] = _remap_motion_for_portrait(scene.get("motion", "static"))

            clip_manifest = _filter_manifest_to_clip(
                fetch_manifest, scene_plan["scenes"], clip_start, clip_end
            )

            assemble_video(
                analysis=clip_analysis,
                scene_plan=clip_scene_plan,
                fetch_manifest=clip_manifest,
                audio_path=audio_path,
                output_path=reel_output,
                resolution="portrait",
                font_path=font,
                effects_level=effects,
                clip_start=clip_start,
                clip_end=clip_end,
                audio_fade_out=1.5,
                subtitle_margin_bottom=200,
                cinematic_bars=False,
            )
            click.echo(f"  → Rolka {clip_id} — {section} ({assembly_num}/{total})... ✅")

    # Summary
    click.echo(f"\nGotowe! Wygenerowano {total} pliki:")
    if generate_full:
        click.echo(f"  {output_dir}/pelny/{stem}_youtube.mp4")
    if generate_social:
        for clip_info in social_clips["clips"]:
            click.echo(f"  {output_dir}/social/{stem}_rolka_{clip_info['id']}_{reel_duration}s.mp4")
```

Important: Store the original analysis before any clip filtering as `full_analysis` early in the `cli` function. The `analysis` variable currently gets overwritten by `_filter_analysis_to_clip` in clip mode, so for preset mode we need the original. Add near line 149, right after the analysis logging:

```python
    full_analysis = analysis  # preserve for preset mode (before clip filtering)
```

- [ ] **Step 11: Run all preset tests**

Run: `python3 -m pytest tests/test_cli.py::TestPresetMode -v`
Expected: All PASS

- [ ] **Step 12: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 13: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add --preset and --reel-duration CLI flags with full routing logic"
```

---

### Task 6: Social Clips Cache and Integration Test

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test — social clips cached**

Add to `tests/test_cli.py::TestPresetMode`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_social_clips_cached_on_second_run(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        base_analysis = {
            "lyrics": [],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 180.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_analyze.return_value = base_analysis
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 10.0, "end": 25.0, "section": "verse", "reason": "A"},
                {"id": "B", "start": 60.0, "end": 75.0, "section": "verse", "reason": "B"},
                {"id": "C", "start": 120.0, "end": 135.0, "section": "verse", "reason": "C"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 180.0,
                        "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"
        args = [str(audio_file), "--output", str(output_dir), "--preset", "social"]

        # First run
        runner.invoke(cli, args)
        assert mock_social.call_count == 1

        # Second run — social clips should be cached
        runner.invoke(cli, args)
        assert mock_social.call_count == 1  # not called again
```

- [ ] **Step 2: Run test to verify**

Run: `python3 -m pytest tests/test_cli.py::TestPresetMode::test_social_clips_cached_on_second_run -v`
Expected: PASS (caching is implemented in Task 5 Step 10)

- [ ] **Step 3: Write test — reel_duration invalidates social clips cache**

Add to `tests/test_cli.py::TestPresetMode`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_different_reel_duration_invalidates_cache(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        base_analysis = {
            "lyrics": [],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 180.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_analyze.return_value = base_analysis
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 10.0, "end": 25.0, "section": "verse", "reason": "A"},
                {"id": "B", "start": 60.0, "end": 75.0, "section": "verse", "reason": "B"},
                {"id": "C", "start": 120.0, "end": 135.0, "section": "verse", "reason": "C"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 180.0,
                        "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"

        # Run with 15s
        runner.invoke(cli, [str(audio_file), "--output", str(output_dir), "--preset", "social"])
        assert mock_social.call_count == 1

        # Run with 30s — different cache key
        runner.invoke(cli, [str(audio_file), "--output", str(output_dir), "--preset", "social", "--reel-duration", "30"])
        assert mock_social.call_count == 2  # called again because different duration
```

- [ ] **Step 4: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: add social clips cache and reel-duration invalidation tests"
```

---

### Task 7: Final Integration — Progress Logging and Edge Cases

**Files:**
- Modify: `musicvid/musicvid.py` (progress logging refinements)
- Modify: `tests/test_cli.py` (output verification)

- [ ] **Step 1: Write test — preset without --preset flag is unchanged**

Add to `tests/test_cli.py::TestPresetMode`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_no_preset_flag_unchanged_behavior(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        """Without --preset, existing behavior is preserved exactly."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 60.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 60.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 60.0,
                        "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [str(audio_file), "--output", str(output_dir)])

        assert result.exit_code == 0, result.output
        assert mock_assemble.call_count == 1
        call_kwargs = mock_assemble.call_args[1]
        assert "_musicvideo.mp4" in call_kwargs["output_path"]
        # Should NOT create pelny/ or social/ subdirs
        assert "pelny" not in call_kwargs["output_path"]
        assert "social" not in call_kwargs["output_path"]
```

- [ ] **Step 2: Run test**

Run: `python3 -m pytest tests/test_cli.py::TestPresetMode::test_no_preset_flag_unchanged_behavior -v`
Expected: PASS

- [ ] **Step 3: Write test — social reels get social-specific assembler params**

Add to `tests/test_cli.py::TestPresetMode`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_social_clips")
    def test_social_reels_use_correct_assembler_params(
        self, mock_social, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [],
            "beats": [0.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 180.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_social.return_value = {
            "clips": [
                {"id": "A", "start": 10.0, "end": 25.0, "section": "verse", "reason": "A"},
                {"id": "B", "start": 60.0, "end": 75.0, "section": "verse", "reason": "B"},
                {"id": "C", "start": 120.0, "end": 135.0, "section": "verse", "reason": "C"},
            ]
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 180.0,
                        "visual_prompt": "t", "motion": "static", "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "t"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir), "--preset", "social",
        ])

        assert result.exit_code == 0, result.output
        for call in mock_assemble.call_args_list:
            kwargs = call[1]
            assert kwargs["resolution"] == "portrait"
            assert kwargs["audio_fade_out"] == 1.5
            assert kwargs["subtitle_margin_bottom"] == 200
            assert kwargs["cinematic_bars"] == False
            assert kwargs["clip_start"] is not None
            assert kwargs["clip_end"] is not None
```

- [ ] **Step 4: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: complete preset mode with progress logging and edge case tests"
```

- [ ] **Step 6: Run full test suite one final time**

Run: `python3 -m pytest tests/ -v`
Expected: All 150+ tests PASS (existing + ~20 new tests)
