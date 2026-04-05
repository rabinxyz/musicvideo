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


_SECTION_FONT_SIZES = {
    "chorus": 64,
    "verse":  54,
    "bridge": 48,
    "intro":  50,
    "outro":  46,
}
_DEFAULT_FONT_SIZE = 54


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
        # Apply outgoing transition effect
        if i < len(scene_clips) - 1:
            trans, d = transitions[i]
            if trans == "cross_dissolve" and d > 0:
                positioned = positioned.with_effects([vfx.CrossFadeOut(d)])
            elif trans == "fade" and d > 0:
                positioned = positioned.with_effects([vfx.FadeOut(d)])
        clips_positioned.append(positioned)
        # Advance cursor; overlap for dissolves
        if i < len(scene_clips) - 1:
            trans, d = transitions[i]
            if trans == "cross_dissolve":
                cursor += clip.duration - d
            else:
                cursor += clip.duration

    # dip_white: add white flash overlays at transition points
    white_clips = []
    flash_cursor = 0.0
    for i, clip in enumerate(scene_clips[:-1]):
        trans, d = transitions[i]
        if trans == "cross_dissolve":
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


def _create_subtitle_clips(lyrics, subtitle_style, size, font_path=None, subtitle_margin_bottom=80, sections=None):
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
            font_size = subtitle_style.get("font_size", _DEFAULT_FONT_SIZE)
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

        clips.append(txt_clip)

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


def _load_scene_clip(video_path, scene, target_size, reels_style="blur-bg"):
    """Load a video or image clip for a scene."""
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

    # Animated clips from Runway Gen-4: resize only, skip Ken Burns
    if scene.get("animate", False) and path.suffix.lower() == ".mp4":
        return clip.resized(new_size=target_size)

    return _create_ken_burns_clip(clip, duration, scene.get("motion", "static"), target_size)


def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path, resolution="1080p", font_path=None, effects_level="minimal", clip_start=None, clip_end=None, title_card_text=None, audio_fade_out=1.0, subtitle_margin_bottom=80, cinematic_bars=False, logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85, lut_path=None, lut_style=None, lut_intensity=0.85, reels_style="blur-bg"):
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
        scene_clips.append(clip)

    bpm = analysis.get("bpm", 120.0)
    video = _concatenate_with_transitions(scene_clips, scenes, bpm, target_size)

    subtitle_clips = _create_subtitle_clips(
        analysis.get("lyrics", []),
        scene_plan.get("subtitle_style", {}),
        target_size,
        font_path=font_path,
        subtitle_margin_bottom=subtitle_margin_bottom,
        sections=analysis.get("sections"),
    )

    layers = [video] + subtitle_clips

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
