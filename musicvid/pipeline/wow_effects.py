"""WOW effects: FFmpeg post-processing for zoom punch, light flash, reactive color grade, etc.

Integration:
    After MoviePy writes output_path, call:
        apply_wow_effects(video_path, analysis, scene_plan, wow_config, video_width, video_height)
    which runs FFmpeg in-place with a generated filter chain.
"""

import os
import shutil
import subprocess
import tempfile

# Set to False to skip the zoom-punch (scale+t) filter that crashes FFmpeg 7.x
# in init eval_mode. Safe to re-enable when FFmpeg fixes scale eval.
ENABLE_ZOOMPAN = False

# Effects balance constants (fix-effects-balance spec)
FLASH_MAX_BRIGHTNESS = 89  # 255 * 0.35 opacity cap
FLASH_PEAK_TIME = 0.06     # seconds (was 0.05)
FLASH_FADE_RATE = 6        # exp(-6*t) for 0.5s visible decay (was exp(-15) for 0.3s)


def default_wow_config():
    """Return default WOW effects configuration dict."""
    return {
        "enabled": True,
        "zoom_punch": True,
        "light_flash": True,
        "dynamic_grade": True,
        "dynamic_vignette": True,
        "motion_blur": True,
        "particles": False,
    }


def build_ffmpeg_filter_chain(analysis, scene_plan, wow_config, video_width=1920, video_height=1080):
    """Build FFmpeg -vf filter chain string from analysis + wow_config.

    Args:
        analysis: Audio analysis dict (sections, beats, duration, energy_peaks).
        scene_plan: Scene plan dict (scenes, overall_style).
        wow_config: Dict from default_wow_config() or CLI overrides.
        video_width: Output video width in pixels.
        video_height: Output video height in pixels.

    Returns:
        str filter chain for use with ffmpeg -vf, or None if no effects active.
    """
    if not wow_config.get("enabled", True):
        return None

    sections = analysis.get("sections", [])
    beats = analysis.get("beats", [])

    filters = []

    if ENABLE_ZOOMPAN and wow_config.get("zoom_punch", True):
        f = _build_zoom_punch_filter(beats, sections, video_width, video_height)
        if f:
            filters.append(f)

    if wow_config.get("light_flash", True):
        f = _build_light_flash_filter(sections)
        if f:
            filters.append(f)

    if wow_config.get("dynamic_grade", True):
        f = _build_color_grade_filter(sections)
        if f:
            filters.append(f)

    if wow_config.get("dynamic_vignette", True):
        f = _build_vignette_filter(sections)
        if f:
            filters.append(f)

    if wow_config.get("motion_blur", True):
        filters.append("tblend=all_mode=average:all_opacity=0.15")

    if not filters:
        return None

    return ",".join(filters)


def apply_wow_effects(video_path, analysis, scene_plan, wow_config, video_width=1920, video_height=1080):
    """Apply WOW effects to video_path in-place using FFmpeg post-processing.

    Writes to a temp file, then replaces video_path on success.
    No-op if build_ffmpeg_filter_chain returns None.

    Args:
        video_path: Path to the input/output MP4 file (modified in-place).
        analysis: Audio analysis dict.
        scene_plan: Scene plan dict.
        wow_config: WOW effects config dict.
        video_width: Video width in pixels (for crop calculations).
        video_height: Video height in pixels.
    """
    filter_chain = build_ffmpeg_filter_chain(
        analysis, scene_plan, wow_config, video_width, video_height
    )
    if not filter_chain:
        return

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(tmp_fd)
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", filter_chain,
                "-c:v", "libx264",
                "-b:v", "8000k",
                "-c:a", "copy",
                tmp_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg WOW effects failed (rc={result.returncode}):\n{result.stderr}"
            )
        shutil.move(tmp_path, video_path)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        print(f"WARN: WOW effects failed — używam wideo bez efektów: {e}")


# ---------------------------------------------------------------------------
# Internal filter builders
# ---------------------------------------------------------------------------

def _get_chorus_downbeats(beats, sections):
    """Return beat times that fall within chorus sections (every 4th beat = downbeat)."""
    chorus_ranges = [
        (s["start"], s["end"])
        for s in sections
        if s.get("label") == "chorus"
    ]
    if not chorus_ranges:
        return []

    # Downbeats = every 4th beat
    downbeats = beats[::4] if beats else []
    result = []
    for bt in downbeats:
        for start, end in chorus_ranges:
            if start <= bt <= end:
                result.append(round(float(bt), 3))
                break
    # Limit: at most every 2nd downbeat to avoid over-punching
    return result[::2]


