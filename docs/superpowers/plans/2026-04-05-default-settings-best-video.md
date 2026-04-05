# Default Settings for Best Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `python3 -m musicvid.musicvid song.mp3` produce the most professional video by default, adding startup summary, --quick/--economy shortcuts, graceful API fallbacks, and wiring through --lut-style/--transitions/--subtitle-style/--beat-sync CLI options.

**Architecture:** All changes are confined to `musicvid/musicvid.py` (CLI layer only). New CLI flags are added and passed to existing pipeline functions. The assembler already supports `lut_style`/`lut_intensity` — they just need to be wired. `--transitions` and `--subtitle-style` override fields in the `scene_plan` dict before assembly. `--beat-sync auto` realigns scene boundaries to nearest beat positions after the director stage.

**Tech Stack:** Python 3.11+, Click, existing `musicvid` pipeline (assembler, director, color_grade)

---

## File Map

| File | Change |
|------|--------|
| `musicvid/musicvid.py` | All changes: new CLI options, defaults, summary, fallbacks, quick/economy |
| `tests/test_cli.py` | New tests for new flags, summary, fallbacks, quick/economy |

No new files. No assembler changes (it already supports `lut_style`).

---

### Task 1: Change existing defaults and add new CLI flags

**Files:**
- Modify: `musicvid/musicvid.py:113-135`
- Test: `tests/test_cli.py`

The following changes to the `@click.command()` decorator:
- `--mode` default: `"stock"` → `"ai"`
- `--preset` default: `None` → `"all"`
- Add `--lut-style`: `type=click.Choice(["warm","cold","cinematic","natural","faded"])`, `default="warm"`
- Add `--lut-intensity`: `type=float`, `default=0.85`
- Add `--subtitle-style`: `type=click.Choice(["fade","karaoke","none"])`, `default="karaoke"`
- Add `--transitions`: `type=click.Choice(["cut","auto"])`, `default="auto"`
- Add `--beat-sync`: `type=click.Choice(["off","auto"])`, `default="auto"`
- Add `--yes`: `is_flag=True`, `default=False`, help: "Skip confirmation prompt."
- Add `--quick`: `is_flag=True`, `default=False`, help: "Quick mode: stock images, no animation, no LUT, cut transitions."
- Add `--economy`: `is_flag=True`, `default=False`, help: "Economy mode: flux-dev images, no Runway animation, warm LUT."

- [ ] **Step 1: Write failing tests for new CLI flags**

```python
# In tests/test_cli.py, add to class TestCLI:

def test_lut_style_flag_accepted(self, runner, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake")
    result = runner.invoke(cli, [str(audio_file), "--lut-style", "warm", "--help"])
    assert result.exit_code == 0

def test_subtitle_style_flag_accepted(self, runner, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake")
    result = runner.invoke(cli, [str(audio_file), "--subtitle-style", "karaoke", "--help"])
    assert result.exit_code == 0

def test_transitions_flag_accepted(self, runner, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake")
    result = runner.invoke(cli, [str(audio_file), "--transitions", "cut", "--help"])
    assert result.exit_code == 0

def test_beat_sync_flag_accepted(self, runner, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake")
    result = runner.invoke(cli, [str(audio_file), "--beat-sync", "auto", "--help"])
    assert result.exit_code == 0

def test_yes_flag_accepted(self, runner, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake")
    result = runner.invoke(cli, [str(audio_file), "--yes", "--help"])
    assert result.exit_code == 0

def test_quick_flag_accepted(self, runner, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake")
    result = runner.invoke(cli, [str(audio_file), "--quick", "--help"])
    assert result.exit_code == 0

def test_economy_flag_accepted(self, runner, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake")
    result = runner.invoke(cli, [str(audio_file), "--economy", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_cli.py::TestCLI::test_lut_style_flag_accepted tests/test_cli.py::TestCLI::test_subtitle_style_flag_accepted tests/test_cli.py::TestCLI::test_transitions_flag_accepted tests/test_cli.py::TestCLI::test_beat_sync_flag_accepted tests/test_cli.py::TestCLI::test_yes_flag_accepted tests/test_cli.py::TestCLI::test_quick_flag_accepted tests/test_cli.py::TestCLI::test_economy_flag_accepted -v
```
Expected: FAIL with "No such option"

- [ ] **Step 3: Add new CLI options and change defaults in musicvid.py**

Replace the `@click.command()` block (lines 113–135) with:

