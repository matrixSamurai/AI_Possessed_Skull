from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QLineEdit,
    QDialogButtonBox,
    QLabel,
)


class ConfigurationDialog(QDialog):
    """Runtime edits are validated as a whole and never persist credentials."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MALACHI • Runtime configuration")
        self.form = QFormLayout(self)
        self.fields = {}
        specs = [
            ("camera_index", "Camera index", 0, 20),
            ("face_facing_hold_seconds", "Facing hold (seconds)", 0.1, 60),
            ("face_yaw_threshold", "Yaw threshold (degrees)", 1, 90),
            ("face_pitch_threshold", "Pitch threshold (degrees)", 1, 90),
            ("eye_smoothing_seconds", "Eye smoothing (seconds)", 0.01, 2),
            ("eye_max_pan_degrees", "Eye pan limit (degrees)", 1, 30),
            ("eye_max_tilt_degrees", "Eye tilt limit (degrees)", 1, 25),
            ("conversation_idle_timeout_seconds", "Idle timeout (seconds)", 1, 300),
            ("visitor_absence_timeout_seconds", "Absence timeout (seconds)", 1, 120),
            ("max_session_duration_seconds", "Session limit (seconds)", 10, 180),
        ]
        for name, label, low, high in specs:
            box = QSpinBox() if name == "camera_index" else QDoubleSpinBox()
            box.setRange(low, high)
            box.setValue(getattr(settings, name))
            self.fields[name] = box
            self.form.addRow(label, box)
        self.agent = QLineEdit(settings.elevenlabs_agent_id)
        self.form.addRow("ElevenLabs agent ID", self.agent)
        self.form.addRow(
            QLabel("Camera changes require Stop / Start camera. Settings last for this run.")
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.form.addRow(buttons)

    def values(self):
        return {
            **{n: b.value() for n, b in self.fields.items()},
            "elevenlabs_agent_id": self.agent.text().strip(),
        }
