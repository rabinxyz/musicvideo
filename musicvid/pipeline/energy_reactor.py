"""Energy-reactive effect parameter provider.

Provides energy-reactive parameters at arbitrary time t based on the
audio analysis energy_curve. Visual effects (color grade, zoom, vignette,
transitions, subtitles) query this class for dynamic values.
"""

import bisect


class EnergyReactor:
    """Energy-reactive effect parameter provider."""

    FLASH_SPIKE_THRESHOLD = 0.4
    FLASH_ENERGY_THRESHOLD = 0.85
    MAX_FLASHES = 2

    def __init__(self, analysis, reel_mode=False):
        self.energy_curve = analysis.get("energy_curve", [])
        self.energy_mean = analysis.get("energy_mean", 0.0)
        self.beats = analysis.get("beats", [])
        self.bpm = analysis.get("bpm", 120)
        self.sections = analysis.get("sections", [])
        self.energy_peaks = analysis.get("energy_peaks", [])
        self.reel_mode = reel_mode

        # Pre-extract times and energies for binary search
        self._times = [p[0] for p in self.energy_curve]
        self._energies = [p[1] for p in self.energy_curve]

    def _get_energy_raw(self, t):
        """Linear interpolation of energy_curve at time t, without reel boost."""
        if not self._times:
            return 0.0

        # Before first point
        if t <= self._times[0]:
            return self._energies[0]

        # After last point
        if t >= self._times[-1]:
            return self._energies[-1]

        # Binary search for the right interval
        idx = bisect.bisect_right(self._times, t)
        t0 = self._times[idx - 1]
        t1 = self._times[idx]
        e0 = self._energies[idx - 1]
        e1 = self._energies[idx]

        # Linear interpolation
        frac = (t - t0) / (t1 - t0)
        return e0 + frac * (e1 - e0)

    def get_energy(self, t):
        """Linear interpolation of energy_curve at time t with optional reel boost."""
        energy = self._get_energy_raw(t)
        if self.reel_mode:
            energy = min(1.0, energy * 1.3)
        return energy

    def get_section(self, t):
        """Return section label at time t. Defaults to 'verse'."""
        for sec in self.sections:
            if sec["start"] <= t < sec["end"]:
                return sec["label"]
        return "verse"

    def get_saturation(self, t):
        """Saturation: 0.82 + energy * 0.28."""
        return 0.82 + self.get_energy(t) * 0.28

    def get_contrast(self, t):
        """Contrast: 1.05 + energy * 0.15."""
        return 1.05 + self.get_energy(t) * 0.15

    def get_zoom_scale(self, t):
        """Zoom scale: min(1.08, 1.02 + energy * 0.06)."""
        return min(1.08, 1.02 + self.get_energy(t) * 0.06)

    def get_vignette_strength(self, t):
        """Vignette strength: max(0.2, 0.7 - energy * 0.5)."""
        return max(0.2, 0.7 - self.get_energy(t) * 0.5)

    def get_transition(self, t):
        """Return transition dict based on energy at time t."""
        energy = self.get_energy(t)
        if energy > 0.75:
            ttype = "cut"
        elif energy > 0.45:
            ttype = "cross_dissolve"
        elif energy > 0.20:
            ttype = "fade"
        else:
            ttype = "cross_dissolve"
        duration = max(0.15, 0.8 - energy * 0.65)
        return {"type": ttype, "duration": duration}

    def get_font_size(self, t, base=54):
        """Font size: int(base + energy * 12)."""
        return int(base + self.get_energy(t) * 12)

    def get_subtitle_animation(self, t):
        """Subtitle animation style based on energy."""
        energy = self.get_energy(t)
        if energy > 0.7:
            return "scale_pop"
        elif energy > 0.4:
            return "slide_up"
        else:
            return "fade"

    def get_light_flash_times(self):
        """Find energy spikes for light flash effects.

        Detects energy jumps > FLASH_SPIKE_THRESHOLD in 0.5s window
        AND absolute energy > FLASH_ENERGY_THRESHOLD.
        Returns top MAX_FLASHES times sorted by spike magnitude.
        """
        if len(self._times) < 2:
            return []

        spikes = []
        for i in range(len(self._times)):
            t = self._times[i]
            energy = self._energies[i]

            if energy <= self.FLASH_ENERGY_THRESHOLD:
                continue

            # Look back 0.5s for the energy jump
            t_back = t - 0.5
            energy_back = self._get_energy_raw(max(t_back, self._times[0]))
            spike = energy - energy_back

            if spike > self.FLASH_SPIKE_THRESHOLD:
                spikes.append((spike, t))

        # Sort by spike magnitude descending, take top MAX_FLASHES
        spikes.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in spikes[:self.MAX_FLASHES]]
