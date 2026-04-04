# Clip Duration Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--clip [15|20|25|30]` flag that uses Claude to select the best social-media fragment of a song, then generates a short video with fades, correct output naming, and optional title card.

**Architecture:** A new `clip_selector.py` module asks Claude to pick the best start/end for the clip. The CLI filters the full audio analysis to the clip window (adjusting timestamps to start at 0) before passing to the director, so the rest of the pipeline stays unchanged. The assembler gains `clip_start`/`clip_end` parameters to trim audio and apply fades. A `--platform` flag maps to portrait resolution (1080×1920) and adds platform name to the output filename.

**Tech Stack:** Python 3.11+, Click, anthropic SDK, MoviePy 2.x (afx for audio fades, vfx for video fades), pytest + unittest.mock

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `musicvid/pipeline/clip_selector.py` | Claude API call to select best clip fragment |
| Create | `tests/test_clip_selector.py` | Tests for clip_selector |
| Modify | `musicvid/musicvid.py` | Add --clip, --platform, --title-card; filter analysis; update caching + output naming |
| Modify | `musicvid/pipeline/assembler.py` | Add clip_start/clip_end params; trim audio; add fades; add title card; portrait resolution |
| Modify | `tests/test_assembler.py` | Tests for clip mode in assembler |
| Modify | `tests/test_cli.py` | Tests for --clip, --platform, --title-card flags |

---

### Task 1: clip_selector module

**Files:**
- Create: `musicvid/pipeline/clip_selector.py`
- Create: `tests/test_clip_selector.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_clip_selector.py
"""Tests for clip_selector module."""
import json
from unittest.mock import patch, MagicMock

import pytest

from musicvid.pipeline.clip_selector import select_clip


def _make_analysis(duration=180.0):
    return {
        "duration": duration,
        "bpm": 120,
        "sections": [
            {"label": "intro", "start": 0.0, "end": 20.0},
            {"label": "chorus", "start": 45.0, "end": 75.0},
        ],
        "lyrics": [
            {"start": 45.0, "end": 48.0, "text": "Amazing grace"},
            {"start": 48.0, "end": 52.0, "text": "How sweet the sound"},
            {"start": 52.0, "end": 56.0, "text": "That saved a wretch like me"},
        ],
    }


@patch("musicvid.pipeline.clip_selector.anthropic")
def test_select_clip_returns_start_end_reason(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "start": 45.0,
        "end": 60.0,
        "reason": "chorus is most recognizable",
    }))]
    mock_client.messages.create.return_value = mock_response

    result = select_clip(_make_analysis(), 15)

    assert result["start"] == 45.0
    assert result["end"] == 60.0
    assert "reason" in result


@patch("musicvid.pipeline.clip_selector.anthropic")
def test_select_clip_retries_on_invalid_json(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    invalid_response = MagicMock()
    invalid_response.content = [MagicMock(text="not valid json")]
    valid_response = MagicMock()
    valid_response.content = [MagicMock(text=json.dumps({
        "start": 30.0,
        "end": 45.0,
        "reason": "chorus",
    }))]
    mock_client.messages.create.side_effect = [invalid_response, valid_response]

    result = select_clip(_make_analysis(), 15)

    assert mock_client.messages.create.call_count == 2
    assert result["start"] == 30.0


@patch("musicvid.pipeline.clip_selector.anthropic")
def test_select_clip_passes_clip_duration_in_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "start": 60.0,
        "end": 90.0,
        "reason": "chorus",
    }))]
    mock_client.messages.create.return_value = mock_response

    select_clip(_make_analysis(), 30)

    call_kwargs = mock_client.messages.create.call_args[1]
    user_content = call_kwargs["messages"][0]["content"]
    assert "30-second" in user_content


@patch("musicvid.pipeline.clip_selector.anthropic")
def test_select_clip_fallback_on_all_attempts_fail(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="bad json")]
    mock_client.messages.create.return_value = mock_response

    result = select_clip(_make_analysis(duration=120.0), 15)

    # Fallback: center of 120s song → start at 52.5, end at 67.5
    assert result["start"] == pytest.approx(52.5, abs=1.0)
    assert result["end"] == pytest.approx(67.5, abs=1.0)
    assert "reason" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_clip_selector.py -v
```

Expected: `ModuleNotFoundError: No module named 'musicvid.pipeline.clip_selector'`

- [ ] **Step 3: Implement clip_selector.py**

