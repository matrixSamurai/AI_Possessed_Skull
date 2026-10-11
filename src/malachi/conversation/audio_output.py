from collections import deque
import threading
import numpy as np
from malachi.motion.jaw_sync import JawSync


class PlaybackBuffer:
    """Bounded PCM queue; consumed in 20 ms blocks by real or simulated output."""

    def __init__(self, settings):
        self.lock = threading.Lock()
        self.chunks = deque()
        self.samples = 0
        self.jaw = JawSync(settings.jaw_noise_gate, settings.jaw_gain)
        self.muted = False
        self.speaking = False
        self.generation = 0

    def push(self, audio):
        if len(audio) % 2:
            raise ValueError("PCM16 needs complete samples")
        block = np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768
        with self.lock:
            if self.samples + len(block) > 16000 * 15:
                raise BufferError("speech buffer exceeds 15 seconds")
            self.chunks.append(block)
            self.samples += len(block)

    def render(self, frames):
        with self.lock:
            output = np.zeros(frames, np.float32)
            offset = 0
            while self.chunks and offset < frames:
                chunk = self.chunks[0]
                count = min(len(chunk), frames - offset)
                output[offset : offset + count] = chunk[:count]
                offset += count
                self.samples -= count
                if count == len(chunk):
                    self.chunks.popleft()
                else:
                    self.chunks[0] = chunk[count:]
            if self.muted:
                output.fill(0)
            self.speaking = bool(np.any(np.abs(output) > self.jaw.noise_gate))
            position = self.jaw.process(output)
            return output, position, self.generation

    def clear(self):
        with self.lock:
            self.chunks.clear()
            self.samples = 0
            self.speaking = False
            self.generation += 1
            self.jaw.reset()
