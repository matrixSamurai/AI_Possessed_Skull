#!/usr/bin/env bash
set -euo pipefail
cd /workspace/AI_Possessed_Skull
export XDG_CACHE_HOME=/workspace/malachi-cache
export MPLCONFIGDIR=/workspace/malachi-cache/matplotlib
export PIP_CACHE_DIR=/workspace/malachi-cache/pip
export LD_LIBRARY_PATH="/workspace/malachi-runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
mkdir -p "$XDG_CACHE_HOME" "$MPLCONFIGDIR"
if [ ! -x /workspace/malachi-venv/bin/python ]; then
    python3 -m venv /workspace/malachi-venv
fi
/workspace/malachi-venv/bin/python -m pip install -c constraints-cloud-py312.txt -e '.[conversation,dev]'
# Cloud has no audio devices. This native library validates loading, not live audio.
if ! /workspace/malachi-venv/bin/python -c 'import sounddevice' >/dev/null 2>&1; then
    portaudio_source=$(mktemp -d /tmp/malachi-portaudio.XXXXXX)
    trap 'rm -rf "$portaudio_source"' EXIT
    git clone --quiet --depth 1 --branch v19.7.0 https://github.com/PortAudio/portaudio.git "$portaudio_source"
    test "$(git -C "$portaudio_source" rev-parse HEAD)" = 147dd722548358763a8b649b3e4b41dfffbcfbb6
    (
        cd "$portaudio_source"
        ./configure --prefix=/workspace/malachi-runtime --without-alsa --without-jack
        make -j2
        make install
    )
fi
/workspace/malachi-venv/bin/python -c 'import sounddevice; print(sounddevice.get_portaudio_version())'
/workspace/malachi-venv/bin/python -m pip check
QT_QPA_PLATFORM=offscreen /workspace/malachi-venv/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen /workspace/malachi-venv/bin/malachi --demo --smoke-seconds 2
if [ "${1:-}" = --with-model ]; then
    /workspace/malachi-venv/bin/python scripts/download_model.py
fi
