# Project MALACHI — Autonomous AI-Powered Halloween Animatronic Skull

## Your Role

Act as a senior robotics engineer, embedded systems engineer, Python architect, and computer vision engineer.

Build a complete, modular, extensible application called **MALACHI**, an autonomous AI-powered Halloween animatronic skull.

I want actual working, maintainable code, not pseudocode or disconnected examples.

The application must initially run on my Mac using the built-in or external webcam, microphone, and speakers. Later, the same application should run on a Raspberry Pi 5 connected to an ESP32-S3 microcontroller controlling physical servos.

**Important:** I currently own only the physical Halloween skull. I do not yet have the Raspberry Pi, ESP32, servos, or camera module.

Therefore, the entire first version must work on macOS without additional hardware, using simulated eyes, jaw, and head movements.

Do not make physical hardware a prerequisite for running and testing the project.

---

# 1. Project Objectives

Build a Halloween skull that can:

1. Detect human faces using a camera.
2. Track a person's face with animated eyes.
3. Determine approximately whether a person is facing the skull.
4. Activate its AI conversation after 3 seconds of sustained face orientation toward the camera.
5. Connect to an existing ElevenLabs ElevenAgents conversational agent.
6. Listen continuously during an active conversation session.
7. Speak using the custom ElevenLabs ghost voice.
8. Animate its jaw in synchronization with generated speech.
9. Maintain eye tracking while listening or speaking.
10. Respond to visitor disappearance, inactivity, and goodbye.
11. Automatically close conversations to control API usage.
12. Prevent repeated activations from the same stationary visitor.
13. Support future physical motors, lights, and head movements.
14. Provide a visually impressive local control and debugging dashboard.

The experience should feel like a supernatural being noticing, watching, and eventually talking to a visitor.

---

# 2. Technology Stack

## Raspberry Pi / Mac Application

- Python 3.11+
- OpenCV for camera capture and image processing
- MediaPipe Face Landmarker for facial landmarks and head-pose estimation
- NumPy for image and mathematical operations
- ElevenLabs official Python SDK or documented WebSocket conversation API
- sounddevice / PortAudio or another compatible audio input-output backend
- PySide6 for a desktop dashboard and animated eye simulation
- asyncio for asynchronous operations
- pyserial for eventual ESP32 communication
- Pydantic for configuration and validated events
- Python logging for structured diagnostics
- pytest for automated testing

Prefer well-maintained packages and avoid unnecessary dependencies.

Use the official documented ElevenLabs APIs. Do not invent SDK methods, events, authentication formats, or payloads.

## Embedded Firmware

Target the ESP32-S3 using:

- ESP-IDF
- C
- FreeRTOS
- UART or USB serial communication
- I2C
- PCA9685 servo driver
- Hardware timers and watchdogs

The initial implementation should include the firmware project structure, protocol definitions, and mocked hardware interfaces. Full physical integration will happen later.

---

# 3. High-Level Architecture

Use the following data flow:

Camera
→ OpenCV
→ Face Detection
→ Head-Pose Estimation
→ Face Tracking
→ Behavior State Machine

The behavior state machine controls two independent systems:

**System A — Conversational AI**

Behavior State Machine
→ ElevenLabs Session Manager
→ Microphone Audio Stream
→ ElevenLabs ElevenAgents
→ Generated Ghost Speech
→ Audio Playback
→ Jaw Animation Controller

**System B — Animatronics**

Face Tracker
→ Eye Target Calculator
→ Motion Controller
→ Simulated Animated Eyes

Later replace the simulator with:

Motion Controller
→ USB Serial
→ ESP32-S3
→ PCA9685
→ Servo Motors

Maintain a clear separation between AI services, perception, behavioral logic, animation, and hardware drivers.

The computer vision loop must not block while ElevenLabs is connecting, generating speech, or playing audio.

---

# 4. Behavior State Machine

Implement the following states:

### IDLE

No visitor is currently detected.

Behavior:
- ElevenLabs WebSocket disconnected.
- Animated eyes remain in a neutral downward position.
- Occasional subtle eye movements are allowed.
- Camera continues monitoring locally.
- Audio streaming disabled.

