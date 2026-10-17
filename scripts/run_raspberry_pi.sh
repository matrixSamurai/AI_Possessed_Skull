#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
    echo 'Run bash scripts/setup_raspberry_pi.sh first.' >&2
    exit 1
fi
# Without a desktop, use local camera/audio services without creating any Qt window.
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    set -- --headless "$@"
fi
# Remove inherited headless/foreign Qt paths, keeping the Pi desktop's platform selection.
exec env -u QT_QPA_PLATFORM -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH .venv/bin/python -X faulthandler -m malachi.main "$@"
