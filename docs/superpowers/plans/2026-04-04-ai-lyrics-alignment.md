# AI Lyrics Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align correct lyrics text from a file to Whisper timing using Claude API, so subtitles have correct text with accurate timing.

**Architecture:** New function `align_with_claude()` in `lyrics_parser.py` calls Claude API to match file lines to Whisper segments by semantic similarity. The CLI (`musicvid.py`) is updated to call this when a lyrics file is present, caching the result as `lyrics_aligned_{lyrics_hash}.json`. The existing `parse_lyrics()` flow (variant A/B) is replaced by the alignment flow when both Whisper segments and a lyrics file are available.

**Tech Stack:** Python, `anthropic` SDK (Claude API), `tenacity` (retry), `json` (parsing)

---

### Task 1: Add `align_with_claude` function with tests

**Files:**
- Modify: `musicvid/pipeline/lyrics_parser.py`
- Create: `tests/test_lyrics_alignment.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lyrics_alignment.py` with tests for the `align_with_claude` function:

```python
"""Tests for AI lyrics alignment using Claude API."""

import json
from unittest.mock import patch, MagicMock

import pytest

from musicvid.pipeline.lyrics_parser import align_with_claude


class TestAlignWithClaude:
    """Tests for align_with_claude function."""

    def _make_mock_response(self, content):
        """Helper to create a mock Claude API response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=content)]
        return mock_response

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_equal_segments_and_lines(self, mock_anthropic):
        """When N_segments == N_lines, each line maps to one segment."""
        whisper_segments = [
            {"start": 0.5, "end": 2.0, "text": "Amezing grejz hau swit de saund"},
            {"start": 2.5, "end": 4.0, "text": "Det sejwd a recz lajk mi"},
        ]
        file_lines = [
            "Amazing grace how sweet the sound",
            "That saved a wretch like me",
        ]
        expected = [
            {"start": 0.5, "end": 2.0, "text": "Amazing grace how sweet the sound"},
            {"start": 2.5, "end": 4.0, "text": "That saved a wretch like me"},
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(expected))

        result = align_with_claude(whisper_segments, file_lines)

        assert result == expected
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["max_tokens"] == 2000

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_more_segments_than_lines_merges(self, mock_anthropic):
        """When N_segments > N_lines, Claude merges segments."""
        whisper_segments = [
            {"start": 0.0, "end": 1.0, "text": "seg1"},
            {"start": 1.0, "end": 2.0, "text": "seg2"},
            {"start": 2.0, "end": 3.0, "text": "seg3"},
        ]
        file_lines = ["Line one", "Line two"]
        merged = [
            {"start": 0.0, "end": 2.0, "text": "Line one"},
            {"start": 2.0, "end": 3.0, "text": "Line two"},
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(merged))

        result = align_with_claude(whisper_segments, file_lines)

        assert result == merged

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_more_lines_than_segments_splits(self, mock_anthropic):
        """When N_lines > N_segments, Claude splits time for extra lines."""
        whisper_segments = [
            {"start": 0.0, "end": 2.0, "text": "seg1"},
        ]
        file_lines = ["Line one", "Line two", "Line three"]
        split = [
            {"start": 0.0, "end": 2.0, "text": "Line one"},
            {"start": 2.0, "end": 3.0, "text": "Line two"},
            {"start": 3.0, "end": 4.0, "text": "Line three"},
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(split))

        result = align_with_claude(whisper_segments, file_lines)

        assert result == split

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_empty_segments_filtered(self, mock_anthropic):
        """Empty Whisper segments (text.strip()=='') should be filtered before sending."""
        whisper_segments = [
            {"start": 0.0, "end": 1.0, "text": "  "},
            {"start": 1.0, "end": 2.0, "text": "actual text"},
        ]
        file_lines = ["Correct text"]
        expected = [{"start": 1.0, "end": 2.0, "text": "Correct text"}]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(expected))

        result = align_with_claude(whisper_segments, file_lines)

        assert result == expected
        # Verify only non-empty segments were sent in the prompt
        call_kwargs = mock_client.messages.create.call_args[1]
        user_msg = call_kwargs["messages"][0]["content"]
        assert "actual text" in user_msg
        assert '"  "' not in user_msg

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_validates_response_format(self, mock_anthropic):
        """Response missing required keys should raise ValueError."""
        whisper_segments = [{"start": 0.0, "end": 1.0, "text": "seg"}]
        file_lines = ["Line"]
        bad_response = [{"start": 0.0, "text": "Line"}]  # missing "end"

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(bad_response))

        with pytest.raises(ValueError, match="missing required key"):
            align_with_claude(whisper_segments, file_lines)

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_json_parse_error_retries_then_raises(self, mock_anthropic):
        """Invalid JSON should retry up to 2 times, then raise ValueError."""
        whisper_segments = [{"start": 0.0, "end": 1.0, "text": "seg"}]
        file_lines = ["Line"]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response("not valid json {{{")

        with pytest.raises(ValueError, match="Failed to parse"):
            align_with_claude(whisper_segments, file_lines)

        # Should have been called 2 times (initial + 1 retry)
        assert mock_client.messages.create.call_count == 2

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_prompt_contains_whisper_segments_and_file_lines(self, mock_anthropic):
        """Verify the prompt includes both Whisper segments and file lines."""
        whisper_segments = [{"start": 0.5, "end": 2.0, "text": "Whisper text here"}]
        file_lines = ["Correct lyrics text"]
        expected = [{"start": 0.5, "end": 2.0, "text": "Correct lyrics text"}]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(expected))

        align_with_claude(whisper_segments, file_lines)

        call_kwargs = mock_client.messages.create.call_args[1]
        user_msg = call_kwargs["messages"][0]["content"]
        system_msg = call_kwargs["system"]

        assert "Whisper text here" in user_msg
        assert "Correct lyrics text" in user_msg
        assert "JSON" in system_msg

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_strips_markdown_code_block_from_response(self, mock_anthropic):
        """If Claude wraps response in ```json...```, strip it."""
        whisper_segments = [{"start": 0.0, "end": 1.0, "text": "seg"}]
        file_lines = ["Line"]
        expected = [{"start": 0.0, "end": 1.0, "text": "Line"}]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        wrapped = '```json\n' + json.dumps(expected) + '\n```'
        mock_client.messages.create.return_value = self._make_mock_response(wrapped)

        result = align_with_claude(whisper_segments, file_lines)

        assert result == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_lyrics_alignment.py -v`
