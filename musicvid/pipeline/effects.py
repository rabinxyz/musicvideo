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
