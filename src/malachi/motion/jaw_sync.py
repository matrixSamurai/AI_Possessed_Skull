import math
import numpy as np
from malachi.motion.controller import clamp


class JawSync:
    """Envelope of the PCM block consumed by the playback callback, never speech text."""

    def __init__(self, noise_gate=0.015, gain=5):
        self.noise_gate, self.gain = noise_gate, gain
        self.position = 0.0

    def process(self, pcm, rate=16000):
        samples = np.asarray(pcm, dtype=np.float32)
        rms = float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0
        target = clamp((rms - self.noise_gate) * self.gain, 0, 1)
        seconds = samples.size / rate
        tau = 0.04 if target > self.position else 0.1
        self.position += (target - self.position) * (1 - math.exp(-seconds / tau))
        if self.position < 0.001:
            self.position = 0.0
        return self.position

    def reset(self):
        self.position = 0.0
