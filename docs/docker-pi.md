# Raspberry Pi 5 Docker deployment

This runs the complete camera/audio/conversation application headlessly on ARM64
Raspberry Pi OS Trixie. It uses the Pi's CSI camera and USB microphone directly,
and the host's PipeWire/PulseAudio service for Bluetooth or other speaker playback.
The host still manages Bluetooth pairing. A container does not repair camera ribbon
faults, lighting problems, or unavailable audio hardware.

The image installs camera libraries from Raspberry Pi's signed Trixie repository.
The launcher stages the host's OS-managed public keyring from
`/usr/share/keyrings/raspberrypi-archive-keyring.gpg`. This avoids the legacy
standalone key download with an obsolete SHA-1 binding. No private keys are copied.
APT signature checks remain enabled; if the host keyring is outdated too, update
`raspberrypi-archive-keyring` through the host's trusted repositories first.
Do not add `trusted=yes`, allow insecure repositories, or weaken SHA-1 policy.
Build it on the Pi. This is not an x86 desktop image. Rebuild after host camera-stack
updates if compatibility changes. Real CSI/Bluetooth operation must be checked on
your Pi; cloud tests cannot verify that hardware.

## First installation

Stop any existing MALACHI process with Ctrl+C first so only one process owns the camera.
Keep your existing `.env`, including the new ElevenLabs key, outside the image.
Install Docker from Debian's packages, then enable boot startup:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose pulseaudio-utils
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
sudo loginctl enable-linger "$USER"
systemctl --user enable --now pipewire.socket pipewire-pulse.socket wireplumber.service
```

Log out of SSH and back in for Docker group membership. Docker group membership
provides administrative access to the Pi. Lingering keeps your user audio services
available after SSH disconnects and at boot. Your speaker must reconnect through
Bluetooth for playback to work.

```bash
cd ~/Desktop/AI_Possessed_Skull
git switch raspberry-pi5
git pull origin raspberry-pi5
bash scripts/run_docker_pi.sh
```

The build can take several minutes on the first run. It downloads packages and the
base image. `restart: unless-stopped` restarts the process after a crash and starts
it after reboot. It does not restart a process that is still alive but stuck, or
restart a container you deliberately stopped. Ordinary session errors already use
the application's retry/cooldown behavior and do not necessarily exit the process.

## Check and manage

```bash
docker compose --env-file .env --env-file docker/pi-host.env -f compose.pi.yaml ps
docker compose --env-file .env --env-file docker/pi-host.env -f compose.pi.yaml logs --tail 100 -f
```

Application logs and minute snapshots persist in the host project `logs/` folder,
with the existing three-day rolling cleanup. Docker's separate stdout/stderr logs
include native camera messages and are size-limited (three 10 MB files), not age-limited.

For an explicit device check, stop the running service first, then run:

```bash
docker compose --env-file .env --env-file docker/pi-host.env -f compose.pi.yaml stop
docker compose --env-file .env --env-file docker/pi-host.env -f compose.pi.yaml run --rm malachi python -m malachi.devices --check-audio --check-camera
docker compose --env-file .env --env-file docker/pi-host.env -f compose.pi.yaml up -d
```

The container uses `USB PnP Sound Device` as input and `default` as output, overriding
the host's numeric audio IDs. To select different devices, add these to `.env` using
names from the container device check:

```dotenv
MALACHI_DOCKER_INPUT_DEVICE=USB PnP Sound Device
MALACHI_DOCKER_OUTPUT_DEVICE=default
```

Use `bash scripts/run_docker_pi.sh` again after code or `.env` changes. It rebuilds
and recreates the service as necessary. Do not run the ordinary Python launcher
at the same time.

This deployment uses privileged hardware access for CSI/libcamera compatibility.
It runs the app as your normal UID, but privileged mode grants broad device access;
use it as a dedicated Pi appliance. Secrets are runtime environment variables, not
baked into the image. Do not publish `docker compose config` output: it can include
resolved credentials. The optional ESP32 backend retains its existing safety latch.

## Repository key errors during build

If an older build reports `SHA1 is not considered secure` or `No binding signature`,
update the checkout and run the launcher again. It supplies the host keyring before
building; direct `docker compose build` requires this staging step first. If the
updated build still fails, run `sudo apt update` on the Pi and share the signature
error. An outdated host keyring requires an authenticated keyring update; it is not
a reason to bypass package signature verification.
