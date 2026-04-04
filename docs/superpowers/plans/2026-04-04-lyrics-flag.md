# --lyrics Flag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--lyrics PATH` CLI flag with auto-detection of .txt files, a lyrics file parser supporting plain text and timestamped formats, and cache integration — skipping Whisper when lyrics are available.

**Architecture:** New `lyrics_parser.py` module handles file parsing (variant A: equal segments, variant B: timestamps). CLI gains `--lyrics` option and auto-detection logic in a helper function. The parsed lyrics replace Whisper output in the analysis dict before caching. Lyrics file MD5 hash is included in the cache key for `audio_analysis.json`.

**Tech Stack:** Python 3.11+, Click CLI, hashlib MD5, re (regex for timestamp parsing), pytest + unittest.mock

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `musicvid/pipeline/lyrics_parser.py` | Create | Parse .txt lyrics files (variant A + B), return `list[dict]` |
| `musicvid/musicvid.py` | Modify | Add `--lyrics` flag, auto-detection, integrate parser, update cache key |
| `tests/test_lyrics_parser.py` | Create | Unit tests for lyrics_parser module |
| `tests/test_cli.py` | Modify | CLI integration tests for `--lyrics` flag and auto-detection |

---

### Task 1: Lyrics Parser — Variant A (plain text, no timestamps)

**Files:**
- Create: `tests/test_lyrics_parser.py`
- Create: `musicvid/pipeline/lyrics_parser.py`

- [ ] **Step 1: Write failing tests for variant A**

```python
"""Tests for the lyrics parser module."""

import pytest

from musicvid.pipeline.lyrics_parser import parse


class TestVariantA:
    """Variant A: lines without timestamps, evenly distributed."""

    def test_four_lines_60s_audio(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\nLine two\nLine three\nLine four\n")
        result = parse(str(lyrics_file), 60.0)
        assert len(result) == 4
        assert result[0] == {"start": 0.0, "end": 14.7, "text": "Line one"}
        assert result[1] == {"start": 15.0, "end": 29.7, "text": "Line two"}
        assert result[2] == {"start": 30.0, "end": 44.7, "text": "Line three"}
        assert result[3] == {"start": 45.0, "end": 59.7, "text": "Line four"}

    def test_single_line(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Only line\n")
        result = parse(str(lyrics_file), 10.0)
        assert len(result) == 1
        assert result[0] == {"start": 0.0, "end": 9.7, "text": "Only line"}

    def test_blank_lines_are_skipped(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\n\nLine two\n\n")
        result = parse(str(lyrics_file), 20.0)
        assert len(result) == 2
        assert result[0]["text"] == "Line one"
        assert result[1]["text"] == "Line two"

    def test_empty_file_raises_value_error(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("")
        with pytest.raises(ValueError, match="empty"):
            parse(str(lyrics_file), 60.0)

    def test_whitespace_only_file_raises_value_error(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("   \n  \n")
        with pytest.raises(ValueError, match="empty"):
            parse(str(lyrics_file), 60.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_lyrics_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'musicvid.pipeline.lyrics_parser'`

- [ ] **Step 3: Implement lyrics_parser with variant A support**

```python
"""Lyrics file parser — reads .txt files and returns timed lyrics segments."""

import re


_TIMESTAMP_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s+(.+)$")


def _parse_timestamp(match):
    """Convert regex match to seconds."""
    groups = match.groups()
    if groups[2] is not None:
        # HH:MM:SS
        return int(groups[0]) * 3600 + int(groups[1]) * 60 + int(groups[2])
    else:
        # MM:SS
        return int(groups[0]) * 60 + int(groups[1])


def parse(lyrics_path, audio_duration):
    """Parse a lyrics .txt file and return timed segments.

    Args:
        lyrics_path: Path to the .txt lyrics file.
        audio_duration: Total audio duration in seconds.

    Returns:
        list[dict] with keys: start (float), end (float), text (str).

    Raises:
        ValueError: If the file is empty or contains only whitespace.
    """
    with open(lyrics_path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    lines = [line.strip() for line in raw_lines if line.strip()]

    if not lines:
        raise ValueError(f"Lyrics file is empty: {lyrics_path}")

    # Detect variant from first non-empty line
    first_match = _TIMESTAMP_RE.match(lines[0])
    if first_match:
        return _parse_variant_b(lines, audio_duration)
    else:
        return _parse_variant_a(lines, audio_duration)


def _parse_variant_a(lines, audio_duration):
    """Variant A: no timestamps — distribute evenly across audio duration."""
    count = len(lines)
    segment = audio_duration / count
    result = []
    for i, text in enumerate(lines):
        start = round(i * segment, 1)
        end = round((i + 1) * segment - 0.3, 1)
        result.append({"start": start, "end": end, "text": text})
    return result


def _parse_variant_b(lines, audio_duration):
    """Variant B: lines prefixed with MM:SS or HH:MM:SS timestamps."""
    entries = []
    for line in lines:
        match = _TIMESTAMP_RE.match(line)
        if not match:
            continue
        timestamp = float(_parse_timestamp(match))
        text = match.group(4).strip()
        entries.append({"timestamp": timestamp, "text": text})

    result = []
    for i, entry in enumerate(entries):
        start = entry["timestamp"]
        if i + 1 < len(entries):
            end = round(entries[i + 1]["timestamp"] - 0.3, 1)
        else:
            end = round(audio_duration - 1.0, 1)
        result.append({"start": start, "end": end, "text": entry["text"]})
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_lyrics_parser.py::TestVariantA -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/lyrics_parser.py tests/test_lyrics_parser.py
git commit -m "feat: add lyrics_parser with variant A (plain text) support"
```

