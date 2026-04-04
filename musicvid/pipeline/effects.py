"""Visual effects for music video clips."""

import numpy as np


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