### WATCHING

A face has been detected continuously for at least 300 milliseconds.

Behavior:
- Animated eyes turn toward the detected face.
- Eye tracking operates at approximately 10 Hz.
- ElevenLabs remains disconnected.
- The skull does not speak.

### STALKING

The detected visitor appears to be facing toward the skull.

Behavior:
- Start a 3-second qualifying timer.
- Maintain eye contact.
- Optionally perform subtle eye micro-movements.
- Reset or pause the qualifying timer when orientation is no longer valid.

### AWAKENING

The visitor has faced the skull for 3 seconds.

Behavior:
- Animate eyes toward the visitor.
- Prepare conversational audio.
- Establish an ElevenLabs conversation session.
- Play the configured first greeting when the conversation is ready.
- Enter CONVERSING once the session is active.

### CONVERSING

The ElevenLabs session is connected.

Behavior:
- Stream microphone audio to ElevenLabs.
- Play generated ghost speech.
- Keep tracking the visitor's face.
- Synchronize simulated jaw movements to actual speech playback.
- Track visitor and agent speaking status.
- Respond to interruptions.
- Monitor idle and visitor-absence timers.

### ENDING

A termination condition has been reached.

Behavior:
- If appropriate, finish the current response.
- Stop microphone streaming.
- Close the ElevenLabs session cleanly.
- Clear pending animation commands.
- Close the jaw.
- Return eyes to resting position.

### COOLDOWN

Prevent the skull from automatically greeting the same visitor repeatedly.

Behavior:
- Do not initiate another conversation while the same visitor remains in the detection zone.
- Rearm after the visitor is absent for a configurable duration.
- Provide a manual reset option on the dashboard.

Use explicit state transitions, validated events, and a deterministic state machine.

Avoid scattering state logic across multiple unrelated modules.

---

# 5. Camera and Computer Vision

Implement a camera service that:

- Supports macOS and Raspberry Pi.
- Automatically discovers or selects a camera.
- Uses configurable camera indices.
- Captures approximately 15–30 FPS where supported.
- Provides face bounding boxes.
- Calculates normalized face-center coordinates.
- Tracks faces between frames.
- Estimates yaw and pitch using facial landmarks.
- Provides face detection confidence and stability information.
- Recovers from temporary camera failures.

## Face Selection

If multiple faces are detected:

- Track the currently selected visitor.
- Avoid jumping between people every frame.
- Prefer the current target when still visible.
- Otherwise choose the largest or closest-looking face using a configurable heuristic.
- Provide an optional manual target selection in the dashboard.

Do not implement personal identity recognition or storage of facial identities.

## Looking Toward the Skull

Estimate head pose using MediaPipe facial landmarks.

Start with these configurable thresholds:

- Maximum absolute yaw: 25 degrees.
- Maximum absolute pitch: 20 degrees.
- Sustained duration: 3 seconds.
- Brief detection dropout tolerance: 250 milliseconds.

Head-pose orientation is only an approximation of attention, not direct eye-gaze detection.

Calibrate neutral head pose and camera placement before relying on these thresholds.

## Distance

Do not pretend that a single RGB camera provides accurate physical distance.

In the Mac prototype, use apparent face size only as a rough proximity heuristic.

Later support an optional time-of-flight distance sensor.

---

# 6. Eye Tracking System

Implement a reusable eye-motion engine.

Input:

- Selected face coordinates.
- Screen or camera dimensions.
- Current eye positions.
- Configured maximum movement limits.

Output:

- Eye horizontal position.
- Eye vertical position.
- Optional head target position.

Represent virtual movement in normalized values between -1 and +1.

Initial physical servo calibration limits:

- Horizontal: approximately ±20 degrees.
- Vertical: approximately ±15 degrees.

These are placeholders until hardware calibration.

## Movement Requirements

- Smooth interpolation rather than instant jumps.
- Exponential smoothing or another stable filter.
- Configurable movement speed.
- Maximum velocity constraints.
- Small, randomized eye movements.
- Natural-looking blinks in the simulator.
- Neutral pose when no face is present.
- Ability to override tracking for expressive animations.