---

### Task 2: Lyrics Parser — Variant B (timestamps)

**Files:**
- Modify: `tests/test_lyrics_parser.py`

- [ ] **Step 1: Write failing tests for variant B**

Add to `tests/test_lyrics_parser.py`:

```python
class TestVariantB:
    """Variant B: lines with MM:SS or HH:MM:SS timestamps."""

    def test_mm_ss_format(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("0:00 First line\n0:30 Second line\n1:00 Third line\n")
        result = parse(str(lyrics_file), 90.0)
        assert len(result) == 3
        assert result[0] == {"start": 0.0, "end": 29.7, "text": "First line"}
        assert result[1] == {"start": 30.0, "end": 59.7, "text": "Second line"}
        assert result[2] == {"start": 60.0, "end": 89.0, "text": "Third line"}

    def test_hh_mm_ss_format(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("0:00:00 Opening\n0:01:30 Middle\n0:03:00 End\n")
        result = parse(str(lyrics_file), 240.0)
        assert len(result) == 3
        assert result[0] == {"start": 0.0, "end": 89.7, "text": "Opening"}
        assert result[1] == {"start": 90.0, "end": 179.7, "text": "Middle"}
        assert result[2] == {"start": 180.0, "end": 239.0, "text": "End"}

    def test_last_line_ends_at_duration_minus_one(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("0:00 Only line\n")
        result = parse(str(lyrics_file), 60.0)
        assert len(result) == 1
        assert result[0]["end"] == 59.0

    def test_two_digit_minutes(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("00:00 Start\n12:30 Later\n")
        result = parse(str(lyrics_file), 800.0)
        assert result[0]["start"] == 0.0
        assert result[1]["start"] == 750.0
```

- [ ] **Step 2: Run tests to verify they pass (variant B already implemented in Task 1)**

Run: `python3 -m pytest tests/test_lyrics_parser.py::TestVariantB -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_lyrics_parser.py
git commit -m "test: add variant B (timestamp) tests for lyrics_parser"
```

---

### Task 3: CLI --lyrics flag and auto-detection