Expected: FAIL with `ImportError: cannot import name 'align_with_claude'`

- [ ] **Step 3: Implement `align_with_claude` in lyrics_parser.py**

Add imports at the top of `musicvid/pipeline/lyrics_parser.py`:

```python
import json

import anthropic
from tenacity import retry, stop_after_attempt, retry_if_exception_type
```

Add the function after the existing code:

```python
def align_with_claude(whisper_segments, file_lines):
    """Align correct lyrics text to Whisper timing using Claude API.

    Args:
        whisper_segments: list of dicts with start/end/text from Whisper.
        file_lines: list of correct lyrics strings (already filtered).

    Returns:
        list[dict] with keys: start (float), end (float), text (str).

    Raises:
        ValueError: If Claude returns invalid JSON after 2 attempts,
                    or if response items are missing required keys.
    """
    # Filter empty Whisper segments
    filtered_segments = [
        {"start": s["start"], "end": s["end"], "text": s["text"]}
        for s in whisper_segments if s["text"].strip()
    ]

    system_prompt = (
        "Jesteś asystentem do synchronizacji tekstu piosenek.\n"
        "Zwracaj WYŁĄCZNIE czysty JSON, bez markdown, bez komentarzy."
    )

    user_prompt = (
        "Mam transkrypcję Whisper (niedokładną) i poprawny tekst piosenki.\n"
        "Dopasuj każdą linię poprawnego tekstu do segmentu Whisper który\n"
        "najbardziej jej odpowiada — na podstawie podobieństwa brzmienia,\n"
        "kolejności w piosence i kontekstu.\n\n"
        "Zasady:\n"
        "- Zachowaj kolejność — linie z pliku pojawiają się w tej samej kolejności co w piosence\n"
        "- Każda linia z pliku musi być przypisana do dokładnie jednego segmentu Whisper\n"
        "- Jeśli jest więcej segmentów Whisper niż linii w pliku — scal sąsiednie segmenty\n"
        "  (użyj start pierwszego i end ostatniego segmentu w grupie)\n"
        "- Jeśli jest więcej linii w pliku niż segmentów Whisper — podziel dostępny\n"
        "  czas równomiernie dla nadmiarowych linii po ostatnim segmencie\n"
        "- Puste linie w pliku są już usunięte — ignoruj je\n\n"
        f"Segmenty Whisper (z niedokładnym tekstem):\n{json.dumps(filtered_segments, ensure_ascii=False)}\n\n"
        f"Poprawne linie z pliku:\n{json.dumps(file_lines, ensure_ascii=False)}\n\n"
        'Zwróć JSON:\n[{"start": float, "end": float, "text": "poprawna linia z pliku"}]'
    )

    last_error = None
    for attempt in range(2):
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            last_error = e
            continue

        # Validate structure
        for item in result:
            for key in ("start", "end", "text"):
                if key not in item:
                    raise ValueError(f"Alignment result missing required key: {key}")

        return result

    raise ValueError(f"Failed to parse Claude alignment response after 2 attempts: {last_error}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_lyrics_alignment.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/lyrics_parser.py tests/test_lyrics_alignment.py
git commit -m "feat: add align_with_claude for AI lyrics alignment"
```

