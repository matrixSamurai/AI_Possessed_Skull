# Hardware roadmap — nothing additional needed for the Mac prototype

Current ownership: Halloween skull only. Raspberry Pi 5, ESP32-S3, servos and camera
are future purchases. Keep MOTION_BACKEND=simulation until the mechanics are calibrated.
The shared eye mechanism has two servos total: horizontal and vertical; eyes are not
independently actuated. Physical eyelids, head rotation, LEDs and ToF range are optional.

## Pi preparation (not yet tested)

Use a 64-bit Raspberry Pi OS release with Python 3.11/3.12. Install system Qt/OpenGL,
PortAudio and camera support through the OS package manager. Test pip wheel availability
for pinned PySide6 and MediaPipe on aarch64 before purchasing/deploying; versions may
need a separately validated Pi dependency profile. Do not silently build arbitrary
native versions or claim the macOS dependency set is validated on Pi.

A USB UVC camera can use OpenCV's camera-index backend. CSI Pi cameras should use
Picamera2/libcamera with a separate capture adapter that returns BGR frames; this adapter
is not implemented. Test `rpicam-hello` first when using the Pi camera stack.
A desktop display/session is currently required by PySide6. A future headless appliance
should separate the control service from the dashboard rather than launch Qt as root.

## Wiring and calibration plan

- Choose servo torque, geometry and travel after measuring the skull/linkage. Start with
  one unloaded servo. ±20° horizontal/±15° vertical are display placeholders, not measured limits.
- Use a separately regulated servo supply sized for simultaneous stall currents, with
  appropriate fuse, bulk capacitance and a physical power cutoff. Do not power motors
  from Pi/ESP32 3.3V rails. Share signal ground between logic and servo supply.
- Connect the PCA9685 logic side to a correctly rated I2C bus. Select SDA/SCL from the
  actual ESP32-S3 board schematic. Confirm pull-up voltage and address, normally 0x40.
  Servo power goes to the board's dedicated motor supply, not logic VCC.
- Match each servo's documented frequency/pulse range; constrain pulses in firmware.
  Calibrate safe neutral and endpoints mechanically. Never assume 0–180° is safe.
- Calibrate jaw closed/open without loading teeth/linkages. Confirm loss-of-power behavior.
- Add head motion only after assessing cable twist, pinch points, stops and mechanical load.
- Keep LLM-generated content away from raw motor/PWM control. The existing JSON protocol
  only accepts bounded absolute positions and predefined effects.

## Future startup with systemd

After a tested headless control entry point exists, use a dedicated unprivileged user,
WorkingDirectory pointing to the checkout, ExecStart pointing to its venv interpreter,
Restart=on-failure with rate limits, and a securely permissioned EnvironmentFile.
Require serial device access through the appropriate device group. Keep audio/camera
availability checks and firmware STOP on shutdown. Do not enable an unattended service
that can create paid sessions until termination/cooldown have been validated on the Pi.

The ESP-IDF scaffold has no PCA9685/I2C driver or real actuator power enable yet.
It is a host-testable integration boundary, not a physical integration claim.