def _build_zoom_punch_filter(beats, sections, video_width, video_height):
    """Build scale+crop FFmpeg filter for zoom punch on chorus downbeats.

    Each beat: zoom 1.0->1.08 over 0.1s, 1.08->1.0 over 0.3s.
    """
    beat_times = _get_chorus_downbeats(beats, sections)
    if not beat_times:
        return None

    zoom_parts = []
    for bt in beat_times:
        part = (
            f"(gt(t,{bt:.3f})*lt(t,{bt+0.4:.3f})*"
            f"(0.08*if(lt(t,{bt+0.1:.3f}),"
            f"(t-{bt:.3f})/0.1,"
            f"max(0,1-(t-{bt+0.1:.3f})/0.3))))"
        )
        zoom_parts.append(part)

    zoom_expr = "1+(" + "+".join(zoom_parts) + ")"
    w, h = video_width, video_height
    return (
        f"scale=w='iw*({zoom_expr})':h='ih*({zoom_expr})',"
        f"crop=w={w}:h={h}:x='(iw-{w})/2':y='(ih-{h})/2'"
    )


def _build_light_flash_filter(sections):
    """Build FFmpeg geq filter for white light flash at first and last chorus start.

    Max 2 flashes per video. Flash: brightness spike at chorus start, decaying over 0.5s.
    """
    chorus_starts = [
        round(float(s["start"]), 3)
        for s in sections
        if s.get("label") == "chorus"
    ]
    if not chorus_starts:
        return None

    # Balance spec: only first and last chorus
    if len(chorus_starts) == 1:
        flash_times = chorus_starts
    else:
        flash_times = [chorus_starts[0], chorus_starts[-1]]

    flash_parts = []
    for t in flash_times:
        flash_parts.append(
            f"({FLASH_MAX_BRIGHTNESS}*between(T,{t:.3f},{t+FLASH_PEAK_TIME:.3f})*exp(-{FLASH_FADE_RATE}*(T-{t:.3f})))"
        )

    flash_expr = "+".join(flash_parts)
    return (
        f"geq=r='clip(r(X,Y)+{flash_expr},0,255)':"
        f"g='clip(g(X,Y)+{flash_expr},0,255)':"
        f"b='clip(b(X,Y)+{flash_expr},0,255)'"
    )


def _build_color_grade_filter(sections):
    """Build FFmpeg eq+colorbalance filter for reactive color grade.

    VERSE: saturation=0.85, contrast=1.05, warm tones.
    CHORUS: saturation=1.15, contrast=1.15, vivid tones.
    Uses FFmpeg enable= expressions for per-section activation.
    """
    if not sections:
        return None

    filters = []
    for sec in sections:
        start = round(float(sec["start"]), 3)
        end = round(float(sec["end"]), 3)
        label = sec.get("label", "verse")
        enable = f"between(t,{start:.3f},{end:.3f})"

        if label == "chorus":
            filters.append(
                f"eq=saturation=1.05:brightness=0.0:contrast=1.10:enable='{enable}'"
            )
            filters.append(
                f"colorbalance=rs=0.08:gs=0.03:bs=-0.05:enable='{enable}'"
            )
        else:
            filters.append(
                f"eq=saturation=0.90:brightness=0.02:contrast=1.05:enable='{enable}'"
            )
            filters.append(
                f"colorbalance=rs=0.05:gs=0.02:bs=-0.03:enable='{enable}'"
            )

    return ",".join(filters)


def _build_vignette_filter(sections):
    """Build FFmpeg vignette filter with intensity per section.

    VERSE: angle=0.6 (stronger, intimate).
    CHORUS: angle=0.3 (weaker, open/energetic).
    """
    if not sections:
        return None

    filters = []
    for sec in sections:
        start = round(float(sec["start"]), 3)
        end = round(float(sec["end"]), 3)
        label = sec.get("label", "verse")
        enable = f"between(t,{start:.3f},{end:.3f})"
        angle = 0.3 if label == "chorus" else 0.6
        filters.append(f"vignette=a={angle}:enable='{enable}'")

    return ",".join(filters)
