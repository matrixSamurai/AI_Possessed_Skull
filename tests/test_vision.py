import cv2
import numpy as np
from types import SimpleNamespace
from malachi.vision.face_tracker import FaceTracker
from malachi.vision.head_pose import MODEL, INDICES, estimate_pose


def test_target_stability_and_manual_selection(face):
    tracker = FaceTracker()
    first, faces = tracker.select([face], 0)
    large = face.model_copy(update={"center_x": 0.85, "box": (0.6, 0.1, 1, 0.9)})
    selected, faces = tracker.select([face, large], 0.1)
    assert selected.track_id == first.track_id and selected.stable
    tracker.manual = next(f.track_id for f in faces if f.track_id != first.track_id)
    selected, _ = tracker.select([face, large], 0.2)
    assert selected.track_id == tracker.manual


def test_pose_recovers_known_rotation():
    camera = np.array([[640.0, 0, 320], [0, 640.0, 240], [0, 0, 1.0]])
    projected, _ = cv2.projectPoints(
        MODEL, np.zeros(3), np.array([0.0, 0, 500.0]), camera, np.zeros(4)
    )
    landmarks = [SimpleNamespace(x=0, y=0) for _ in range(468)]
    for index, point in zip(INDICES, projected[:, 0]):
        landmarks[index] = SimpleNamespace(x=point[0] / 640, y=point[1] / 480)
    yaw, pitch = estimate_pose(landmarks, 640, 480)
    assert abs(yaw) < 0.1 and abs(pitch) < 0.1
