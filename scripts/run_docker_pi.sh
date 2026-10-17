#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -m)" != aarch64 ]]; then
    echo 'Run on your 64-bit Raspberry Pi 5.' >&2
    exit 1
fi
if [[ "$EUID" == 0 ]]; then
    echo 'Run as the normal Pi user with Docker access, not sudo.' >&2
    exit 1
fi
if [[ ! -f .env ]]; then
    echo 'Create your .env first; see .env.raspberry-pi.example.' >&2
    exit 1
fi
export MALACHI_UID="$(id -u)"
export MALACHI_GID="$(id -g)"
export MALACHI_AUDIO_GID="$(getent group audio | cut -d: -f3)"
export MALACHI_VIDEO_GID="$(getent group video | cut -d: -f3)"
export MALACHI_RENDER_GID="$(getent group render | cut -d: -f3 || true)"
MALACHI_RENDER_GID="${MALACHI_RENDER_GID:-65534}"
if [[ ! -S "/run/user/$MALACHI_UID/pulse/native" ]]; then
    echo 'Host audio service is unavailable. Start PipeWire/PulseAudio for your Pi user first.' >&2
    exit 1
fi
mkdir -p logs
chmod 700 logs
# Persist only nonsecret interpolation values for reboot and compose management.
printf 'MALACHI_UID=%s\nMALACHI_GID=%s\nMALACHI_AUDIO_GID=%s\nMALACHI_VIDEO_GID=%s\nMALACHI_RENDER_GID=%s\n' \
    "$MALACHI_UID" "$MALACHI_GID" "$MALACHI_AUDIO_GID" "$MALACHI_VIDEO_GID" "$MALACHI_RENDER_GID" > docker/pi-host.env
chmod 600 docker/pi-host.env
docker compose --env-file .env --env-file docker/pi-host.env -f compose.pi.yaml up -d --build
