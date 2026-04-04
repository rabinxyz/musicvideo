"""Logo overlay utilities for compositing logos onto video frames."""

from pathlib import Path
from PIL import Image


def load_logo(path, logo_width, logo_height, opacity):
    """Load a logo image, resize it, and apply opacity.

    Supports PNG and JPG. Returns a PIL Image in RGBA mode.
    Raises FileNotFoundError if path does not exist.
    """
    logo_path = Path(path)
    if not logo_path.exists():
        raise FileNotFoundError(f"Logo file not found: {path}")

    ext = logo_path.suffix.lower()

    if ext == ".svg":
        img = _load_svg(path, logo_width, logo_height)
    else:
        img = Image.open(path)

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    img = img.resize((logo_width, logo_height), Image.LANCZOS)

    # Apply opacity — scale existing alpha by opacity factor
    r, g, b, a = img.split()
    a = a.point(lambda x: int(x * opacity))
    img = Image.merge("RGBA", (r, g, b, a))

    return img


def compute_margin(frame_width, frame_height):
    """Return broadcast safe-zone margin (5% of shorter dimension)."""
    return int(min(frame_width, frame_height) * 0.05)


def compute_logo_size(frame_width, frame_height, orig_width, orig_height, requested_size=None):
    """Return (logo_width, logo_height) preserving aspect ratio.

    When requested_size is None, auto-scales to 12% of frame width.
    """
    logo_width = requested_size if requested_size else int(frame_width * 0.12)
    aspect = orig_height / orig_width
    logo_height = int(logo_width * aspect)
    return logo_width, logo_height


def get_logo_position(position, logo_size, frame_size):
    """Return (x, y) coordinates for logo placement.

    position: "top-left" | "top-right" | "bottom-left" | "bottom-right"
    logo_size: (width, height)
    frame_size: (width, height)
    """
    logo_w, logo_h = logo_size
    frame_w, frame_h = frame_size
    margin = compute_margin(frame_w, frame_h)

    positions = {
        "top-left": (margin, margin),
        "top-right": (frame_w - logo_w - margin, margin),
        "bottom-left": (margin, frame_h - logo_h - margin),
        "bottom-right": (frame_w - logo_w - margin, frame_h - logo_h - margin),
    }
    return positions[position]
