# Validation

Run from the repository root, Python 3.11/3.12:

```sh
python -m pip install -e '.[conversation,dev]'
QT_QPA_PLATFORM=offscreen python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
QT_QPA_PLATFORM=offscreen malachi --demo --smoke-seconds 8
python -m pip check
```

The demo is intentionally silent and model-free. Unit tests use fake monotonic times;
Qt integration tests execute actual mock-worker startup, synthetic capture, animated
jaw, shutdown and cooldown. WebSocket tests exercise the real adapter using a fake
transport, official SDK import, negotiated formats, audio/interruption filtering,
ping/pong and conservative goodbye matching. Portable firmware tests compile the real
C parser/motion with upstream MIT cJSON v1.7.18 using warnings as errors.

The C compiler is the only optional test prerequisite; firmware tests report skipped
when no `cc` exists. No tests need credentials or physical devices. All runtime imports
for ElevenLabs, MediaPipe and PortAudio are lazy so vision/demo work without live audio.

Cloud validation is recorded in `docs/validation.md`. It is Linux validation, not
macOS or Raspberry Pi device validation. Required live checks on your Mac:

1. Download the model, start webcam, calibrate pose and follow your face across the frame.
2. Look away during qualification; confirm reset. Test multiple faces and selection.
3. Enable the real agent. Verify first greeting, full duplex interaction and interruptions.
4. Compare jaw motion to audible playback, including pauses; mute speaker and check closure.
5. Test 30 s idle, 10 s absence, 180 s maximum and cooldown rearming.
6. Disconnect network and audio devices; verify responsive vision/UI and clean shutdown.
7. Grant/revoke macOS permissions to verify useful error reporting.

Known limitations are documented in README and state-machine/hardware notes rather
than hidden behind passing mocks. The model download is blocked in the current cloud
runtime until its network settings are applied.