**Files:**
- Modify: `musicvid/musicvid.py:1-123`
- Create (append): `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for --lyrics flag and auto-detection**

Add to `tests/test_cli.py`:

```python
class TestLyricsFlag:
    """Tests for --lyrics CLI option and auto-detection."""

    def test_lyrics_flag_accepted(self, runner, tmp_path):
        """The --lyrics flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--lyrics", str(tmp_path / "lyrics.txt"), "--help"])
        assert result.exit_code == 0

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_lyrics_flag_skips_whisper(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """When --lyrics is provided, Whisper is skipped and lyrics come from file."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\nLine two\n")

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

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])

        assert result.exit_code == 0
        # Lyrics should have been replaced in the analysis passed to assembler
        call_kwargs = mock_assemble.call_args[1]
        analysis_used = call_kwargs["analysis"]
        assert len(analysis_used["lyrics"]) == 2
        assert analysis_used["lyrics"][0]["text"] == "Line one"

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_auto_detect_single_txt(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """When exactly one .txt exists in audio dir, use it automatically."""
        audio_dir = tmp_path / "music"
        audio_dir.mkdir()
        audio_file = audio_dir / "song.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = audio_dir / "lyrics.txt"
        lyrics_file.write_text("Auto line one\nAuto line two\n")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0], "bpm": 120.0,
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

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [str(audio_file), "--output", str(output_dir)])

        assert result.exit_code == 0
        assert "lyrics.txt" in result.output
        call_kwargs = mock_assemble.call_args[1]
        analysis_used = call_kwargs["analysis"]
        assert len(analysis_used["lyrics"]) == 2
        assert analysis_used["lyrics"][0]["text"] == "Auto line one"

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_auto_detect_multiple_txt_uses_whisper(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """When multiple .txt files exist, ignore auto-detection and use Whisper."""
        audio_dir = tmp_path / "music"
        audio_dir.mkdir()
        audio_file = audio_dir / "song.mp3"
        audio_file.write_bytes(b"fake audio")
        (audio_dir / "a.txt").write_text("A")
        (audio_dir / "b.txt").write_text("B")

        mock_analyze.return_value = {
            "lyrics": [{"start": 0.0, "end": 5.0, "text": "Whisper text", "words": []}],
            "beats": [0.0], "bpm": 120.0,
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

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [str(audio_file), "--output", str(output_dir)])

        assert result.exit_code == 0
        # Should warn about multiple txt files
        assert "--lyrics" in result.output
        # Whisper lyrics should be used (not replaced)
        call_kwargs = mock_assemble.call_args[1]
        analysis_used = call_kwargs["analysis"]
        assert analysis_used["lyrics"][0]["text"] == "Whisper text"

    def test_lyrics_flag_missing_file(self, runner, tmp_path):
        """--lyrics with a nonexistent file should give a clear error."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        result = runner.invoke(cli, [
            str(audio_file), "--lyrics", str(tmp_path / "nonexistent.txt"),
        ])

        assert result.exit_code != 0
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py::TestLyricsFlag -v`
Expected: FAIL — no `--lyrics` option

- [ ] **Step 3: Implement --lyrics flag and auto-detection in CLI**

Modify `musicvid/musicvid.py`:

1. Add import at top:
```python
from musicvid.pipeline.lyrics_parser import parse as parse_lyrics
```

2. Add helper function before `cli()`:
```python
def _detect_lyrics_file(audio_path):
    """Auto-detect a single .txt file in the same directory as the audio file."""
    audio_dir = Path(audio_path).parent
    txt_files = sorted(audio_dir.glob("*.txt"))
    if len(txt_files) == 1:
        return txt_files[0]
    elif len(txt_files) > 1:
        return None  # caller handles warning
    return None


def _get_lyrics_hash(lyrics_path):
    """Return MD5 hex digest of lyrics file content."""
    import hashlib
    with open(lyrics_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:12]
```

3. Add `--lyrics` option to CLI decorator:
```python
@click.option("--lyrics", "lyrics_path", type=click.Path(), default=None, help="Path to .txt lyrics file (skips Whisper).")
```

4. Update `cli()` signature to include `lyrics_path`.

5. After `cache_dir` setup and before Stage 1, add lyrics detection and handling:
```python
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
        click.echo("  ⚠ Znaleziono wiele plików .txt — użyj --lyrics aby wybrać")
```

6. In Stage 1, after getting `analysis` (whether from cache or `analyze_audio`), if `lyrics_file` is set, replace lyrics:
```python
    if lyrics_file:
        from musicvid.pipeline.lyrics_parser import parse as parse_lyrics
        parsed_lyrics = parse_lyrics(str(lyrics_file), analysis["duration"])
        analysis["lyrics"] = parsed_lyrics
        line_count = len(parsed_lyrics)
        if lyrics_path:
            click.echo(f"[1/4] Tekst: wczytano z pliku ({line_count} linijek)")
        else:
            click.echo(f"[1/4] Tekst: znaleziono automatycznie → {lyrics_file.name} ({line_count} linijek)")
```

- [ ] **Step 4: Run all tests**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: All tests PASS (old + new)

- [ ] **Step 5: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add --lyrics CLI flag with auto-detection and parser integration"
```

---

### Task 4: Cache integration — lyrics hash in cache key

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for cache invalidation on lyrics change**

Add to `tests/test_cli.py` in `TestLyricsFlag`:

```python
    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_lyrics_hash_in_cache(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """When --lyrics is provided, lyrics file hash should affect cache."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\nLine two\n")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0], "bpm": 120.0,
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

        output_dir = tmp_path / "output"
        # First run
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])
        assert result.exit_code == 0

        # Modify lyrics file
        lyrics_file.write_text("Changed line\n")
        mock_analyze.reset_mock()

        # Second run — audio_analysis cache should be invalidated because lyrics hash changed
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])
        assert result.exit_code == 0
        # analyze_audio should be called again because lyrics hash changed
        mock_analyze.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::TestLyricsFlag::test_lyrics_hash_in_cache -v`
Expected: FAIL — second run uses cached analysis, `mock_analyze` not called

- [ ] **Step 3: Implement lyrics hash in cache**

In `musicvid/musicvid.py`, modify the cache logic for Stage 1. After resolving `lyrics_file`, compute a lyrics hash and include it in the cache filename:

```python
    # Compute lyrics hash for cache invalidation
    lyrics_hash = None
    if lyrics_file:
        lyrics_hash = _get_lyrics_hash(str(lyrics_file))

    # Stage 1: Analyze Audio
    analysis_cache_name = "audio_analysis.json"
    if lyrics_hash:
        analysis_cache_name = f"audio_analysis_{lyrics_hash}.json"

    analysis = load_cache(str(cache_dir), analysis_cache_name) if not new else None
    if analysis:
        click.echo("[1/4] Audio analysis... CACHED (skipped)")
    else:
        click.echo("[1/4] Analyzing audio...")
        analysis = analyze_audio(str(audio_path), output_dir=str(cache_dir))
        save_cache(str(cache_dir), analysis_cache_name, analysis)
```

- [ ] **Step 4: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: include lyrics file hash in cache key for invalidation"
```

---

### Task 5: Final integration verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (original 65 + new tests)

- [ ] **Step 2: Verify CLI help shows --lyrics option**

Run: `python3 -m musicvid.musicvid --help`
Expected: Output includes `--lyrics PATH` with description

- [ ] **Step 3: Commit if any fixes needed**

Only commit if fixes were made in previous steps.
