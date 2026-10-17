import http.client
import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from malachi.vision.stream import CameraStream
from malachi.vision.camera import CameraService


def connect(stream):
    client = http.client.HTTPConnection("127.0.0.1", stream.server.server_port, timeout=3)
    client.request("GET", "/stream.mjpg")
    return client, client.getresponse()


def read_frame(response):
    assert response.readline() == b"--malachi\r\n"
    assert response.readline() == b"Content-Type: image/jpeg\r\n"
    size = int(response.readline().split(b":")[1])
    assert response.readline() == b"\r\n"
    jpeg = response.read(size)
    assert response.read(2) == b"\r\n"
    return cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)


def test_multiple_viewers_share_snapshot_and_stale_camera_ends_stream(monkeypatch):
    # Any attempt to open a second capture is a test failure.
    monkeypatch.setattr(cv2, "VideoCapture", lambda *a: pytest.fail("opened another camera"))
    camera = SimpleNamespace(
        lock=threading.Lock(),
        frame=np.full((720, 1280, 3), 127, np.uint8),
        error="",
        updated=time.monotonic(),
        stop_event=threading.Event(),
    )
    stream = CameraStream(camera, "127.0.0.1", 0, fps=20)
    stream.start()
    clients = []
    try:
        for _ in range(2):
            client, response = connect(stream)
            clients.append(client)
            assert response.status == 200
            image = read_frame(response)
            assert image.shape == (360, 640, 3)
            assert abs(float(image.mean()) - 127) < 2
        with camera.lock:
            camera.error = "camera disconnected"
            camera.updated = 0
        # The producer invalidates the last frame; connections terminate rather than freeze.
        deadline = time.monotonic() + 2
        while stream.jpeg is not None and time.monotonic() < deadline:
            time.sleep(0.01)
        client, response = connect(stream)
        clients.append(client)
        assert response.read() == b""
    finally:
        for client in clients:
            client.close()
        stream.stop()
    assert not stream.producer.is_alive()
    assert not stream.http_thread.is_alive()


def test_camera_lifecycle_demo_stream_and_restart(settings, monkeypatch):
    monkeypatch.setattr(cv2, "VideoCapture", lambda *a: pytest.fail("opened another camera"))
    settings.camera_stream_enabled = True
    settings.camera_stream_host = "127.0.0.1"
    settings.camera_stream_port = 8089
    # Avoid reserving a fixed port in tests; the real setting disallows port zero.
    from malachi.vision import stream as module

    original = module.CameraStream
    monkeypatch.setattr(module, "CameraStream", lambda c, h, p, f: original(c, h, 0, f))
    camera = CameraService(settings, demo=True)
    for _ in range(2):
        camera.start()
        try:
            deadline = time.monotonic() + 3
            while camera.stream.jpeg is None and time.monotonic() < deadline:
                time.sleep(0.01)
            client, response = connect(camera.stream)
            try:
                assert read_frame(response).shape == (480, 640, 3)
            finally:
                client.close()
        finally:
            camera.stop()
        assert camera.stream is None
        assert not camera.thread.is_alive()


def test_routes_and_viewer_limit():
    camera = SimpleNamespace(
        lock=threading.Lock(), frame=None, error="stopped", updated=0, stop_event=threading.Event()
    )
    stream = CameraStream(camera, "127.0.0.1", 0)
    stream.start()
    client = http.client.HTTPConnection("127.0.0.1", stream.server.server_port, timeout=3)
    try:
        client.request("GET", "/missing")
        response = client.getresponse()
        assert response.status == 404
        response.read()
        for _ in range(4):
            assert stream.clients.acquire(blocking=False)
        other, response = connect(stream)
        try:
            assert response.status == 503
            response.read()
        finally:
            other.close()
        for _ in range(4):
            stream.clients.release()
    finally:
        client.close()
        stream.stop()


def test_real_capture_owner_is_opened_once_for_two_viewers(settings, monkeypatch):
    import malachi.vision.capture as capture_module
    import malachi.vision.detector_factory as detector_module
    from malachi.vision import stream as stream_module

    opens = []
    releases = []

    class Capture:
        def read(self):
            return True, np.full((240, 320, 3), 90, np.uint8)

        def release(self):
            releases.append(True)

    def open_capture(_):
        opens.append(True)
        return Capture()

    monkeypatch.setattr(capture_module, "open_capture", open_capture)
    monkeypatch.setattr(
        detector_module,
        "create_detector",
        lambda _: SimpleNamespace(detect=lambda *a: [], close=lambda: None),
    )
    original = stream_module.CameraStream
    monkeypatch.setattr(stream_module, "CameraStream", lambda c, h, p, f: original(c, h, 0, f))
    settings.camera_stream_enabled = True
    settings.camera_stream_host = "127.0.0.1"
    camera = CameraService(settings)
    clients = []
    camera.start()
    try:
        deadline = time.monotonic() + 3
        while camera.stream.jpeg is None and time.monotonic() < deadline:
            time.sleep(0.01)
        for _ in range(2):
            client, response = connect(camera.stream)
            clients.append(client)
            assert read_frame(response).shape == (240, 320, 3)
        assert len(opens) == 1
        assert camera.snapshot()[0] is not None
    finally:
        for client in clients:
            client.close()
        camera.stop()
    assert len(releases) == 1
