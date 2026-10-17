#!/usr/bin/env bash
# Run as your desktop user. Only apt operations use sudo; never pip into system Python.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -m)" != aarch64 ]] || ! grep -q 'Raspberry Pi' /proc/device-tree/model 2>/dev/null; then
    echo 'This installer requires a Raspberry Pi running 64-bit Raspberry Pi OS.' >&2
    exit 1
fi
if [[ "$EUID" == 0 ]]; then
    echo 'Run this script as your normal desktop user, not with sudo.' >&2
    exit 1
fi
python3 -c 'import sys; print("Python:",sys.version.split()[0]); assert (3,11) <= sys.version_info[:2] < (3,14), "Use Raspberry Pi OS with Python 3.11-3.13"'
cat /etc/os-release
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-numpy python3-opencv \
    opencv-data python3-picamera2 python3-libcamera libportaudio2 libsndfile1 libxcb-cursor0 alsa-utils
use_system_qt=false
if apt-cache show python3-pyside6.qtwidgets >/dev/null 2>&1; then
    sudo apt-get install -y python3-pyside6.qtwidgets qt6-wayland
    use_system_qt=true
fi
if [[ -f .venv/pyvenv.cfg ]] && ! grep -q 'include-system-site-packages = true' .venv/pyvenv.cfg; then
    echo 'Existing .venv cannot see Pi camera packages. Rename it, then rerun this script.' >&2
    exit 1
fi
python3 -m venv --system-site-packages .venv
if [[ "$use_system_qt" == false ]]; then
    .venv/bin/python -m pip install --only-binary=:all: 'PySide6==6.8.3' || {
        echo 'No compatible Qt wheel. Use current Raspberry Pi OS 64-bit (Trixie) with packaged PySide6.' >&2
        exit 1
    }
fi
# On ARM, OpenCV/Qt/libcamera/NumPy are supplied by OS packages. Do not replace
# their ABI-linked packages with the desktop OpenCV/MediaPipe wheels.
.venv/bin/python -m pip install -e '.[conversation]'
.venv/bin/python -c 'import cv2,numpy,libcamera,picamera2,sounddevice; from PySide6.QtWidgets import QApplication; print("Pi camera, audio and GUI imports OK")'
if [[ ! -f .env ]]; then
    cp .env.raspberry-pi.example .env
    chmod 600 .env
    echo 'Created .env from the Pi template. Set your existing ElevenLabs key and agent ID locally.'
else
    echo 'Preserved existing .env. Compare its camera/audio options with .env.raspberry-pi.example.'
fi
.venv/bin/python -m malachi.devices
printf '\nSetup complete. From the Pi desktop, run: bash scripts/run_raspberry_pi.sh\n'
