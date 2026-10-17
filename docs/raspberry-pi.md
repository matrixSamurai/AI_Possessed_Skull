# MALACHI on Raspberry Pi 5

Use the `raspberry-pi5` branch. It runs on the Pi and uses the Pi's attached camera,
microphone and speaker, not devices on the Mac or in the Codex cloud. A local desktop
(or remote desktop session) is required for the animated eyes and dashboard.

## Install

Use **64-bit Raspberry Pi OS with Desktop**. The installer supports Python 3.11–3.13,
including Bookworm and Trixie. It detects the Python version and architecture rather
than assuming the Mac environment will work on ARM. It requires Internet access for
apt/PyPI and sudo permission for OS packages.

From a terminal on the Pi:

```bash
git clone --branch raspberry-pi5 https://github.com/matrixSamurai/AI_Possessed_Skull.git
cd AI_Possessed_Skull
bash scripts/setup_raspberry_pi.sh
```

If the repository is already cloned, commit/stash any local source changes first,
then fetch and switch to `raspberry-pi5` instead of cloning another copy. Preserve your
existing `.env` file. Do not copy a Mac `.venv` to the Pi.

The installer uses apt's OpenCV/NumPy/Picamera2/libcamera packages and a virtualenv
with `--system-site-packages`. Current Raspberry Pi OS supplies PySide6 through apt;
if unavailable, the installer tries a binary PySide6 wheel and fails with guidance
if the older OS has no compatible wheel. It never builds Qt/MediaPipe from source,
uses sudo pip, or replaces libcamera with an unrelated pip package. An existing venv
without system-site access is not overwritten; rename it and rerun setup.

A new `.env` is created from `.env.raspberry-pi.example` only if none exists. Edit it:

```bash
nano .env
```

Set your existing `ELEVENLABS_AGENT_ID` and `ELEVENLABS_API_KEY` locally. Do not commit
or paste them into chat. Existing `.env` files are preserved: compare their camera
and audio options with the Pi template. Registered ElevenLabs eye/lighting tools and
image-upload permissions still apply to this branch.

## Camera

For the official ribbon camera (including Camera Module 3 / NoIR):

```dotenv
CAMERA_BACKEND=picamera2
CAMERA_INDEX=0
CAMERA_WIDTH=1280
CAMERA_HEIGHT=720
CAMERA_FPS=15
FACE_BACKEND=opencv
```

Close other camera applications before starting. `rpicam-hello --list-cameras` should
list the sensor. `CAMERA_INDEX` refers to the Picamera2 camera number. Cable fitting
and sensor detection must work in Raspberry Pi OS first. NoIR still needs IR lighting
in darkness; colors under IR are not reliable clothing colors.

For a USB camera, explicitly choose:

```dotenv
CAMERA_BACKEND=opencv
CAMERA_INDEX=0
```

Auto selection uses Picamera2 on a Raspberry Pi and OpenCV elsewhere. A failed CSI
camera is not silently replaced with an unintended USB camera. Captured RGB888 data
from libcamera is byte-ordered BGR on the Pi, matching the existing OpenCV pipeline.
Scene snapshots and camera reflections use the same fresh local camera feed.

The ARM default is OpenCV's frontal-face cascade, with no downloaded Face Landmarker
or MediaPipe wheel required. Frontal detections can qualify sessions after the normal
hold time; head yaw/pitch are **not measured** and the UI says so. Tracking eye position,
occupancy and scene uploads continue. Profile/occluded/tiny faces may be missed;
this is not equivalent in accuracy to MediaPipe's landmarks. Lower
`FACE_OPENCV_MIN_SIZE` toward 16 to search smaller faces (more false positives/CPU),
or increase `FACE_OPENCV_MAX_WIDTH` toward 1280 to retain more small-face detail.
`FACE_OPENCV_MIN_NEIGHBORS=5` controls false detections. The desktop MediaPipe backend
remains selectable with `FACE_BACKEND=mediapipe` when installed with its model.

## Microphone and speaker

The Pi 5 has no built-in microphone or analog headphone output. Your attached USB,
I2S or HDMI audio must first appear as a Raspberry Pi OS audio device. Additional I2S
hardware may need its vendor's driver/device-tree configuration; the installer does
not guess wiring or change boot overlays.

