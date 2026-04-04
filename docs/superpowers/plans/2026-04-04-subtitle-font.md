# Subtitle Font Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Montserrat font with auto-download, Polish character support, fallback chain, and `--font` CLI flag for custom fonts.

**Architecture:** New `font_loader.py` module handles font resolution (custom → local Montserrat → download → DejaVuSans fallback). Assembler receives resolved font path and uses updated subtitle style (58px, outline). CLI passes `--font` option through to assembler.

**Tech Stack:** Python 3.14, MoviePy 2.1.2, requests (for font download), zipfile (stdlib)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `musicvid/pipeline/font_loader.py` | Create | Font resolution: custom path → local Montserrat → download → fallback chain |
| `musicvid/assets/fonts/.gitkeep` | Create | Empty dir for cached font downloads |
| `musicvid/pipeline/assembler.py` | Modify | Accept `font_path` param, update default font_size to 58 |
| `musicvid/musicvid.py` | Modify | Add `--font` CLI option, pass to `assemble_video()` |
| `tests/test_font_loader.py` | Create | Tests for font resolution, download, fallback |
| `tests/test_assembler.py` | Modify | Tests for font_path parameter in subtitle clips |
| `tests/test_cli.py` | Modify | Test `--font` flag acceptance and passthrough |

---

### Task 1: Font Loader — Core Resolution Logic

**Files:**
- Create: `tests/test_font_loader.py`
- Create: `musicvid/pipeline/font_loader.py`
- Create: `musicvid/assets/__init__.py`
- Create: `musicvid/assets/fonts/.gitkeep`

- [ ] **Step 1: Create assets directory structure**

```bash
mkdir -p musicvid/assets/fonts
touch musicvid/assets/__init__.py
touch musicvid/assets/fonts/.gitkeep
```

- [ ] **Step 2: Write failing test — custom path returns as-is when file exists**

Create `tests/test_font_loader.py`:

```python
"""Tests for font_loader module."""

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from musicvid.pipeline.font_loader import get_font_path


class TestGetFontPathCustom:
    """Tests for custom font path."""

    def test_custom_path_returned_when_exists(self, tmp_path):
        font_file = tmp_path / "custom.ttf"
        font_file.write_bytes(b"fake font")
        result = get_font_path(custom_path=str(font_file))
        assert result == str(font_file)

    def test_custom_path_raises_when_missing(self):
        with pytest.raises(FileNotFoundError):
            get_font_path(custom_path="/nonexistent/font.ttf")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_font_loader.py::TestGetFontPathCustom -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'musicvid.pipeline.font_loader'`

- [ ] **Step 4: Write minimal font_loader with custom path support**

Create `musicvid/pipeline/font_loader.py`:

```python
"""Font loader with auto-download and fallback chain."""

import io
import logging
import zipfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

ASSETS_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
MONTSERRAT_FILENAME = "Montserrat-Light.ttf"
MONTSERRAT_URL = "https://fonts.google.com/download?family=Montserrat"

SYSTEM_FONT_PATHS = [
    # macOS
    "/opt/homebrew/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/local/share/fonts/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    # Liberation Sans fallback
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
]


def _find_system_fallback():
    """Find the first available system fallback font."""
    for path in SYSTEM_FONT_PATHS:
        if Path(path).exists():
            logger.info("Using system fallback font: %s", path)
            return path
    return None


def _download_montserrat():
    """Download Montserrat font family ZIP and extract Light variant."""
    ASSETS_FONTS_DIR.mkdir(parents=True, exist_ok=True)
    target = ASSETS_FONTS_DIR / MONTSERRAT_FILENAME

    try:
        logger.info("Downloading Montserrat font from Google Fonts...")
        resp = requests.get(MONTSERRAT_URL, timeout=30)
        resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if name.endswith(MONTSERRAT_FILENAME):
                    target.write_bytes(zf.read(name))
                    logger.info("Saved font to %s", target)
                    return str(target)

        logger.warning("Montserrat-Light.ttf not found in downloaded ZIP")
        return None
    except Exception as exc:
        logger.warning("Failed to download Montserrat: %s", exc)
        return None


def get_font_path(custom_path=None):
    """Get the best available font path.

    Priority:
    1. custom_path (if provided and exists)
    2. Local Montserrat-Light.ttf (cached)
    3. Download Montserrat from Google Fonts
    4. System DejaVuSans.ttf or Liberation Sans

    Returns:
        str: Path to a .ttf font file.
    Raises:
        FileNotFoundError: If custom_path is given but doesn't exist.
        RuntimeError: If no font can be found at all.
    """
    if custom_path:
        if not Path(custom_path).exists():
            raise FileNotFoundError(f"Custom font not found: {custom_path}")
        return str(custom_path)

    # Check local cached Montserrat
    local_montserrat = ASSETS_FONTS_DIR / MONTSERRAT_FILENAME
    if local_montserrat.exists():
        return str(local_montserrat)

    # Try downloading
    downloaded = _download_montserrat()
    if downloaded:
        return downloaded

    # System fallback
    fallback = _find_system_fallback()
    if fallback:
        return fallback

    raise RuntimeError(
        "No suitable font found. Install DejaVuSans or provide --font path."
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_font_loader.py::TestGetFontPathCustom -v`
Expected: PASS

