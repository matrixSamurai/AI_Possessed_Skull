import asyncio
import queue
import threading
import time
import numpy as np
from malachi.events import ConversationEvent
from malachi.conversation.audio_output import PlaybackBuffer
from malachi.conversation.audio_input import AudioDuplex


class ConversationManager:
    """One worker per authorization. Bounded retries only before connection succeeds."""

    def __init__(self, settings, client_factory=None):
        self.settings = settings
        self.events = queue.Queue(maxsize=512)
        self.jaws = queue.Queue(maxsize=256)
        self.playback = PlaybackBuffer(settings)
        self.audio = AudioDuplex(self.playback, self.emit, self.jaw_emit)
        self.stop_event = threading.Event()
        self.thread = None
        self.connected = False
        self.ever_connected = False
        self.sessions = self.failures = 0
        self.total_seconds = 0.0
        self.connected_at = None
        self.last_started = self.last_ended = None
        self.factory = client_factory
        self.scene_status = "Disabled"
        self.pending_frame = None
        self.mock_reply = threading.Event()

    def emit(self, event):
        if event.kind == "connected":
            self.ever_connected = True
        try:
            self.events.put_nowait(event)
        except queue.Full:
            self.stop_event.set()

    def jaw_emit(self, value, due, generation):
        try:
            self.jaws.put_nowait((due, value, generation))
        except queue.Full:
            self.stop_event.set()

    def start(self, frame=None):
        if self.thread and self.thread.is_alive():
            return False
        self.stop_event.clear()
        self.ever_connected = False
        self.mock_reply.clear()
        if (
            self.settings.conversation_backend != "elevenlabs"
            or not self.settings.vision_context_enabled
        ):
            frame = None
        self.pending_frame = frame
        self.thread = threading.Thread(target=self._worker, daemon=True, name="conversation")
        self.thread.start()
        return True

    def _worker(self):
        frame, self.pending_frame = self.pending_frame, None
        try:
            if self.settings.conversation_backend == "mock":
                self._mock()
            elif self.settings.conversation_backend == "elevenlabs":
                coroutine = self._live(frame)
                frame = None
                asyncio.run(coroutine)
        finally:
            self.audio.stop()
            self.emit(ConversationEvent(kind="closed"))

    def _prepare_snapshot(self, frame):
        if not self.settings.vision_context_enabled:
            self.emit(ConversationEvent(kind="scene", detail="Disabled"))
            return None
        if frame is None:
            self.emit(ConversationEvent(kind="scene", detail="Skipped: no fresh camera snapshot"))
            return None
        from malachi.vision.scene_context import PreparedSnapshot, encode_snapshot

        try:
            snapshot = PreparedSnapshot(
                encode_snapshot(frame, self.settings.vision_context_max_image_side)
            )
            self.emit(ConversationEvent(kind="scene", detail="Snapshot ready for ElevenLabs"))
            return snapshot
        except Exception as exc:
            self.emit(
                ConversationEvent(
                    kind="scene", detail=f"Snapshot skipped ({type(exc).__name__}); voice continues"
                )
            )
            return None

    async def _live(self, frame=None):
        from malachi.conversation.elevenlabs_client import ElevenLabsClient

        snapshot = self._prepare_snapshot(frame) if not self.stop_event.is_set() else None
        frame = None
        factory = self.factory or ElevenLabsClient
        try:
            for attempt in range(3):
                if self.stop_event.is_set():
                    return
                try:
                    client = factory(self.settings, self.playback, self.audio, self.emit)
                    if snapshot is not None:
                        client.snapshot = snapshot
                    await client.run(self.stop_event)
                    return
                except Exception as exc:
                    self.failures += 1
                    self.emit(
                        ConversationEvent(
                            kind="summary", detail=f"Connection: {type(exc).__name__}"
                        )
                    )
                    if (
                        self.ever_connected
                        or isinstance(exc, (ValueError, ImportError))
                        or attempt == 2
                    ):
                        self.emit(
                            ConversationEvent(
                                kind="error", detail="Conversation failed; see setup docs"
                            )
                        )
                        return
                    if getattr(exc, "status_code", None) in (401, 403, 429):
                        self.emit(
                            ConversationEvent(kind="error", detail="Authentication or rate limit")
                        )
                        return
                    for _ in range(10 * 2**attempt):
                        if self.stop_event.is_set():
                            return
                        await asyncio.sleep(0.1)
        finally:
            if snapshot is not None:
                snapshot.take()

    def _mock(self):
        self.emit(ConversationEvent(kind="connected"))
        self.emit(
            ConversationEvent(
                kind="summary", detail="OFFLINE mock: synthetic audio, no remote streaming"
            )
        )
        self._tone()
        while not self.stop_event.wait(0.02):
            if self.mock_reply.is_set():
                self.mock_reply.clear()
                self.emit(ConversationEvent(kind="user_end"))
                self._tone()
            samples, jaw, generation = self.playback.render(320)
            speaking = self.playback.speaking
            if speaking != self.audio.agent_speaking:
                self.audio.agent_speaking = speaking
                self.emit(ConversationEvent(kind="agent_start" if speaking else "agent_end"))
            self.jaw_emit(jaw, time.monotonic(), generation)

    def _tone(self):
        t = np.arange(16000 * 2) / 16000
        envelope = np.maximum(0, np.sin(2 * np.pi * 3 * t)) * np.minimum(1, t * 8)
        samples = 0.3 * envelope * (np.sin(2 * np.pi * 130 * t) + 0.3 * np.sin(2 * np.pi * 260 * t))
        self.playback.push((samples * 32767).astype("<i2").tobytes())
        self.emit(ConversationEvent(kind="activity"))

    def mark(self, event, now):
        if event.kind == "scene":
            self.scene_status = event.detail
        if event.kind == "connected" and not self.connected:
            self.connected, self.connected_at = True, now
            self.last_started = now
            self.sessions += 1
        elif event.kind == "closed" and self.connected:
            self.last_ended = now
            self.total_seconds += now - self.connected_at
            self.connected, self.connected_at = False, None

    def end(self):
        self.stop_event.set()
        self.playback.clear()

    def shutdown(self):
        self.end()
        if self.thread:
            self.thread.join(timeout=3)
