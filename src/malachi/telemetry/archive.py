"""Local diagnostic images and sliding retention for application-owned files."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
import time


PREFIX = "malachi-"


def prune(directory, retention_seconds, now=None):
    """Delete only our expired regular files; never recurse or follow symlinks."""
    cutoff = (time.time() if now is None else now) - retention_seconds
    for path in Path(directory).glob("malachi-*"):
        if path.is_symlink() or not path.is_file():
            continue
        if not (path.name.startswith("malachi-image-") and path.suffix == ".jpg") and not (
            path.name.startswith("malachi-events-") and ".jsonl" in path.name
        ):
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            logging.getLogger("malachi").warning("Could not remove expired diagnostic file")


class CameraArchive:
    def __init__(self, settings, snapshot):
        self.settings = settings
        self.snapshot = snapshot
        self.directory = settings.log_directory
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.thread = threading.Thread(target=self._run, name="diagnostic-images", daemon=True)
        self.thread.start()

    def capture(self):
        import cv2

        frame = self.snapshot()
        if frame is None:
            logging.getLogger("malachi").info("Diagnostic image skipped: no fresh camera frame")
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        path = self.directory / f"malachi-image-{timestamp}.jpg"
        ok, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise OSError("JPEG encoding failed")
        # Exclusive creation and private permissions; never overwrite an existing file.
        import os

        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data.tobytes())
        logging.getLogger("malachi").info("Diagnostic image saved: %s", path.name)

    def _run(self):
        while not self.stop_event.is_set():
            try:
                prune(self.directory, self.settings.log_retention_days * 86400)
            except OSError:
                logging.getLogger("malachi").warning("Diagnostic retention cleanup failed")
            if self.stop_event.wait(60):
                break
            try:
                self.capture()
            except Exception as exc:
                logging.getLogger("malachi").warning(
                    "Diagnostic image failed (%s)", type(exc).__name__
                )

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
