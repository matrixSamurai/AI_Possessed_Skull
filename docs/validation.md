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

## Movement and tracking-loss grace

Active-session presence now follows visible face occupancy rather than a fixed
geometric track ID. Rapid movement or occlusion can change IDs without ending the
connection. The default continuous-absence timeout is 20 seconds, configurable via
VISITOR_ABSENCE_TIMEOUT_SECONDS; any returning visible face resets the timer.
Activation pose thresholds, 30-second idle policy, 180-second maximum, manual stop
and emergency stop remain independent. Existing .env timeout overrides are preserved.

Regression result: **66 tests passed**. Tests cover track-ID changes and extreme pose
within one session, late reacquisition, repeated nonaccumulating detection losses,
20-second default/30-second custom absence limits, and retained 10-second override
behavior. Lint and formatting checks pass. Real Mac movement testing is still needed.

## GPT visual context

Added opt-in one-snapshot OpenAI analysis at interaction start. Official OpenAI SDK
3.29.0 Responses requests are verified using a mocked HTTP transport. The description
is supplied through ElevenLabs visual_context dynamic variables and a contextual_update;
a fallback dynamic variable keeps the agent usable when analysis fails or is disabled.
No images/descriptions are written to local disk/logs. API response storage is disabled
with store=False; provider retention is governed separately by account/service policies.

Regression result: **79 tests passed**, including actual SDK serialization, JPEG resize,
no repeat analysis across voice retries, timeout/cancellation, missing key/frame and
provider-error fallback, no mock/demo uploads, and documented context handoff. Existing
audio/motion/absence tests still pass. Constrained install and cloud setup script pass.
No live GPT request was made: OPENAI_API_KEY is absent in this environment. Real photo
accuracy and the ghost's response to visual context need validation on the user's Mac.

## ElevenLabs-only visual input (supersedes the GPT route above)

Removed the direct OpenAI analyzer, key/model settings and dependency requirement.
The existing ElevenLabs key now authenticates image upload to the active conversation.
The official SDK's multimodal message references the returned file ID at a speech pause;
the agent's selected image-capable LLM handles interpretation through ElevenLabs.

Current validation: **83 tests passed**, 0 failed/skipped; two upstream SDK deprecation
warnings. Lint, formatting, dependency refresh and cloud setup/demo smoke pass. Tests
exercise actual ElevenLabs SDK multipart upload/authentication with mocked HTTP,
no upload retry, official multimodal serialization, upload timeout/cancellation,
no offline upload, single-use snapshot release, speech-pause coordination and concurrent
audio/ping during upload. The prior OpenAI tests were replaced by this route's tests.

No live ElevenLabs image upload was made: credentials and a real camera are absent
in the cloud. File input and a compatible multimodal agent/model must be enabled in
the user's ElevenLabs account. API send success is not proof of model interpretation.
The image is uploaded remotely as a conversation file; no local image is persisted.
A multimodal input can generate a conversational response and its turn ordering is
best-effort. See docs/scene-context.md for limits, retention and setup.

## Agent vision diagnostics

Added a read-only `python -m malachi.diagnostics` command using the official agent GET
API. It reports local upload enablement, declared file input, default LLM and presence
of the legacy prompt variable, without printing keys/prompts or starting a session.
Updated image instructions to request visible details when an actual image is available;
removed the misleading connection-time 'no visual context' phrasing. Upload exceptions
show HTTP status, not error body. **86 tests passed**, lint/format/diff checks passed.
The user's Client data screenshot contains the compatibility placeholder; it does not
establish successful file delivery or image-capable model selection. Actual root cause
remains unconfirmed pending local delivery status and agent configuration output.

## Live upload rejection diagnosis

The user's updated dashboard confirms local photo capture is enabled but the image
REST upload is rejected with ApiError HTTP 400; voice remains connected. Agent config
previously reported file input enabled and qwen35-397b-a17b. The specific rejection
reason remains unknown; neither that model name nor SDK support proves live acceptance.

Added bounded/redacted extraction of the API's error message instead of dumping its
response. Redaction, omitted HTML/input-validation data and opaque-body behavior have
unit tests. **89 tests passed**, lint/format/diff checks pass. Actual image upload and
interpretation remain unresolved pending the new error reason from the user's Mac.
