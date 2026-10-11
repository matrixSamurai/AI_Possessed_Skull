import queue
import threading
from malachi.motion.controller import clamp
from malachi.motion.protocol import encode, parse_reply


class ESP32MotionController:
    """Optional backend. All blocking I/O stays on a serial worker; STOP is latched."""

    def __init__(self, settings):
        self.settings = settings
        self.targets = {
            "EYES": {"x": 0.0, "y": 0.3},
            "JAW": {"open": 0.0},
            "HEAD": {"pan": 0.0, "tilt": 0.0},
            "LED": {"effect": "off"},
        }
        self.lock = threading.Lock()
        self.stopped = True  # Requires explicit Resume after connecting.
        self.error = ""
        self.commands = queue.Queue(maxsize=8)
        self.exit = threading.Event()
        self.seq = 0
        self.thread = threading.Thread(target=self._run, daemon=True, name="serial")
        self.thread.start()

    def _target(self, kind, values):
        with self.lock:
            if not self.stopped:
                self.targets[kind] = values

    def set_eye_target(self, x, y):
        self._target("EYES", {"x": clamp(x), "y": clamp(y)})

    def set_jaw_position(self, value):
        self._target("JAW", {"open": clamp(value, 0, 1)})

    def set_head_target(self, x, y):
        self._target("HEAD", {"pan": clamp(x), "tilt": clamp(y)})

    def set_led_effect(self, effect):
        self._target("LED", {"effect": effect})

    def neutral_position(self):
        self.set_eye_target(0, 0.3)
        self.set_jaw_position(0)
        self.set_head_target(0, 0)

    def emergency_stop(self):
        with self.lock:
            self.stopped = True

    def resume(self):
        with self.lock:
            self.targets["EYES"] = {"x": 0.0, "y": 0.3}
            self.targets["JAW"] = {"open": 0.0}
            self.targets["HEAD"] = {"pan": 0.0, "tilt": 0.0}
            self.stopped = False
        try:
            self.commands.put_nowait("RESET")
        except queue.Full:
            self.emergency_stop()

    def _exchange(self, port, kind, values):
        self.seq = (self.seq + 1) % 2147483647
        port.write(encode({"v": 1, "seq": self.seq, "type": kind, **values}))
        reply = parse_reply(port.read_until(b"\n", 256))
        if reply["seq"] != self.seq or reply["type"] != "ACK":
            raise IOError("ESP32 rejected command or acknowledgment timed out")

    def _run(self):
        import serial

        while not self.exit.is_set():
            try:
                with serial.Serial(
                    self.settings.serial_port,
                    self.settings.serial_baudrate,
                    timeout=0.15,
                    write_timeout=0.15,
                ) as port:
                    self.emergency_stop()
                    self._exchange(port, "STOP", {})
                    while not self.exit.is_set():
                        try:
                            command = self.commands.get_nowait()
                            self._exchange(port, command, {})
                        except queue.Empty:
                            pass
                        with self.lock:
                            stopped = self.stopped
                            targets = {k: dict(v) for k, v in self.targets.items()}
                        if stopped:
                            self._exchange(port, "STOP", {})
                        else:
                            for kind, values in targets.items():
                                self._exchange(port, kind, values)
                        self.exit.wait(0.04)
                    self._exchange(port, "STOP", {})
            except Exception:
                self.emergency_stop()
                self.error = "Serial disconnected or invalid reply; motors latched STOP"
                self.exit.wait(1)

    def close(self):
        self.emergency_stop()
        self.exit.set()
        self.thread.join(timeout=2)
