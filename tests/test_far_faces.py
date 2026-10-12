from types import SimpleNamespace
import numpy as np
import pytest
from malachi.vision.face_detector import FaceDetector, map_crop_face, same_detection


def test_crop_coordinates_and_duplicate_suppression(face):
    crop = face.model_copy(update={"box": (0.2, 0.2, 0.4, 0.4)})
    mapped = map_crop_face(crop, 400, 200, 600, 300, 1000, 500)
    assert mapped.box == pytest.approx((0.52, 0.52, 0.64, 0.64))
    assert mapped.center_x == pytest.approx(0.58)
    assert same_detection(mapped, mapped)
    assert not same_detection(mapped, face.model_copy(update={"box": (0.1, 0.1, 0.2, 0.2)}))


def test_rotating_far_scan_cache_expires_and_resets(settings, monkeypatch):
    import malachi.vision.face_detector as module

    monkeypatch.setattr(module, "estimate_pose", lambda *a: (5, 6))
    landmarks = [SimpleNamespace(x=0.2, y=0.2), SimpleNamespace(x=0.4, y=0.4)]
    empty = SimpleNamespace(face_landmarks=[])
    small = SimpleNamespace(face_landmarks=[landmarks])
    calls = []

    class Crop:
        result = small

        def detect(self, image):
            calls.append(image.shape)
            return self.result

    detector = object.__new__(FaceDetector)
    detector.settings = settings
    detector.mp = SimpleNamespace(
        Image=lambda **kw: kw["data"], ImageFormat=SimpleNamespace(SRGB=1)
    )
    detector.detector = SimpleNamespace(detect_for_video=lambda *a: empty)
    detector.crop_detector = Crop()
    detector.timestamp = -1
    detector.reset_far_scan()
    frame = np.zeros((500, 1000, 3), np.uint8)
    first = detector.detect(frame, 0)
    assert len(first) == 1 and first[0].center_x == pytest.approx(0.18)
    assert calls == [(300, 600, 3)]
    assert len(detector.detect(frame, 0.1)) == 1
    assert len(calls) == 1  # Scanning is throttled.
    detector.crop_detector.result = empty
    assert len(detector.detect(frame, 0.2)) == 1  # Other crop retains previous observation.
    assert not detector.detect(frame, 1.2)  # Old observations cannot persist indefinitely.
    detector.reset_far_scan()
    assert not detector.crop_results


def test_failed_pose_still_counts_as_present(settings, monkeypatch):
    import malachi.vision.face_detector as module

    def fail(*a):
        raise ValueError("poor pose")

    monkeypatch.setattr(module, "estimate_pose", fail)
    detector = object.__new__(FaceDetector)
    detector.settings = settings
    result = SimpleNamespace(
        face_landmarks=[[SimpleNamespace(x=0.2, y=0.2), SimpleNamespace(x=0.4, y=0.4)]]
    )
    faces = detector._faces(result, 640, 480)
    assert len(faces) == 1 and faces[0].yaw == 90
    assert faces[0].confidence == settings.face_min_detection_confidence
