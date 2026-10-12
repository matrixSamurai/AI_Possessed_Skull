from types import SimpleNamespace
from malachi.ui.eye_effects import EyeEffects
from malachi.ui.animated_skull import AnimatedSkull


def test_fury_builds_gradually_and_settles():
    effects = EyeEffects()
    effects.update("AWAKENING", 0)
    first = effects.update("AWAKENING", 0.02)
    assert 0 < first < 0.02
    for i in range(1, 401):
        effects.update("AWAKENING", i * 0.02)
    assert 0.7 < effects.intensity < 0.9
    before = effects.intensity
    effects.update("IDLE", 8.02)
    assert 0 < effects.intensity < before
    for i in range(402, 1100):
        effects.update("IDLE", i * 0.02, emergency=True)
    assert effects.intensity < 0.03


def test_eye_animation_is_similar_at_different_frame_rates():
    levels = []
    for fps in (30, 60):
        effects = EyeEffects()
        for i in range(fps * 6 + 1):
            effects.update("AWAKENING", i / fps)
        levels.append(effects.intensity)
    assert abs(levels[0] - levels[1]) < 0.001


def test_paint_eyes_at_each_intensity_and_blink(qtbot):
    motion = SimpleNamespace(x=0.8, y=-0.7, jaw=0.4)
    eyes = SimpleNamespace(angles=lambda: (12, -6))
    widget = AnimatedSkull(motion, eyes)
    qtbot.addWidget(widget)
    widget.resize(420, 420)
    for fury, blink in [(0, False), (0.5, False), (1, False), (1, True)]:
        widget.effects.intensity = fury
        widget.blink = blink
        image = widget.grab().toImage()
        assert not image.isNull() and image.width() == 420
    assert len(widget.veins) == 12
