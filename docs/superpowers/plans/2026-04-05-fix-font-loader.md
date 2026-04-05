# Fix Montserrat Font Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `font_loader.py` to download Montserrat-Light.ttf directly as a TTF file from GitHub instead of extracting it from a Google Fonts ZIP archive that no longer returns a valid ZIP.

**Architecture:** Replace ZIP download+extract logic in `_download_montserrat()` with a direct TTF download using `requests.get()`. Remove unused `io` and `zipfile` imports. Update tests to match the new implementation.

**Tech Stack:** Python 3.11+, `requests`, `pathlib`, `pytest`

---

### Task 1: Fix `_download_montserrat` and update tests

**Files:**
- Modify: `musicvid/pipeline/font_loader.py`
- Modify: `tests/test_font_loader.py`

- [ ] **Step 1: Write the failing tests for the new TTF-direct download**

Replace the `TestDownloadMontserrat` class in `tests/test_font_loader.py` with tests that match the new direct-download behaviour:

```python
class TestDownloadMontserrat:
    """Tests for the download helper."""

    @patch("musicvid.pipeline.font_loader.requests.get")
    def test_downloads_ttf_directly(self, mock_get, tmp_path):
        fake_ttf = b"fake ttf data"
        mock_resp = MagicMock()
        mock_resp.content = fake_ttf
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR", tmp_path):
            result = _download_montserrat()

        assert result is not None
        assert result == str(tmp_path / "Montserrat-Light.ttf")
        assert (tmp_path / "Montserrat-Light.ttf").read_bytes() == fake_ttf
        mock_get.assert_called_once_with(
            "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Light.ttf",
            timeout=30,
        )

    @patch(
        "musicvid.pipeline.font_loader.requests.get",
        side_effect=Exception("network error"),
    )
    def test_returns_none_on_failure(self, mock_get, tmp_path):
        with patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR", tmp_path):
            result = _download_montserrat()

        assert result is None
```

Remove the `import io` and `import zipfile` lines from the test file (they are no longer needed).

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python3 -m pytest tests/test_font_loader.py::TestDownloadMontserrat -v
```

Expected: `FAILED` — `test_downloads_ttf_directly` fails because the current code still does ZIP extraction and the mock URL doesn't match.

- [ ] **Step 3: Fix `font_loader.py`**

Apply these changes to `musicvid/pipeline/font_loader.py`:

1. Remove `import io` and `import zipfile` from the top.
2. Change `MONTSERRAT_URL`:
```python
MONTSERRAT_URL = "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Light.ttf"
```
3. Replace `_download_montserrat()` body with direct TTF download (no ZIP logic):
```python
def _download_montserrat():
    """Download Montserrat-Light.ttf directly from GitHub."""
    ASSETS_FONTS_DIR.mkdir(parents=True, exist_ok=True)
    target = ASSETS_FONTS_DIR / MONTSERRAT_FILENAME

    try:
        logger.info("Downloading Montserrat font from GitHub...")
        resp = requests.get(MONTSERRAT_URL, timeout=30)
        resp.raise_for_status()
        target.write_bytes(resp.content)
        logger.info("Saved font to %s", target)
        return str(target)
    except Exception as exc:
        logger.warning("Failed to download Montserrat: %s", exc)
        return None
```

The full updated file should be:

```python
"""Font loader with auto-download and fallback chain."""

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

ASSETS_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
MONTSERRAT_FILENAME = "Montserrat-Light.ttf"
MONTSERRAT_URL = "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Light.ttf"

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
    """Download Montserrat-Light.ttf directly from GitHub."""
    ASSETS_FONTS_DIR.mkdir(parents=True, exist_ok=True)
    target = ASSETS_FONTS_DIR / MONTSERRAT_FILENAME

    try:
        logger.info("Downloading Montserrat font from GitHub...")
        resp = requests.get(MONTSERRAT_URL, timeout=30)
        resp.raise_for_status()
        target.write_bytes(resp.content)
        logger.info("Saved font to %s", target)
        return str(target)
    except Exception as exc:
        logger.warning("Failed to download Montserrat: %s", exc)
        return None


def get_font_path(custom_path=None):
    """Get the best available font path.

    Priority:
    1. custom_path (if provided and exists)
    2. Local Montserrat-Light.ttf (cached)
    3. Download Montserrat from GitHub
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

- [ ] **Step 4: Run all font_loader tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python3 -m pytest tests/test_font_loader.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: same pass count as before (≥322), no new failures.

- [ ] **Step 6: Commit**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && git add musicvid/pipeline/font_loader.py tests/test_font_loader.py && git commit -m "fix: download Montserrat-Light.ttf directly from GitHub, remove ZIP extraction"
```
