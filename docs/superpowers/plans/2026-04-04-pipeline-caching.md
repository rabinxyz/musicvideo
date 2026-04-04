# Pipeline Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add content-addressed caching for intermediate pipeline results so stages can be skipped when the same audio file has already been processed, with a `--new` flag to force recalculation.

**Architecture:** Hash first 64KB of the audio file (MD5, truncated to 12 chars) to create a cache directory under `output/tmp/{audio_hash}/`. Before each of stages 1-3, check for cached JSON; if present (and `--new` not set), load and skip. Stage 3 additionally verifies downloaded files still exist on disk. The `--new` flag deletes the cache directory and forces full re-processing.

**Tech Stack:** Python stdlib (hashlib, json, pathlib, shutil), Click CLI, pytest

---

### Task 1: Cache utility module — `get_audio_hash`

**Files:**
- Create: `musicvid/pipeline/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cache.py
"""Tests for the pipeline cache utilities."""

import json
from pathlib import Path

from musicvid.pipeline.cache import get_audio_hash, load_cache, save_cache


class TestGetAudioHash:
    """Tests for audio file hashing."""

    def test_returns_12_char_hex_string(self, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"x" * 100_000)
        result = get_audio_hash(str(audio))
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_file_same_hash(self, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"identical content here" * 1000)
        assert get_audio_hash(str(audio)) == get_audio_hash(str(audio))

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a.mp3"
        b = tmp_path / "b.mp3"
        a.write_bytes(b"content_a" * 1000)
        b.write_bytes(b"content_b" * 1000)
        assert get_audio_hash(str(a)) != get_audio_hash(str(b))

    def test_only_reads_first_64kb(self, tmp_path):
        """Files that share the first 64KB but differ after should hash the same."""
        shared = b"A" * 65536
        a = tmp_path / "a.mp3"
        b = tmp_path / "b.mp3"
        a.write_bytes(shared + b"extra_a")
        b.write_bytes(shared + b"extra_b")
        assert get_audio_hash(str(a)) == get_audio_hash(str(b))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cache.py -v`
