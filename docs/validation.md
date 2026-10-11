# Validation record — 2026-10-11

Executed in the cloud Linux x86_64 environment with Python 3.12.14.

| Check | Result |
|---|---|
| `python -m pytest -q` with offscreen Qt | **51 passed**, 0 failed, 0 skipped |
| `ruff check src tests scripts` | Passed |
| `ruff format --check src tests scripts` | Passed |
| `pip check` | No broken requirements |
| Editable install, then constrained refresh via `bash scripts/setup_cloud.sh` | Passed |
| `pip wheel . --no-deps` | Built malachi_skull-0.1.0-py3-none-any.whl |
| 14 second offscreen demo smoke | Passed: STALKING → AWAKENING → CONVERSING; clean exit |
| Qt dashboard screenshot | Rendered and visually inspected, saved in assets/dashboard-demo.png |
| Portable C motion/parser compilation | Passed with `-Wall -Wextra -Werror`; protocol tests passed |
| Model installer verification logic | Passed offline tests for checksum/archive validation, repeatability and rejection |
| Native PortAudio import | Passed; v19.7.0, **zero audio devices** |
| MediaPipe import | Passed; v0.10.21 |
| Real Face Landmarker model download | **Blocked**: proxy CONNECT returned HTTP 403 for storage.googleapis.com |
| Actual face detection/head pose on real camera | **Unrun**: model and camera unavailable |
| Live ElevenLabs authentication/audio | **Unrun**: no credentials or physical audio devices |
| macOS webcam/microphone permissions and playback latency | **Unrun**: this runtime is Linux |
| Full ESP-IDF build / FreeRTOS / physical motion | **Unrun**: toolchain/board absent |
| Raspberry Pi installation | **Unrun** |
| GitHub Actions matrix | Added but **unrun**; no changes pushed |

Official SDK contracts were inspected from installed elevenlabs 2.71.0. WebSocket
behavior was tested through mocked transport, not a live agent. PortAudio was compiled
from upstream v19.7.0 commit 147dd722548358763a8b649b3e4b41dfffbcfbb6 into
/workspace/malachi-runtime with OSS support only; this enables loading in the cloud,
not real Mac/Pi audio. cJSON v1.7.18 is vendored for host parser tests with its MIT license.

Cloud configuration draft saved successfully: install_script, start_skill, and custom
network domain storage.googleapis.com. Existing package-manager presets were retained.
Saving did not apply the new network policy or publish an environment. The saved
installer runs demo/tests and then the real model installer; the final step remains
blocked until that domain setting is applied. Review and save changes in environment
settings, then publish the prepared environment when appropriate. After networking
is applied, rerun `python scripts/download_model.py` and validate real model inference.

This validation was performed before the initial Git commit and push to the originally
empty repository. No credentials, raw audio, camera images of real people,
or transcripts were stored. A new-task snapshot restore has not been tested.

## Speaker feedback fix

After the user reported real Mac camera tracking and live ElevenLabs voice, repeated
agent words appearing as user input identified speaker feedback. Speaker echo guard
now defaults on: silence is transmitted during playback and its 300 ms DAC/reverberation
tail; headphones plus guard disabled retain voice interruption. Added bounded playback
prebuffering, 100 ms microphone batching, higher device latency and diagnostic counters.

Audio regression validation: **62 tests passed**, lint/format checks passed, and the
updated offscreen dashboard smoke check passed. Tests cover jitter without sample loss,
short tails, immediate interruption, echo suppression/tail/reopening, full duplex
opt-out, microphone batching and device-underrun reporting. Actual speaker acoustic
performance remains to be confirmed on the user's Mac; this is suppression, not AEC.
