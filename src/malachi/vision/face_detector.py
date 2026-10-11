import cv2
from malachi.events import Face
from malachi.vision.head_pose import estimate_pose


class FaceDetector:
    def __init__(self, path):
        if not path.is_file():
            raise FileNotFoundError("Face model missing. Run python scripts/download_model.py")
        import mediapipe as mp

        self.mp = mp
        self.detector = mp.tasks.vision.FaceLandmarker.create_from_options(
            mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_faces=4,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        self.timestamp = -1

    def detect(self, frame, now):
        h, w = frame.shape[:2]
        self.timestamp = max(self.timestamp + 1, int(now * 1000))
        result = self.detector.detect_for_video(
            self.mp.Image(
                image_format=self.mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ),
            self.timestamp,
        )
        faces = []
        for landmarks in result.face_landmarks:
            xs = [max(0, min(1, p.x)) for p in landmarks]
            ys = [max(0, min(1, p.y)) for p in landmarks]
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            try:
                yaw, pitch = estimate_pose(landmarks, w, h)
            except ValueError:
                continue
            # Landmarker exposes no per-face probability: report configured lower bound.
            faces.append(
                Face(
                    track_id=-1,
                    center_x=(x1 + x2) / 2,
                    center_y=(y1 + y2) / 2,
                    box=(x1, y1, x2, y2),
                    yaw=yaw,
                    pitch=pitch,
                    confidence=0.5,
                )
            )
        return faces

    def close(self):
        self.detector.close()