---

### Task 2: Integrate alignment into CLI with caching

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add new test class in `tests/test_cli.py`:

```python
class TestAILyricsAlignment:
    """Tests for AI lyrics alignment integration in CLI."""

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.align_with_claude")
    def test_lyrics_file_triggers_alignment(
        self, mock_align, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """When --lyrics is provided, align_with_claude should be called."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Correct line one\nCorrect line two\n")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 0.5, "end": 2.0, "text": "whisper text 1", "words": []},
                {"start": 2.5, "end": 4.0, "text": "whisper text 2", "words": []},
            ],
            "beats": [0.0], "bpm": 120.0, "duration": 10.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_align.return_value = [
            {"start": 0.5, "end": 2.0, "text": "Correct line one"},
            {"start": 2.5, "end": 4.0, "text": "Correct line two"},
        ]
        mock_direct.return_value = {
            "overall_style": "contemplative", "color_palette": ["#aaa"],
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
        mock_align.assert_called_once()
        # Verify aligned lyrics were passed to assembler
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["analysis"]["lyrics"][0]["text"] == "Correct line one"

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.align_with_claude")
    def test_alignment_result_cached(
        self, mock_align, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """Second run with same lyrics should use cached alignment."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\nLine two\n")

        mock_analyze.return_value = {
            "lyrics": [
                {"start": 0.5, "end": 2.0, "text": "w1", "words": []},
                {"start": 2.5, "end": 4.0, "text": "w2", "words": []},
            ],
            "beats": [0.0], "bpm": 120.0, "duration": 10.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_align.return_value = [
            {"start": 0.5, "end": 2.0, "text": "Line one"},
            {"start": 2.5, "end": 4.0, "text": "Line two"},
        ]
        mock_direct.return_value = {
            "overall_style": "contemplative", "color_palette": ["#aaa"],
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

        # Second run — alignment should be cached
        mock_align.reset_mock()
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--lyrics", str(lyrics_file),
        ])
        assert result.exit_code == 0
        mock_align.assert_not_called()
        assert "AI dopasowanie" in result.output

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_no_lyrics_file_uses_whisper(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """Without lyrics file, Whisper lyrics should be used as-is."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [{"start": 0.0, "end": 5.0, "text": "Whisper text", "words": []}],
            "beats": [0.0], "bpm": 120.0, "duration": 10.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative", "color_palette": ["#aaa"],
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
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["analysis"]["lyrics"][0]["text"] == "Whisper text"

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.align_with_claude")
    def test_alignment_log_message(
        self, mock_align, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
    ):
        """CLI should display alignment log message with line count."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\nLine two\nLine three\n")

        mock_analyze.return_value = {
            "lyrics": [{"start": 0.0, "end": 3.0, "text": "w", "words": []}],
            "beats": [0.0], "bpm": 120.0, "duration": 10.0,
            "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_align.return_value = [
            {"start": 0.0, "end": 1.0, "text": "Line one"},
            {"start": 1.0, "end": 2.0, "text": "Line two"},
            {"start": 2.0, "end": 3.0, "text": "Line three"},
        ]
        mock_direct.return_value = {
            "overall_style": "contemplative", "color_palette": ["#aaa"],
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
        assert "Whisper timing + AI dopasowanie" in result.output
        assert "3 linii" in result.output
```

- [ ] **Step 2: Run new CLI tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py::TestAILyricsAlignment -v`
Expected: FAIL with `ImportError` (align_with_claude not imported in musicvid.py)

- [ ] **Step 3: Update musicvid.py to use alignment**

In `musicvid/musicvid.py`, add the import:

```python
from musicvid.pipeline.lyrics_parser import align_with_claude
```

Replace the lyrics handling block (lines 87-95) with:

```python
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
```

- [ ] **Step 4: Run new CLI tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py::TestAILyricsAlignment -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Update existing lyrics CLI tests**

The existing `TestLyricsFlag` tests mock `parse_lyrics` behavior. Some tests need updating since the flow now uses `align_with_claude` instead of `parse_lyrics` when a lyrics file is present.

Update `test_lyrics_flag_skips_whisper` to also mock `align_with_claude`:
- Add `@patch("musicvid.musicvid.align_with_claude")` decorator
- Set `mock_align.return_value` to aligned lyrics list
- Verify `mock_align` was called and result was used

Update `test_auto_detect_single_txt` similarly.

Update `test_lyrics_hash_invalidates_cache` to also mock `align_with_claude`.

- [ ] **Step 6: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: integrate AI lyrics alignment into CLI with caching"
```