```python
@click.command()
@click.argument("audio_file", type=click.Path(exists=True))
@click.option("--mode", type=click.Choice(["stock", "ai", "hybrid"]), default="ai", help="Video source mode.")
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
@click.option("--animate", "animate_mode", type=click.Choice(["auto", "always", "never"]), default="auto", help="Animated video via Runway Gen-4.")
@click.option("--preset", type=click.Choice(["full", "social", "all"]), default="all", help="Preset mode: full (YouTube), social (3 reels), all (both).")
@click.option("--reel-duration", type=click.Choice(["15", "20", "30"]), default="15", help="Duration of social media reels in seconds.")
@click.option("--logo", "logo_path", type=click.Path(), default=None, help="Path to logo file (SVG/PNG) to overlay on video.")
@click.option("--logo-position", type=click.Choice(["top-left", "top-right", "bottom-left", "bottom-right"]), default="top-left", help="Logo position on screen.")
@click.option("--logo-size", type=int, default=None, help="Logo width in pixels (default: auto 12%% of frame width).")
@click.option("--logo-opacity", type=float, default=0.85, help="Logo opacity 0.0-1.0.")
@click.option("--lut-style", type=click.Choice(["warm", "cold", "cinematic", "natural", "faded"]), default="warm", help="Built-in LUT color grade style.")
@click.option("--lut-intensity", type=float, default=0.85, help="LUT intensity 0.0-1.0.")
@click.option("--subtitle-style", "subtitle_style_override", type=click.Choice(["fade", "karaoke", "none"]), default="karaoke", help="Subtitle animation style.")
@click.option("--transitions", "transitions_mode", type=click.Choice(["cut", "auto"]), default="auto", help="Scene transition style (auto: director decides, cut: force hard cuts).")
@click.option("--beat-sync", "beat_sync", type=click.Choice(["off", "auto"]), default="auto", help="Align scene cuts to beat positions.")
@click.option("--yes", "skip_confirm", is_flag=True, default=False, help="Skip confirmation prompt.")
@click.option("--quick", "quick_mode", is_flag=True, default=False, help="Quick mode: stock images, no animation, cut transitions, no LUT.")
@click.option("--economy", "economy_mode", is_flag=True, default=False, help="Economy mode: flux-dev AI images, no Runway animation, warm LUT.")
def cli(audio_file, mode, provider, style, output, resolution, lang, new, font_path, lyrics_path,
        effects, clip_duration, platform, title_card, animate_mode, preset, reel_duration,
        logo_path, logo_position, logo_size, logo_opacity,
        lut_style, lut_intensity, subtitle_style_override, transitions_mode, beat_sync,
        skip_confirm, quick_mode, economy_mode):
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_lut_style_flag_accepted tests/test_cli.py::TestCLI::test_subtitle_style_flag_accepted tests/test_cli.py::TestCLI::test_transitions_flag_accepted tests/test_cli.py::TestCLI::test_beat_sync_flag_accepted tests/test_cli.py::TestCLI::test_yes_flag_accepted tests/test_cli.py::TestCLI::test_quick_flag_accepted tests/test_cli.py::TestCLI::test_economy_flag_accepted -v
```
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): add --lut-style, --subtitle-style, --transitions, --beat-sync, --yes, --quick, --economy flags; change mode/preset defaults"
```

---

### Task 2: Apply --quick and --economy mode overrides at start of cli()

**Files:**
- Modify: `musicvid/musicvid.py` (beginning of `cli()` function body, after argument parsing)
- Test: `tests/test_cli.py`

`--quick` overrides: mode="stock", preset="full", effects="none", animate_mode="never", lut_style=None, transitions_mode="cut", beat_sync="off"
`--economy` overrides: mode="ai", provider="flux-dev", preset="full", effects="minimal", animate_mode="never", lut_style="warm", transitions_mode="auto", beat_sync="auto"

- [ ] **Step 1: Write failing tests for --quick and --economy**

```python
@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_quick_mode_uses_stock_and_no_animation(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
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
    result = runner.invoke(cli, [str(audio_file), "--output", str(output_dir), "--quick"])
    assert result.exit_code == 0
    mock_fetch.assert_called_once()  # stock mode: fetch_videos called, not generate_images
    call_kwargs = mock_assemble.call_args
    assert call_kwargs.kwargs.get("lut_style") is None  # --quick has no LUT

@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.generate_images")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_economy_mode_uses_flux_dev(
    self, mock_analyze, mock_direct, mock_gen, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
        "mood_energy": "contemplative", "language": "en",
    }
    mock_direct.return_value = {
        "overall_style": "contemplative", "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "fade"},
        "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                    "visual_prompt": "test", "motion": "static",
                    "transition": "cut", "overlay": "none", "animate": False}],
    }
    mock_gen.return_value = ["/fake/img.jpg"]
    output_dir = tmp_path / "output"
    result = runner.invoke(cli, [str(audio_file), "--output", str(output_dir), "--economy"])
    assert result.exit_code == 0
    mock_gen.assert_called_once()
    _, gen_kwargs = mock_gen.call_args
    assert gen_kwargs.get("provider") == "flux-dev"
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_quick_mode_uses_stock_and_no_animation tests/test_cli.py::TestCLI::test_economy_mode_uses_flux_dev -v
```
Expected: FAIL

- [ ] **Step 3: Add quick/economy override logic at start of cli() body**

Add this block immediately after the `"""Generate a music video from AUDIO_FILE."""` docstring, before `audio_path = Path(audio_file).resolve()`:

```python
    # Apply --quick mode overrides
    if quick_mode:
        mode = "stock"
        preset = "full"
        effects = "none"
        animate_mode = "never"
        lut_style = None
        transitions_mode = "cut"
        beat_sync = "off"

    # Apply --economy mode overrides
    if economy_mode:
        mode = "ai"
        provider = "flux-dev"
        preset = "full"
        effects = "minimal"
        animate_mode = "never"
        lut_style = "warm"
        transitions_mode = "auto"
        beat_sync = "auto"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_quick_mode_uses_stock_and_no_animation tests/test_cli.py::TestCLI::test_economy_mode_uses_flux_dev -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): implement --quick and --economy mode overrides"