```python
# musicvid/pipeline/clip_selector.py
"""Stage 1.5: AI clip selection for social media clips."""
import json

import anthropic


def select_clip(analysis, clip_duration):
    """Ask Claude to select the best fragment of the song for a social media clip.

    Args:
        analysis: Audio analysis dict (lyrics, sections, duration, bpm).
        clip_duration: Desired clip duration in seconds (15, 20, 25, or 30).

    Returns:
        dict with keys: start (float), end (float), reason (str).
    """
    client = anthropic.Anthropic()

    segments = [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
        for seg in analysis.get("lyrics", [])
    ]
    sections = analysis.get("sections", [])
    duration = analysis.get("duration", 0)

    user_message = (
        f"You are selecting a {clip_duration}-second clip from a song for social media "
        f"(Instagram Reels, YouTube Shorts, TikTok).\n\n"
        f"Song duration: {duration:.1f}s\n"
        f"BPM: {analysis.get('bpm', 'unknown')}\n"
        f"Sections: {json.dumps(sections)}\n"
        f"Lyrics with timestamps:\n{json.dumps(segments, indent=2)}\n\n"
        f"Rules:\n"
        f"- Prefer the chorus (most recognizable part)\n"
        f"- Avoid the first 5 seconds unless no other option\n"
        f"- Do not cut in the middle of a word or lyric line\n"
        f"- Start on a musical phrase boundary if possible\n"
        f"- End at the end of a lyric line, not mid-word\n"
        f"- The clip length (end - start) must be exactly {clip_duration}s \u00b12s\n\n"
        f"Return ONLY valid JSON (no markdown, no explanation):\n"
        f'{{"start": <float seconds>, "end": <float seconds>, "reason": "<brief>"}}'
    )

    for _attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=256,
                messages=[{"role": "user", "content": user_message}],
            )
            result = json.loads(response.content[0].text.strip())
            if "start" in result and "end" in result:
                return result
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

    # Fallback: center of song
    fallback_start = max(0.0, (duration - clip_duration) / 2)
    return {
        "start": fallback_start,
        "end": fallback_start + clip_duration,
        "reason": "Fallback: center of song",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_clip_selector.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/clip_selector.py tests/test_clip_selector.py
git commit -m "feat: add clip_selector module for AI-based clip fragment selection"
```

---

