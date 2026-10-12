"""Preview lighting state ready for a future LED backend, independent of Qt."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class LightingFrame:
    rgb: tuple[int, int, int]
    brightness: float
    effect: str


class UnderLighting:
    def __init__(self):
        self.frame = LightingFrame((95, 125, 105), 0.15, "calm")
        self.level = 0.15
        self.last_time = None

    def update(self, preset, accent, intensity, phase, now, emergency=False):
        dt = 0 if self.last_time is None else min(0.25, max(0, now - self.last_time))
        self.last_time = now
        if emergency:
            self.level = 0.0
            self.frame = LightingFrame((0, 0, 0), 0.0, "off")
            return self.frame
        target = 0.18 + 0.5 * intensity
        self.level += (target - self.level) * (1 - math.exp(-dt / 1.5))
        pulse = 0.86 + 0.14 * math.sin(phase * 0.85)
        if preset == "inferno":
            # Organic ember movement without abrupt flashes.
            pulse = 0.82 + 0.10 * math.sin(phase * 2.1) + 0.08 * math.sin(phase * 3.7)
        rgb = tuple(max(0, min(255, round(channel))) for channel in accent)
        self.frame = LightingFrame(rgb, max(0, min(1, self.level * pulse)), preset)
        return self.frame
