import heapq
import logging
import queue
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QProgressBar,
    QGroupBox,
    QGridLayout,
    QPlainTextEdit,
    QDialog,
)
from malachi.behavior.state_machine import State, StateMachine
from malachi.conversation.conversation_manager import ConversationManager
from malachi.motion.eye_motion import EyeMotion
from malachi.motion.simulation import SimulatedMotionController
from malachi.ui.animated_skull import AnimatedSkull
from malachi.ui.camera_widget import CameraWidget
from malachi.ui.controls import ConfigurationDialog
from malachi.vision.camera import CameraService

STYLE = """
QMainWindow,QDialog,QWidget {background:#101017;color:#e7dee7;font-size:13px;}
QGroupBox {border:1px solid #393040;border-radius:10px;margin-top:18px;padding:12px;}
QGroupBox::title {subcontrol-origin:margin;left:15px;color:#c194b4;}
QPushButton {background:#2c2434;border:1px solid #5c3c55;border-radius:6px;padding:9px;}
QPushButton:hover {background:#4a2b41;}
QPushButton:pressed {background:#73223a;}
QLabel#title {font-size:28px;font-weight:700;color:#f0d7dc;}
QLabel#state {font-size:24px;font-weight:700;color:#ef687d;}
QProgressBar {border:1px solid #493547;border-radius:4px;height:12px;text-align:center;}
QProgressBar::chunk {background:#9c3458;}
QPlainTextEdit {background:#0a090f;border:1px solid #322737;color:#b0a2bb;}
"""


