"""Logo overlay utilities for compositing logos onto video frames."""

import io
import numpy as np
from pathlib import Path
from PIL import Image
from moviepy import ImageClip

try:
    import cairosvg
except ImportError:
    cairosvg = None


def _load_svg(path, logo_width, logo_height):
    """Convert SVG to PIL Image via cairosvg at 2x resolution for retina sharpness."""
    if cairosvg is None:
        raise ImportError(
            "cairosvg is required for SVG logo files. Install it with: pip install cairosvg"
        )
    # Render at 2x for sharp edges, then downscale
    png_data = cairosvg.svg2png(
        url=path,
        output_width=logo_width * 2,
        output_height=logo_height * 2,
    )
    return Image.open(io.BytesIO(png_data))


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


def apply_logo(clip, logo_path, position, size, opacity):
    """Create a logo ImageClip positioned over the video.

    Args:
        clip: The base MoviePy video clip (used for size/duration).
        logo_path: Path to logo file (SVG, PNG, JPG).
        position: "top-left" | "top-right" | "bottom-left" | "bottom-right"
        size: Logo width in px, or None for auto (12% of frame width).
        opacity: Float 0.0-1.0 for logo transparency.

    Returns:
        MoviePy ImageClip positioned and sized for compositing.
    """
    frame_w, frame_h = clip.size

    # Get original image dimensions for aspect ratio calculation
    logo_path_obj = Path(logo_path)
    if logo_path_obj.suffix.lower() == ".svg":
        # For SVG, use a nominal size — _load_svg will render at target resolution
        orig_w, orig_h = 100, 100
    else:
        with Image.open(logo_path) as orig_img:
            orig_w, orig_h = orig_img.size

    logo_w, logo_h = compute_logo_size(frame_w, frame_h, orig_w, orig_h, requested_size=size)
    logo_img = load_logo(logo_path, logo_w, logo_h, opacity)
    logo_arr = np.array(logo_img)

    logo_clip = ImageClip(logo_arr)
    logo_clip = logo_clip.with_duration(clip.duration)

    pos = get_logo_position(position, (logo_w, logo_h), (frame_w, frame_h))
    logo_clip = logo_clip.with_position(pos)

    return logo_clip
