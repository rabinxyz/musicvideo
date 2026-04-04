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
