"""LUT (Look Up Table) color grading for cinematic video output."""

import numpy as np


def _identity_lut(size=33):
    """Generate identity LUT — no color change."""
    r = np.linspace(0, 1, size)
    g = np.linspace(0, 1, size)
    b = np.linspace(0, 1, size)
    rr, gg, bb = np.meshgrid(r, g, b, indexing="ij")
    lut = np.stack([rr, gg, bb], axis=-1)
    return lut


def _apply_contrast(lut, amount):
    """Apply S-curve contrast to LUT values."""
    mid = 0.5
    lut = mid + (lut - mid) * (1 + amount)
    return np.clip(lut, 0, 1)


def _apply_saturation(lut, amount):
    """Adjust saturation. amount=-0.1 means 10% less saturated."""
    gray = 0.2126 * lut[..., 0] + 0.7152 * lut[..., 1] + 0.0722 * lut[..., 2]
    gray = gray[..., np.newaxis]
    lut = gray + (lut - gray) * (1 + amount)
    return np.clip(lut, 0, 1)


def _style_warm(lut):
    """Warm style: amber shadows, warm midtones, cream highlights."""
    lut[..., 0] = lut[..., 0] + 0.03
    lut[..., 1] = lut[..., 1] + 0.01
    lut[..., 2] = lut[..., 2] - 0.02
    lut = np.clip(lut, 0, 1)
    lut = _apply_contrast(lut, 0.10)
    lut = _apply_saturation(lut, -0.08)
    return lut


def _style_cinematic(lut):
    """Cinematic: lifted shadows, desaturated, S-curve contrast."""
    lut = 0.05 + lut * 0.95
    lut[..., 2] = lut[..., 2] + 0.01
    lut = np.clip(lut, 0, 1)
    lut = _apply_contrast(lut, 0.15)
    lut = _apply_saturation(lut, -0.15)
    mask = lut > 0.85
    lut[mask] = 0.85 + (lut[mask] - 0.85) * 0.7
    return np.clip(lut, 0, 1)


def _style_cold(lut):
    """Cold: blue shadows, cool midtones."""
    lut[..., 0] = lut[..., 0] - 0.02
    lut[..., 2] = lut[..., 2] + 0.03
    lut = np.clip(lut, 0, 1)
    lut = _apply_contrast(lut, 0.08)
    lut = _apply_saturation(lut, -0.05)
    return lut


def _style_natural(lut):
    """Natural: minimal changes, gentle contrast, slight shadow lift."""
    lut = 0.01 + lut * 0.99
    lut = _apply_contrast(lut, 0.05)
    return np.clip(lut, 0, 1)


def _style_faded(lut):
    """Faded: lifted blacks, desaturated, slight warmth."""
    lut = 0.08 + lut * 0.92
    lut[..., 0] = lut[..., 0] + 0.01
    lut = np.clip(lut, 0, 1)
    lut = _apply_saturation(lut, -0.20)
    return lut


STYLES = {
    "warm": _style_warm,
    "cold": _style_cold,
    "cinematic": _style_cinematic,
    "natural": _style_natural,
    "faded": _style_faded,
}


def generate_builtin_lut(style, size=33):
    """Generate a 3D LUT array for the given style.

    Args:
        style: One of "warm", "cold", "cinematic", "natural", "faded".
        size: LUT cube size (default 33).

    Returns:
        numpy.ndarray of shape (size, size, size, 3) with float values 0.0-1.0.
    """
    if style not in STYLES:
        raise ValueError(f"Unknown LUT style: {style}. Choose from: {list(STYLES.keys())}")
    lut = _identity_lut(size)
    lut = STYLES[style](lut)
    return lut
