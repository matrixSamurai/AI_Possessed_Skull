"""Time-based theatrical eye intensity, independent of tracking and hardware."""

import math


class EyeEffects:
    def __init__(self):
        self.intensity = 0.0
        self.phase = 0.0
        self.last_time = None

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
        # Build slowly; settle gently. No flashing or frame-rate-dependent steps.
        tau = 3.0 if target > self.intensity else 4.0
        self.intensity += (target - self.intensity) * (1 - math.exp(-dt / tau))
        return self.intensity
