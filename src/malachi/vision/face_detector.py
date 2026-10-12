import cv2
from malachi.events import Face
from malachi.vision.head_pose import estimate_pose


class FaceDetector:
    def __init__(self, path, settings=None):
        from malachi.config import Settings

        self.settings = settings or Settings(_env_file=None)
        if not path.is_file():
            raise FileNotFoundError("Face model missing. Run python scripts/download_model.py")
        import mediapipe as mp

        self.mp = mp
        self.detector = mp.tasks.vision.FaceLandmarker.create_from_options(
            mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_faces=4,
                min_face_detection_confidence=self.settings.face_min_detection_confidence,
                min_face_presence_confidence=self.settings.face_min_presence_confidence,
                min_tracking_confidence=self.settings.face_min_tracking_confidence,
            )
        )
        self.crop_detector = None
        if self.settings.face_far_scan_enabled:
            self.crop_detector = mp.tasks.vision.FaceLandmarker.create_from_options(
                mp.tasks.vision.FaceLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_faces=4,
                    min_face_detection_confidence=self.settings.face_min_detection_confidence,
                    min_face_presence_confidence=self.settings.face_min_presence_confidence,
                    min_tracking_confidence=self.settings.face_min_tracking_confidence,
                )
            )
        self.timestamp = -1
        self.reset_far_scan()

    def reset_far_scan(self):
        self.crop_results = {}
        self.crop_index = 0
        self.last_crop = float("-inf")

    def detect(self, frame, now):
        h, w = frame.shape[:2]
        self.timestamp = max(self.timestamp + 1, int(now * 1000))
        result = self.detector.detect_for_video(
            self.mp.Image(
                image_format=self.mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ),
            self.timestamp,
        )
        faces = self._faces(result, w, h)
        if self.crop_detector is not None:
            interval = self.settings.face_far_scan_interval_seconds
            if now - self.last_crop >= interval:
                cw, ch = max(1, round(w * 0.6)), max(1, round(h * 0.6))
                x = 0 if self.crop_index % 2 == 0 else w - cw
                y = 0 if self.crop_index < 2 else h - ch
                crop = frame[y : y + ch, x : x + cw]
                result = self.crop_detector.detect(
                    self.mp.Image(
                        image_format=self.mp.ImageFormat.SRGB,
                        data=cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
                    )
                )
                mapped = [map_crop_face(f, x, y, cw, ch, w, h) for f in self._faces(result, cw, ch)]
                self.crop_results[self.crop_index] = (now, mapped)
                self.crop_index = (self.crop_index + 1) % 4
                self.last_crop = now
            # Retain one scan cycle to avoid flicker between rotating crops.
            for timestamp, candidates in self.crop_results.values():
                if now - timestamp <= interval * 4 + 0.1:
                    for candidate in candidates:
                        if not any(same_detection(candidate, face) for face in faces):
                            faces.append(candidate)
        return faces

    def _faces(self, result, w, h):
        faces = []
        for landmarks in result.face_landmarks:
            xs = [max(0, min(1, p.x)) for p in landmarks]
            ys = [max(0, min(1, p.y)) for p in landmarks]
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            try:
                yaw, pitch = estimate_pose(landmarks, w, h)
            except ValueError:
                yaw, pitch = 90.0, 90.0
            faces.append(
                Face(
                    track_id=-1,
                    center_x=(x1 + x2) / 2,
                    center_y=(y1 + y2) / 2,
                    box=(x1, y1, x2, y2),
                    yaw=yaw,
                    pitch=pitch,
                    confidence=self.settings.face_min_detection_confidence,
                )
            )
        return faces

    def close(self):
        self.detector.close()
        if self.crop_detector is not None:
            self.crop_detector.close()


def map_crop_face(face, x, y, cw, ch, width, height):
    x1, y1, x2, y2 = face.box
    box = (
        (x + x1 * cw) / width,
        (y + y1 * ch) / height,
        (x + x2 * cw) / width,
        (y + y2 * ch) / height,
    )
    return face.model_copy(
        update={"box": box, "center_x": (box[0] + box[2]) / 2, "center_y": (box[1] + box[3]) / 2}
    )


def same_detection(a, b):
    ax1, ay1, ax2, ay2 = a.box
    bx1, by1, bx2, by2 = b.box
    overlap = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    area = min((ax2 - ax1) * (ay2 - ay1), (bx2 - bx1) * (by2 - by1))
    return area > 0 and overlap / area >= 0.6
