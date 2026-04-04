"""Visual effects for music video clips."""

import numpy as np
from moviepy import ColorClip, ImageClip, vfx


def apply_warm_grade(clip):
    """Apply warm color grading: R+15, G+5, B-10, clamped to 0-255."""
    def _warm(get_frame, t):
        frame = get_frame(t).astype(np.int16)
        frame[:, :, 0] += 15
        frame[:, :, 1] += 5
        frame[:, :, 2] -= 10
        return np.clip(frame, 0, 255).astype(np.uint8)
    return clip.transform(_warm)


def apply_vignette(clip):
    """Apply vignette: darken edges by up to 40% using Gaussian mask."""
    _vignette_cache = {}

    def _vignette(get_frame, t):
        frame = get_frame(t)
        h, w = frame.shape[:2]
        key = (h, w)
        if key not in _vignette_cache:
            y = np.linspace(-1, 1, h)
            x = np.linspace(-1, 1, w)
            xv, yv = np.meshgrid(x, y)
            dist = np.sqrt(xv ** 2 + yv ** 2)
            # Gaussian falloff: center=1.0, edges~0.6
            sigma = 0.8
            mask = np.exp(-(dist ** 2) / (2 * sigma ** 2))
            # Scale so center is 1.0, corners darken by ~40%
            mask = 0.6 + 0.4 * mask
            _vignette_cache[key] = mask[:, :, np.newaxis].astype(np.float32)
        return (frame * _vignette_cache[key]).astype(np.uint8)
    return clip.transform(_vignette)


def apply_film_grain(clip):
    """Apply animated film grain: Gaussian noise sigma=8, opacity 0.15."""
    def _grain(get_frame, t):
        frame = get_frame(t).astype(np.float32)
        noise = np.random.normal(0, 8, frame.shape).astype(np.float32)
        result = frame + noise * 0.15
        return np.clip(result, 0, 255).astype(np.uint8)
    return clip.transform(_grain)


def create_light_leak(duration, size):
    """Create an animated light leak overlay for a scene.

    Orange-gold gradient, opacity 0.2, appears once between 20-60% of duration,
    sweeps across the frame over ~1.5 seconds.
    """
    w, h = size
    # Create orange-gold gradient image
    gradient = np.zeros((h, w, 3), dtype=np.uint8)
    for x in range(w):
        alpha = max(0, 1 - abs(x - w // 2) / (w // 2))
        gradient[:, x, 0] = int(255 * alpha * 0.2)  # R
        gradient[:, x, 1] = int(180 * alpha * 0.2)   # G
        gradient[:, x, 2] = int(50 * alpha * 0.2)    # B

    leak_duration = min(1.5, duration * 0.3)
    start_time = duration * (0.2 + np.random.random() * 0.4)

    clip = ImageClip(gradient)
    clip = clip.with_duration(leak_duration)
    clip = clip.with_start(start_time)
    clip = clip.with_end(start_time + leak_duration)
    clip = clip.with_position("center")
    clip = clip.with_effects([
        vfx.CrossFadeIn(leak_duration * 0.3),
        vfx.CrossFadeOut(leak_duration * 0.3),
    ])

    return clip


def create_cinematic_bars(width, height, duration):
    """Create top and bottom black cinematic bars (12% height each)."""
    bar_h = int(height * 0.12)
    top = ColorClip(size=(width, bar_h), color=(0, 0, 0))
    top = top.with_duration(duration)
    top = top.with_position(("center", 0))

    bottom = ColorClip(size=(width, bar_h), color=(0, 0, 0))
    bottom = bottom.with_duration(duration)
    bottom = bottom.with_position(("center", height - bar_h))

    return [top, bottom]
