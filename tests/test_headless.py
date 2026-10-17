"""The SSH entrypoint must work without importing any graphical toolkit."""

import os
from pathlib import Path
import subprocess
import sys


def test_headless_demo_without_qt():
    script = """
import builtins
original = builtins.__import__
def no_qt(name, *args, **kwargs):
    if name.startswith("PySide6"):
        raise AssertionError("Headless mode imported Qt")
    return original(name, *args, **kwargs)
builtins.__import__ = no_qt
from malachi.main import main
raise SystemExit(main())
"""
    env = dict(os.environ)
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    env["FACE_FACING_HOLD_SECONDS"] = "0.1"
    result = subprocess.run(
        [sys.executable, "-c", script, "--headless", "--demo", "--smoke-seconds", "2"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "State.CONVERSING" in result.stderr
    assert "Headless mode" in result.stderr
