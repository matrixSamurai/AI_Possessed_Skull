# iPhone camera viewer (same Wi-Fi)

The separate `matrixSamurai/MALACHI-iOS` SwiftUI app consumes
`http://malachi.local:8080/stream.mjpg`. This is video only: no audio, recording,
remote control, or Internet relay. Streaming is disabled by default.

## Pi setup

Use this streaming change on top of `raspberry-pi5`. Keep your existing `.env`
and installation; see [Raspberry Pi setup](raspberry-pi.md) for first-time setup.
In `.env`, add or update these settings (avoid duplicate keys):

```dotenv
CAMERA_STREAM_ENABLED=true
CAMERA_STREAM_HOST=0.0.0.0
CAMERA_STREAM_PORT=8080
CAMERA_STREAM_FPS=10
```

Stop the existing MALACHI process, then restart **that same application**:

```bash
bash scripts/run_raspberry_pi.sh
# Or, when intentionally running without the dashboard:
# bash scripts/run_raspberry_pi.sh --headless
```

Do not launch another camera process, standalone capture server, or a second MALACHI
instance. `CameraService` remains the sole capture owner (CSI or USB). A separate
worker copies the latest fresh frame under its lock, then downsizes and JPEG-encodes
outside the lock, once per streaming interval. All clients share that encoded frame;
slow clients cannot build an unbounded frame queue. Dashboard, face detection,
scene snapshots and conversations continue using the existing camera pipeline.
No new Python dependencies are needed.

The endpoint serves multipart JPEG at up to 10 fps by default, maximum 640px width,
quality 75. Four simultaneous viewers are permitted. A stopped, failed or stale
camera ends streams; the phone clears its image and retries. Starting/stopping the
camera in the dashboard also starts/stops the server. An occupied stream port
causes a startup error: choose a free port in `.env` and in the phone's settings.

## Local network

The phone and Pi must be on the same trusted LAN/Wi-Fi with client isolation off.
`malachi.local` requires the Pi hostname `malachi` and working mDNS/Avahi. Check:

```bash
hostname
systemctl status avahi-daemon
hostname -I
```

If needed, configure the hostname through Raspberry Pi Configuration / raspi-config,
then reboot. Alternatively, enter the Pi's IPv4 address in the app. Allow TCP 8080
from your local subnet if a Pi firewall is enabled. Do not port-forward this endpoint.
It is plain HTTP and unauthenticated: anyone who can reach it can view the camera.
Disable streaming when unwanted, or bind `CAMERA_STREAM_HOST` to the Pi's specific
LAN address to limit interfaces. This first version is for a trusted LAN only.

With MALACHI running and the camera started, from a Mac on that LAN:

```bash
curl -v --max-time 3 http://malachi.local:8080/stream.mjpg -o /tmp/malachi-stream.mjpg
```

Expect HTTP 200, `multipart/x-mixed-replace; boundary=malachi`, and JPEG data.
Curl exit 28 after three seconds is expected for this never-ending response.
A browser may also render the MJPEG URL. A 200 header alone does not prove frames
are arriving: the saved file should contain repeated `Content-Length` parts.

## Troubleshooting

- No hostname resolution: use the IPv4 address; check Avahi and Wi-Fi isolation.
- Connection refused: confirm MALACHI is running, camera started, streaming enabled,
  port matches, and restart after changing `.env`.
- iPhone permission denied: enable Local Network for MALACHI in iOS Settings.
- Retry loop / blank image: check Pi camera errors. End other capture applications;
  do not run `--check-camera` concurrently with MALACHI.
- HTTP 503: close extra viewers (limit four).
- Backgrounding the app stops its connection. Returning to the foreground reconnects
  if the user had connected; manual Disconnect stays disconnected for that session.

## Validation

On a development machine with MALACHI's dev dependencies installed:

```bash
PYTHONPATH=src pytest -q tests/test_camera_stream.py tests/test_pi_devices.py tests/test_vision.py
```

Before relying on a physical deployment, view from an iPhone while the dashboard and
face detection run, turn Wi-Fi off/on, stop/start the dashboard camera, restart the
Pi application, and confirm fresh images return. Verify there are no “camera busy”
errors. Physical CSI performance, local-network permission prompts and Xcode signing
must be checked on the actual Pi/Mac/iPhone.
