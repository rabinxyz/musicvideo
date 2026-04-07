"""Stage 4: Video assembly using MoviePy + FFmpeg."""

from pathlib import Path

from moviepy import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
    ColorClip,
    vfx,
    afx,
)

from musicvid.pipeline.effects import apply_effects, create_cinematic_bars, create_light_leak
from musicvid.pipeline.logo_overlay import apply_logo
from musicvid.pipeline.color_grade import prepare_lut_ffmpeg_params
from musicvid.pipeline.smart_crop import convert_for_platform
from musicvid.pipeline.wow_effects import apply_wow_effects


_SECTION_FONT_SIZES = {
    "chorus": 64,
    "verse":  54,
    "bridge": 48,
    "intro":  50,
    "outro":  46,
}
_DEFAULT_FONT_SIZE = 54

_SECTION_GRADES = {
    "verse":  (0.88, 1.08, 0.01),
    "chorus": (1.10, 1.18, 0.0),
    "bridge": (0.80, 1.25, -0.02),
    "intro":  (0.85, 1.05, 0.02),
    "outro":  (0.82, 1.03, 0.01),
}
_DEFAULT_GRADE = (0.92, 1.10, 0.0)


def apply_section_grade(clip, section):
    """Apply per-section color grade (saturation, contrast, brightness).

    Uses NumPy luminance-based saturation — no cv2 dependency.
    """
    import numpy as np

    sat, cont, bright = _SECTION_GRADES.get(section, _DEFAULT_GRADE)

    def grade_frame(frame):
        f = frame.astype(np.float32) + bright * 255
        f = (f - 128) * cont + 128
        # Saturation: blend toward luminance
        r, g, b = f[..., 0], f[..., 1], f[..., 2]
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        lum3 = np.stack([luminance] * 3, axis=-1)
        result = lum3 + (f - lum3) * sat
        return np.clip(result, 0, 255).astype(np.uint8)

    return clip.image_transform(grade_frame)


def _get_section_for_time(t, sections):
    """Return section label at time t, or 'verse' if not found."""
    if not sections:
        return "verse"
    for section in sections:
        if section["start"] <= t < section["end"]:
            return section.get("label", "verse")
    return "verse"


RESOLUTION_MAP = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
    "portrait": (1080, 1920),
}


def _get_resolution(resolution_str):
    """Map resolution string to (width, height) tuple."""
    return RESOLUTION_MAP.get(resolution_str, (1920, 1080))


