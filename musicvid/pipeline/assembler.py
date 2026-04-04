"""Stage 4: Video assembly using MoviePy + FFmpeg."""

from pathlib import Path

from moviepy import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
    vfx,
)


RESOLUTION_MAP = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}


def _get_resolution(resolution_str):
    """Map resolution string to (width, height) tuple."""
    return RESOLUTION_MAP.get(resolution_str, (1920, 1080))


def _create_ken_burns_clip(clip, duration, motion="slow_zoom_in", target_size=(1920, 1080)):
    """Apply Ken Burns effect (zoom/pan) to a clip."""
    w, h = target_size
    clip = clip.resized(new_size=(int(w * 1.15), int(h * 1.15)))
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

    else:  # static
        clip = clip.resized(new_size=(w, h))
        clip = clip.with_duration(duration)
        return clip


def _create_subtitle_clips(lyrics, subtitle_style, size):
    """Create subtitle TextClips from lyrics with word-level timing."""
    clips = []
    font_size = subtitle_style.get("font_size", 48)
    color = subtitle_style.get("color", "#FFFFFF")
    outline_color = subtitle_style.get("outline_color", "#000000")
    margin_bottom = 80

    for segment in lyrics:
        duration = segment["end"] - segment["start"]
        if duration <= 0:
            continue

        txt_clip = TextClip(
            text=segment["text"],
            font_size=font_size,
            color=color,
            stroke_color=outline_color,
            stroke_width=2,
            font="Arial-Bold",
            method="caption",
            size=(size[0] - 100, None),
        )
        txt_clip = txt_clip.with_duration(duration)
        txt_clip = txt_clip.with_start(segment["start"])
        txt_clip = txt_clip.with_position(("center", size[1] - margin_bottom - font_size))

        fade_duration = min(0.3, duration / 3)
        txt_clip = txt_clip.with_effects([
            vfx.CrossFadeIn(fade_duration),
            vfx.CrossFadeOut(fade_duration),
        ])

        clips.append(txt_clip)

    return clips


def _load_scene_clip(video_path, scene, target_size):
    """Load a video or image clip for a scene."""
    path = Path(video_path)
    duration = scene["end"] - scene["start"]

    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
        clip = ImageClip(str(path))
    else:
        clip = VideoFileClip(str(path))
        if clip.duration < duration:
            loops = int(duration / clip.duration) + 1
            clip = concatenate_videoclips([clip] * loops)
        clip = clip.subclipped(0, duration)

    return _create_ken_burns_clip(clip, duration, scene.get("motion", "static"), target_size)


def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path, resolution="1080p"):
    """Assemble the final music video.

    Args:
        analysis: Audio analysis dict from Stage 1.
        scene_plan: Scene plan dict from Stage 2.
        fetch_manifest: List of dicts with scene_index, video_path, search_query.
        audio_path: Path to the original audio file.
        output_path: Path for the output MP4 file.
        resolution: Output resolution string (720p, 1080p, 4k).
    """
    target_size = _get_resolution(resolution)
    scenes = scene_plan["scenes"]

    scene_clips = []
    for manifest_entry in fetch_manifest:
        idx = manifest_entry["scene_index"]
        scene = scenes[idx]
        clip = _load_scene_clip(manifest_entry["video_path"], scene, target_size)
        scene_clips.append(clip)

    video = concatenate_videoclips(scene_clips, method="compose")

    subtitle_clips = _create_subtitle_clips(
        analysis.get("lyrics", []),
        scene_plan.get("subtitle_style", {}),
        target_size,
    )

    final = CompositeVideoClip([video] + subtitle_clips, size=target_size)

    audio = AudioFileClip(audio_path)
    final = final.with_audio(audio)
    final = final.with_duration(min(final.duration, audio.duration))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        fps=30,
    )
