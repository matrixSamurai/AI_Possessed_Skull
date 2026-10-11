import cv2
import numpy as np

# Landmark correspondence: nose, chin, eye outer corners, mouth corners.
INDICES = [1, 152, 33, 263, 61, 291]
MODEL = np.array(
    [
        (0, 0, 0),
        (0, 63.6, -12.5),
        (-43.3, -32.7, -26),
        (43.3, -32.7, -26),
        (-28.9, 28.9, -24.1),
        (28.9, 28.9, -24.1),
    ],
    dtype=np.float64,
)


def estimate_pose(landmarks, width, height):
    """Approximate pose from a generic face model; calibrate against a neutral face."""
    points = np.array(
        [(landmarks[i].x * width, landmarks[i].y * height) for i in INDICES], dtype=np.float64
    )
    camera = np.array([[width, 0, width / 2], [0, width, height / 2], [0, 0, 1.0]])
    ok, rotation, _ = cv2.solvePnP(MODEL, points, camera, np.zeros(4), flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        raise ValueError("pose estimation failed")
    matrix, _ = cv2.Rodrigues(rotation)
    pitch, yaw, _ = cv2.RQDecomp3x3(matrix)[0]
    return float(yaw), float(pitch)