def _create_ken_burns_clip(clip, duration, motion="slow_zoom_in", target_size=(1920, 1080)):
    """Apply Ken Burns effect (zoom/pan) to a clip."""
    w, h = target_size
    kb_w, kb_h = int(w * 1.15), int(h * 1.15)

    # Cover scale: expand to fill kb_w × kb_h preserving aspect ratio, then center-crop
    img_w, img_h = clip.size
    scale = max(kb_w / img_w, kb_h / img_h)
    clip = clip.resized(scale)
    x1 = (clip.w - kb_w) // 2
    y1 = (clip.h - kb_h) // 2
    clip = clip.cropped(x1=x1, y1=y1, x2=x1 + kb_w, y2=y1 + kb_h)
    clip = clip.with_duration(duration)

    if motion == "slow_zoom_in":
        def zoom_in(get_frame, t):
            progress = t / duration
            scale = 1.0 + 0.15 * progress
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            new_w, new_h = int(fw / scale), int(fh / scale)
            x = (fw - new_w) // 2
            y = (fh - new_h) // 2
            cropped = frame[y:y + new_h, x:x + new_w]
            from PIL import Image
            import numpy as np
            img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
            return np.array(img)
        return clip.transform(zoom_in)

    elif motion == "slow_zoom_out":
        def zoom_out(get_frame, t):
            progress = t / duration
            scale = 1.15 - 0.15 * progress
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            new_w, new_h = int(fw / scale), int(fh / scale)
            x = (fw - new_w) // 2
            y = (fh - new_h) // 2
            cropped = frame[y:y + new_h, x:x + new_w]
            from PIL import Image
            import numpy as np
            img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
            return np.array(img)
        return clip.transform(zoom_out)

    elif motion == "pan_left":
        def pan_l(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_offset = fw - w
            x = int(max_offset * (1 - progress))
            cropped = frame[0:h, x:x + w]
            return cropped
        return clip.transform(pan_l)

    elif motion == "pan_right":
        def pan_r(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_offset = fw - w
            x = int(max_offset * progress)
            cropped = frame[0:h, x:x + w]
            return cropped
        return clip.transform(pan_r)

    elif motion == "pan_up":
        def pan_u(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_offset = fh - h
            y = int(max_offset * (1 - progress))
            cropped = frame[y:y + h, 0:w]
            return cropped
        return clip.transform(pan_u)

    elif motion == "pan_down":
        def pan_d(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_offset = fh - h
            y = int(max_offset * progress)
            cropped = frame[y:y + h, 0:w]
            return cropped
        return clip.transform(pan_d)

    elif motion == "diagonal_drift":
        def diagonal(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_x = fw - w
            max_y = fh - h
            x = int(max_x * progress)
            y = int(max_y * progress)
            x = max(0, min(x, max_x))
            y = max(0, min(y, max_y))
            return frame[y:y + h, x:x + w]
        return clip.transform(diagonal)

    elif motion == "cut_zoom":
        def cut_zoom_fn(get_frame, t):
            progress = t / duration
            scale = 1.0 + 0.25 * progress  # 1.0 → 1.25
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            new_w, new_h = int(fw / scale), int(fh / scale)
            x = (fw - new_w) // 2
            y = (fh - new_h) // 2
            cropped = frame[y:y + new_h, x:x + new_w]
            from PIL import Image
            import numpy as np
            img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
            return np.array(img)
        return clip.transform(cut_zoom_fn)

    else:  # static
        clip = clip.resized(new_size=(w, h))
        clip = clip.with_duration(duration)
        return clip


def _remap_motion_for_portrait(motion):
    """Remap horizontal pans to vertical for portrait (9:16) format."""
    remap = {"pan_left": "pan_up", "pan_right": "pan_down"}
    return remap.get(motion, motion)


def convert_16_9_to_9_16(clip, target_w=1080, target_h=1920):
    """Convert a landscape clip to portrait 9:16 via scale + center crop.

    Scales so height == target_h preserving aspect ratio, then crops width to target_w.
    """
    src_w, src_h = clip.size
    scale = target_h / src_h
    new_w = int(src_w * scale)
    clip = clip.resized((new_w, target_h))
    x1 = (new_w - target_w) // 2
    x2 = x1 + target_w
    clip = clip.cropped(x1=x1, y1=0, x2=x2, y2=target_h)
    return clip


def _concatenate_with_transitions(scene_clips, scenes, bpm, target_size):
    """Concatenate scene clips applying per-scene transitions.

    Uses scene[i]["transition_to_next"] (set by _assign_dynamic_transitions).
    Falls back to "cut" if field absent.
    """
    beat_duration = 60.0 / bpm
    trans_durations = {
        "cut":           0.0,
        "cross_dissolve": max(0.2, min(0.8, round(beat_duration / 2, 2))),
        "fade":          max(0.2, min(0.8, round(beat_duration, 2))),
        "dip_white":     max(0.2, min(0.8, round(beat_duration * 0.75, 2))),
        "slide_left":    0.3,
        "slide_up":      0.3,
        "wipe_right":    0.2,
        "zoom_in_hard":  0.1,
    }

    # Determine transitions between each consecutive pair
    transitions = []
    for i in range(len(scenes) - 1):
        trans = scenes[i].get("transition_to_next", "cut")
        d = trans_durations.get(trans, 0.0)
        transitions.append((trans, d))

    # Fast path: all cuts
    if all(t == "cut" for t, _ in transitions):
        return concatenate_videoclips(scene_clips, method="compose")

    # Build composited clips with offsets
    clips_positioned = []
    cursor = 0.0
    for i, clip in enumerate(scene_clips):
        positioned = clip.with_start(cursor)
        # Apply incoming transition effect
        if i > 0:
            prev_trans, prev_d = transitions[i - 1]
            if prev_trans == "cross_dissolve" and prev_d > 0:
                positioned = positioned.with_effects([vfx.CrossFadeIn(prev_d)])
            elif prev_trans == "fade" and prev_d > 0:
                positioned = positioned.with_effects([vfx.FadeIn(prev_d)])
            elif prev_trans == "slide_left" and prev_d > 0:
                w = target_size[0]
                _d = prev_d
                def _make_slide_left_pos(w, _d):
                    def pos(t):
                        if t < _d:
                            return (int(w * (1 - t / _d)), 0)
                        return (0, 0)
                    return pos
                positioned = positioned.with_position(_make_slide_left_pos(w, _d))
            elif prev_trans == "slide_up" and prev_d > 0:
                h = target_size[1]
                _d = prev_d
                def _make_slide_up_pos(h, _d):
                    def pos(t):
                        if t < _d:
                            return (0, int(h * (1 - t / _d)))
                        return (0, 0)
                    return pos
                positioned = positioned.with_position(_make_slide_up_pos(h, _d))
            elif prev_trans == "wipe_right" and prev_d > 0:
                positioned = positioned.with_effects([vfx.CrossFadeIn(prev_d)])
        # Apply outgoing transition effect
        if i < len(scene_clips) - 1:
            trans, d = transitions[i]
            if trans == "cross_dissolve" and d > 0:
                positioned = positioned.with_effects([vfx.CrossFadeOut(d)])
            elif trans == "fade" and d > 0:
                positioned = positioned.with_effects([vfx.FadeOut(d)])
            elif trans == "zoom_in_hard" and d > 0:
                pass  # zoom_in_hard doesn't need outgoing effect on the outgoing clip
        clips_positioned.append(positioned)
        # Advance cursor; overlap for dissolves/slides
        if i < len(scene_clips) - 1:
            trans, d = transitions[i]
            if trans in ("cross_dissolve", "slide_left", "slide_up", "wipe_right", "zoom_in_hard"):
                cursor += clip.duration - d
            else:
                cursor += clip.duration

    # dip_white: add white flash overlays at transition points
    white_clips = []
    flash_cursor = 0.0
    for i, clip in enumerate(scene_clips[:-1]):
        trans, d = transitions[i]
        if trans in ("cross_dissolve", "slide_left", "slide_up", "wipe_right", "zoom_in_hard"):
            flash_cursor += clip.duration - d
        else:
            flash_cursor += clip.duration
        if trans == "dip_white" and d > 0:
            flash = ColorClip(size=target_size, color=(255, 255, 255), duration=d)
            flash = flash.with_start(flash_cursor - d / 2)
            flash = flash.with_effects([vfx.CrossFadeIn(d / 2), vfx.CrossFadeOut(d / 2)])
            white_clips.append(flash)

    all_clips = clips_positioned + white_clips
    total_duration = clips_positioned[-1].start + scene_clips[-1].duration
    return CompositeVideoClip(all_clips, size=target_size).with_duration(total_duration)


def _make_scale_pop_transform(anim_duration=0.15):
    """Return a MoviePy transform function for scale pop (1.15->1.0 over anim_duration).

    Used for chorus subtitle entry animation.
    """
    from PIL import Image
    import numpy as np

    def scale_pop(get_frame, t):
        frame = get_frame(t)
        if t >= anim_duration:
            return frame
        progress = t / anim_duration  # 0.0 -> 1.0
        scale = 1.15 - 0.15 * progress  # 1.15 -> 1.0
        h, w = frame.shape[:2]
        new_w = max(1, int(w / scale))
        new_h = max(1, int(h / scale))
        cx, cy = w // 2, h // 2
        x1 = max(0, cx - new_w // 2)
        y1 = max(0, cy - new_h // 2)
        x2 = min(w, x1 + new_w)
        y2 = min(h, y1 + new_h)
        cropped = frame[y1:y2, x1:x2]
        img = Image.fromarray(cropped)
        img = img.resize((w, h), Image.LANCZOS)
        return np.array(img)

    return scale_pop


def _make_reel_zoom_punch(punch_times):
    """Return a MoviePy transform for reel zoom punch on chorus downbeats.

    Scale 1.0 -> 1.12 in 2 frames (0.067s), return 1.12 -> 1.0 in 8 frames (0.267s).
    """
    from PIL import Image
    import numpy as np

    def zoom_punch(get_frame, t):
        frame = get_frame(t)
        for pt in punch_times:
            dt = t - pt
            if 0 <= dt < 0.067:
                scale = 1.0 + 0.12 * (dt / 0.067)
            elif 0.067 <= dt < 0.333:
                scale = 1.12 - 0.12 * ((dt - 0.067) / 0.267)
            else:
                continue
            fh, fw = frame.shape[:2]
            new_w = max(1, int(fw / scale))
            new_h = max(1, int(fh / scale))
            x = (fw - new_w) // 2
            y = (fh - new_h) // 2
            cropped = frame[y:y + new_h, x:x + new_w]
            img = Image.fromarray(cropped).resize((fw, fh), Image.LANCZOS)
            return np.array(img)
        return frame

    return zoom_punch


def _create_subtitle_clips(lyrics, subtitle_style, size, font_path=None, subtitle_margin_bottom=80, sections=None, reels_mode=False):
    """Create subtitle TextClips from lyrics with word-level timing."""
    clips = []
    color = subtitle_style.get("color", "#FFFFFF")
    outline_color = subtitle_style.get("outline_color", "#000000")
    margin_bottom = subtitle_margin_bottom

    if not lyrics:
        print("Warning: no lyrics segments — subtitles skipped")
        return clips

    for segment in lyrics:
        duration = segment["end"] - segment["start"]
        if duration <= 0:
            continue

        print(f"Napis: '{segment['text']}' start={segment['start']:.1f}s end={segment['end']:.1f}s")

        if sections:
            section = _get_section_for_time(segment["start"], sections)
            font_size = _SECTION_FONT_SIZES.get(section, subtitle_style.get("font_size", _DEFAULT_FONT_SIZE))
        else:
            section = None
            font_size = subtitle_style.get("font_size", _DEFAULT_FONT_SIZE)
        if reels_mode and section == "chorus":
            font_size = 72
        descender_pad = int(font_size * 0.35)
        padded_height = font_size + descender_pad

        y_pos = size[1] - margin_bottom - padded_height
        if y_pos >= size[1]:
            print(f"Warning: subtitle y={y_pos} is outside frame height={size[1]}, clamping")
            y_pos = size[1] - padded_height - 10

        effective_font = font_path
        try:
            txt_clip = TextClip(
                text=segment["text"],
                font_size=font_size,
                color=color,
                stroke_color=outline_color,
                stroke_width=2,
                font=effective_font,
                method="caption",
                size=(size[0] - 100, padded_height),
            )
        except Exception as e:
            print(f"Warning: subtitle failed for '{segment['text']}' with font {effective_font!r}: {e}")
            if effective_font is not None:
                try:
                    txt_clip = TextClip(
                        text=segment["text"],
                        font_size=font_size,
                        color=color,
                        stroke_color=outline_color,
                        stroke_width=2,
                        font=None,
                        method="caption",
                        size=(size[0] - 100, padded_height),
                    )
                except Exception as e2:
                    print(f"Warning: subtitle fallback also failed: {e2}")
                    continue
            else:
                continue

        offset_start = max(0.0, segment["start"] - 0.1)
        offset_duration = duration + (segment["start"] - offset_start)
        txt_clip = txt_clip.with_duration(offset_duration)
        txt_clip = txt_clip.with_start(offset_start)
        txt_clip = txt_clip.with_position(("center", y_pos))

        fade_duration = min(0.3, duration / 3)
        txt_clip = txt_clip.with_effects([
            vfx.CrossFadeIn(fade_duration),
            vfx.CrossFadeOut(fade_duration),
        ])

        # Scale-pop animation for chorus subtitles
        if sections and _get_section_for_time(segment["start"], sections) == "chorus":
            txt_clip = txt_clip.transform(_make_scale_pop_transform(0.15))

        clips.append(txt_clip)

        # White flash on subtitle entry for reels
        if reels_mode:
            flash_duration = 0.05
            flash = ColorClip(size=size, color=(255, 255, 255), duration=flash_duration)
            flash = flash.with_start(offset_start)
            flash = flash.with_effects([
                vfx.CrossFadeIn(flash_duration / 2),
                vfx.CrossFadeOut(flash_duration / 2),
            ])
            # Set opacity to 0.6 via mask
            import numpy as np
            mask_frame = np.full((size[1], size[0]), 0.6, dtype=np.float32)
            mask_clip = ImageClip(mask_frame, is_mask=True).with_duration(flash_duration)
            flash = flash.with_mask(mask_clip)
            clips.append(flash)

    return clips


def _create_title_card(text, size, duration=2.0):
    """Create a solid black title card with centred white text."""
    bg = ColorClip(size=size, color=(0, 0, 0), duration=duration)
    txt = TextClip(
        text=text,
        font_size=72,
        color="#FFFFFF",
        method="caption",
        size=(size[0] - 200, None),
    )
    txt = txt.with_duration(duration).with_position("center")
    return CompositeVideoClip([bg, txt], size=size)


def _create_bottom_gradient(width, height, duration, gradient_height_pct=0.3, opacity=0.6):
    """Create a dark gradient overlay at the bottom of the frame for reels.

    Gradient goes from transparent (top) to semi-opaque black (bottom).
    Improves subtitle readability in portrait/reels mode.

    Args:
        width: Frame width in pixels.
        height: Frame height in pixels.
        duration: Clip duration in seconds.
        gradient_height_pct: Gradient height as fraction of frame height (default 0.3).
        opacity: Maximum opacity of gradient (default 0.6, mapped to 0-1 mask values).

    Returns:
        MoviePy ImageClip positioned at the bottom of the frame.
    """
    import numpy as np

    grad_h = int(height * gradient_height_pct)

    # Solid black frame
    black_frame = np.zeros((grad_h, width, 3), dtype=np.uint8)
    clip = ImageClip(black_frame).with_duration(duration)

    # Gradient mask: 0 (transparent) at top, opacity at bottom
    mask_values = np.linspace(0, opacity, grad_h)[:, np.newaxis] * np.ones((1, width))
    mask_frame = mask_values.astype(np.float32)
    mask_clip = ImageClip(mask_frame, is_mask=True).with_duration(duration)

    clip = clip.with_mask(mask_clip)
    clip = clip.with_position(("center", height - grad_h))

    return clip


def _create_reel_intro_hook(video_clip, target_size, freeze_duration=0.5, fade_duration=0.3):
    """Create a freeze frame intro hook for reels.

    Takes the frame at 50% of the first second (the 'peak visual moment'),
    displays it for freeze_duration, then fades out into the normal video.

    Args:
        video_clip: The concatenated video clip.
        target_size: (width, height) tuple.
        freeze_duration: How long to show the freeze frame (default 0.5s).
        fade_duration: Fade out duration (default 0.3s).

    Returns:
        ImageClip of the freeze frame, or None if extraction fails.
    """
    try:
        sample_t = min(0.5, video_clip.duration / 2)
        frame = video_clip.get_frame(sample_t)
        freeze = ImageClip(frame).with_duration(freeze_duration)
        freeze = freeze.with_effects([vfx.FadeOut(fade_duration)])
        return freeze
    except Exception as e:
        print(f"WARN: reel intro hook failed: {e}")
        return None


def _load_scene_clip(video_path, scene, target_size, reels_style="blur-bg"):
    """Load a video or image clip for a scene."""
    if video_path is None:
        raise ValueError("video_path is None — no asset for this scene")

    path = Path(video_path)
    duration = scene["end"] - scene["start"]
    is_portrait = target_size == (1080, 1920)

    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
        if is_portrait:
            processed_path = convert_for_platform(str(path), "reels", style=reels_style)
            clip = ImageClip(processed_path)
        else:
            clip = ImageClip(str(path))
    else:
        clip = VideoFileClip(str(path))
        if clip.duration < duration:
            loops = int(duration / clip.duration) + 1
            clip = concatenate_videoclips([clip] * loops)
        clip = clip.subclipped(0, duration)

    # Video files (.mp4): skip Ken Burns — video already has motion
    if path.suffix.lower() == ".mp4":
        if is_portrait:
            return convert_16_9_to_9_16(clip, target_w=target_size[0], target_h=target_size[1])
        return clip.resized(new_size=target_size)

    return _create_ken_burns_clip(clip, duration, scene.get("motion", "static"), target_size)


def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path, resolution="1080p", font_path=None, effects_level="minimal", clip_start=None, clip_end=None, title_card_text=None, audio_fade_out=1.0, subtitle_margin_bottom=80, cinematic_bars=False, logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85, lut_path=None, lut_style=None, lut_intensity=0.85, reels_style="blur-bg", color_grade=None, wow_config=None):
    """Assemble the final music video.

    Args:
        analysis: Audio analysis dict from Stage 1.
        scene_plan: Scene plan dict from Stage 2.
        fetch_manifest: List of dicts with scene_index, video_path, search_query.
        audio_path: Path to the original audio file.
        output_path: Path for the output MP4 file.
        resolution: Output resolution string (720p, 1080p, 4k).
        font_path: Path to a font file for subtitles.
    """
    target_size = _get_resolution(resolution)
    scenes = scene_plan["scenes"]

    scene_clips = []
    for manifest_entry in fetch_manifest:
        idx = manifest_entry["scene_index"]
        scene = scenes[idx]
        clip = _load_scene_clip(manifest_entry["video_path"], scene, target_size, reels_style=reels_style)
        clip = apply_effects(clip, level=effects_level)
        section = scene.get("section", "verse")
        clip = apply_section_grade(clip, section)
        scene_clips.append(clip)

    bpm = analysis.get("bpm", 120.0)
    video = _concatenate_with_transitions(scene_clips, scenes, bpm, target_size)

    # Reel zoom punch on chorus downbeats
    if target_size == (1080, 1920):
        sections = analysis.get("sections", [])
        beats = analysis.get("beats", [])
        downbeats = beats[::4]
        chorus_downbeats = []
        for db in downbeats:
            for sec in sections:
                if sec.get("label") == "chorus" and sec["start"] <= db < sec["end"]:
                    chorus_downbeats.append(db)
                    break
        if chorus_downbeats:
            video = video.transform(_make_reel_zoom_punch(chorus_downbeats))

    subtitle_clips = _create_subtitle_clips(
        analysis.get("lyrics", []),
        scene_plan.get("subtitle_style", {}),
        target_size,
        font_path=font_path,
        subtitle_margin_bottom=subtitle_margin_bottom,
        sections=analysis.get("sections"),
        reels_mode=(target_size == (1080, 1920)),
    )

    layers = [video] + subtitle_clips

    # Bottom gradient overlay for portrait/reels mode — improves subtitle readability
    if target_size == (1080, 1920):
        gradient = _create_bottom_gradient(target_size[0], target_size[1], video.duration)
        layers.insert(1, gradient)

    if cinematic_bars:
        bars = create_cinematic_bars(target_size[0], target_size[1], video.duration)
        layers.extend(bars)

    if effects_level == "full":
        for manifest_entry in fetch_manifest:
            idx = manifest_entry["scene_index"]
            scene = scenes[idx]
            scene_duration = scene["end"] - scene["start"]
            leak = create_light_leak(scene_duration, target_size)
            leak = leak.with_start(leak.start + scene["start"])
            leak = leak.with_end(leak.end + scene["start"])
            layers.append(leak)

    # Logo overlay — topmost layer
    if logo_path:
        logo_clip = apply_logo(
            video, logo_path, logo_position, logo_size, logo_opacity
        )
        layers.append(logo_clip)

    final = CompositeVideoClip(layers, size=target_size)

    # Reel intro hook: freeze frame prepended to reel
    if target_size == (1080, 1920):
        intro_hook = _create_reel_intro_hook(video, target_size)
        if intro_hook:
            final = concatenate_videoclips([intro_hook, final])

    if clip_start is not None:
        final = final.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(1.0)])

    if title_card_text is not None:
        final = concatenate_videoclips([_create_title_card(title_card_text, target_size), final])

    audio = AudioFileClip(audio_path)
    if clip_start is not None:
        audio = audio.subclipped(clip_start, clip_end)
        audio = audio.with_effects([afx.AudioFadeIn(0.5), afx.AudioFadeOut(audio_fade_out)])
    final = final.with_audio(audio)
    final = final.with_duration(min(final.duration, audio.duration))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    lut_ffmpeg_params = prepare_lut_ffmpeg_params(
        lut_path=lut_path, lut_style=lut_style, intensity=lut_intensity
    )

    write_kwargs = dict(
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        fps=30,
    )
    if lut_ffmpeg_params:
        write_kwargs["ffmpeg_params"] = lut_ffmpeg_params

    final.write_videofile(output_path, **write_kwargs)

    # Apply global color grade via FFmpeg curves (post-write)
    if color_grade:
        from musicvid.pipeline.color_grade import apply_global_color_grade
        import shutil
        is_social = (target_size == (1080, 1920))
        tmp_graded = output_path + ".graded.mp4"
        success = apply_global_color_grade(output_path, tmp_graded, color_grade, is_social=is_social)
        if success:
            shutil.move(tmp_graded, output_path)

    if wow_config and wow_config.get("enabled", True):
        apply_wow_effects(
            video_path=output_path,
            analysis=analysis,
            scene_plan=scene_plan,
            wow_config=wow_config,
            video_width=target_size[0],
            video_height=target_size[1],
        )
