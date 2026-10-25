"""Hardware detection without importing optional Pi libraries on other computers."""

from pathlib import Path


def is_raspberry_pi():
    try:
        return b"Raspberry Pi" in Path("/proc/device-tree/model").read_bytes()
    except OSError:
        return False
