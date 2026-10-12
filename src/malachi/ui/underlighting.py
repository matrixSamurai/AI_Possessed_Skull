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
        self.rgb = [95.0, 125.0, 105.0]
        self.last_time = None
        self.command = None
        self.command_until = 0.0

    def choose(self, command, now):
        self.command = command
        self.command_until = now + command.duration_seconds

    def clear_override(self):
        self.command = None

    def update(self, preset, accent, intensity, phase, now, emergency=False):
        dt = 0 if self.last_time is None else min(0.25, max(0, now - self.last_time))
        self.last_time = now
        if emergency:
            self.command = None
            self.level = 0.0
            self.rgb = [0.0, 0.0, 0.0]
            self.frame = LightingFrame((0, 0, 0), 0.0, "off")
            return self.frame
        target = 0.18 + 0.5 * intensity
        custom = self.command if self.command is not None and now < self.command_until else None
        if custom is None:
            self.command = None
        else:
            colors = {
                "red": (210, 18, 10),
                "green": (30, 165, 60),
                "blue": (25, 70, 200),
                "violet": (135, 35, 175),
                "amber": (210, 105, 15),
                "white": (190, 190, 170),
                "cyan": (25, 155, 165),
                "off": (0, 0, 0),
            }
            accent = colors[custom.color]
            target = custom.brightness
            preset = custom.effect
            if custom.color == "off" or target == 0:
                self.level = 0
                self.rgb = [0.0, 0.0, 0.0]
                self.frame = LightingFrame((0, 0, 0), 0, "off")
                return self.frame
        self.level += (target - self.level) * (1 - math.exp(-dt / 1.5))
        pulse = 0.86 + 0.14 * math.sin(phase * 0.85)
        if preset == "steady":
            pulse = 1
        if preset in ("inferno", "ember"):
            # Organic ember movement without abrupt flashes.
            pulse = 0.82 + 0.10 * math.sin(phase * 2.1) + 0.08 * math.sin(phase * 3.7)
        alpha = 1 - math.exp(-dt / 0.5)
        for i, channel in enumerate(accent):
            self.rgb[i] += (channel - self.rgb[i]) * alpha
        rgb = tuple(max(0, min(255, round(channel))) for channel in self.rgb)
        self.frame = LightingFrame(rgb, max(0, min(1, self.level * pulse)), preset)
        return self.frame
