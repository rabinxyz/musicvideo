"""Logo overlay utilities for compositing logos onto video frames."""


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
