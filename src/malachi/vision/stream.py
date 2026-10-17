"""Opt-in LAN MJPEG server. Only the producer reads CameraService's snapshots."""

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2


class CameraStream:
    def __init__(self, camera, host, port, fps=10):
        self.camera = camera
        self.fps = fps
        self.condition = threading.Condition()
        self.stopped = threading.Event()
        self.jpeg = None
        self.sequence = 0
        self.clients = threading.BoundedSemaphore(4)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path != "/stream.mjpg":
                    self.send_error(404)
                    return
                if not owner.clients.acquire(blocking=False):
                    self.send_error(503, "Viewer limit reached")
                    return
                try:
                    self.connection.settimeout(3)
                    self.send_response(200)
                    self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=malachi")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    seen = 0
                    while not owner.stopped.is_set():
                        with owner.condition:
                            owner.condition.wait_for(
                                lambda: owner.stopped.is_set() or owner.sequence != seen,
                                timeout=2,
                            )
                            seen = owner.sequence
                            jpeg = owner.jpeg
                        if owner.stopped.is_set():
                            break
                        if jpeg is None:
                            # End the connection rather than replay a frozen image.
                            break
                        self.wfile.write(
                            b"--malachi\r\nContent-Type: image/jpeg\r\nContent-Length: "
                            + str(len(jpeg)).encode()
                            + b"\r\n\r\n"
                            + jpeg
                            + b"\r\n"
                        )
                        self.wfile.flush()
                except (OSError, TimeoutError):
                    pass
                finally:
                    owner.clients.release()

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.server.daemon_threads = True
        self.server.block_on_close = False
        self.http_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.producer = threading.Thread(target=self._produce, daemon=True)

    def start(self):
        self.http_thread.start()
        self.producer.start()

    def stop(self):
        self.stopped.set()
        with self.condition:
            self.condition.notify_all()
        self.server.shutdown()
        self.server.server_close()
        self.producer.join(timeout=3)
        self.http_thread.join(timeout=3)

    def _produce(self):
        while not self.stopped.is_set():
            started = time.monotonic()
            jpeg = None
            with self.camera.lock:
                frame = (
                    self.camera.frame.copy()
                    if self.camera.frame is not None
                    and not self.camera.error
                    and not self.camera.stop_event.is_set()
                    and started - self.camera.updated <= 0.5
                    else None
                )
            if frame is not None:
                try:
                    height, width = frame.shape[:2]
                    if width > 640:
                        frame = cv2.resize(frame, (640, max(1, round(height * 640 / width))))
                    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if ok:
                        jpeg = encoded.tobytes()
                except Exception:
                    logging.getLogger(__name__).exception("Stream JPEG encoding failed")
            with self.condition:
                self.jpeg = jpeg
                self.sequence += 1
                self.condition.notify_all()
            self.stopped.wait(max(0, 1 / self.fps - (time.monotonic() - started)))
