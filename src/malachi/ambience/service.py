"""Exclusive output ownership: idle ambience transfers to the conversation mixer."""

import threading
import time
import numpy as np
from malachi.ambience.engine import AmbienceEngine
from malachi.events import ConversationEvent
from malachi.conversation.device_audio import SampleRateConverter, stream_options


class AmbienceService:
    def __init__(self, settings, emit):
        self.engine = AmbienceEngine(settings)
        self.emit = emit
        self.fresh_effects = None
        self.converter = SampleRateConverter(16000, 16000)
        self.pending = np.zeros(0, np.float32)
        self.output_rate = 16000
        self.exit = threading.Event()
        self.lock = threading.Lock()
        self.voice_owns_output = False
        self.last_audible_until = 0.0
        self.released = threading.Event()
        self.released.set()
        self.thread = threading.Thread(target=self._run, daemon=True, name="background-voices")
        self.thread.start()

    def release_output(self):
        with self.lock:
            self.voice_owns_output = True
        if not self.released.wait(2):
            raise RuntimeError("Background output handover timed out")
        return self.last_audible_until

    def return_output(self):
        with self.lock:
            self.voice_owns_output = False

    def render(self, frames, foreground=False, user_speaking=False):
        return self.engine.render(frames, foreground, user_speaking)

    def _callback(self, data, frames, timing, status):
        needed = max(0, frames - len(self.pending))
        count = self.converter.input_needed(needed) if needed else 0
        samples = self.engine.render(count)
        self.pending = np.concatenate((self.pending, self.converter.process(samples)))
        output = self.pending[:frames]
        self.pending = self.pending[frames:]
        data.fill(0)
        data[: len(output), :] = output[:, None]
        if np.any(samples):
            delay = max(0, timing.outputBufferDacTime - timing.currentTime)
            self.last_audible_until = time.monotonic() + delay + frames / self.output_rate + 0.3

    def _run(self):
        stream = None
        try:
            self.engine.load()
            if (
                self.engine.settings.ambience_fresh_effects_enabled
                and self.engine.settings.elevenlabs_api_key.get_secret_value()
            ):
                from malachi.ambience.fresh_effects import FreshEffects

                self.fresh_effects = FreshEffects(
                    self.engine.settings, self.engine.install_fresh, self.emit
                )
                if not self.engine.clips:
                    self.fresh_effects.request()
            last_burst = None
            while not self.exit.is_set():
                if self.engine.active and self.engine.started != last_burst:
                    last_burst = self.engine.started
                    if self.fresh_effects is not None:
                        self.fresh_effects.request()
                with self.lock:
                    wanted = (
                        self.engine.active
                        and not self.engine.paused
                        and not self.engine.muted
                        and not self.voice_owns_output
                    )
                    if not wanted and stream is not None:
                        stream.stop()
                        stream.close()
                        stream = None
                        self.released.set()
                    if wanted and stream is not None and not stream.active:
                        stream.close()
                        stream = None
                        self.released.set()
                        self.engine.stop()
                        self.engine.settings.ambience_enabled = False
                        self.emit(
                            ConversationEvent(
                                kind="summary",
                                detail="Background audio device stopped; ambience disabled",
                            )
                        )
                        wanted = False
                    if wanted and stream is None:
                        self.released.clear()
                        try:
                            import sounddevice as sd

                            options = stream_options(sd, self.engine.settings, "output")
                            self.output_rate = options["samplerate"]
                            self.converter = SampleRateConverter(16000, self.output_rate)
                            self.pending = np.zeros(0, np.float32)
                            stream = sd.OutputStream(
                                **options,
                                callback=self._callback,
                            )
                            stream.start()
                        except Exception as exc:
                            if stream is not None:
                                stream.close()
                            stream = None
                            self.released.set()
                            self.engine.stop()
                            self.engine.settings.ambience_enabled = False
                            self.engine.status = (
                                f"Background audio unavailable ({type(exc).__name__})"
                            )
                            self.emit(ConversationEvent(kind="summary", detail=self.engine.status))
                self.exit.wait(0.02)
        finally:
            try:
                if stream is not None:
                    stream.stop()
                    stream.close()
            finally:
                self.released.set()
                if self.fresh_effects is not None:
                    self.fresh_effects.close()

    def stop(self):
        self.engine.stop()

    def close(self):
        self.engine.stop()
        self.exit.set()
        self.thread.join(2)
        if self.fresh_effects is not None:
            self.fresh_effects.close()