- [ ] **Step 6: Write failing tests — local Montserrat and download**

Add to `tests/test_font_loader.py`:

```python
class TestGetFontPathMontserrat:
    """Tests for Montserrat resolution."""

    @patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR")
    def test_returns_local_montserrat_when_exists(self, mock_dir, tmp_path):
        font_file = tmp_path / "Montserrat-Light.ttf"
        font_file.write_bytes(b"fake font")
        mock_dir.__truediv__ = lambda self, name: tmp_path / name
        mock_dir.return_value = tmp_path
        # Use a fresh patch on the constant
        result = get_font_path()
        assert "Montserrat-Light.ttf" in result

    @patch("musicvid.pipeline.font_loader._find_system_fallback", return_value=None)
    @patch("musicvid.pipeline.font_loader._download_montserrat", return_value=None)
    @patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR", new_callable=lambda: type("P", (), {"__truediv__": lambda s, n: Path("/nonexistent") / n})())
    def test_raises_when_no_font_available(self, mock_dir, mock_dl, mock_fb):
        with pytest.raises(RuntimeError, match="No suitable font found"):
            get_font_path()
```

Actually, let me simplify the mocking approach. It's better to mock at a higher level:

```python
class TestGetFontPathFallback:
    """Tests for fallback chain."""

    @patch("musicvid.pipeline.font_loader._find_system_fallback")
    @patch("musicvid.pipeline.font_loader._download_montserrat")
    @patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR")
    def test_tries_download_when_no_local(self, mock_dir, mock_download, mock_fallback, tmp_path):
        mock_local = MagicMock()
        mock_local.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_local)

        mock_download.return_value = "/downloaded/Montserrat-Light.ttf"

        result = get_font_path()
        assert result == "/downloaded/Montserrat-Light.ttf"
        mock_download.assert_called_once()

    @patch("musicvid.pipeline.font_loader._find_system_fallback")
    @patch("musicvid.pipeline.font_loader._download_montserrat")
    @patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR")
    def test_uses_system_fallback_when_download_fails(self, mock_dir, mock_download, mock_fallback):
        mock_local = MagicMock()
        mock_local.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_local)

        mock_download.return_value = None
        mock_fallback.return_value = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        result = get_font_path()
        assert result == "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    @patch("musicvid.pipeline.font_loader._find_system_fallback", return_value=None)
    @patch("musicvid.pipeline.font_loader._download_montserrat", return_value=None)
    @patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR")
    def test_raises_when_nothing_available(self, mock_dir, mock_download, mock_fallback):
        mock_local = MagicMock()
        mock_local.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_local)

        with pytest.raises(RuntimeError, match="No suitable font found"):
            get_font_path()
```

- [ ] **Step 7: Run tests to verify they pass (implementation already handles these cases)**

Run: `python3 -m pytest tests/test_font_loader.py -v`
Expected: PASS

- [ ] **Step 8: Write failing test — download helper**

Add to `tests/test_font_loader.py`:

