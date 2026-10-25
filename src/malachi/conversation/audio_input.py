import queue
import threading
import time
import numpy as np
from malachi.events import ConversationEvent
from malachi.conversation.device_audio import SampleRateConverter, stream_options


class AudioDuplex:
    """PortAudio callbacks never perform network I/O. PCM16 mono, 16 kHz."""

    def __init__(self, playback, emit, jaw_emit):
        self.playback, self.emit, self.jaw_emit = playback, emit, jaw_emit
        self.input_converter = SampleRateConverter(16000, 16000)
        self.output_converter = SampleRateConverter(16000, 16000)
        self.output_pending = np.zeros(0, np.float32)
        self.output_rate = 16000
        self.output_generation = playback.generation
        self.mic_muted = False
        self.opening_pending = False
        self.ambience = None
        self.active = False
        self.input = self.output_stream = None
        self.queue = queue.Queue(maxsize=50)
        self.stop_event = threading.Event()
        self.thread = None
        self.user_speaking = self.agent_speaking = False
        self.last_voice = 0.0
        self.suppress_mic_during_playback = playback.settings.audio_suppress_mic_during_playback
        self.speaker_guard_until = 0.0
        self.output_underruns = 0
        self.last_output_notice = float("-inf")
        self.overflow_reported = False

    def start(self, send):
        import sounddevice as sd

        self.stop_event.clear()
        self.send = send
        self.user_speaking = self.agent_speaking = False
        self.last_voice = self.speaker_guard_until = 0.0
        self.overflow_reported = False
        while not self.queue.empty():
            self.queue.get_nowait()
        try:
            if self.ambience is not None:
                self.speaker_guard_until = max(
                    self.speaker_guard_until, self.ambience.release_output()
                )
            input_options = stream_options(sd, self.playback.settings, "input")
            output_options = stream_options(sd, self.playback.settings, "output")
            self.input_converter = SampleRateConverter(input_options["samplerate"], 16000)
            self.output_converter = SampleRateConverter(16000, output_options["samplerate"])
            self.output_pending = np.zeros(0, np.float32)
            self.output_rate = output_options["samplerate"]
            self.output_stream = sd.OutputStream(
                **output_options,
                callback=self._output,
                finished_callback=self._finished,
            )
            self.input = sd.InputStream(
                **input_options,
                callback=self._input,
                finished_callback=self._finished,
            )
            self.output_stream.start()
            self.input.start()
            self.active = True
            self.thread = threading.Thread(target=self._sender, daemon=True, name="microphone")
            self.thread.start()
        except Exception:
            self.stop()
            raise

    def _finished(self):
        if not self.stop_event.is_set():
            self.emit(ConversationEvent(kind="error", detail="Audio device stopped unexpectedly"))

    def _input(self, data, frames, timing, status):
        mono = data.astype(np.float32).mean(axis=1)
        converted = self.input_converter.process(mono)
        if not len(converted):
            return
        audio = np.clip(converted, -32768, 32767).astype("<i2")
        now = time.monotonic()
        guarded = self.suppress_mic_during_playback and (
            (self.playback.samples > 0 and not self.playback.muted)
            or now < self.speaker_guard_until
        )
        if self.mic_muted or self.opening_pending or guarded:
            audio.fill(0)
        rms = float(np.sqrt(np.mean((audio.astype(np.float32) / 32768) ** 2)))
        if rms > 0.025:
            self.last_voice = now
        speaking = rms > 0.025 or (self.user_speaking and now - self.last_voice < 0.4)
        if speaking != self.user_speaking:
            self.user_speaking = speaking
            self.emit(ConversationEvent(kind="user_start" if speaking else "user_end"))
        try:
            self.queue.put_nowait(audio.astype("<i2").tobytes())
        except queue.Full:
            if not self.overflow_reported:
                self.overflow_reported = True
                self.emit(
                    ConversationEvent(
                        kind="error", detail="Microphone network backlog exceeded 1 second"
                    )
                )
        if status:
            self.emit(ConversationEvent(kind="summary", detail="audio input status"))

    def _output(self, data, frames, timing, status):
        if self.output_generation != self.playback.generation:
            self.output_converter = SampleRateConverter(16000, self.output_rate)
            self.output_pending = np.zeros(0, np.float32)
            self.output_generation = self.playback.generation
        needed = max(0, frames - len(self.output_pending))
        source_frames = self.output_converter.input_needed(needed) if needed else 0
        samples, jaw, generation = self.playback.render(source_frames)
        agent_audible = bool(np.any(samples))
        # Only agent PCM drives jaw/speaking telemetry. Background voices are a
        # separate quiet channel mixed here so only one device output is active.
        if self.ambience is not None:
            background = self.ambience.render(
                source_frames, self.playback.speaking, self.user_speaking
            )
            samples = np.clip(samples + background, -1, 1)
        converted = self.output_converter.process(samples)
        self.output_pending = np.concatenate((self.output_pending, converted))
        output = self.output_pending[:frames]
        self.output_pending = self.output_pending[frames:]
        data.fill(0)
        data[: len(output), :] = output[:, None]
        # Schedule jaw for actual DAC presentation time, including device buffering.
        delay = max(0, timing.outputBufferDacTime - timing.currentTime)
        now = time.monotonic()
        self.jaw_emit(jaw, now + delay, generation)
        if agent_audible:
            self.speaker_guard_until = now + delay + frames / self.output_rate + 0.3
        speaking = self.playback.speaking
        if speaking != self.agent_speaking:
            self.agent_speaking = speaking
            self.emit(ConversationEvent(kind="agent_start" if speaking else "agent_end"))
        if status:
            if getattr(status, "output_underflow", False):
                self.output_underruns += 1
            if now - self.last_output_notice >= 5:
                self.last_output_notice = now
                self.emit(
                    ConversationEvent(
                        kind="summary", detail="Audio device underrun/status; check audio load"
                    )
                )

    def _sender(self):
        # 100 ms packets reduce WebSocket traffic; PortAudio stays at 20 ms for jaw timing.
        target_bytes = 32 * self.playback.settings.audio_input_chunk_ms
        pending = bytearray()
        while not self.stop_event.is_set():
            try:
                pending.extend(self.queue.get(timeout=0.1))
                if len(pending) < target_bytes:
                    continue
            except queue.Empty:
                if not pending:
                    continue
                try:
                    if not self.stop_event.is_set():
                        self.send(bytes(pending))
                    pending.clear()
                except Exception:
                    if not self.stop_event.is_set():
                        self.emit(
                            ConversationEvent(kind="error", detail="audio transmission failed")
                        )
                    return
                continue
            if self.stop_event.is_set():
                return
            try:
                while len(pending) >= target_bytes:
                    self.send(bytes(pending[:target_bytes]))
                    del pending[:target_bytes]
            except Exception:
                if not self.stop_event.is_set():
                    self.emit(ConversationEvent(kind="error", detail="audio transmission failed"))
                return

    def stop(self):
        self.active = False
        self.stop_event.set()
        for stream in (self.input, self.output_stream):
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
        self.input = self.output_stream = None
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=1)
        self.playback.clear()
        if self.ambience is not None:
            self.ambience.return_output()