Important: The real physical design uses two servos for a shared eye mechanism. Do not assume both eyes can move independently.

## Mac Simulation

Create two animated eyeballs in the dashboard.

Both pupils should move together and follow the user's face.

Provide animated eyelids for blinking in the simulation, but treat physical eyelid motors as an optional future upgrade.

Include a visual indicator showing the target face coordinates and calculated servo angles.

---

# 7. ElevenLabs Conversational AI Integration

I already have an ElevenLabs ElevenAgents ghost agent configured.

The application must connect to this existing agent rather than creating a new one.

Use environment variables:

ELEVENLABS_AGENT_ID
ELEVENLABS_API_KEY

Never hardcode credentials.

Use the official ElevenLabs Python SDK if it supports the required audio streaming and session events. Otherwise, implement the documented WebSocket protocol.

## Session Lifecycle

The ElevenLabs session should start only when the behavior state machine enters AWAKENING.

While connected:

- Capture microphone audio.
- Send audio in the format required by ElevenLabs.
- Receive generated audio.
- Play the audio through the configured speaker.
- Receive available agent/user conversation events.
- Track session connection status.
- Support interruption and cancellation.
- Handle connection failures gracefully.

Do not reopen a WebSocket for every conversational turn.

Use one connection for the duration of an active session.

## End Conditions

End the session when any of the following occurs:

1. No meaningful conversational activity for 30 seconds.
2. Visitor absent from camera for 10 seconds.
3. Visitor says goodbye and the application can reliably identify the conversation-ending intent.
4. Maximum session duration reaches 180 seconds.
5. User presses End Session in the dashboard.
6. Connection failure or controlled application shutdown.

Do not terminate while the visitor or agent is actively speaking merely because an idle timer expired.

Define the idle timer relative to meaningful conversation activity, including visitor speech start/end and agent output.

Use monotonic clocks for timing.

For the maximum duration, request a graceful stop when practical, but allow service-enforced hard limits to take precedence.

## Reconnection

Implement exponential backoff for unexpected connection failures, but only reconnect while the state machine still authorizes a conversation.

Never create infinite uncontrolled paid sessions.

## Cost Awareness

Track:

- Session start timestamp.
- Session end timestamp.
- Total connected duration.
- Number of sessions.
- Connection failures.

Display these in the dashboard.

Do not invent exact API billing amounts. If pricing data is unavailable, report duration rather than estimated cost.

## Conversation Privacy

Do not store raw microphone recordings or full conversation transcripts by default.

Allow optional local diagnostic logging without exposing API keys.

Provide a clear visible indicator when remote audio streaming is active.

---

# 8. Jaw Synchronization

The jaw must animate in response to generated ElevenLabs speech.

For the Mac prototype, implement a simulated jaw visualization.

Use an audio-driven technique first.

## Algorithm

1. Receive generated speech audio.
2. Decode or normalize it into PCM samples.
3. Buffer the samples for playback.
4. Calculate short-window RMS amplitude.
5. Convert amplitude into a normalized jaw position.
6. Apply smoothing and noise-gate thresholds.
7. Synchronize movement with the samples being played.
8. Close the jaw when speech ends.

Initial parameters:

- Audio analysis window: 20 ms.
- Jaw position: 0–100%.
- Jaw attack time: approximately 40 ms.
- Jaw release time: approximately 100 ms.
- Noise gate: configurable.

Avoid commanding the jaw open during silence.

Do not drive the jaw using speech text length or randomly generated movement.

The animation must follow the actual audio playback timeline, including buffering delays.

Later, send jaw positions to the ESP32 at approximately 25–50 Hz.

If the selected ElevenLabs SDK hides the raw audio playback stream, implement an application-controlled audio playback adapter or document the limitation and keep lip-sync disabled until synchronized audio is available.

---

# 9. Desktop Dashboard

Build a clean, modern, dark Halloween-themed desktop UI using PySide6.

The interface should be attractive enough to demonstrate as a portfolio project.

