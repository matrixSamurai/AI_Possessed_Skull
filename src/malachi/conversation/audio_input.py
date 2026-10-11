import queue
import threading
import time
import numpy as np
from malachi.events import ConversationEvent


class AudioDuplex:
    """PortAudio callbacks never perform network I/O. PCM16 mono, 16 kHz."""

    def __init__(self, playback, emit, jaw_emit):
        self.playback, self.emit, self.jaw_emit = playback, emit, jaw_emit
        self.mic_muted = False
        self.active = False
        self.input = self.output_stream = None
        self.queue = queue.Queue(maxsize=16)
        self.stop_event = threading.Event()
        self.thread = None
        self.user_speaking = self.agent_speaking = False
        self.last_voice = 0.0

    def start(self, send):
        import sounddevice as sd

        self.stop_event.clear()
        self.send = send
        try:
            self.output_stream = sd.OutputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                blocksize=320,
                callback=self._output,
                finished_callback=self._finished,
            )
            self.input = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="int16",
                blocksize=320,
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
        audio = data.copy()
        if self.mic_muted:
            audio.fill(0)
        rms = float(np.sqrt(np.mean((audio.astype(np.float32) / 32768) ** 2)))
        now = time.monotonic()
        if rms > 0.025:
            self.last_voice = now
        speaking = rms > 0.025 or (self.user_speaking and now - self.last_voice < 0.4)
        if speaking != self.user_speaking:
            self.user_speaking = speaking
            self.emit(ConversationEvent(kind="user_start" if speaking else "user_end"))
        try:
            self.queue.put_nowait(audio.astype("<i2").tobytes())
        except queue.Full:
            self.emit(ConversationEvent(kind="error", detail="microphone send queue overflow"))
        if status:
            self.emit(ConversationEvent(kind="summary", detail="audio input status"))

    def _output(self, data, frames, timing, status):
        samples, jaw, generation = self.playback.render(frames)
        data[:, 0] = samples
        # Schedule jaw for actual DAC presentation time, including device buffering.
        delay = max(0, timing.outputBufferDacTime - timing.currentTime)
        self.jaw_emit(jaw, time.monotonic() + delay, generation)
        speaking = self.playback.speaking
        if speaking != self.agent_speaking:
            self.agent_speaking = speaking
            self.emit(ConversationEvent(kind="agent_start" if speaking else "agent_end"))
        if status:
            self.emit(ConversationEvent(kind="summary", detail="audio output status"))

    def _sender(self):
        while not self.stop_event.is_set():
            try:
                audio = self.queue.get(timeout=0.1)
                self.send(audio)
            except queue.Empty:
                continue
            except Exception:
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
