"""Time-based theatrical eye intensity, independent of tracking and hardware."""

import math


class EyeEffects:
    def __init__(self):
        self.intensity = 0.0
        self.phase = 0.0
        self.last_time = None
        self.preset = "calm"
        self.command = None
        self.command_until = 0.0
        self.accent = [100.0, 220.0, 210.0]

    def choose(self, command, now):
        self.command = command
        self.command_until = now + command.duration_seconds

    def update(self, state, now, qualification=0.0, speaking=False, emergency=False):
        dt = 0.0 if self.last_time is None else min(0.25, max(0.0, now - self.last_time))
        self.last_time = now
        self.phase += dt
        state = getattr(state, "value", state)
        targets = {
            "IDLE": 0.05,
            "WATCHING": 0.2,
            "STALKING": 0.3 + 0.4 * qualification,
            "AWAKENING": 0.85,
            "CONVERSING": 0.7 + 0.2 * math.sin(self.phase * 0.22) ** 2,
            "ENDING": 0.35,
            "COOLDOWN": 0.05,
        }
        target = (
            0.0 if emergency else min(1.0, targets.get(state, 0.05) + (0.06 if speaking else 0))
        )
        if emergency or state in ("ENDING", "COOLDOWN", "IDLE"):
            self.command = None
        if self.command is not None and now < self.command_until:
            self.preset = self.command.preset
            target = self.command.intensity if self.preset != "calm" else 0.05
        else:
            self.command = None
            if state == "CONVERSING":
                self.preset = (
                    "spectral"
                    if speaking
                    else ("hypnosis", "mischievous", "storm", "mirror")[int(self.phase / 12) % 4]
                )
            else:
                self.preset = "inferno" if state in ("AWAKENING", "STALKING") else "calm"
        if emergency:
            self.preset = "calm"
        colors = {
            "calm": (90, 210, 195),
            "inferno": (255, 40, 12),
            "spectral": (90, 250, 215),
            "storm": (170, 140, 255),
            "hypnosis": (240, 90, 220),
            "mischievous": (255, 190, 60),
            "mirror": (160, 200, 250),
        }
        alpha = 1 - math.exp(-dt / 0.8)
        for i, channel in enumerate(colors[self.preset]):
            self.accent[i] += (channel - self.accent[i]) * alpha
        # Build slowly; settle gently. No flashing or frame-rate-dependent steps.
        tau = 3.0 if target > self.intensity else 4.0
        self.intensity += (target - self.intensity) * (1 - math.exp(-dt / tau))
        return self.intensity