Use black, charcoal, deep red, and subtle purple accents.

## Main Dashboard Layout

### Camera Preview

Display:
- Live webcam feed.
- Face bounding boxes.
- Selected tracked face.
- Approximate head orientation.
- Face confidence.
- Detection and qualification timer.

### Animated Skull Panel

Display:
- Two realistic or stylized animated eyeballs.
- Pupils following the tracked face.
- Blinking animation.
- A simplified animated skull jaw or mouth.
- Current simulated head orientation.

### State Monitor

Show:
- Current state.
- Previous state.
- Last transition reason.
- Time in current state.
- Face tracking status.
- ElevenLabs connection status.

### Session Monitor

Show:
- Current session duration.
- Total connected time.
- User speaking / agent speaking / waiting.
- Inactivity countdown.
- Visitor absence countdown.
- Conversation event summaries.

### Controls

Provide:

- Start camera.
- Stop camera.
- Manually start conversation.
- End conversation.
- Enable/disable autonomous mode.
- Enable/disable eye tracking.
- Mute microphone.
- Mute speaker.
- Center eyes.
- Test jaw animation.
- Reset cooldown.
- Emergency Stop.

### Configuration Panel

Allow adjustment of:
- Camera index.
- Face trigger duration.
- Head-pose thresholds.
- Eye smoothing.
- Servo movement limits.
- Conversation inactivity timeout.
- Visitor absence timeout.
- Session maximum duration.
- ElevenLabs agent ID.

Never expose the API key in the interface.

Use background workers, asyncio integration, or threads so the UI never freezes while processing camera frames or network activity.

All UI mutations must occur on the appropriate UI thread.

---

# 10. Hardware Abstraction Layer

Design interfaces that support switching between simulation and real hardware.

Create:

MotionController interface
- set_eye_target(x, y)
- set_jaw_position(value)
- set_head_target(x, y)
- set_led_effect(effect)
- neutral_position()
- emergency_stop()

Implement:

SimulatedMotionController

Initially updates the dashboard animations.

ESP32MotionController

Later sends serial commands to an ESP32.

The application should select its backend through configuration.

Example:

MOTION_BACKEND=simulation

or

MOTION_BACKEND=esp32

All motion commands must be clamped to calibrated limits.

---

# 11. ESP32 Communication Protocol

Define a simple, versioned serial protocol.

For readability in the prototype, newline-delimited JSON is acceptable.

Example:

{"v":1,"type":"EYES","x":0.25,"y":-0.1}

{"v":1,"type":"JAW","open":0.65}

{"v":1,"type":"HEAD","pan":0.15,"tilt":0.0}

{"v":1,"type":"LED","effect":"red_pulse"}

{"v":1,"type":"STOP"}

Each command must be validated.

Define acknowledgment and error messages.

Plan for:
- Message framing.
- Partial messages.
- Maximum packet size.
- Invalid JSON.
- Disconnection recovery.
- Rate limiting.
- Watchdog timeout.
- Emergency stop.
- Serial port reconnection.

Do not assume physical servos are safe to move across their full nominal angular ranges.

---

# 12. ESP32-S3 Firmware

Create a separate ESP-IDF project.

The firmware should eventually:

- Initialize USB serial or UART.
- Initialize I2C.
- Initialize the PCA9685 driver.
- Parse and validate motion commands.
- Maintain target servo positions.
- Smoothly interpolate servo movement.
- Enforce calibrated position limits.
- Handle loss of communication.
- Return motors to safe positions when appropriate.
- Support an emergency-stop state.
- Avoid blocking the serial input loop.

Use FreeRTOS tasks where appropriate.

Start with mock actuator functions so host-side protocol tests can be developed without the physical hardware.

Use safe defaults until servo models, geometry, power capacity, and current limits have been confirmed.

Do not enable arbitrary remote execution or accept raw PWM values directly from the LLM.

---

# 13. Configuration

Create an .env.example file and a validated configuration module.

Suggested variables:

APP_MODE=development
MOTION_BACKEND=simulation

CAMERA_INDEX=0
CAMERA_FPS=20

