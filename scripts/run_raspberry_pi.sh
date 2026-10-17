#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
    echo 'Run bash scripts/setup_raspberry_pi.sh first.' >&2
    exit 1
fi
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo 'The animated dashboard needs a Pi desktop display. Launch from its desktop terminal or use a remote desktop.' >&2
    exit 1
fi
# Remove inherited headless/foreign Qt paths, keeping the Pi desktop's platform selection.
exec env -u QT_QPA_PLATFORM -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH .venv/bin/python -X faulthandler -m malachi.main "$@"
