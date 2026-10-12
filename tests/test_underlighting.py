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
