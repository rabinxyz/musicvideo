"""LUT (Look Up Table) color grading for cinematic video output."""

import numpy as np
import tempfile
import os
import subprocess


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


def save_lut_as_cube(lut, path):
    """Save a numpy LUT array as a .cube file."""
    size = lut.shape[0]
    with open(path, "w") as f:
        f.write(f"TITLE \"MusicVid LUT\"\n")
        f.write(f"LUT_3D_SIZE {size}\n")
        f.write("DOMAIN_MIN 0.0 0.0 0.0\n")
        f.write("DOMAIN_MAX 1.0 1.0 1.0\n")
        for b in range(size):
            for g in range(size):
                for r in range(size):
                    rgb = lut[r, g, b]
                    f.write(f"{rgb[0]:.6f} {rgb[1]:.6f} {rgb[2]:.6f}\n")
    return path


def load_lut_file(path):
    """Validate and return path to a .cube LUT file."""
    import os
    if not os.path.exists(path):
        raise FileNotFoundError(f"LUT file not found: {path}")
    if not path.endswith(".cube"):
        raise ValueError(f"LUT file must have .cube extension, got: {path}")
    return path


def get_ffmpeg_lut_filter(lut_path, intensity):
    """Build FFmpeg video filter string for LUT application."""
    if intensity <= 0.0:
        return None
    if intensity >= 1.0:
        return f"lut3d='{lut_path}':interp=trilinear"
    return (
        f"split[a][b];"
        f"[b]lut3d='{lut_path}':interp=trilinear[graded];"
        f"[a][graded]blend=all_mode=normal:all_opacity={intensity:.2f}"
    )


def prepare_lut_ffmpeg_params(lut_path=None, lut_style=None, intensity=0.85):
    """Prepare FFmpeg params for LUT color grading.

    Priority: lut_path (custom .cube file) > lut_style (built-in).
    If neither is provided, returns empty list (no LUT).

    Args:
        lut_path: Path to custom .cube file (optional).
        lut_style: Built-in style name (optional).
        intensity: LUT intensity 0.0-1.0 (default 0.85).

    Returns:
        List of FFmpeg params, e.g. ["-vf", "lut3d='...'"] or [].
    """
    if intensity <= 0.0:
        return []

    cube_path = None

    if lut_path:
        cube_path = load_lut_file(lut_path)
    elif lut_style:
        lut = generate_builtin_lut(lut_style)
        tmp_dir = tempfile.gettempdir()
        cube_path = os.path.join(tmp_dir, f"musicvid_lut_{lut_style}.cube")
        save_lut_as_cube(lut, cube_path)

    if not cube_path:
        return []

    vf_filter = get_ffmpeg_lut_filter(cube_path, intensity)
    if vf_filter is None:
        return []

    return ["-vf", vf_filter]


CURVES_GRADES = {
    "worship-warm": {
        "curves": "curves=r='0/0 0.3/0.28 0.7/0.75 1/1':g='0/0 0.3/0.29 0.7/0.72 1/0.97':b='0/0.05 0.3/0.32 0.7/0.68 1/0.92'",
        "eq_full": "eq=saturation=0.92:contrast=1.12",
        "eq_social": "eq=saturation=1.05:contrast=1.15",
    },
    "teal-orange": {
        "curves": "curves=r='0/0 0.5/0.58 1/1':g='0/0 0.5/0.50 1/0.96':b='0/0.08 0.5/0.45 1/0.88'",
        "eq_full": "eq=saturation=1.05:contrast=1.15",
        "eq_social": "eq=saturation=1.10:contrast=1.18",
    },
    "bleach": {
        "curves": None,
        "eq_full": "eq=saturation=0.75:contrast=1.30:brightness=-0.01",
        "eq_social": "eq=saturation=0.78:contrast=1.35:brightness=-0.01",
    },
    "natural": {
        "curves": None,
        "eq_full": "eq=saturation=0.95:contrast=1.05",
        "eq_social": "eq=saturation=0.98:contrast=1.08",
    },
}


def get_curves_grade_filter(grade_name, is_social=False):
    """Return FFmpeg -vf filter string for the given color grade.

    Args:
        grade_name: One of worship-warm, teal-orange, bleach, natural.
        is_social: If True, use slightly stronger eq for social reels.

    Returns:
        FFmpeg -vf filter string.
    """
    grade = CURVES_GRADES.get(grade_name, CURVES_GRADES["worship-warm"])
    eq_key = "eq_social" if is_social else "eq_full"
    parts = []
    if grade["curves"]:
        parts.append(grade["curves"])
    parts.append(grade[eq_key])
    return ",".join(parts)


def apply_global_color_grade(input_path, output_path, grade_name, is_social=False):
    """Apply global color grade via FFmpeg as a post-processing step.

    Returns True on success, False on failure (original preserved).
    """
    vf = get_curves_grade_filter(grade_name, is_social=is_social)
    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        "-y", output_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception:
        print(f"WARN: Global color grade failed for {input_path} — using original")
        return False
