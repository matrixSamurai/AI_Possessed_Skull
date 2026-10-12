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


def test_agent_choice_expires_and_emergency_clears_it():
    from malachi.ui.eye_commands import EyeCommand

    effects = EyeEffects()
    effects.choose(EyeCommand(preset="inferno", duration_seconds=2), 10)
    effects.update("CONVERSING", 10, speaking=True)
    assert effects.preset == "inferno"
    effects.update("CONVERSING", 12.1, speaking=True)
    assert effects.preset == "spectral" and effects.command is None
    effects.choose(EyeCommand(preset="mirror"), 13)
    effects.update("CONVERSING", 13, emergency=True)
    assert effects.command is None


def test_all_presets_render_distinct_images_and_owned_reflection(qtbot):
    import numpy as np
    from malachi.ui.eye_commands import PRESETS

    widget = AnimatedSkull(SimpleNamespace(x=0, y=0, jaw=0), SimpleNamespace(angles=lambda: (0, 0)))
    qtbot.addWidget(widget)
    widget.resize(420, 420)
    frame = np.full((80, 120, 3), [20, 60, 200], np.uint8)
    widget.set_reflection(frame, 1)
    assert widget.reflection.pixelColor(0, 0).red() == 200
    frame[:] = 0
    assert widget.reflection.pixelColor(0, 0).red() == 200  # Owned copy, not borrowed pixels.
    rendered = []
    for preset in PRESETS:
        widget.effects.preset = preset
        widget.effects.intensity = 0.95
        widget.effects.phase = 4
        rendered.append(bytes(widget.grab().toImage().bits()))
    assert len(set(rendered)) == len(PRESETS)
    widget.set_reflection(None, 2)
    assert widget.reflection is None


def test_eye_command_rejects_unknown_or_unbounded_requests():
    import pytest
    from pydantic import ValidationError
    from malachi.ui.eye_commands import EyeCommand

    for args in [
        {"preset": "unknown"},
        {"preset": "storm", "intensity": 2},
        {"preset": "mirror", "duration_seconds": 1000},
        {"preset": "calm", "intensity": float("nan")},
        {"preset": "calm", "hardware": "move"},
    ]:
        with pytest.raises(ValidationError):
            EyeCommand.model_validate(args)


def test_reflection_has_blur_and_animated_glitch(qtbot):
    import numpy as np

    widget = AnimatedSkull(SimpleNamespace(x=0, y=0, jaw=0), SimpleNamespace(angles=lambda: (0, 0)))
    qtbot.addWidget(widget)
    widget.resize(420, 500)
    frame = np.zeros((160, 160, 3), np.uint8)
    frame[:, ::2] = 255
    widget.set_reflection(frame, 1)
    assert 0 < widget.reflection.pixelColor(80, 80).red() < 255
    widget.effects.preset = "mirror"
    widget.effects.phase = 1
    first = bytes(widget.grab().toImage().bits())
    widget.effects.phase = 4
    second = bytes(widget.grab().toImage().bits())
    assert first != second