class Dashboard(QMainWindow):
    def __init__(self, settings, demo=False):
        super().__init__()
        self.settings = settings
        self.demo = demo
        self.machine = StateMachine(settings, time.monotonic())
        self.manager = ConversationManager(settings)
        self.camera = CameraService(settings, demo)
        self.motion = SimulatedMotionController()
        self.hardware = None
        if settings.motion_backend == "esp32":
            from malachi.motion.serial_controller import ESP32MotionController

            self.hardware = ESP32MotionController(settings)
        self.eyes = EyeMotion(settings)
        self.jaw_pending = []
        self.last_tick = self.last_eyes = time.monotonic()
        self.face = None
        self.tracking = True
        self.closed = False
        self.diagnostic_until = 0.0
        self.setWindowTitle("MALACHI • Autonomous spectral intelligence")
        self.resize(1260, 850)
        self.setStyleSheet(STYLE)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        title = QLabel("M A L A C H I     /     THE WATCHER")
        title.setObjectName("title")
        layout.addWidget(title)
        self.streaming = QLabel("OFFLINE • Local perception only")
        layout.addWidget(self.streaming)
        self.scene_label = QLabel("ElevenLabs visual context: disabled (no image upload)")
        self.scene_label.setWordWrap(True)
        layout.addWidget(self.scene_label)
        self.ambience_label = QLabel("Background voices: disabled")
        self.ambience_label.setWordWrap(True)
        layout.addWidget(self.ambience_label)
        panels = QHBoxLayout()
        layout.addLayout(panels, stretch=3)
        camera_group = QGroupBox("PERCEPTION / click a face to select")
        cv = QVBoxLayout(camera_group)
        self.preview = CameraWidget()
        self.preview.selected.connect(self.select_face)
        cv.addWidget(self.preview)
        self.face_label = QLabel("No visitor")
        cv.addWidget(self.face_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        cv.addWidget(self.progress)
        panels.addWidget(camera_group, stretch=3)
        skull_group = QGroupBox("SIMULATED ACTUATORS")
        sv = QVBoxLayout(skull_group)
        self.skull = AnimatedSkull(self.motion, self.eyes)
        sv.addWidget(self.skull)
        panels.addWidget(skull_group, stretch=2)
        monitor = QHBoxLayout()
        layout.addLayout(monitor)
        state_group = QGroupBox("BEHAVIOR")
        st = QVBoxLayout(state_group)
        self.state_label = QLabel("IDLE")
        self.state_label.setObjectName("state")
        st.addWidget(self.state_label)
        self.state_detail = QLabel()
        st.addWidget(self.state_detail)
        monitor.addWidget(state_group)
        session_group = QGroupBox("SESSION / DURATION, NOT BILLING")
        ss = QVBoxLayout(session_group)
        self.session_label = QLabel()
        self.session_label.setWordWrap(True)
        ss.addWidget(self.session_label)
        monitor.addWidget(session_group)
        controls = QGroupBox("CONTROL ROOM")
        grid = QGridLayout(controls)
        actions = [
            ("Start camera", self.camera.start),
            ("Stop camera", self.camera.stop),
            ("Start session", lambda: self.machine.start(time.monotonic())),
            ("End session", lambda: self.machine.end("manual end", time.monotonic())),
            ("Center eyes", self.center),
            ("Test jaw / mock reply", self.test_jaw),
            ("Reset cooldown", lambda: self.machine.reset(time.monotonic())),
            ("Calibrate neutral pose", self.calibrate),
            ("Configuration", self.configure),
            ("Auto-select face", lambda: setattr(self.camera.tracker, "manual", None)),
            ("Resume after stop", self.resume),
            ("EMERGENCY STOP", self.emergency_stop),
        ]
        for i, (label, callback) in enumerate(actions):
            button = QPushButton(label)
            button.clicked.connect(callback)
            if label == "EMERGENCY STOP":
                button.setStyleSheet("background:#8c1835;font-weight:bold")
            grid.addWidget(button, i // 6, i % 6)
        toggles = [
            ("Autonomous", True, lambda v: setattr(self.machine, "autonomous", v)),
            ("Eye tracking", True, lambda v: setattr(self, "tracking", v)),
            ("Mute microphone", False, lambda v: setattr(self.manager.audio, "mic_muted", v)),
            ("Mute speaker", False, lambda v: setattr(self.manager.playback, "muted", v)),
        ]
        if self.manager.ambience is not None:
            toggles.append(
                ("Background voices", True, lambda v: setattr(self.settings, "ambience_enabled", v))
            )
        toggles.append(
            (
                "Speaker echo guard (no voice interrupt)",
                self.manager.audio.suppress_mic_during_playback,
                lambda v: setattr(self.manager.audio, "suppress_mic_during_playback", v),
            )
        )
        self.auto_toggle = None
        for i, (label, checked, callback) in enumerate(toggles):
            box = QCheckBox(label)
            box.setChecked(checked)
            box.toggled.connect(callback)
            grid.addWidget(box, 2, i)
            if i == 0:
                self.auto_toggle = box
        layout.addWidget(controls)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(150)
        self.log.setMaximumHeight(105)
        layout.addWidget(self.log)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(20)
        self.camera.start()

    def select_face(self, x, y):
        _, _, faces, _ = self.camera.snapshot()
        for face in faces:
            x1, y1, x2, y2 = face.box
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.camera.tracker.manual = face.track_id
                return

    def center(self):
        self.tracking = False
        self.eyes.x = self.eyes.y = 0
        self.motion.set_eye_target(0, 0)

    def calibrate(self):
        if self.face:
            self.settings.neutral_yaw, self.settings.neutral_pitch = self.face.yaw, self.face.pitch
            self.log.appendPlainText("Neutral pose calibrated for this run")

    def configure(self):
        if self.machine.state in (State.AWAKENING, State.CONVERSING, State.ENDING):
            self.log.appendPlainText("End session before changing configuration")
            return
        dialog = ConfigurationDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = self.settings.model_dump()
            values.update(dialog.values())
            new = type(self.settings).model_validate(values)
            # Shared configuration object, preserving references held by workers.
            for name in dialog.values():
                setattr(self.settings, name, getattr(new, name))
            self.log.appendPlainText("Runtime settings updated")

    def test_jaw(self):
        if self.machine.emergency:
            return
        if self.settings.conversation_backend == "mock" and self.manager.connected:
            self.manager.mock_reply.set()
        elif not self.manager.thread or not self.manager.thread.is_alive():
            # Silent local PCM playback simulation, consumed on the 20 ms UI clock.
            self.manager.playback.clear()
            self.manager._tone()
            self.diagnostic_until = time.monotonic() + 2.2

    def emergency_stop(self):
        self.machine.stop(time.monotonic())
        self.auto_toggle.setChecked(False)
        self.manager.end()
        if self.manager.ambience is not None:
            self.manager.ambience.stop()
        self.motion.emergency_stop()
        self.jaw_pending.clear()
        if self.hardware:
            self.hardware.emergency_stop()
        self.log.appendPlainText("Emergency stop latched; explicit Resume required")

    def resume(self):
        if self.machine.state in (State.AWAKENING, State.CONVERSING, State.ENDING):
            return
        self.motion.stopped = False
        self.machine.emergency = False
        self.machine.reset(time.monotonic())
        if self.hardware:
            self.hardware.resume()
        self.log.appendPlainText("Stop latch cleared; enable Autonomous to rearm")

    def tick(self):
        now = time.monotonic()
        old = self.machine.state
        frame, self.face, faces, error = self.camera.snapshot()
        while True:
            try:
                event = self.manager.events.get_nowait()
            except queue.Empty:
                break
            self.manager.mark(event, now)
            self.machine.event(event, now)
            if event.kind in ("summary", "error", "closed", "connected", "scene"):
                self.log.appendPlainText(f"{event.kind}: {event.detail}")
        self.machine.tick(self.face, now, people_present=bool(faces))
        state = self.machine.state
        if self.manager.ambience is not None:
            moving, _ = self.camera.motion_snapshot()
            self.manager.ambience.engine.update(
                self.face is not None,
                moving,
                state in (State.AWAKENING, State.CONVERSING, State.ENDING),
                self.manager.audio.suppress_mic_during_playback,
                self.machine.emergency,
                self.manager.playback.muted,
                now,
            )
            self.ambience_label.setText("Background voices: " + self.manager.ambience.engine.status)
        if state == State.AWAKENING:
            if not self.manager.thread or not self.manager.thread.is_alive():
                frame = (
                    self.camera.interaction_snapshot()
                    if self.settings.vision_context_enabled
                    else None
                )
                self.manager.start(frame, snapshot_provider=self.camera.interaction_snapshot)
        if state == State.ENDING:
            self.manager.end()
            self.motion.neutral_position()
            self.jaw_pending.clear()
        if state != old:
            logging.getLogger("malachi").info(
                "transition %s -> %s: %s", old, state, self.machine.reason
            )
            self.log.appendPlainText(f"{old.value} → {state.value}: {self.machine.reason}")
            if state == State.COOLDOWN:
                self.motion.neutral_position()
        if now - self.last_eyes >= 1 / self.settings.eye_tracking_hz:
            target = None if state in (State.IDLE, State.ENDING, State.COOLDOWN) else self.face
            x, y = self.eyes.update(target, now - self.last_eyes, now, self.tracking)
            self.last_eyes = now
            self.motion.set_eye_target(x, y)
        while True:
            try:
                heapq.heappush(self.jaw_pending, self.manager.jaws.get_nowait())
            except queue.Empty:
                break
        while self.jaw_pending and self.jaw_pending[0][0] <= now:
            _, jaw, generation = heapq.heappop(self.jaw_pending)
            if generation == self.manager.playback.generation and state == State.CONVERSING:
                self.motion.set_jaw_position(jaw)
        if (
            self.diagnostic_until > now
            and state not in (State.AWAKENING, State.CONVERSING, State.ENDING)
            and not self.machine.emergency
        ):
            _, jaw, _ = self.manager.playback.render(320)
            self.motion.set_jaw_position(jaw)
        elif state != State.CONVERSING:
            self.motion.set_jaw_position(0)
        if self.hardware:
            self.hardware.set_eye_target(self.motion.x, self.motion.y)
            self.hardware.set_jaw_position(self.motion.jaw)
            if self.hardware.error:
                self.log.appendPlainText(self.hardware.error)
                self.hardware.error = ""
                self.emergency_stop()
        self.skull.blink = now < self.eyes.blink_until
        self.skull.update()
        self.preview.show_frame(frame, faces, self.face)
        self.state_label.setText(state.value)
        self.state_detail.setText(
            f"Previous: {self.machine.previous.value}  •  {now - self.machine.entered:.1f}s\n"
            f"{self.machine.reason}"
        )
        if self.face:
            self.face_label.setText(
                f"Target #{self.face.track_id}  •  ({self.face.center_x:.2f}, {self.face.center_y:.2f})"
                f"  •  yaw {self.face.yaw:+.1f}° / pitch {self.face.pitch:+.1f}°\n"
                f"{'Stable track' if self.face.stable else 'New track'}  •  detection threshold ≥0.5 (not a probability)"
            )
        else:
            self.face_label.setText(error or "No visitor • local monitoring")
        self.progress.setValue(int(self.machine.qualification(now) * 100))
        duration = now - self.manager.connected_at if self.manager.connected_at is not None else 0
        total = self.manager.total_seconds + duration
        policy = self.machine.policy
        idle = max(0, self.settings.conversation_idle_timeout_seconds - (now - policy.activity))
        absence = self.settings.visitor_absence_timeout_seconds
        if policy.absent_since is not None:
            absence = max(0, absence - (now - policy.absent_since))
        speaker = (
            "VISITOR" if policy.user_speaking else "GHOST" if policy.agent_speaking else "WAITING"
        )
        audio_stats = self.manager.playback.stats()
        self.session_label.setText(
            f"{speaker}  •  Current {duration:.1f}s  /  Total {total:.1f}s\n"
            f"Sessions {self.manager.sessions}  •  Failures {self.manager.failures}\n"
            f"Idle {idle:.1f}s  •  Absence {absence:.1f}s\n"
            f"Audio buffer {audio_stats['buffer_ms']:.0f}ms  •  Device underruns {self.manager.audio.output_underruns}"
            f"  •  Interruptions {audio_stats['interruptions']}"
        )
        self.scene_label.setText("ElevenLabs visual context: " + self.manager.scene_status)
        remote = self.settings.conversation_backend == "elevenlabs" and self.manager.audio.active
        self.streaming.setText(
            "● REMOTE AUDIO STREAM ACTIVE • ElevenLabs"
            if remote
            else "OFFLINE DEMO • synthetic visitor and audio"
            if self.demo
            else "LOCAL PERCEPTION • " + self.settings.conversation_backend.upper()
        )
        self.streaming.setStyleSheet(
            "color:#ff5670;font-weight:bold" if remote else "color:#ad9ab5"
        )
        self.last_tick = now

    def closeEvent(self, event):
        if not self.closed:
            self.closed = True
            self.timer.stop()
            self.emergency_stop()
            self.camera.stop()
            self.manager.shutdown()
            if self.hardware:
                self.hardware.close()
        event.accept()
