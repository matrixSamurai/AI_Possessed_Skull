"""Camera and conversation control loop without Qt or a desktop session."""

import heapq
import logging
import queue
import signal
import threading
import time

from malachi.behavior.state_machine import State, StateMachine
from malachi.conversation.conversation_manager import ConversationManager
from malachi.motion.eye_motion import EyeMotion
from malachi.vision.camera import CameraService


class HeadlessRuntime:
    def __init__(self, settings, demo=False):
        self.settings = settings
        self.machine = StateMachine(settings, time.monotonic())
        self.manager = ConversationManager(settings)
        self.camera = CameraService(settings, demo)
        self.eyes = EyeMotion(settings)
        self.last_eyes = time.monotonic()
        self.jaws = []
        self.hardware = None
        if settings.motion_backend == "esp32":
            from malachi.motion.serial_controller import ESP32MotionController

            self.hardware = ESP32MotionController(settings)
        self.log = logging.getLogger("malachi")

    def tick(self):
        now = time.monotonic()
        old = self.machine.state
        _, face, faces, _ = self.camera.snapshot()
        while True:
            try:
                event = self.manager.events.get_nowait()
            except queue.Empty:
                break
            self.manager.mark(event, now)
            self.machine.event(event, now)
            if event.kind in ("summary", "error", "scene", "closed", "connected"):
                self.log.info("%s: %s", event.kind, event.detail)
            elif event.kind in ("eye_effect", "lighting_effect"):
                self.log.info("%s: visual effect unavailable without dashboard", event.kind)
        self.machine.tick(face, now, people_present=bool(faces))
        state = self.machine.state
        if self.manager.ambience is not None:
            moving, _ = self.camera.motion_snapshot()
            self.manager.ambience.engine.update(
                bool(faces),
                moving,
                state in (State.AWAKENING, State.CONVERSING, State.ENDING),
                self.manager.audio.suppress_mic_during_playback,
                self.machine.emergency,
                self.manager.playback.muted,
                now,
            )
        if state == State.AWAKENING:
            if not self.manager.thread or not self.manager.thread.is_alive():
                snapshot = (
                    self.camera.interaction_snapshot()
                    if self.settings.vision_context_enabled
                    else None
                )
                self.manager.start(snapshot, snapshot_provider=self.camera.interaction_snapshot)
        if state == State.ENDING:
            self.manager.end()
            self.jaws.clear()
            if self.hardware:
                self.hardware.neutral_position()
        if state != old:
            self.log.info("transition %s -> %s: %s", old, state, self.machine.reason)
            if state == State.COOLDOWN and self.hardware:
                self.hardware.neutral_position()
        if now - self.last_eyes >= 1 / self.settings.eye_tracking_hz:
            target = None if state in (State.IDLE, State.ENDING, State.COOLDOWN) else face
            x, y = self.eyes.update(target, now - self.last_eyes, now, True)
            self.last_eyes = now
            if self.hardware:
                self.hardware.set_eye_target(x, y)
        while True:
            try:
                heapq.heappush(self.jaws, self.manager.jaws.get_nowait())
            except queue.Empty:
                break
        while self.jaws and self.jaws[0][0] <= now:
            _, jaw, generation = heapq.heappop(self.jaws)
            if self.hardware and generation == self.manager.playback.generation:
                self.hardware.set_jaw_position(jaw if state == State.CONVERSING else 0)
        if self.hardware and self.hardware.error:
            self.log.error("Hardware error; stopping")
            raise RuntimeError("Hardware controller failed")

    def close(self):
        self.machine.stop(time.monotonic())
        try:
            if self.hardware:
                self.hardware.emergency_stop()
        finally:
            try:
                self.camera.stop()
            finally:
                try:
                    self.manager.shutdown()
                finally:
                    if self.hardware:
                        self.hardware.close()


def run(settings, demo=False, smoke_seconds=0):
    stop = threading.Event()
    previous = {}
    runtime = HeadlessRuntime(settings, demo)
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, lambda *_: stop.set())
        runtime.log.info("Headless mode: local camera, microphone and speaker; Ctrl+C to stop")
        runtime.camera.start()
        deadline = time.monotonic() + smoke_seconds if smoke_seconds else None
        while not stop.is_set():
            runtime.tick()
            if deadline is not None and time.monotonic() >= deadline:
                break
            stop.wait(0.02)
    finally:
        try:
            runtime.close()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return 0
