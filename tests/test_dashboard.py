import time
from malachi.ui.dashboard import Dashboard
from malachi.behavior.state_machine import State


def test_dashboard_demo_full_lifecycle(qtbot, settings):
    settings.face_facing_hold_seconds = 0.1
    settings.face_detection_hold_seconds = 0.05
    window = Dashboard(settings, demo=True)
    qtbot.addWidget(window)
    window.show()
    # Manual activation ensures test doesn't depend on demo visitor's periodic absence.
    window.machine.start(time.monotonic())
    qtbot.waitUntil(lambda: window.machine.state == State.CONVERSING, timeout=4000)
    qtbot.waitUntil(lambda: window.motion.jaw > 0.1, timeout=3000)
    assert window.manager.sessions == 1
    assert "OFFLINE" in window.streaming.text() or "LOCAL" in window.streaming.text()
    window.emergency_stop()
    qtbot.waitUntil(lambda: window.machine.state == State.COOLDOWN, timeout=4000)
    assert window.motion.jaw == 0 and window.machine.emergency
    window.close()
    assert not window.manager.thread.is_alive()


def test_demo_camera_frames(qtbot, settings):
    window = Dashboard(settings, demo=True)
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.camera.snapshot()[0] is not None, timeout=2000)
    assert window.camera.snapshot()[0].shape == (480, 640, 3)
    window.close()