### Task 2: CLI clip support

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_cli.py` inside the `TestCLI` class (after the existing tests):

```python
    def test_clip_flag_accepted(self, runner, tmp_path):
        """The --clip flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--clip", "15", "--help"])
        assert result.exit_code == 0

    def test_platform_flag_accepted(self, runner, tmp_path):
        """The --platform flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--platform", "reels", "--help"])
        assert result.exit_code == 0

    def test_title_card_flag_accepted(self, runner, tmp_path):
        """The --title-card flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--title-card", "--help"])
        assert result.exit_code == 0

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_clip")
    def test_clip_mode_calls_select_clip(
        self, mock_select, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 45.0, "end": 60.0, "text": "Amazing grace"}],
            "beats": [45.0, 46.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "chorus", "start": 45.0, "end": 75.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_select.return_value = {"start": 45.0, "end": 60.0, "reason": "chorus"}
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "chorus", "start": 0.0, "end": 15.0,
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
            "--clip", "15",
        ])

        assert result.exit_code == 0
        mock_select.assert_called_once()
        select_args = mock_select.call_args
        assert select_args[0][1] == 15

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_clip")
    def test_clip_mode_output_filename_has_duration_suffix(
        self, mock_select, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "mysong.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 45.0, "end": 60.0, "text": "Amazing grace"}],
            "beats": [45.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "chorus", "start": 45.0, "end": 75.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_select.return_value = {"start": 45.0, "end": 60.0, "reason": "chorus"}
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "chorus", "start": 0.0, "end": 15.0,
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
            "--clip", "30",
        ])

        assert result.exit_code == 0
        assemble_call_args = mock_assemble.call_args[1]
        assert "30s" in assemble_call_args["output_path"]

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_clip")
    def test_clip_mode_with_platform_uses_portrait_resolution(
        self, mock_select, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 45.0, "end": 60.0, "text": "Amazing grace"}],
            "beats": [45.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "chorus", "start": 45.0, "end": 75.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_select.return_value = {"start": 45.0, "end": 60.0, "reason": "chorus"}
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "chorus", "start": 0.0, "end": 15.0,
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
            "--clip", "30",
            "--platform", "reels",
        ])

        assert result.exit_code == 0
        assemble_call_args = mock_assemble.call_args[1]
        assert assemble_call_args["resolution"] == "portrait"
        assert "reels" in assemble_call_args["output_path"]

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.select_clip")
    def test_clip_mode_filters_analysis_to_clip_window(
        self, mock_select, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font,
        runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 10.0, "end": 15.0, "text": "Before clip"},
                {"start": 45.0, "end": 55.0, "text": "In clip"},
                {"start": 80.0, "end": 90.0, "text": "After clip"},
            ],
            "beats": [10.0, 45.0, 50.0, 80.0],
            "bpm": 120.0,
            "duration": 180.0,
            "sections": [{"label": "chorus", "start": 45.0, "end": 75.0}],
            "mood_energy": "contemplative",
            "language": "en",
        }
        mock_select.return_value = {"start": 45.0, "end": 60.0, "reason": "chorus"}
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "chorus", "start": 0.0, "end": 15.0,
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
            "--clip", "15",
        ])

        assert result.exit_code == 0
        # Director receives filtered analysis: only "In clip" segment, offset by clip_start
        director_analysis = mock_direct.call_args[0][0]
        assert director_analysis["duration"] == pytest.approx(15.0, abs=0.5)
        filtered_lyrics = director_analysis["lyrics"]
        assert len(filtered_lyrics) == 1
        assert filtered_lyrics[0]["text"] == "In clip"
        # Times should be offset relative to clip_start=45.0
        assert filtered_lyrics[0]["start"] == pytest.approx(0.0, abs=0.5)
```

Note: `pytest` must be imported in the test file. It already is via the existing test file header.

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_clip_flag_accepted \
  tests/test_cli.py::TestCLI::test_platform_flag_accepted \
  tests/test_cli.py::TestCLI::test_title_card_flag_accepted \
  tests/test_cli.py::TestCLI::test_clip_mode_calls_select_clip \
  tests/test_cli.py::TestCLI::test_clip_mode_output_filename_has_duration_suffix \
  tests/test_cli.py::TestCLI::test_clip_mode_with_platform_uses_portrait_resolution \
  tests/test_cli.py::TestCLI::test_clip_mode_filters_analysis_to_clip_window \
  -v
```

Expected: Some tests fail because `--clip`, `--platform`, `--title-card` options don't exist yet.

- [ ] **Step 3: Implement CLI changes in musicvid/musicvid.py**

Replace the full contents of `musicvid/musicvid.py` with:

```python
"""MusicVid CLI — Christian Music Video Generator."""

import hashlib
import shutil
from pathlib import Path

import click
from dotenv import load_dotenv

from musicvid.pipeline.audio_analyzer import analyze_audio
from musicvid.pipeline.cache import get_audio_hash, load_cache, save_cache
from musicvid.pipeline.clip_selector import select_clip
from musicvid.pipeline.director import create_scene_plan
from musicvid.pipeline.stock_fetcher import fetch_videos
from musicvid.pipeline.image_generator import generate_images
from musicvid.pipeline.assembler import assemble_video
from musicvid.pipeline.font_loader import get_font_path
from musicvid.pipeline.lyrics_parser import align_with_claude


load_dotenv()


def _video_files_exist(manifest):
    """Check that all video files referenced in the manifest exist on disk."""
    return all(Path(entry["video_path"]).exists() for entry in manifest)


def _image_files_exist(manifest):
    """Check that all image files referenced in the manifest exist on disk."""
    return all(Path(entry["video_path"]).exists() for entry in manifest)


def _filter_analysis_to_clip(analysis, clip_start, clip_end):
    """Return a copy of analysis restricted to the [clip_start, clip_end] window.

    Lyrics, beats, and section times are offset by clip_start so they start at t=0.
    """
    clip_duration = clip_end - clip_start

    lyrics = [
        {**seg, "start": seg["start"] - clip_start, "end": seg["end"] - clip_start}
        for seg in analysis.get("lyrics", [])
        if seg["start"] >= clip_start - 0.1 and seg["end"] <= clip_end + 0.1
    ]

    sections = [
        {
            **sec,
            "start": max(0.0, sec["start"] - clip_start),
            "end": min(clip_duration, sec["end"] - clip_start),
        }
        for sec in analysis.get("sections", [])
        if sec["start"] < clip_end and sec["end"] > clip_start
    ]

    beats = [
        b - clip_start
        for b in analysis.get("beats", [])
        if clip_start <= b <= clip_end
    ]

    return {
        **analysis,
        "lyrics": lyrics,
        "sections": sections,
        "beats": beats,
        "duration": clip_duration,
    }


@click.command()
@click.argument("audio_file", type=click.Path(exists=True))
@click.option("--mode", type=click.Choice(["stock", "ai", "hybrid"]), default="stock", help="Video source mode.")
@click.option("--provider", type=click.Choice(["flux-dev", "flux-pro", "flux-schnell"]), default="flux-pro", help="Image provider for --mode ai.")
@click.option("--style", type=click.Choice(["auto", "contemplative", "joyful", "worship", "powerful"]), default="auto", help="Visual style.")
@click.option("--output", type=click.Path(), default="./output/", help="Output directory.")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p", help="Output resolution.")
@click.option("--lang", default="auto", help="Language for transcription.")
@click.option("--new", is_flag=True, default=False, help="Force recalculation, ignore cache.")
@click.option("--font", "font_path", type=click.Path(), default=None, help="Custom .ttf font file for subtitles.")
@click.option("--lyrics", "lyrics_path", type=click.Path(), default=None, help="Path to .txt lyrics file (skips Whisper).")
@click.option("--effects", type=click.Choice(["none", "minimal", "full"]), default="minimal", help="Visual effects level.")
@click.option("--clip", "clip_duration", type=click.Choice(["15", "20", "25", "30"]), default=None, help="Clip duration in seconds for social media (selects best fragment).")
@click.option("--platform", type=click.Choice(["reels", "shorts", "tiktok"]), default=None, help="Social media platform (sets portrait 9:16 resolution).")
@click.option("--title-card", is_flag=True, default=False, help="Add 2-second title card with song name at start of clip.")
def cli(audio_file, mode, provider, style, output, resolution, lang, new, font_path, lyrics_path, effects, clip_duration, platform, title_card):
    """Generate a music video from AUDIO_FILE."""
    audio_path = Path(audio_file).resolve()
    output_dir = Path(output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_hash = get_audio_hash(str(audio_path))
    cache_dir = output_dir / "tmp" / audio_hash
    cache_dir.mkdir(parents=True, exist_ok=True)

    if new and cache_dir.exists():
        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

    # Resolve lyrics file (explicit flag or auto-detection)
    lyrics_file = None
    txt_files_in_dir = sorted(audio_path.parent.glob("*.txt"))

    if lyrics_path:
        lyrics_file = Path(lyrics_path).resolve()
        if not lyrics_file.exists():
            raise click.BadParameter(f"Lyrics file not found: {lyrics_file}", param_hint="--lyrics")
    elif len(txt_files_in_dir) == 1:
        lyrics_file = txt_files_in_dir[0]
    elif len(txt_files_in_dir) > 1:
        click.echo("  \u26a0 Znaleziono wiele plik\u00f3w .txt \u2014 u\u017cyj --lyrics aby wybra\u0107")

    # Compute lyrics hash for cache invalidation
    lyrics_hash = None
    if lyrics_file:
        with open(lyrics_file, "rb") as f:
            lyrics_hash = hashlib.md5(f.read()).hexdigest()[:12]

    # Stage 1: Analyze Audio
    analysis_cache_name = f"audio_analysis_{lyrics_hash}.json" if lyrics_hash else "audio_analysis.json"
    analysis = load_cache(str(cache_dir), analysis_cache_name) if not new else None
    if analysis:
        click.echo("[1/4] Audio analysis... CACHED (skipped)")
    else:
        click.echo("[1/4] Analyzing audio...")
        analysis = analyze_audio(str(audio_path), output_dir=str(cache_dir))
        save_cache(str(cache_dir), analysis_cache_name, analysis)
    # Replace lyrics using AI alignment if lyrics file available
    if lyrics_file:
        aligned_cache_name = f"lyrics_aligned_{lyrics_hash}.json"
        aligned = load_cache(str(cache_dir), aligned_cache_name) if not new else None
        if aligned:
            analysis["lyrics"] = aligned
            line_count = len(aligned)
            click.echo(f"[1/4] Tekst: AI dopasowanie... CACHED ({line_count} linii)")
        else:
            with open(lyrics_file, "r", encoding="utf-8") as f:
                file_lines = [line.strip() for line in f if line.strip()]
            aligned = align_with_claude(analysis["lyrics"], file_lines)
            save_cache(str(cache_dir), aligned_cache_name, aligned)
            analysis["lyrics"] = aligned
            line_count = len(file_lines)
            click.echo(f"[1/4] Tekst: Whisper timing + AI dopasowanie tekstu z pliku ({line_count} linii)")

    click.echo(f"  BPM: {analysis['bpm']}, Duration: {analysis['duration']}s, "
               f"Sections: {len(analysis['sections'])}, Mood: {analysis['mood_energy']}")

    # Clip selection (between Stage 1 and Stage 2)
    clip_start = None
    clip_end = None
    if clip_duration is not None:
        clip_secs = int(clip_duration)
        clip_cache_name = f"clip_{clip_secs}s.json"
        clip_info = load_cache(str(cache_dir), clip_cache_name) if not new else None
        if clip_info:
            click.echo(f"[clip] Clip selection ({clip_secs}s)... CACHED (skipped)")
        else:
            click.echo(f"[clip] Selecting best {clip_secs}s fragment...")
            clip_info = select_clip(analysis, clip_secs)
            save_cache(str(cache_dir), clip_cache_name, clip_info)
        clip_start = clip_info["start"]
        clip_end = clip_info["end"]
        click.echo(f"  Clip: {clip_start:.1f}s\u2013{clip_end:.1f}s — {clip_info.get('reason', '')}")
        analysis = _filter_analysis_to_clip(analysis, clip_start, clip_end)

    # Determine resolution (platform overrides --resolution)
    effective_resolution = "portrait" if platform else resolution

    # Stage 2: Direct Scenes
    style_override = style if style != "auto" else None
    scene_cache_name = f"scene_plan_clip_{clip_duration}s.json" if clip_duration else "scene_plan.json"
    scene_plan = load_cache(str(cache_dir), scene_cache_name) if not new else None
    if scene_plan:
        click.echo("[2/4] Scene planning... CACHED (skipped)")
    else:
        click.echo("[2/4] Creating scene plan...")
        scene_plan = create_scene_plan(analysis, style_override=style_override, output_dir=str(cache_dir))
        save_cache(str(cache_dir), scene_cache_name, scene_plan)
    click.echo(f"  Style: {scene_plan['overall_style']}, Scenes: {len(scene_plan['scenes'])}")

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
    else:
        video_cache_name = f"video_manifest{manifest_suffix}.json"
        fetch_manifest = load_cache(str(cache_dir), video_cache_name) if not new else None
        if fetch_manifest and _video_files_exist(fetch_manifest):
            click.echo("[3/4] Fetching videos... CACHED (skipped)")
        else:
            click.echo("[3/4] Fetching stock videos...")
            fetch_manifest = fetch_videos(scene_plan, output_dir=str(cache_dir))
            save_cache(str(cache_dir), video_cache_name, fetch_manifest)
        fetched = sum(1 for f in fetch_manifest if f["video_path"].endswith(".mp4"))
        click.echo(f"  Fetched: {fetched}/{len(fetch_manifest)} videos")

    # Resolve font
    font = get_font_path(custom_path=font_path)

    # Build output filename
    if clip_duration:
        suffix = f"_{clip_duration}s"
        if platform:
            suffix += f"_{platform}"
        output_filename = audio_path.stem + suffix + ".mp4"
    else:
        output_filename = audio_path.stem + "_musicvideo.mp4"
    output_path = str(output_dir / output_filename)

    # Build title card text if requested
    title_card_text = audio_path.stem if title_card and clip_duration else None

    # Stage 4: Assemble Video
    click.echo("[4/4] Assembling video...")
    assemble_video(
        analysis=analysis,
        scene_plan=scene_plan,
        fetch_manifest=fetch_manifest,
        audio_path=str(audio_path),
        output_path=output_path,
        resolution=effective_resolution,
        font_path=font,
        effects_level=effects,
        clip_start=clip_start,
        clip_end=clip_end,
        title_card_text=title_card_text,
    )
    click.echo(f"  Done! Output: {output_path}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_clip_flag_accepted \
  tests/test_cli.py::TestCLI::test_platform_flag_accepted \
  tests/test_cli.py::TestCLI::test_title_card_flag_accepted \
  tests/test_cli.py::TestCLI::test_clip_mode_calls_select_clip \
  tests/test_cli.py::TestCLI::test_clip_mode_output_filename_has_duration_suffix \
  tests/test_cli.py::TestCLI::test_clip_mode_with_platform_uses_portrait_resolution \
  tests/test_cli.py::TestCLI::test_clip_mode_filters_analysis_to_clip_window \
  -v
```

Expected: 7 tests PASSED

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python3 -m pytest tests/ -v
```

Expected: All existing tests still pass plus new tests.

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add --clip, --platform, --title-card CLI options with clip selection and analysis filtering"
```

---

### Task 3: Assembler clip mode — audio trim, fades, title card, portrait resolution

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write the failing tests**

Add the following class to `tests/test_assembler.py` (after `TestAssembleVideoEffects`):

```python
class TestAssembleVideoClipMode:
    """Tests for clip mode (clip_start/clip_end, fades, title card, portrait resolution)."""

    def _make_mock_clip(self):
        mock_clip = MagicMock()
        mock_clip.duration = 15.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_end.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip
        return mock_clip

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_clip_mode_trims_audio(
        self, mock_concat, mock_composite, mock_text, mock_audio_cls,
        mock_image, mock_video, mock_vfx, mock_afx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = self._make_mock_clip()
        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio_cls.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=str(tmp_output / "output.mp4"),
            resolution="1080p",
            clip_start=45.0,
            clip_end=60.0,
        )

        mock_clip.subclipped.assert_called_with(45.0, 60.0)

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_clip_mode_applies_audio_fades(
        self, mock_concat, mock_composite, mock_text, mock_audio_cls,
        mock_image, mock_video, mock_vfx, mock_afx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = self._make_mock_clip()
        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio_cls.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=str(tmp_output / "output.mp4"),
            resolution="1080p",
            clip_start=45.0,
            clip_end=60.0,
        )

        # Audio should have with_effects called with AudioFadeIn and AudioFadeOut instances
        mock_afx.AudioFadeIn.assert_called_with(0.5)
        mock_afx.AudioFadeOut.assert_called_with(1.0)

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_clip_mode_applies_video_fades(
        self, mock_concat, mock_composite, mock_text, mock_audio_cls,
        mock_image, mock_video, mock_vfx, mock_afx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = self._make_mock_clip()
        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio_cls.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=str(tmp_output / "output.mp4"),
            resolution="1080p",
            clip_start=45.0,
            clip_end=60.0,
        )

        mock_vfx.FadeIn.assert_called_with(0.5)
        mock_vfx.FadeOut.assert_called_with(1.0)

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    @patch("musicvid.pipeline.assembler.ColorClip")
    def test_clip_mode_title_card_prepended(
        self, mock_color_clip, mock_concat, mock_composite, mock_text, mock_audio_cls,
        mock_image, mock_video, mock_vfx, mock_afx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = self._make_mock_clip()
        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio_cls.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_color_clip.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=str(tmp_output / "output.mp4"),
            resolution="1080p",
            clip_start=45.0,
            clip_end=60.0,
            title_card_text="My Song",
        )

        # Title card text should appear in a TextClip call
        text_calls = [str(c) for c in mock_text.call_args_list]
        assert any("My Song" in c for c in text_calls)

    def test_portrait_resolution_maps_correctly(self):
        from musicvid.pipeline.assembler import _get_resolution
        w, h = _get_resolution("portrait")
        assert w == 1080
        assert h == 1920

    @patch("musicvid.pipeline.assembler.create_cinematic_bars")
    @patch("musicvid.pipeline.assembler.create_light_leak")
    @patch("musicvid.pipeline.assembler.apply_effects")
    @patch("musicvid.pipeline.assembler.afx")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_no_clip_mode_no_audio_trim(
        self, mock_concat, mock_composite, mock_text, mock_audio_cls,
        mock_image, mock_video, mock_vfx, mock_afx, mock_apply_effects,
        mock_light_leak, mock_bars,
        sample_analysis, sample_scene_plan, tmp_output
    ):
        """Without clip_start/clip_end, audio should NOT be subclipped."""
        mock_clip = self._make_mock_clip()
        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio_cls.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip
        mock_apply_effects.return_value = mock_clip
        mock_bars.return_value = [mock_clip]

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
        ]

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=str(tmp_output / "output.mp4"),
            resolution="1080p",
        )

        # subclipped should not have been called on the audio (only on video clips)
        # The audio mock_clip.subclipped should not be called with (start, end) floats
        subclipped_calls = mock_clip.subclipped.call_args_list
        float_calls = [c for c in subclipped_calls if len(c[0]) == 2 and isinstance(c[0][0], float)]
        assert len(float_calls) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_assembler.py::TestAssembleVideoClipMode -v
```

Expected: Tests fail because `assemble_video` doesn't accept `clip_start`, `clip_end`, `title_card_text` yet, and `_get_resolution("portrait")` doesn't work.

- [ ] **Step 3: Implement assembler clip mode changes**

Replace the full contents of `musicvid/pipeline/assembler.py` with:

```python
"""Stage 4: Video assembly using MoviePy + FFmpeg."""

from pathlib import Path

from moviepy import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    ColorClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
    vfx,
    afx,
)

from musicvid.pipeline.effects import apply_effects, create_cinematic_bars, create_light_leak


RESOLUTION_MAP = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
    "portrait": (1080, 1920),
}


def _get_resolution(resolution_str):
    """Map resolution string to (width, height) tuple."""
    return RESOLUTION_MAP.get(resolution_str, (1920, 1080))


def _create_ken_burns_clip(clip, duration, motion="slow_zoom_in", target_size=(1920, 1080)):
    """Apply Ken Burns effect (zoom/pan) to a clip."""
    w, h = target_size
    clip = clip.resized(new_size=(int(w * 1.15), int(h * 1.15)))
    clip = clip.with_duration(duration)

    if motion == "slow_zoom_in":
        def zoom_in(get_frame, t):
            progress = t / duration
            scale = 1.0 + 0.15 * progress
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            new_w, new_h = int(fw / scale), int(fh / scale)
            x = (fw - new_w) // 2
            y = (fh - new_h) // 2
            cropped = frame[y:y + new_h, x:x + new_w]
            from PIL import Image
            import numpy as np
            img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
            return np.array(img)
        return clip.transform(zoom_in)

    elif motion == "slow_zoom_out":
        def zoom_out(get_frame, t):
            progress = t / duration
            scale = 1.15 - 0.15 * progress
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            new_w, new_h = int(fw / scale), int(fh / scale)
            x = (fw - new_w) // 2
            y = (fh - new_h) // 2
            cropped = frame[y:y + new_h, x:x + new_w]
            from PIL import Image
            import numpy as np
            img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
            return np.array(img)
        return clip.transform(zoom_out)

    elif motion == "pan_left":
        def pan_l(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_offset = fw - w
            x = int(max_offset * (1 - progress))
            cropped = frame[0:h, x:x + w]
            return cropped
        return clip.transform(pan_l)

    elif motion == "pan_right":
        def pan_r(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_offset = fw - w
            x = int(max_offset * progress)
            cropped = frame[0:h, x:x + w]
            return cropped
        return clip.transform(pan_r)

    else:  # static
        clip = clip.resized(new_size=(w, h))
        clip = clip.with_duration(duration)
        return clip


def _create_subtitle_clips(lyrics, subtitle_style, size, font_path=None):
    """Create subtitle TextClips from lyrics with word-level timing."""
    clips = []
    font_size = subtitle_style.get("font_size", 58)
    color = subtitle_style.get("color", "#FFFFFF")
    outline_color = subtitle_style.get("outline_color", "#000000")
    margin_bottom = 80

    for segment in lyrics:
        duration = segment["end"] - segment["start"]
        if duration <= 0:
            continue

        txt_clip = TextClip(
            text=segment["text"],
            font_size=font_size,
            color=color,
            stroke_color=outline_color,
            stroke_width=2,
            font=font_path,
            method="caption",
            size=(size[0] - 100, None),
        )
        txt_clip = txt_clip.with_duration(duration)
        txt_clip = txt_clip.with_start(segment["start"])
        txt_clip = txt_clip.with_position(("center", size[1] - margin_bottom - font_size))

        fade_duration = min(0.3, duration / 3)
        txt_clip = txt_clip.with_effects([
            vfx.CrossFadeIn(fade_duration),
            vfx.CrossFadeOut(fade_duration),
        ])

        clips.append(txt_clip)

    return clips


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

    return _create_ken_burns_clip(clip, duration, scene.get("motion", "static"), target_size)


def _create_title_card(text, size, duration=2.0):
    """Create a solid black title card with centred white text."""
    bg = ColorClip(size=size, color=(0, 0, 0), duration=duration)
    txt = TextClip(
        text=text,
        font_size=72,
        color="#FFFFFF",
        method="caption",
        size=(size[0] - 200, None),
    )
    txt = txt.with_duration(duration).with_position("center")
    return CompositeVideoClip([bg, txt], size=size)


def assemble_video(
    analysis,
    scene_plan,
    fetch_manifest,
    audio_path,
    output_path,
    resolution="1080p",
    font_path=None,
    effects_level="minimal",
    clip_start=None,
    clip_end=None,
    title_card_text=None,
):
    """Assemble the final music video.

    Args:
        analysis: Audio analysis dict from Stage 1.
        scene_plan: Scene plan dict from Stage 2.
        fetch_manifest: List of dicts with scene_index, video_path, search_query.
        audio_path: Path to the original audio file.
        output_path: Path for the output MP4 file.
        resolution: Output resolution string (720p, 1080p, 4k, portrait).
        font_path: Path to a font file for subtitles.
        effects_level: Visual effects level (none, minimal, full).
        clip_start: Start time in seconds for clip mode audio trim (None = full song).
        clip_end: End time in seconds for clip mode audio trim (None = full song).
        title_card_text: If set, a 2-second title card is prepended with this text.
    """
    target_size = _get_resolution(resolution)
    scenes = scene_plan["scenes"]

    scene_clips = []
    for manifest_entry in fetch_manifest:
        idx = manifest_entry["scene_index"]
        scene = scenes[idx]
        clip = _load_scene_clip(manifest_entry["video_path"], scene, target_size)
        clip = apply_effects(clip, level=effects_level)
        scene_clips.append(clip)

    video = concatenate_videoclips(scene_clips, method="compose")

    subtitle_clips = _create_subtitle_clips(
        analysis.get("lyrics", []),
        scene_plan.get("subtitle_style", {}),
        target_size,
        font_path=font_path,
    )

    layers = [video] + subtitle_clips

    if effects_level in ("minimal", "full"):
        bars = create_cinematic_bars(target_size[0], target_size[1], video.duration)
        layers.extend(bars)

    if effects_level == "full":
        for manifest_entry in fetch_manifest:
            idx = manifest_entry["scene_index"]
            scene = scenes[idx]
            scene_duration = scene["end"] - scene["start"]
            leak = create_light_leak(scene_duration, target_size)
            leak = leak.with_start(leak.start + scene["start"])
            leak = leak.with_end(leak.end + scene["start"])
            layers.append(leak)

    final = CompositeVideoClip(layers, size=target_size)

    # Apply video fades in clip mode
    if clip_start is not None:
        final = final.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(1.0)])

    # Prepend title card if requested
    if title_card_text:
        title_card = _create_title_card(title_card_text, target_size)
        final = concatenate_videoclips([title_card, final])

    audio = AudioFileClip(audio_path)
    if clip_start is not None:
        audio = audio.subclipped(clip_start, clip_end)
        audio = audio.with_effects([afx.AudioFadeIn(0.5), afx.AudioFadeOut(1.0)])

    final = final.with_audio(audio)
    final = final.with_duration(min(final.duration, audio.duration))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        fps=30,
    )
```

- [ ] **Step 4: Run new assembler tests**

```bash
python3 -m pytest tests/test_assembler.py::TestAssembleVideoClipMode -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: All tests pass (existing + new). If `test_no_clip_mode_no_audio_trim` flaps due to mock interaction with video subclipped calls, adjust the assertion to check that `subclipped` was not called with two float arguments that match audio clip coordinates specifically.

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: add clip_start/clip_end/title_card_text to assembler with audio trim, fades, and portrait resolution"
```

---

## Spec Coverage Self-Check

| Spec requirement | Task | Status |
|---|---|---|
| `--clip [15\|20\|25\|30]` CLI flag | Task 2 | ✅ |
| Claude selects best fragment (chorus pref, boundary rules) | Task 1 | ✅ |
| Returns start/end/reason JSON | Task 1 | ✅ |
| Stage 2 gets clip window analysis only | Task 2 (filter) | ✅ |
| Stage 3 uses separate manifest cache for clip | Task 2 (manifest_suffix) | ✅ |
| Stage 4 trims audio to clip window | Task 3 | ✅ |
| Fade in audio 0.5s, fade out audio 1.0s | Task 3 | ✅ |
| Fade in video 0.5s, fade out video 1.0s | Task 3 | ✅ |
| `--platform reels/shorts/tiktok` → portrait 9:16 | Task 2+3 | ✅ |
| Output filename `song_15s.mp4`, `song_30s_reels.mp4` | Task 2 | ✅ |
| Cache clip selection in `clip_{duration}s.json` | Task 2 | ✅ |
| Separate scene_plan cache per clip duration | Task 2 | ✅ |
| `--title-card` adds 2s title card | Task 2+3 | ✅ |
| Full song when `--clip` not provided (no change) | Task 2+3 (no-op path) | ✅ |
| `python3 -m pytest tests/ -v` passes | Every task | ✅ |
