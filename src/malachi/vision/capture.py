"""Camera backends return unannotated uint8 BGR frames."""

import cv2
from malachi.platform import is_raspberry_pi


class OpenCVCapture:
    def __init__(self, settings):
        self.camera = cv2.VideoCapture(settings.camera_index)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, settings.camera_width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_height)
        self.camera.set(cv2.CAP_PROP_FPS, settings.camera_fps)
        if not self.camera.isOpened():
            self.camera.release()
            raise RuntimeError("Cannot open USB/OpenCV camera; check CAMERA_INDEX")

    def read(self):
        return self.camera.read()

    def release(self):
        self.camera.release()


class PiCameraCapture:
    def __init__(self, settings):
        from picamera2 import Picamera2

        self.camera = Picamera2(camera_num=settings.camera_index)
        try:
            # libcamera's packed RGB888 is byte-ordered B,G,R on the Pi; this
            # matches OpenCV. BGR888 would swap red and blue in scene uploads.
            config = self.camera.create_video_configuration(
                main={"size": (settings.camera_width, settings.camera_height), "format": "RGB888"},
                controls={"FrameRate": settings.camera_fps},
                buffer_count=4,
            )
            self.camera.configure(config)
            if "AfMode" in getattr(self.camera, "camera_controls", {}):
                from libcamera import controls

                self.camera.set_controls({"AfMode": controls.AfModeEnum.Continuous})
            self.camera.start()
        except Exception:
            self.camera.close()
            raise

    def read(self):
        frame = self.camera.capture_array("main")
        return frame is not None and frame.size > 0, frame

    def release(self):
        try:
            self.camera.stop()
        finally:
            self.camera.close()


def open_capture(settings):
    backend = settings.camera_backend
    if backend == "auto":
        # Pi defaults to its CSI camera. USB users explicitly choose opencv;
        # never silently replace a failed ribbon camera with another device.
        backend = "picamera2" if is_raspberry_pi() else "opencv"
    return PiCameraCapture(settings) if backend == "picamera2" else OpenCVCapture(settings)