List local devices:

```bash
source .venv/bin/activate
python -m malachi.devices
```

Blank settings use the OS default input and output. To choose explicitly, use an
exact/unique PortAudio device name or its numeric ID from that listing:

```dotenv
AUDIO_INPUT_DEVICE=USB Microphone
AUDIO_OUTPUT_DEVICE=USB Audio
```

Replace those example names with your actual devices; indexes can change on reboot,
so stable names are preferable. Set the Pi desktop's default output to the attached
speaker rather than HDMI if HDMI is not your speaker. Idle ambience and conversation
use the same selected output, with exclusive handover between their streams.

The app negotiates supported mono/stereo formats at 16 kHz or the device's native
rate (including 44.1/48 kHz). Microphone channels are mixed to mono and downsampled
with a low-pass filter; remote audio stays PCM16/16 kHz. Playback is resampled for
the speaker and duplicated to stereo if needed. Unsupported devices fail with a
selection hint rather than changing the negotiated ElevenLabs format.

Check devices without starting a paid conversation or saving recordings/images:

```bash
python -m malachi.devices --check-audio --check-camera
python -m malachi.devices --test-speaker
python -m malachi.devices --test-microphone
```

Verify you hear the test tone on the intended speaker. Speak during the two-second
microphone check and verify its RMS responds; zero RMS can mean mute or a wrong input.
The camera check captures and discards one frame. Format checks alone do not prove
actual stream playback, so run the speaker/microphone tests too.

## Start

From a terminal in the Pi's desktop:

```bash
bash scripts/run_raspberry_pi.sh --vision-only
```

Once camera tracking is working, close that window and start the real conversation:

```bash
bash scripts/run_raspberry_pi.sh
```

Do **not** use `--demo` for real devices. `--demo` intentionally uses synthetic frames
and mock audio for offline tests. SSH alone does not provide a GUI display; use the
Pi desktop/remote desktop to see the eyes. No background autostart service is enabled
without first confirming local camera/audio work. Keep speaker echo guard enabled
for speakers, and physically separate the microphone from the speaker. The guard
suppresses the agent's own playback; background ambience is not acoustic echo-cancelled.
Physical servos/LED wiring remains a separate integration; `MOTION_BACKEND=simulation`
keeps the existing animated skull and lighting preview.

## Validation scope

Camera lifecycle/configuration, BGR preservation, multi-face cascade coordinates,
mono/stereo format negotiation, 16/44.1/48 kHz streaming conversion, playback pitch,
input downmix and interruption handling are covered in automated tests. The real
OpenCV cascade also runs against blank frames on the cloud. The cloud is x86-64,
not a Pi: apt installation on ARM, actual camera/USB/I2S operation and live ElevenLabs
conversations need the local checks above. Do not treat an offline smoke test as
proof of physical Pi readiness.

### Run over SSH without a display

The launcher automatically uses headless mode when neither `DISPLAY` nor
`WAYLAND_DISPLAY` is set. Camera detection, microphone/speaker conversations,
periodic image context and ambience run locally on the Pi, with terminal logs.
No desktop session or graphical window is required:

```bash
cd ~/Desktop/AI_Possessed_Skull
bash scripts/run_raspberry_pi.sh --headless
```

Press Ctrl+C to stop and release the camera/audio devices. Explicit `--headless`
also works when desktop environment variables are present. Bluetooth still needs
an active audio service and a selected playback device; headless mode does not
repair missing speaker routing. On-screen eye animations and underlighting are
not rendered, and visual tool requests are logged as unavailable. The existing
ESP32 motor backend retains its explicit resume safety latch; headless operation
does not automatically arm motors.

### Intermittent face detection

Startup now preserves the greeting countdown across geometric tracking-ID changes
and brief missed detections. `FACE_STARTUP_GRACE_SECONDS=1.25` controls the allowed
startup gap (0–5 seconds); the larger of this and `FACE_DROPOUT_SECONDS` applies.
A current detected face is still required to start a conversation. A longer
observed absence resets qualification; looking away when head pose is available
also resets the facing countdown. Active conversations retain their separate
`VISITOR_ABSENCE_TIMEOUT_SECONDS` policy. These tolerances do not fix camera I/O
faults or make OpenCV detect faces in darkness.
