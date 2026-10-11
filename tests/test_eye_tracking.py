from malachi.motion.eye_motion import EyeMotion
from malachi.motion.simulation import SimulatedMotionController


def test_smoothing_velocity_and_angles(settings, face):
    eye = EyeMotion(settings, seed=1)
    face = face.model_copy(update={"center_x": 1, "center_y": 0})
    previous = (eye.x, eye.y)
    x, y = eye.update(face, 0.1, 0)
    assert 0 < x < 1 and y < previous[1]
    assert abs(x - previous[0]) <= settings.eye_max_velocity * 0.1
    for i in range(100):
        eye.update(face, 0.1, i * 0.1)
    pan, tilt = eye.angles()
    assert -20 <= pan <= 20 and -15 <= tilt <= 15


def test_simulation_limits_and_emergency():
    motion = SimulatedMotionController()
    motion.set_eye_target(99, -99)
    motion.set_jaw_position(4)
    assert (motion.x, motion.y, motion.jaw) == (1, -1, 1)
    motion.emergency_stop()
    motion.set_jaw_position(1)
    assert motion.jaw == 0


def test_no_face_neutral(settings):
    eye = EyeMotion(settings, seed=1)
    eye.x = 1
    for i in range(100):
        eye.update(None, 0.1, i * 0.1)
    assert abs(eye.x) < 0.05
    assert 0.25 < eye.y < 0.35
