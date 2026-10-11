"""Portable firmware logic, compiled with upstream MIT cJSON v1.7.18."""

import ctypes
from pathlib import Path
import shutil
import subprocess
import pytest


class Motion(ctypes.Structure):
    _fields_ = [
        (n, ctypes.c_float)
        for n in [
            "x",
            "y",
            "jaw",
            "pan",
            "tilt",
            "target_x",
            "target_y",
            "target_jaw",
            "target_pan",
            "target_tilt",
        ]
    ] + [("stopped", ctypes.c_bool)]


@pytest.fixture(scope="module")
def firmware(tmp_path_factory):
    compiler = shutil.which("cc")
    if not compiler:
        pytest.skip("C compiler required for optional portable firmware validation")
    root = Path(__file__).resolve().parents[1]
    source = root / "firmware/esp32_skull/main"
    cjson = root / "tests/vendor/cjson"
    output = tmp_path_factory.mktemp("firmware") / "motion.so"
    subprocess.run(
        [
            compiler,
            "-shared",
            "-fPIC",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(source),
            "-I",
            str(cjson),
            str(source / "motion.c"),
            str(source / "protocol.c"),
            str(cjson / "cJSON.c"),
            "-lm",
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    library = ctypes.CDLL(str(output))
    library.motion_init.argtypes = [ctypes.POINTER(Motion)]
    library.motion_step.argtypes = [ctypes.POINTER(Motion), ctypes.c_float]
    library.motion_stop.argtypes = [ctypes.POINTER(Motion)]
    library.protocol_apply.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(Motion),
        ctypes.POINTER(ctypes.c_int),
    ]
    library.protocol_apply.restype = ctypes.c_bool
    return library


def test_firmware_parser_limits_stop_and_interpolation(firmware):
    state = Motion()
    firmware.motion_init(ctypes.byref(state))
    seq = ctypes.c_int()

    def apply(packet):
        return firmware.protocol_apply(packet, ctypes.byref(state), ctypes.byref(seq))

    assert state.stopped
    assert not apply(b'{"v":1,"type":"EYES","seq":1,"x":0.5,"y":0}')
    assert apply(b'{"v":1,"type":"RESET","seq":2}')
    assert apply(b'{"v":1,"type":"EYES","seq":3,"x":0.5,"y":-0.3}')
    assert seq.value == 3
    firmware.motion_step(ctypes.byref(state), 0.02)
    assert 0 < state.x <= 0.041 and -0.041 <= state.y < 0
    assert not apply(b'{"v":1,"type":"JAW","seq":4,"open":1.5}')
    assert apply(b'{"v":1,"type":"STOP","seq":5}')
    firmware.motion_step(ctypes.byref(state), 0.02)
    assert state.stopped and state.x == 0 and state.jaw == 0


@pytest.mark.parametrize(
    "packet",
    [
        b"not json",
        b'{"v":2,"seq":1,"type":"PING"}',
        b'{"v":1,"seq":1,"type":"RESET","pwm":1000}',
        b'{"v":1,"seq":1,"type":"RESET","type":"STOP"}',
        b'{"v":1,"seq":1.5,"type":"PING"}',
        b'{"v":1,"seq":1,"type":"PING"} trailing',
    ],
)
def test_firmware_rejects_invalid_commands(firmware, packet):
    state = Motion()
    firmware.motion_init(ctypes.byref(state))
    seq = ctypes.c_int()
    assert not firmware.protocol_apply(packet, ctypes.byref(state), ctypes.byref(seq))
    assert state.stopped