```

---

### Task 3: Graceful API key fallbacks

**Files:**
- Modify: `musicvid/musicvid.py` (after quick/economy overrides, before Stage 1)
- Test: `tests/test_cli.py`

When BFL_API_KEY is absent and mode=="ai", fall back to mode="stock" with an informative message.
When RUNWAY_API_KEY is absent and animate_mode in ("auto","always"), show an informative message (per-scene fallback already exists but we want an early global warning).

- [ ] **Step 1: Write failing tests for API key fallbacks**

```python
@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_missing_bfl_api_key_falls_back_to_stock(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
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
    import os
    env = {k: v for k, v in os.environ.items() if k != "BFL_API_KEY"}
    output_dir = tmp_path / "output"
    with patch.dict("os.environ", env, clear=True):
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir), "--mode", "ai",
        ])
    assert result.exit_code == 0
    assert "BFL_API_KEY" in result.output
    mock_fetch.assert_called_once()  # fell back to stock

@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_missing_runway_api_key_shows_message(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
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
    import os
    env = {k: v for k, v in os.environ.items() if k != "RUNWAY_API_KEY"}
    output_dir = tmp_path / "output"
    with patch.dict("os.environ", env, clear=True):
        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir),
            "--mode", "stock", "--animate", "auto",
        ])
    assert result.exit_code == 0
    assert "RUNWAY_API_KEY" in result.output
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_missing_bfl_api_key_falls_back_to_stock tests/test_cli.py::TestCLI::test_missing_runway_api_key_shows_message -v
```
Expected: FAIL

- [ ] **Step 3: Add API key fallback logic in cli()**

Add this block after the quick/economy overrides and after `load_dotenv()` is called (it's called at module level), but before `audio_path = Path(audio_file).resolve()`:

```python
    # API key fallbacks
    if mode == "ai" and not os.environ.get("BFL_API_KEY"):
        click.echo(
            "Brak BFL_API_KEY — przełączam na tryb stock (Pexels).\n"
            "Aby używać AI obrazów: dodaj BFL_API_KEY do .env\n"
            "Rejestracja: https://bfl.ai/dashboard"
        )
        mode = "stock"

    if animate_mode in ("auto", "always") and not os.environ.get("RUNWAY_API_KEY"):
        click.echo(
            "Brak RUNWAY_API_KEY — animacje wyłączone (Ken Burns zamiast Runway).\n"
            "Aby używać Runway: dodaj RUNWAY_API_KEY do .env\n"
            "Rejestracja: https://app.runwayml.com"
        )
        animate_mode = "never"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_missing_bfl_api_key_falls_back_to_stock tests/test_cli.py::TestCLI::test_missing_runway_api_key_shows_message -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): graceful fallback when BFL_API_KEY or RUNWAY_API_KEY missing"
