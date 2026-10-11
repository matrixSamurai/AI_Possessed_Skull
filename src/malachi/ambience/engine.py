"""Bounded, shuffled local PCM playback; detection never invokes a paid API."""

import random
import threading
import time
import wave
import numpy as np

RATE = 16000


def read_clip(path):
    with wave.open(str(path), "rb") as wav:
        if (
            wav.getframerate() != RATE
            or wav.getnchannels() != 1
            or wav.getsampwidth() != 2
            or wav.getcomptype() != "NONE"
            or not 0 < wav.getnframes() <= RATE * 30
        ):
            raise ValueError("Clips must be 16kHz mono PCM16 WAV, at most 30 seconds")
        data = wav.readframes(wav.getnframes())
        if len(data) != wav.getnframes() * 2:
            raise ValueError("Truncated WAV")
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768


class AmbienceEngine:
    def __init__(self, settings, clips=None, seed=None, clock=time.monotonic):
        self.settings, self.clock = settings, clock
        self.clips = clips or []
        self.lock = threading.RLock()
        self.rng = random.Random(seed)
        self.bag = []
        self.last_clip = None
        self.current = None
        self.position = self.gap_samples = 0
        self.armed = True
        self.qualifying = self.absent = None
        self.started = self.deadline = self.cooldown_until = 0.0
        self.active = self.paused = False
        self.muted = False
        self.duck_gain = 1.0
        self.status = "Disabled" if not settings.ambience_enabled else "Loading local clips"

    def load(self):
        clips, bad = [], 0
        for path in sorted(self.settings.ambience_directory.glob("*.wav"))[:16]:
            try:
                clips.append(read_clip(path))
            except (ValueError, OSError, EOFError, wave.Error):
                bad += 1
        with self.lock:
            self.clips = clips
            self.status = (
                f"Ready: {len(clips)} local clips"
                if clips
                else "No clips: generate or add 16kHz mono PCM16 WAV files"
            )
            if bad:
                self.status += f" ({bad} invalid files skipped)"

    def stop(self):
        with self.lock:
            self.active = False
            self.current = None
            self.position = self.gap_samples = 0
            self.bag.clear()

    def update(self, present, moving, conversation, guard_enabled, stopped, muted, now):
        with self.lock:
            self.muted = muted
            if stopped or not self.settings.ambience_enabled:
                self.stop()
                self.qualifying = self.absent = None
                self.armed = True
                self.status = "Stopped" if stopped else "Disabled"
                return
            if self.active and now >= self.deadline:
                self.stop()
                self.cooldown_until = now + self.settings.ambience_cooldown_seconds
            blocked = conversation and (
                not self.settings.ambience_during_conversation or guard_enabled
            )
            self.paused = blocked
            detected = present or moving
            if not detected:
                self.qualifying = None
                if self.absent is None:
                    self.absent = now
                if now - self.absent >= self.settings.ambience_rearm_seconds:
                    self.armed = True
            else:
                self.absent = None
                if self.qualifying is None:
                    self.qualifying = now
                if (
                    self.armed
                    and not self.active
                    and not blocked
                    and now >= self.cooldown_until
                    and now - self.qualifying >= self.settings.ambience_trigger_hold_seconds
                    and self.clips
                ):
                    self.started, self.deadline = now, now + self.settings.ambience_duration_seconds
                    self.active, self.armed = True, False
                    self.current = None
                    self.position = self.gap_samples = 0
                    self.duck_gain = 1.0
            if not self.clips:
                self.status = "No clips: generate or add local WAV files"
            elif blocked:
                self.status = "Paused for conversation / speaker echo guard"
            elif self.active:
                self.status = f"Playing background voices ({max(0, self.deadline - now):.0f}s left)"
            else:
                self.status = "Ready: waiting for face or sustained motion"

    def _choose(self):
        if not self.bag:
            self.bag = list(range(len(self.clips)))
            self.rng.shuffle(self.bag)
            if len(self.bag) > 1 and self.bag[-1] == self.last_clip:
                self.bag[0], self.bag[-1] = self.bag[-1], self.bag[0]
        index = self.bag.pop()
        self.last_clip = index
        self.current = self.clips[index]
        self.position = 0

    def render(self, frames, foreground=False, user_speaking=False):
        with self.lock:
            out = np.zeros(frames, np.float32)
            now = self.clock()
            if not self.active or self.paused or self.muted or now >= self.deadline:
                return out
            offset = 0
            while offset < frames:
                if self.gap_samples:
                    count = min(frames - offset, self.gap_samples)
                    self.gap_samples -= count
                    offset += count
                    continue
                if self.current is None:
                    self._choose()
                count = min(frames - offset, len(self.current) - self.position)
                positions = np.arange(self.position, self.position + count)
                # Short endpoint fades prevent clicks between voices.
                fade = np.minimum(
                    1, np.minimum(positions / 160, (len(self.current) - 1 - positions) / 160)
                )
                out[offset : offset + count] = (
                    self.current[self.position : self.position + count] * fade
                )
                self.position += count
                offset += count
                if self.position >= len(self.current):
                    self.current = None
                    self.gap_samples = int(self.rng.uniform(0.6, 1.8) * RATE)
            target = 0.15 if foreground or user_speaking else 1.0
            next_gain = self.duck_gain + (target - self.duck_gain) * min(1, frames / RATE / 0.05)
            gain = np.linspace(self.duck_gain, next_gain, frames, dtype=np.float32)
            self.duck_gain = next_gain
            # Fade burst in/out, independent of clip boundaries.
            envelope = max(0, min(1, (now - self.started) / 0.1, (self.deadline - now) / 0.15))
            out *= self.settings.ambience_volume * envelope * gain
            return out