```python
class TestDownloadMontserrat:
    """Tests for the download helper."""

    @patch("musicvid.pipeline.font_loader.requests.get")
    def test_downloads_and_extracts_ttf(self, mock_get, tmp_path):
        import io
        import zipfile

        # Create a fake ZIP with Montserrat-Light.ttf inside
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("static/Montserrat-Light.ttf", b"fake ttf data")
        buf.seek(0)

        mock_resp = MagicMock()
        mock_resp.content = buf.read()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR", tmp_path):
            from musicvid.pipeline.font_loader import _download_montserrat
            result = _download_montserrat()

        assert result is not None
        assert (tmp_path / "Montserrat-Light.ttf").exists()

    @patch("musicvid.pipeline.font_loader.requests.get", side_effect=Exception("network error"))
    def test_returns_none_on_failure(self, mock_get, tmp_path):
        with patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR", tmp_path):
            from musicvid.pipeline.font_loader import _download_montserrat
            result = _download_montserrat()

        assert result is None
```

- [ ] **Step 9: Run all font_loader tests**

Run: `python3 -m pytest tests/test_font_loader.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add musicvid/assets/__init__.py musicvid/assets/fonts/.gitkeep musicvid/pipeline/font_loader.py tests/test_font_loader.py
git commit -m "feat: add font_loader with auto-download and fallback chain"
```

---

### Task 2: Update Assembler to Use Font Loader

**Files:**
- Modify: `musicvid/pipeline/assembler.py:94-129` (subtitle clips function)
- Modify: `musicvid/pipeline/assembler.py:149-191` (assemble_video function signature)
- Modify: `tests/test_assembler.py`

- [ ] **Step 1: Write failing test — assembler uses font_path parameter**

Add to `tests/test_assembler.py` in `TestCreateSubtitleClips`:

```python
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_uses_provided_font_path(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        subtitle_style = sample_scene_plan["subtitle_style"]
        _create_subtitle_clips(
            sample_analysis["lyrics"],
            subtitle_style,
            (1920, 1080),
            font_path="/custom/font.ttf",
        )

        call_kwargs = mock_text_clip.call_args[1]
        assert call_kwargs["font"] == "/custom/font.ttf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assembler.py::TestCreateSubtitleClips::test_uses_provided_font_path -v`
Expected: FAIL with `TypeError: _create_subtitle_clips() got an unexpected keyword argument 'font_path'`

- [ ] **Step 3: Update _create_subtitle_clips to accept font_path**

In `musicvid/pipeline/assembler.py`, change the function signature and body:

```python
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
```

Key changes:
- Added `font_path=None` parameter
- Changed default `font_size` from 48 to 58
- Changed `font=` from hardcoded path to `font_path` parameter

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_assembler.py::TestCreateSubtitleClips::test_uses_provided_font_path -v`
Expected: PASS

- [ ] **Step 5: Write failing test — assemble_video accepts and passes font_path**

Add to `tests/test_assembler.py` in `TestAssembleVideo`:

```python
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_passes_font_path_to_subtitles(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, mock_vfx, sample_analysis, sample_scene_plan, tmp_output
    ):
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resized.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_clip.with_audio.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
            {"scene_index": 1, "video_path": "/fake/scene_001.mp4", "search_query": "test"},
            {"scene_index": 2, "video_path": "/fake/scene_002.png", "search_query": "test"},
        ]

        output_file = str(tmp_output / "output.mp4")

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            resolution="1080p",
            font_path="/custom/font.ttf",
        )

        # Verify TextClip was called with the custom font
        call_kwargs = mock_text.call_args[1]
        assert call_kwargs["font"] == "/custom/font.ttf"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assembler.py::TestAssembleVideo::test_passes_font_path_to_subtitles -v`
Expected: FAIL with `TypeError: assemble_video() got an unexpected keyword argument 'font_path'`

- [ ] **Step 7: Update assemble_video to accept and pass font_path**

In `musicvid/pipeline/assembler.py`, update the `assemble_video` function:

```python
def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path, resolution="1080p", font_path=None):
```

And update the call to `_create_subtitle_clips`:

```python
    subtitle_clips = _create_subtitle_clips(
        analysis.get("lyrics", []),
        scene_plan.get("subtitle_style", {}),
        target_size,
        font_path=font_path,
    )