```

---

### Task 4: Startup summary + confirmation prompt

**Files:**
- Modify: `musicvid/musicvid.py`
- Test: `tests/test_cli.py`

Show a formatted summary of active settings before any pipeline stage. Prompt for confirmation when running interactively (stdin is a TTY). `--yes` / `--batch-yes` skips the prompt. In non-interactive mode (tests, CI) the prompt is automatically skipped.

- [ ] **Step 1: Write failing test**

```python
@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_startup_summary_shown(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
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
    mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"}]
    output_dir = tmp_path / "output"
    result = runner.invoke(cli, [
        str(audio_file), "--output", str(output_dir), "--mode", "stock",
    ])
    assert result.exit_code == 0
    assert "MusicVid" in result.output
    assert "Obrazy" in result.output or "Mode" in result.output
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_startup_summary_shown -v
```
Expected: FAIL

- [ ] **Step 3: Add startup summary function and call**

Add helper function `_print_startup_summary(mode, provider, preset, effects, animate_mode, lut_style, lut_intensity, subtitle_style_override, transitions_mode, beat_sync, reel_duration)` before `cli()` in `musicvid.py`:

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
    click.echo(f"  Efekty:      {effects}")
    click.echo(f"  Napisy:      {subtitle_style_override} style")
    click.echo(f"  Przejścia:   {transitions_mode}")
    click.echo(f"  Color grade: {lut_desc}")
    click.echo(f"  Beat sync:   {beat_sync}")
    click.echo("  " + "━" * 38)
```

Then call it in `cli()` after API key fallbacks and before `audio_path = ...`, followed by an optional confirmation:

```python
    _print_startup_summary(mode, provider, preset, effects, animate_mode, lut_style,
                           lut_intensity, subtitle_style_override, transitions_mode,
                           beat_sync, reel_duration)

    import sys
    if not skip_confirm and sys.stdin.isatty():
        if not click.confirm("  Kontynuować?", default=True):
            raise SystemExit(0)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_startup_summary_shown -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): add startup summary and optional confirmation prompt"
```

---

### Task 5: Wire --lut-style/--lut-intensity through all assemble_video calls

**Files:**
- Modify: `musicvid/musicvid.py` (lines 336–353 single-output, and `_run_preset_mode` assemble calls)
- Test: `tests/test_cli.py`

The assembler already accepts `lut_style` and `lut_intensity`. They just need to be passed from the CLI.

- [ ] **Step 1: Write failing test**

```python
@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_lut_style_passed_to_assembler(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
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
    mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"}]
    output_dir = tmp_path / "output"
    result = runner.invoke(cli, [
        str(audio_file), "--output", str(output_dir),
        "--mode", "stock", "--preset", "full",
        "--lut-style", "cinematic", "--lut-intensity", "0.7",
    ])
    assert result.exit_code == 0
    call_kwargs = mock_assemble.call_args.kwargs
    assert call_kwargs.get("lut_style") == "cinematic"
    assert abs(call_kwargs.get("lut_intensity", 0) - 0.7) < 0.01
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_lut_style_passed_to_assembler -v
```
Expected: FAIL

- [ ] **Step 3: Add lut_style/lut_intensity to assemble_video calls**

In the single-output `assemble_video(...)` call (around line 336), add:
```python
        lut_style=lut_style,
        lut_intensity=lut_intensity,
```

In `_run_preset_mode`, update the function signature to accept `lut_style=None, lut_intensity=0.85` and pass them to both assemble_video calls (the full YouTube call and the social reels loop).

Also update the `_run_preset_mode(...)` call in `cli()` to pass:
```python
        lut_style=lut_style,
        lut_intensity=lut_intensity,
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_lut_style_passed_to_assembler -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): wire --lut-style and --lut-intensity through to assemble_video"
```

---

### Task 6: Wire --transitions through scene plan overrides

**Files:**
- Modify: `musicvid/musicvid.py` (after scene_plan is loaded/created in Stage 2)
- Test: `tests/test_cli.py`

When `--transitions cut`, override all scene `transition` fields in the scene_plan to `"cut"` before Stage 3 and assembly.

- [ ] **Step 1: Write failing test**

```python
@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_transitions_cut_overrides_scene_plan(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
        "mood_energy": "contemplative", "language": "en",
    }
    mock_direct.return_value = {
        "overall_style": "contemplative", "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "fade"},
        "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                    "visual_prompt": "test", "motion": "static",
                    "transition": "crossfade", "overlay": "none"}],
    }
    mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"}]
    output_dir = tmp_path / "output"
    result = runner.invoke(cli, [
        str(audio_file), "--output", str(output_dir),
        "--mode", "stock", "--preset", "full", "--transitions", "cut",
    ])
    assert result.exit_code == 0
    call_kwargs = mock_assemble.call_args.kwargs
    passed_scene_plan = call_kwargs.get("scene_plan")
    assert all(s["transition"] == "cut" for s in passed_scene_plan["scenes"])
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_transitions_cut_overrides_scene_plan -v
```
Expected: FAIL

- [ ] **Step 3: Add transitions override after Stage 2 in cli()**

After the scene_plan is loaded/created (after the `click.echo(f"  Style: ...")` line), add:

```python
    # Override transitions if --transitions cut
    if transitions_mode == "cut":
        for scene in scene_plan["scenes"]:
            scene["transition"] = "cut"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_transitions_cut_overrides_scene_plan -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): wire --transitions cut to override scene plan transitions"
```

---

### Task 7: Wire --subtitle-style through scene plan

**Files:**
- Modify: `musicvid/musicvid.py` (after scene_plan is loaded, before assembly)
- Test: `tests/test_cli.py`

Override `scene_plan["subtitle_style"]["animation"]` based on `--subtitle-style`:
- `"karaoke"` → animation: `"karaoke"`
- `"fade"` → animation: `"fade"`
- `"none"` → animation: `"none"`

- [ ] **Step 1: Write failing test**

```python
@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_subtitle_style_override_passed_to_scene_plan(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
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
    mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"}]
    output_dir = tmp_path / "output"
    result = runner.invoke(cli, [
        str(audio_file), "--output", str(output_dir),
        "--mode", "stock", "--preset", "full", "--subtitle-style", "karaoke",
    ])
    assert result.exit_code == 0
    call_kwargs = mock_assemble.call_args.kwargs
    passed_scene_plan = call_kwargs.get("scene_plan")
    assert passed_scene_plan["subtitle_style"]["animation"] == "karaoke"
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_subtitle_style_override_passed_to_scene_plan -v
```
Expected: FAIL

- [ ] **Step 3: Add subtitle style override after Stage 2 in cli()**

After the transitions override block, add:

```python
    # Override subtitle animation style
    if subtitle_style_override:
        if "subtitle_style" not in scene_plan:
            scene_plan["subtitle_style"] = {}
        scene_plan["subtitle_style"]["animation"] = subtitle_style_override
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_subtitle_style_override_passed_to_scene_plan -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): wire --subtitle-style to override scene_plan subtitle animation"
```

---

### Task 8: Wire --beat-sync to realign scene boundaries to beats

**Files:**
- Modify: `musicvid/musicvid.py` (after scene_plan is loaded, after transitions/subtitle overrides)
- Test: `tests/test_cli.py`

When `--beat-sync auto`, snap each scene's `start` and `end` to the nearest beat timestamp. This is a pure post-processing step on the scene_plan dict — no assembler changes required.

- [ ] **Step 1: Write failing test**

```python
@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
@patch("musicvid.musicvid.assemble_video")
@patch("musicvid.musicvid.fetch_videos")
@patch("musicvid.musicvid.create_scene_plan")
@patch("musicvid.musicvid.analyze_audio")
def test_beat_sync_auto_snaps_scene_boundaries(
    self, mock_analyze, mock_direct, mock_fetch, mock_assemble, mock_font, runner, tmp_path
):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"fake audio")
    # Beats at 0.0, 0.5, 1.0, 1.5, 2.0
    mock_analyze.return_value = {
        "lyrics": [], "beats": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        "bpm": 120.0,
        "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
        "mood_energy": "contemplative", "language": "en",
    }
    # Scene starts at 0.3 (nearest beat: 0.5) and ends at 2.7 (nearest beat: 2.5)
    mock_direct.return_value = {
        "overall_style": "contemplative", "color_palette": ["#aaa"],
        "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                           "position": "center-bottom", "animation": "fade"},
        "scenes": [
            {"section": "verse", "start": 0.0, "end": 1.3,
             "visual_prompt": "test", "motion": "static", "transition": "cut", "overlay": "none"},
            {"section": "verse", "start": 1.3, "end": 5.0,
             "visual_prompt": "test2", "motion": "static", "transition": "cut", "overlay": "none"},
        ],
    }
    mock_fetch.return_value = [
        {"scene_index": 0, "video_path": "/fake/v0.mp4", "search_query": "test"},
        {"scene_index": 1, "video_path": "/fake/v1.mp4", "search_query": "test2"},
    ]
    output_dir = tmp_path / "output"
    result = runner.invoke(cli, [
        str(audio_file), "--output", str(output_dir),
        "--mode", "stock", "--preset", "full", "--beat-sync", "auto",
    ])
    assert result.exit_code == 0
    call_kwargs = mock_assemble.call_args.kwargs
    passed_scene_plan = call_kwargs.get("scene_plan")
    # Scene 1 ends at 1.3 → should snap to nearest beat (1.5)
    assert abs(passed_scene_plan["scenes"][0]["end"] - 1.5) < 0.01
    # Scene 2 starts at 1.3 → should snap to nearest beat (1.5)
    assert abs(passed_scene_plan["scenes"][1]["start"] - 1.5) < 0.01
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_beat_sync_auto_snaps_scene_boundaries -v
```
Expected: FAIL

- [ ] **Step 3: Add beat-sync helper and call in cli()**

Add helper function before `cli()`:

```python
def _snap_to_nearest_beat(t, beats):
    """Return the beat timestamp closest to t."""
    if not beats:
        return t
    return min(beats, key=lambda b: abs(b - t))


def _apply_beat_sync(scene_plan, beats):
    """Snap scene start/end times to the nearest beat timestamp.

    The first scene's start stays at 0.0. Adjacent scenes share the same
    snapped boundary so there are no gaps.
    """
    scenes = scene_plan["scenes"]
    if not scenes or not beats:
        return scene_plan
    # Snap interior boundaries only (preserve first start and last end)
    for i in range(len(scenes) - 1):
        snapped = _snap_to_nearest_beat(scenes[i]["end"], beats)
        scenes[i]["end"] = snapped
        scenes[i + 1]["start"] = snapped
    return scene_plan
```

Then call it in `cli()` after the subtitle_style override block:

```python
    # Snap scene cuts to beat positions if --beat-sync auto
    if beat_sync == "auto":
        scene_plan = _apply_beat_sync(scene_plan, analysis.get("beats", []))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli.py::TestCLI::test_beat_sync_auto_snaps_scene_boundaries -v
```
Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: All tests pass (or only pre-existing failures).

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): add --beat-sync auto to snap scene cuts to beat positions"
```

---

## Self-Review

### Spec Coverage

| Spec requirement | Task |
|---|---|
| `--mode` default "stock" → "ai" | Task 1 |
| `--provider` default flux-pro (already set) | Task 1 (verified, no change) |
| `--preset` default None → "all" | Task 1 |
| `--effects` default "minimal" (already set) | Task 1 (verified, no change) |
| `--animate` default "auto" (already set) | Task 1 (verified, no change) |
| `--subtitle-style` default "karaoke" | Task 1 + Task 7 |
| `--transitions` default "auto" | Task 1 + Task 6 |
| `--lut-style` default "warm" | Task 1 + Task 5 |
| `--lut-intensity` default 0.85 | Task 1 + Task 5 |
| `--beat-sync` default "auto" | Task 1 + Task 8 |
| Startup summary message | Task 4 |
| `--yes` skip confirmation | Task 4 |
| `--quick` flag | Task 2 |
| `--economy` flag | Task 2 |
| Brak BFL_API_KEY fallback | Task 3 |
| Brak RUNWAY_API_KEY fallback | Task 3 |
| `python3 -m pytest tests/ -v` passes | Task 8 step 5 |

All spec requirements are covered.

### Placeholder Scan

No TBD/TODO patterns present. All code blocks are complete.

### Type Consistency

- `_snap_to_nearest_beat(t, beats)` defined in Task 8 Step 3, used in `_apply_beat_sync` defined in same step — consistent.
- `_apply_beat_sync(scene_plan, beats)` defined and called in same task — consistent.
- `_print_startup_summary(...)` defined and called with same parameter names — consistent.
- `lut_style`/`lut_intensity` parameter names consistent across CLI option, cli() signature, assemble_video calls, and `_run_preset_mode`.