Expected: FAIL with ImportError (module doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

```python
# musicvid/pipeline/cache.py
"""Cache utilities for the MusicVid pipeline."""

import hashlib
import json
from pathlib import Path


def get_audio_hash(audio_path):
    """Return a 12-char hex hash of the first 64KB of the audio file."""
    with open(audio_path, "rb") as f:
        data = f.read(65536)
    return hashlib.md5(data).hexdigest()[:12]


def load_cache(cache_dir, filename):
    """Load a JSON cache file if it exists, else return None."""
    path = Path(cache_dir) / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def save_cache(cache_dir, filename, data):
    """Save data as JSON to cache_dir/filename."""
    path = Path(cache_dir) / filename
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cache.py::TestGetAudioHash -v`
Expected: 4 PASSED

- [ ] **Step 5: Write tests for load_cache and save_cache**

Add to `tests/test_cache.py`:

```python
class TestLoadCache:
    """Tests for loading cached JSON files."""

    def test_returns_none_when_missing(self, tmp_path):
        result = load_cache(str(tmp_path), "nonexistent.json")
        assert result is None

    def test_returns_data_when_exists(self, tmp_path):
        data = {"bpm": 120, "duration": 30.5}
        (tmp_path / "analysis.json").write_text(json.dumps(data))
        result = load_cache(str(tmp_path), "analysis.json")
        assert result == data


class TestSaveCache:
    """Tests for saving cache files."""

    def test_creates_file(self, tmp_path):
        save_cache(str(tmp_path), "test.json", {"key": "value"})
        assert (tmp_path / "test.json").exists()
        loaded = json.loads((tmp_path / "test.json").read_text())
        assert loaded == {"key": "value"}

    def test_creates_directory_if_missing(self, tmp_path):
        cache_dir = tmp_path / "sub" / "dir"
        save_cache(str(cache_dir), "test.json", [1, 2, 3])
        assert (cache_dir / "test.json").exists()
```

- [ ] **Step 6: Run all cache tests**

Run: `python3 -m pytest tests/test_cache.py -v`
Expected: 8 PASSED

- [ ] **Step 7: Commit**

```bash
git add musicvid/pipeline/cache.py tests/test_cache.py
git commit -m "feat: add cache utility module with audio hashing and JSON load/save"
```

---

### Task 2: Integrate caching into CLI orchestrator

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test for --new flag existence**

Add to `tests/test_cli.py`:

```python
def test_new_flag_accepted(self, runner, tmp_path):
    """The --new flag should be accepted by the CLI."""
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    result = runner.invoke(cli, [str(audio_file), "--new", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::TestCLI::test_new_flag_accepted -v`
Expected: FAIL (no such option `--new`)

- [ ] **Step 3: Write test for cache skip behavior (stage 1)**

Add to `tests/test_cli.py` (add `import json` at top if not present):

```python
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_cache_skips_stages_when_cached(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, runner, tmp_path
):
    """When cached JSON files exist, stages 1-3 should be skipped."""
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")

    from musicvid.pipeline.cache import get_audio_hash
    audio_hash = get_audio_hash(str(audio_file))

    output_dir = tmp_path / "output"
    cache_dir = output_dir / "tmp" / audio_hash
    cache_dir.mkdir(parents=True)

    analysis_data = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
        "mood_energy": "contemplative", "language": "en",
    }
    scene_plan_data = {
        "overall_style": "contemplative",
        "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "fade"},
        "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                     "visual_prompt": "test", "motion": "static",
                     "transition": "cut", "overlay": "none"}],
    }
    manifest_data = [
        {"scene_index": 0, "video_path": str(cache_dir / "videos" / "scene_000.mp4"),
         "search_query": "test"},
    ]

    # Create cached JSON files
    (cache_dir / "audio_analysis.json").write_text(json.dumps(analysis_data))
    (cache_dir / "scene_plan.json").write_text(json.dumps(scene_plan_data))
    (cache_dir / "video_manifest.json").write_text(json.dumps(manifest_data))

    # Create the referenced video file so stage 3 cache is valid
    (cache_dir / "videos").mkdir()
    (cache_dir / "videos" / "scene_000.mp4").write_bytes(b"fake video")

    result = runner.invoke(cli, [
        str(audio_file), "--output", str(output_dir),
    ])

    assert result.exit_code == 0
    # Stages 1-3 should NOT have been called
    mock_analyze.assert_not_called()
    mock_direct.assert_not_called()
    mock_fetch.assert_not_called()
    # Stage 4 always runs
    mock_assemble.assert_called_once()
    # Output should show CACHED
    assert "CACHED" in result.output
```

- [ ] **Step 4: Write test for --new flag forcing recalculation**

Add to `tests/test_cli.py`:

```python
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_new_flag_forces_recalculation(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, runner, tmp_path
):
    """The --new flag should ignore cache and run all stages."""
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")

    from musicvid.pipeline.cache import get_audio_hash
    audio_hash = get_audio_hash(str(audio_file))

    output_dir = tmp_path / "output"
    cache_dir = output_dir / "tmp" / audio_hash
    cache_dir.mkdir(parents=True)

    # Create cached files
    analysis_data = {
        "lyrics": [], "beats": [0.0], "bpm": 100.0,
        "duration": 5.0, "sections": [{"label": "verse", "start": 0.0, "end": 5.0}],
        "mood_energy": "worship", "language": "en",
    }
    (cache_dir / "audio_analysis.json").write_text(json.dumps(analysis_data))

    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
        "mood_energy": "contemplative", "language": "en",
    }
    mock_direct.return_value = {
        "overall_style": "contemplative",
        "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "fade"},
        "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                     "visual_prompt": "test", "motion": "static",
                     "transition": "cut", "overlay": "none"}],
    }
    mock_fetch.return_value = [
        {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
    ]

    result = runner.invoke(cli, [
        str(audio_file), "--output", str(output_dir), "--new",
    ])

    assert result.exit_code == 0
    # All stages should have been called despite cache
    mock_analyze.assert_called_once()
    mock_direct.assert_called_once()
    mock_fetch.assert_called_once()
    mock_assemble.assert_called_once()
```

- [ ] **Step 5: Write test for stage 3 cache invalidation when video files missing**

Add to `tests/test_cli.py`:

```python
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_stage3_cache_invalid_when_video_files_missing(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, runner, tmp_path
):
    """Stage 3 cache should be invalidated if video files no longer exist on disk."""
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")

    from musicvid.pipeline.cache import get_audio_hash
    audio_hash = get_audio_hash(str(audio_file))

    output_dir = tmp_path / "output"
    cache_dir = output_dir / "tmp" / audio_hash
    cache_dir.mkdir(parents=True)

    analysis_data = {
        "lyrics": [], "beats": [0.0], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
        "mood_energy": "contemplative", "language": "en",
    }
    scene_plan_data = {
        "overall_style": "contemplative",
        "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "fade"},
        "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                     "visual_prompt": "test", "motion": "static",
                     "transition": "cut", "overlay": "none"}],
    }
    manifest_data = [
        {"scene_index": 0, "video_path": str(cache_dir / "videos" / "scene_000.mp4"),
         "search_query": "test"},
    ]

    (cache_dir / "audio_analysis.json").write_text(json.dumps(analysis_data))
    (cache_dir / "scene_plan.json").write_text(json.dumps(scene_plan_data))
    (cache_dir / "video_manifest.json").write_text(json.dumps(manifest_data))
    # NOTE: video file intentionally NOT created — cache should be invalid

    mock_fetch.return_value = [
        {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
    ]

    result = runner.invoke(cli, [
        str(audio_file), "--output", str(output_dir),
    ])

    assert result.exit_code == 0
    # Stages 1-2 should be skipped (cached)
    mock_analyze.assert_not_called()
    mock_direct.assert_not_called()
    # Stage 3 should run because video file is missing
    mock_fetch.assert_called_once()
    mock_assemble.assert_called_once()
```

- [ ] **Step 6: Run new tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py -v -k "new_flag or cache"`
Expected: FAIL (--new option doesn't exist, cache logic not implemented)

- [ ] **Step 7: Implement caching in musicvid.py**

Replace `musicvid/musicvid.py` with:

```python
"""MusicVid CLI — Christian Music Video Generator."""

import shutil
from pathlib import Path

import click
from dotenv import load_dotenv

from musicvid.pipeline.audio_analyzer import analyze_audio
from musicvid.pipeline.cache import get_audio_hash, load_cache, save_cache
from musicvid.pipeline.director import create_scene_plan
from musicvid.pipeline.stock_fetcher import fetch_videos
from musicvid.pipeline.assembler import assemble_video


load_dotenv()


def _video_files_exist(manifest):
    """Check that all video files referenced in the manifest exist on disk."""
    return all(Path(entry["video_path"]).exists() for entry in manifest)


@click.command()
@click.argument("audio_file", type=click.Path(exists=True))
@click.option("--mode", type=click.Choice(["stock", "ai", "hybrid"]), default="stock", help="Video source mode.")
@click.option("--style", type=click.Choice(["auto", "contemplative", "joyful", "worship", "powerful"]), default="auto", help="Visual style.")
@click.option("--output", type=click.Path(), default="./output/", help="Output directory.")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p", help="Output resolution.")
@click.option("--lang", default="auto", help="Language for transcription.")
@click.option("--new", is_flag=True, default=False, help="Force recalculation, ignore cache.")
def cli(audio_file, mode, style, output, resolution, lang, new):
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

    # Stage 1: Analyze Audio
    analysis = load_cache(str(cache_dir), "audio_analysis.json") if not new else None
    if analysis:
        click.echo("[1/4] Audio analysis... CACHED (skipped)")
    else:
        click.echo("[1/4] Analyzing audio...")
        analysis = analyze_audio(str(audio_path), output_dir=str(cache_dir))
        save_cache(str(cache_dir), "audio_analysis.json", analysis)
    click.echo(f"  BPM: {analysis['bpm']}, Duration: {analysis['duration']}s, "
               f"Sections: {len(analysis['sections'])}, Mood: {analysis['mood_energy']}")

    # Stage 2: Direct Scenes
    style_override = style if style != "auto" else None
    scene_plan = load_cache(str(cache_dir), "scene_plan.json") if not new else None
    if scene_plan:
        click.echo("[2/4] Scene planning... CACHED (skipped)")
    else:
        click.echo("[2/4] Creating scene plan...")
        scene_plan = create_scene_plan(analysis, style_override=style_override, output_dir=str(cache_dir))
        save_cache(str(cache_dir), "scene_plan.json", scene_plan)
    click.echo(f"  Style: {scene_plan['overall_style']}, Scenes: {len(scene_plan['scenes'])}")

    # Stage 3: Fetch Videos
    fetch_manifest = load_cache(str(cache_dir), "video_manifest.json") if not new else None
    if fetch_manifest and _video_files_exist(fetch_manifest):
        click.echo("[3/4] Fetching videos... CACHED (skipped)")
    else:
        click.echo("[3/4] Fetching stock videos...")
        fetch_manifest = fetch_videos(scene_plan, output_dir=str(cache_dir))
        save_cache(str(cache_dir), "video_manifest.json", fetch_manifest)
    fetched = sum(1 for f in fetch_manifest if f["video_path"].endswith(".mp4"))
    click.echo(f"  Fetched: {fetched}/{len(fetch_manifest)} videos")

    # Stage 4: Assemble Video
    click.echo("[4/4] Assembling video...")
    output_filename = audio_path.stem + "_musicvideo.mp4"
    output_path = str(output_dir / output_filename)
    assemble_video(
        analysis=analysis,
        scene_plan=scene_plan,
        fetch_manifest=fetch_manifest,
        audio_path=str(audio_path),
        output_path=output_path,
        resolution=resolution,
    )
    click.echo(f"  Done! Output: {output_path}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 8: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 9: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add pipeline caching with --new flag to force recalculation"
```

---

### Task 3: Update existing CLI test for new tmp_dir structure

**Files:**
- Modify: `tests/test_cli.py`

The existing `test_full_pipeline_integration` test passes `output_dir` but the new code creates `tmp/{audio_hash}/` inside it. The existing test mocks all pipeline functions, so it should still pass since the mocked functions don't actually check the `output_dir` argument. However, verify and fix if needed.

- [ ] **Step 1: Run existing tests to verify nothing is broken**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: If any test fails, fix it and re-run**

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add tests/test_cli.py
git commit -m "fix: update existing CLI tests for new cache directory structure"
```
