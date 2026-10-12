import threading
import time
import cv2
import numpy as np
from malachi.events import Face
from malachi.vision.face_tracker import FaceTracker


class CameraService:
    """Worker-owned capture/detection. Dashboard polls a single bounded latest snapshot."""

    def __init__(self, settings, demo=False):
        self.settings, self.demo = settings, demo
        self.tracker = FaceTracker()
        self.lock = threading.Lock()
        self.frame = self.face = None
        self.faces = []
        self.error = "camera stopped"
        self.updated = 0.0
        self.moving = False
        self.motion_score = 0.0
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True, name="camera")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        with self.lock:
            self.face = None
            self.faces = []
            self.error = "camera stopped"
            self.moving = False

    def snapshot(self):
        with self.lock:
            stale = time.monotonic() - self.updated > 0.5
            return (
                self.frame,
                None if stale else self.face,
                [] if stale else list(self.faces),
                self.error,
            )

    def motion_snapshot(self):
        with self.lock:
            fresh = not self.error and time.monotonic() - self.updated <= 0.5
            return (self.moving and fresh, self.motion_score if fresh else 0.0)

    def interaction_snapshot(self):
        """Fresh, unannotated full frame; never upload stale/stopped/demo capture."""
        with self.lock:
            if (
                self.demo
                or self.stop_event.is_set()
                or self.error
                or self.frame is None
                or time.monotonic() - self.updated > 0.5
            ):
                return None
            return self.frame.copy()

    def _run(self):
        detector = cap = None
        from malachi.vision.motion_detector import MotionDetector

        movement = MotionDetector(self.settings)
        try:
            if not self.demo:
                from malachi.vision.face_detector import FaceDetector

                detector = FaceDetector(self.settings.face_model_path, self.settings)
            while not self.stop_event.is_set():
                started = time.monotonic()
                if self.demo:
                    t = started % 20
                    frame = np.zeros((480, 640, 3), np.uint8)
                    cv2.putText(
                        frame,
                        "SYNTHETIC VISITOR / OFFLINE",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        (170, 150, 210),
                        1,
                    )
                    x = 0.5 + 0.25 * np.sin(started * 0.4)
                    faces = (
                        [
                            Face(
                                track_id=1,
                                center_x=x,
                                center_y=0.45,
                                box=(x - 0.12, 0.2, x + 0.12, 0.7),
                                yaw=0 if t < 14 else 40,
                                pitch=0,
                                confidence=1,
                            )
                        ]
                        if t < 16
                        else []
                    )
                else:
                    if cap is None:
                        cap = cv2.VideoCapture(self.settings.camera_index)
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.camera_width)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.camera_height)
                        cap.set(cv2.CAP_PROP_FPS, self.settings.camera_fps)
                    ok, frame = cap.read()
                    if not ok:
                        cap.release()
                        cap = None
                        with self.lock:
                            self.face, self.faces, self.error = (
                                None,
                                [],
                                "Camera unavailable; retrying",
                            )
                        movement.reset()
                        detector.reset_far_scan()
                        self.stop_event.wait(1)
                        continue
                    faces = detector.detect(frame, started)
                moving = movement.update(frame) if not self.demo else False
                face, faces = self.tracker.select(faces, started)
                with self.lock:
                    self.frame, self.face, self.faces = frame, face, faces
                    self.error, self.updated = "", started
                    self.moving, self.motion_score = moving, movement.score
                self.stop_event.wait(
                    max(0, 1 / self.settings.camera_fps - (time.monotonic() - started))
                )
        except Exception as exc:
            with self.lock:
                self.error = f"Camera: {type(exc).__name__}: {exc}"
                self.face = None
                self.faces = []
        finally:
            if cap is not None:
                cap.release()
            if detector is not None:
                detector.close()
