"""Local device checks. No network, API credentials, recordings or image files."""

import argparse
import platform
from malachi.config import Settings
from malachi.conversation.device_audio import stream_options
from malachi.platform import is_raspberry_pi


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-audio", action="store_true", help="Check input/output formats")
    parser.add_argument(
        "--check-camera", action="store_true", help="Capture one frame, without saving it"
    )
    parser.add_argument(
        "--test-speaker", action="store_true", help="Play a quiet one-second test tone"
    )
    parser.add_argument(
        "--test-microphone",
        action="store_true",
        help="Measure two seconds of microphone input; do not save audio",
    )
    args = parser.parse_args()
    settings = Settings()
    print(
        f"Python {platform.python_version()} / {platform.machine()} / Raspberry Pi: {is_raspberry_pi()}"
    )
    print(
        f"Camera backend: {settings.camera_backend}; index: {settings.camera_index}; face backend: {settings.face_backend}"
    )
    failed = False
    try:
        import sounddevice as sd

        print(sd.query_devices())
        if args.check_audio or args.test_speaker or args.test_microphone:
            options = {kind: stream_options(sd, settings, kind) for kind in ("input", "output")}
            for kind, value in options.items():
                print(
                    f"{kind}: {value['samplerate']} Hz / {value['channels']} channel(s) / device {value['device']!r}"
                )
            if args.test_speaker:
                import numpy as np

                output = options["output"]
                t = np.arange(output["samplerate"]) / output["samplerate"]
                tone = (
                    0.08
                    * np.sin(2 * np.pi * 330 * t)
                    * np.minimum(1, t * 20)
                    * np.minimum(1, (1 - t) * 20)
                ).astype("float32")
                sd.play(
                    np.repeat(tone[:, None], output["channels"], axis=1),
                    samplerate=output["samplerate"],
                    device=output["device"],
                    blocking=True,
                )
                print("Speaker tone completed; verify it was audible on your selected speaker.")
            if args.test_microphone:
                import numpy as np

                mic = options["input"]
                samples = sd.rec(
                    mic["samplerate"] * 2,
                    samplerate=mic["samplerate"],
                    channels=mic["channels"],
                    dtype="float32",
                    device=mic["device"],
                    blocking=True,
                )
                print(
                    f"Microphone captured 2s; RMS={float(np.sqrt(np.mean(samples**2))):.4f}; no recording saved."
                )
    except Exception as exc:
        failed = True
        print(f"Audio check failed: {type(exc).__name__}: {exc}")
    if args.check_camera:
        camera = None
        try:
            from malachi.vision.capture import open_capture

            camera = open_capture(settings)
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("No frame received")
            print(
                f"Camera frame: {frame.shape[1]}x{frame.shape[0]}, {frame.dtype}; no image saved."
            )
        except Exception as exc:
            failed = True
            print(f"Camera check failed: {type(exc).__name__}: {exc}")
        finally:
            if camera is not None:
                camera.release()
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
