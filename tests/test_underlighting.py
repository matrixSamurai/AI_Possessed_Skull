from types import SimpleNamespace
from PySide6.QtCore import Qt
from malachi.ui.underlighting import UnderLighting
from malachi.ui.animated_skull import AnimatedSkull


def test_light_tracks_eye_color_and_stops_immediately():
    light = UnderLighting()
    for i in range(300):
        frame = light.update("inferno", [190, 22, 12], 1, i * 0.02, i * 0.02)
        assert 0 <= frame.brightness <= 1
    assert frame.rgb == (190, 22, 12) and frame.brightness > 0.4
    off = light.update("inferno", [190, 22, 12], 1, 6, 6, emergency=True)
    assert off.brightness == 0 and off.effect == "off"


def test_underglow_paints_a_visible_pool(qtbot):
    widget = AnimatedSkull(SimpleNamespace(x=0, y=0, jaw=0), SimpleNamespace(angles=lambda: (0, 0)))
    qtbot.addWidget(widget)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    widget.setStyleSheet("background: #101017;")
    widget.resize(420, 500)
    for i in range(200):
        widget.underlight.update("inferno", [190, 22, 12], 1, i * 0.02, i * 0.02)
    lit = widget.grab().toImage()
    widget.underlight.update("inferno", [190, 22, 12], 1, 4, 4, emergency=True)
    off = widget.grab().toImage()
    # Logical LED center (0,226) maps below the skull at these widget dimensions.
    assert lit.pixelColor(210, 446).red() > off.pixelColor(210, 446).red()


def test_independent_color_overrides_eyes_then_expires():
    from malachi.ui.eye_commands import LightingCommand

    light = UnderLighting()
    light.choose(
        LightingCommand(color="blue", brightness=0.8, effect="steady", duration_seconds=10), 0
    )
    for i in range(400):
        frame = light.update("inferno", [190, 22, 12], 1, i * 0.02, i * 0.02)
    assert frame.rgb == (25, 70, 200)
    assert abs(frame.brightness - 0.8) < 0.01 and frame.effect == "steady"
    light.update("inferno", [190, 22, 12], 1, 11, 11)
    assert light.command is None
    for i in range(401, 701):
        frame = light.update(
            "inferno", [190, 22, 12], 1, 11 + (i - 400) * 0.02, 11 + (i - 400) * 0.02
        )
    assert frame.rgb == (190, 22, 12) and frame.effect == "inferno"


def test_off_and_emergency_cancel_light_override():
    from malachi.ui.eye_commands import LightingCommand

    light = UnderLighting()
    light.choose(LightingCommand(color="off"), 0)
    frame = light.update("inferno", [190, 22, 12], 1, 1, 1)
    assert frame.brightness == 0 and frame.rgb == (0, 0, 0)
    light.choose(LightingCommand(color="red"), 2)
    frame = light.update("inferno", [190, 22, 12], 1, 2, 2, emergency=True)
    assert frame.effect == "off" and light.command is None
