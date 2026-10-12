from collections import deque
import threading
import time
import numpy as np
from malachi.motion.jaw_sync import JawSync


class PlaybackBuffer:
    """Bounded PCM queue; consumed in 20 ms blocks by real or simulated output."""

    def __init__(self, settings, clock=time.monotonic):
        self.settings = settings
        self.clock = clock
        self.lock = threading.Lock()
        self.playing = False
        self.wait_started = None
        self.drained_at = None
        self.refills = 0
        self.interruptions = 0
        self.dropped_samples = 0
        self.chunks = deque()
        self.samples = 0
        self.jaw = JawSync(settings.jaw_noise_gate, settings.jaw_gain)
        self.muted = False
        self.speaking = False
        self.generation = 0

    def push(self, audio):
        if len(audio) % 2:
            raise ValueError("PCM16 needs complete samples")
        with self.lock:
            capacity = max(
                0, int(16000 * self.settings.audio_playback_queue_seconds) - self.samples
            )
            count = min(len(audio) // 2, capacity)
            dropped = len(audio) // 2 - count
            self.dropped_samples += dropped
            if not count:
                return dropped
            # Preserve queued speech and the next samples; bound memory even for
            # an oversized provider packet. Excess tail is dropped, never fatal.
            block = np.frombuffer(audio, dtype="<i2", count=count).astype(np.float32) / 32768
            if self.wait_started is None and not self.playing:
                now = self.clock()
                self.wait_started = now
                if self.drained_at is not None and now - self.drained_at < 0.5:
                    self.refills += 1
            self.chunks.append(block)
            self.samples += len(block)
            return dropped

    def render(self, frames):
        with self.lock:
            output = np.zeros(frames, np.float32)
            offset = 0
            now = self.clock()
            if not self.playing and self.samples:
                threshold = 16 * self.settings.audio_playback_buffer_ms
                expired = (
                    self.wait_started is not None
                    and now - self.wait_started >= self.settings.audio_playback_max_wait_ms / 1000
                )
                if self.samples >= threshold or expired:
                    self.playing = True
            while self.playing and self.chunks and offset < frames:
                chunk = self.chunks[0]
                count = min(len(chunk), frames - offset)
                output[offset : offset + count] = chunk[:count]
                offset += count
                self.samples -= count
                if count == len(chunk):
                    self.chunks.popleft()
                else:
                    self.chunks[0] = chunk[count:]
            if self.playing and not self.samples:
                self.playing = False
                self.wait_started = None
                self.drained_at = now
            if self.muted:
                output.fill(0)
            self.speaking = bool(np.any(np.abs(output) > self.jaw.noise_gate))
            position = self.jaw.process(output)
            return output, position, self.generation

    def stats(self):
        with self.lock:
            return {
                "buffer_ms": self.samples / 16,
                "refills": self.refills,
                "interruptions": self.interruptions,
                "dropped_samples": self.dropped_samples,
            }

    def clear(self, interrupted=False):
        with self.lock:
            self.playing = False
            self.wait_started = self.drained_at = None
            if interrupted:
                self.interruptions += 1
            self.chunks.clear()
            self.samples = 0
            self.speaking = False
            self.generation += 1
            self.jaw.reset()