FACE_DETECTION_HOLD_SECONDS=0.3
FACE_FACING_HOLD_SECONDS=3.0
FACE_YAW_THRESHOLD=25
FACE_PITCH_THRESHOLD=20

EYE_TRACKING_HZ=10
EYE_MAX_PAN_DEGREES=20
EYE_MAX_TILT_DEGREES=15

CONVERSATION_IDLE_TIMEOUT_SECONDS=30
VISITOR_ABSENCE_TIMEOUT_SECONDS=10
MAX_SESSION_DURATION_SECONDS=180
COOLDOWN_REARM_ABSENCE_SECONDS=5

ELEVENLABS_AGENT_ID=
ELEVENLABS_API_KEY=

SERIAL_PORT=
SERIAL_BAUDRATE=115200

DEBUG_MODE=true

Use strongly typed configuration validation.

Clearly distinguish values measured in seconds, degrees, percentages, and normalized coordinates.

---

# 14. Codebase Structure

Use approximately the following structure:

malachi/
- README.md
- pyproject.toml
- .env.example
- .gitignore
- LICENSE
- assets/
- config/
- docs/
  - architecture.md
  - hardware.md
  - state-machine.md
  - elevenlabs-setup.md
  - testing.md
- src/malachi/
  - main.py
  - config.py
  - events.py
  - vision/
    - camera.py
    - face_detector.py
    - face_tracker.py
    - head_pose.py
  - behavior/
    - state_machine.py
    - session_policy.py
    - animations.py
  - conversation/
    - elevenlabs_client.py
    - audio_input.py
    - audio_output.py
    - conversation_manager.py
  - motion/
    - controller.py
    - simulation.py
    - serial_controller.py
    - eye_motion.py
    - jaw_sync.py
  - ui/
    - dashboard.py
    - camera_widget.py
    - animated_skull.py
    - controls.py
  - telemetry/
    - logging.py
    - metrics.py
- firmware/
  - esp32_skull/
    - CMakeLists.txt
    - main/
    - components/
    - README.md
- tests/
  - test_state_machine.py
  - test_session_policy.py
  - test_eye_tracking.py
  - test_jaw_sync.py
  - test_serial_protocol.py
  - test_elevenlabs_mock.py

You may refine the architecture when necessary, but preserve modular boundaries.

---

# 15. Reliability and Edge Cases

Handle these scenarios explicitly:

1. Camera disconnected while watching a visitor.
2. Multiple people detected simultaneously.
3. Person briefly turns away during the activation countdown.
4. Face temporarily occluded.
5. Internet disconnected during a conversation.
6. ElevenLabs authentication failure.
7. ElevenLabs rate limiting or service errors.
8. User interrupts the ghost.
9. Visitor walks away while the agent is speaking.
10. A new visitor arrives during cooldown.
11. Audio playback device becomes unavailable.
12. Microphone captures sound from the skull's own speaker.
13. Application closes while the session is active.
14. Serial connection to ESP32 fails.
15. Servo controller stops responding.
16. Emergency Stop is activated.

Provide reasonable recovery paths.

For microphone feedback, use headphones during initial development, and later evaluate acoustic echo cancellation or appropriate speaker/microphone placement. Do not assume simple noise gating alone will solve acoustic feedback.

Never allow a network failure to freeze the camera or motion-control loop.

---

# 16. Automated Tests

Create unit tests for:

- State transitions.
- 300 ms face-detection threshold.
- 3-second orientation trigger.
- Brief detection dropout behavior.
- 30-second conversational inactivity.
- 10-second visitor absence.
- 180-second maximum session duration.
- Cooldown and rearming.
- Servo angle clamping.
- Eye position interpolation.
- Jaw movement from synthetic PCM audio.
- JSON message validation.
- ElevenLabs connection failures.
- Prevention of duplicate sessions.

Use mocked cameras, fake clocks, fake audio streams, and fake ElevenLabs clients.

Tests must run without a webcam, microphone, ElevenLabs account, or ESP32.

---

# 17. Development Phases

Implement the project incrementally.

