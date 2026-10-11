import math
import random
from malachi.motion.controller import clamp


class EyeMotion:
    """Shared eye linkage: bounded, time-based smoothing independent of frame rate."""

    def __init__(self, settings, seed=None):
        self.settings = settings
        self.x, self.y = 0.0, 0.3
        self.rng = random.Random(seed)
        self.blink_until = 0.0
        self.next_blink = 3.0
        self.jitter = (0.0, 0.0)
        self.next_jitter = 0.0

    def update(self, face, dt, now, enabled=True):
        if now >= self.next_jitter:
            self.jitter = (self.rng.uniform(-0.025, 0.025), self.rng.uniform(-0.02, 0.02))
            self.next_jitter = now + self.rng.uniform(0.4, 1.0)
        if now >= self.next_blink:
            self.blink_until = now + 0.16
            self.next_blink = now + self.rng.uniform(3, 7)
        target = (2 * face.center_x - 1, 2 * face.center_y - 1) if face and enabled else (0, 0.3)
        alpha = 1 - math.exp(-max(0, dt) / self.settings.eye_smoothing_seconds)
        limit = self.settings.eye_max_velocity * max(0, dt)
        self.x = clamp(self.x + clamp((target[0] + self.jitter[0] - self.x) * alpha, -limit, limit))
        self.y = clamp(self.y + clamp((target[1] + self.jitter[1] - self.y) * alpha, -limit, limit))
        return self.x, self.y

    def angles(self):
        return (
            self.x * self.settings.eye_max_pan_degrees,
            self.y * self.settings.eye_max_tilt_degrees,
        )