```

- [ ] **Step 8: Run all assembler tests**

Run: `python3 -m pytest tests/test_assembler.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: assembler accepts font_path, update default font_size to 58"
```

---

### Task 3: Add --font CLI Flag

**Files:**
- Modify: `musicvid/musicvid.py:30-39` (CLI options)
- Modify: `musicvid/musicvid.py:101-112` (Stage 4 call)
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test — --font flag accepted**

Add to `tests/test_cli.py` in `TestCLI`:

```python
    def test_font_flag_accepted(self, runner, tmp_path):
        """The --font flag should be accepted by the CLI."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        result = runner.invoke(cli, [str(audio_file), "--font", "/some/font.ttf", "--help"])
        assert result.exit_code == 0

    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    @patch("musicvid.musicvid.get_font_path")
    def test_font_flag_passed_to_assembler(
        self, mock_font, mock_analyze, mock_direct, mock_fetch, mock_assemble, runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        font_file = tmp_path / "custom.ttf"
        font_file.write_bytes(b"fake font")

        mock_font.return_value = str(font_file)
        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 58, "color": "#FFF", "outline_color": "#000",
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
            str(audio_file),
            "--output", str(output_dir),
            "--font", str(font_file),
        ])

        assert result.exit_code == 0
        call_kwargs = mock_assemble.call_args[1]
        assert call_kwargs["font_path"] == str(font_file)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::TestCLI::test_font_flag_accepted -v`
Expected: FAIL with `Error: No such option: --font`

- [ ] **Step 3: Add --font option and font_loader integration to CLI**

In `musicvid/musicvid.py`, add the import:

```python
from musicvid.pipeline.font_loader import get_font_path
```

Add the CLI option (after the `--new` option):

```python
@click.option("--font", "font_path", type=click.Path(), default=None, help="Custom .ttf font file for subtitles.")
```

Update the `cli` function signature to include `font_path`:

```python
def cli(audio_file, mode, provider, style, output, resolution, lang, new, font_path):
```

Before Stage 4, resolve the font:

```python
    # Resolve font
    font = get_font_path(custom_path=font_path)
```

Update the `assemble_video` call to pass `font_path=font`:

```python
    assemble_video(
        analysis=analysis,
        scene_plan=scene_plan,
        fetch_manifest=fetch_manifest,
        audio_path=str(audio_path),
        output_path=output_path,
        resolution=resolution,
        font_path=font,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py::TestCLI::test_font_flag_accepted -v`
Expected: PASS

- [ ] **Step 5: Run the font passthrough test**

Run: `python3 -m pytest tests/test_cli.py::TestCLI::test_font_flag_passed_to_assembler -v`
Expected: PASS

- [ ] **Step 6: Fix existing CLI tests — mock get_font_path**

Existing CLI tests that run the full pipeline (like `test_full_pipeline_integration`, `test_new_flag_forces_recalculation`, etc.) will now fail because `get_font_path` tries to download/find fonts. Add `@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")` to each test that calls the full pipeline.

Tests to update:
- `test_full_pipeline_integration`
- `test_cache_skips_stages_when_cached`
- `test_new_flag_forces_recalculation`
- `test_stage3_cache_invalid_when_video_files_missing`
- `test_mode_ai_calls_image_generator`
- `test_mode_ai_cache_skips_generation`

For each, add `@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")` as the outermost decorator and add the corresponding `mock_font` parameter at the end of the parameter list.

- [ ] **Step 7: Run all CLI tests**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add --font CLI flag with font_loader integration"
```

---

### Task 4: Run Full Test Suite and Fix Issues

**Files:**
- All test files

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS (54+ tests)

- [ ] **Step 2: Fix any failures**

If any tests fail, fix them. Common issues:
- Existing assembler tests may need `font_path=` default handling (the default is `None`, so existing calls without it should still work)
- The `test_produces_output_file` test should still pass since `font_path` defaults to `None`

- [ ] **Step 3: Commit if fixes were needed**

```bash
git add -A
git commit -m "fix: resolve test failures after font feature integration"
```