## Phase 1 — Local Vision and Animated Eyes

Deliver:
- Working Mac camera preview.
- Face detection.
- Head-pose estimation.
- Animated eyes that follow faces.
- State transitions.
- Countdown timer.
- No ElevenLabs dependency required at runtime.

This phase must run completely offline after dependencies and models are installed.

## Phase 2 — ElevenLabs Conversations

Deliver:
- Agent ID configuration.
- Authentication.
- Working microphone and speaker.
- Live conversational session.
- Automatic startup.
- Automatic termination.
- Session telemetry.

Include a mock conversation backend for offline testing.

## Phase 3 — Jaw Animation

Deliver:
- Actual streamed audio playback.
- PCM amplitude analysis.
- Simulated jaw movement.
- Playback synchronization.
- Safe jaw rest behavior.

## Phase 4 — Hardware Protocol

Deliver:
- Motion abstraction.
- ESP32 serial protocol.
- Serial simulation.
- Firmware skeleton and parser.
- Motor limit configuration.
- Hardware setup documentation.

## Phase 5 — Physical Integration

Prepare documentation for:
- Raspberry Pi installation.
- Pi camera installation.
- ESP32-S3 wiring.
- PCA9685 connection.
- Separate regulated servo supply.
- Shared electrical ground.
- Eye linkage calibration.
- Jaw servo calibration.
- Safe head rotation.
- Automated startup with systemd.

Do not require physical hardware to finish phases 1–4.

---

# 18. Acceptance Criteria

The first complete software release is successful when:

1. I can install and launch the application on my Mac.
2. A desktop dashboard displays my live camera feed.
3. The application detects my face.
4. Two animated eyeballs visibly follow my movement.
5. When I face the camera, a 3-second timer begins.
6. Looking away interrupts or resets that timer appropriately.
7. After 3 seconds, the application initiates an ElevenLabs conversation.
8. My custom ghost agent greets me using its selected voice.
9. I can speak to it and receive real-time spoken responses.
10. The simulated jaw follows the generated speech playback.
11. The eyeballs continue tracking me throughout the conversation.
12. Walking away for 10 seconds ends the session.
13. Conversation inactivity for 30 seconds also ends the session.
14. The application avoids repeatedly greeting me while I remain in front of it.
15. A new visitor can trigger a fresh session after rearming.
16. All critical behavior can be tested with automated mocks.
17. Network or hardware failures are handled cleanly.
18. The same application architecture is ready for Raspberry Pi deployment.

---

# 19. Additional Engineering Requirements

- Use Python type hints.
- Use clear interfaces and dependency injection where useful.
- Document public classes and non-obvious algorithms.
- Avoid massive single-file implementations.
- Use monotonic timestamps for timers.
- Do not block UI or camera processing on network calls.
- Include graceful shutdown.
- Pin compatible dependency versions.
- Use a proper .gitignore.
- Never commit .env or API credentials.
- Handle SDK changes without silently fabricating unsupported methods.
- Add structured logs.
- Include beginner-friendly installation instructions.
- Provide exact commands for creating the virtual environment, installing dependencies, running tests, and starting the application.
- Add a troubleshooting section for macOS camera and microphone permissions.
- Keep the dashboard usable without connecting ElevenLabs.
- Provide a simulation/demo mode with prerecorded or synthesized test signals.
- Make the project suitable for a public GitHub portfolio.

---

# 20. How You Should Proceed

First inspect the existing repository, if any.

Then:

1. Explain the implementation plan briefly.
2. Create the full repository structure.
3. Implement Phase 1 with working executable code.
4. Write automated tests for Phase 1.
5. Run the tests and fix failures.
6. Implement the remaining phases in order, using mock interfaces where credentials or hardware are unavailable.
7. Document exact setup steps.
8. Run all tests and report the results.
9. State clearly which features are verified and which require live hardware or ElevenLabs credentials.
10. Do not claim hardware integration or live ElevenLabs functionality has been tested unless it actually has.

Prioritize a fully working, polished macOS prototype over implementing every future hardware feature superficially.

**Begin implementation now.**