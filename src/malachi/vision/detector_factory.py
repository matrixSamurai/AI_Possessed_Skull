"""ARM/Python-compatible frontal detection, with optional MediaPipe landmarks."""

from pathlib import Path
import importlib.util
import logging
import cv2
from malachi.events import Face
from malachi.platform import is_raspberry_pi


class OpenCVFaceDetector:
    def __init__(self, settings):
        self.settings = settings
        candidates = [Path(settings.face_cascade_path)] if settings.face_cascade_path else []
        data = getattr(cv2, "data", None)
        if data is not None:
            candidates.append(Path(data.haarcascades) / "haarcascade_frontalface_default.xml")
        candidates.append(
            Path("/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml")
        )
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            raise FileNotFoundError("Install opencv-data or set FACE_CASCADE_PATH")
        self.cascade = cv2.CascadeClassifier(str(path))
        if self.cascade.empty():
            raise ValueError("Cannot load frontal-face cascade")

    def detect(self, frame, now):
        height, width = frame.shape[:2]
        # Bound CPU use while retaining reasonably small faces at 960px width.
        scale = min(1, self.settings.face_opencv_max_width / width)
        small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
        gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
        boxes = self.cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=self.settings.face_opencv_min_neighbors,
            minSize=(self.settings.face_opencv_min_size, self.settings.face_opencv_min_size),
        )
        h, w = gray.shape
        return [
            Face(
                track_id=-1,
                center_x=(x + bw / 2) / w,
                center_y=(y + bh / 2) / h,
                box=(x / w, y / h, (x + bw) / w, (y + bh) / h),
                yaw=self.settings.neutral_yaw,
                pitch=self.settings.neutral_pitch,
                confidence=0,
                pose_available=False,
            )
            for x, y, bw, bh in boxes
        ]

    def reset_far_scan(self):
        pass

    def close(self):
        pass


def create_detector(settings):
    backend = settings.face_backend
    if backend == "auto":
        backend = (
            "opencv"
            if is_raspberry_pi() or importlib.util.find_spec("mediapipe") is None
            else "mediapipe"
        )
    if backend == "opencv":
        logging.getLogger("malachi").info("Using OpenCV frontal faces: head pose is unavailable")
        return OpenCVFaceDetector(settings)
    from malachi.vision.face_detector import FaceDetector

    return FaceDetector(settings.face_model_path, settings)
