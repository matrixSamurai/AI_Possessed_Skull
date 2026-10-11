import asyncio
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
import cv2
import numpy as np
import pytest
from malachi.vision.scene_context import ElevenLabsImageUploader, PreparedSnapshot, encode_snapshot
from malachi.vision.camera import CameraService
from malachi.conversation.conversation_manager import ConversationManager
from malachi.conversation.elevenlabs_client import ElevenLabsClient
from malachi.conversation.audio_output import PlaybackBuffer


@pytest.fixture
def enabled(settings):
    settings.conversation_backend = "elevenlabs"
    settings.vision_context_enabled = True
    settings.elevenlabs_api_key = "test-elevenlabs-key-not-real"
    return settings


def test_official_elevenlabs_sdk_multipart_upload_and_resize(enabled):
    import httpx

    requests = []
    jpeg = encode_snapshot(np.zeros((1080, 1920, 3), np.uint8), 640)

    def handle(request):
        requests.append(request)
        assert request.url.host == "api.elevenlabs.io"
        assert request.url.path == "/v1/convai/conversations/conv_test/files"
        assert request.headers["xi-api-key"] == "test-elevenlabs-key-not-real"
        assert request.headers["content-type"].startswith("multipart/form-data;")
        assert b'filename="interaction.jpg"' in request.content
        assert b"Content-Type: image/jpeg" in request.content
        assert jpeg in request.content
        return httpx.Response(200, json={"file_id": "file_test"})

    uploader = ElevenLabsImageUploader(
        enabled, lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handle), **kw)
    )
    assert asyncio.run(uploader.upload("conv_test", jpeg)) == "file_test"
    assert len(requests) == 1
    decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[:2] == (360, 640)


def test_upload_errors_do_not_retry(enabled):
    import httpx

    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(429, json={"detail": "test rate limit"})

    uploader = ElevenLabsImageUploader(
        enabled, lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handle), **kw)
    )
    with pytest.raises(Exception):
        asyncio.run(uploader.upload("conv_test", b"test-jpeg"))
    assert len(calls) == 1


def test_invalid_image_is_not_uploaded():
    with pytest.raises(ValueError):
        encode_snapshot(np.zeros((40, 40), np.uint8), 640)


def test_snapshot_rejects_stale_stopped_and_demo_images(settings):
    camera = CameraService(settings)
    camera.frame = np.zeros((40, 40, 3), np.uint8)
    camera.updated = time.monotonic()
    camera.error = ""
    snapshot = camera.interaction_snapshot()
    assert snapshot is not camera.frame
    snapshot[:] = 1
    assert not camera.frame.any()
    camera.updated = time.monotonic() - 1
    assert camera.interaction_snapshot() is None
    camera.updated = time.monotonic()
    camera.stop_event.set()
    assert camera.interaction_snapshot() is None
    camera.stop_event.clear()
    camera.demo = True
    assert camera.interaction_snapshot() is None


def test_one_snapshot_is_reused_before_voice_connection_and_released(enabled):
    class Voice:
        snapshots = []

        def __init__(self, *a):
            pass

        async def run(self, stop):
            Voice.snapshots.append(self.snapshot)
            if len(Voice.snapshots) == 1:
                raise OSError("network test")
            assert self.snapshot.take().startswith(b"\xff\xd8")

    manager = ConversationManager(enabled, Voice)
    with patch("malachi.vision.scene_context.encode_snapshot", wraps=encode_snapshot) as encoder:
        asyncio.run(manager._live(np.zeros((20, 20, 3), np.uint8)))
    assert encoder.call_count == 1
    assert len(Voice.snapshots) == 2 and Voice.snapshots[0] is Voice.snapshots[1]
    assert Voice.snapshots[0].take() is None


def make_client(settings, uploader):
    return ElevenLabsClient(
        settings,
        PlaybackBuffer(settings),
        SimpleNamespace(agent_speaking=False, user_speaking=False),
        lambda e: None,
        uploader,
    )


def test_multimodal_delivery_is_official_payload_and_one_shot(enabled):
    import json
    from elevenlabs.conversational_ai.conversation import MultimodalMessageClientToOrchestratorEvent
    from malachi.vision.scene_context import PHOTO_INSTRUCTIONS

    class Uploader:
        calls = 0

        async def upload(self, conversation_id, jpeg):
            self.calls += 1
            assert conversation_id == "conv_test" and jpeg == b"jpeg"
            return "file_test"

    class Socket:
        sent = []

        async def send(self, message):
            self.sent.append(json.loads(message))

    uploader, socket = Uploader(), Socket()
    client = make_client(enabled, uploader)
    snapshot = PreparedSnapshot(b"jpeg")
    client.snapshot = snapshot
    asyncio.run(client._deliver_snapshot(socket, "conv_test", threading.Event()))
    assert uploader.calls == 1 and snapshot.jpeg is None
    assert socket.sent == [
        MultimodalMessageClientToOrchestratorEvent(
            text=PHOTO_INSTRUCTIONS, file_ids=["file_test"]
        ).to_dict()
    ]
    assert socket.sent[0]["type"] == "multimodal_message"
    asyncio.run(client._deliver_snapshot(socket, "conv_test", threading.Event()))
    assert uploader.calls == 1 and len(socket.sent) == 1


def test_photo_waits_for_speech_pause(enabled):
    class Uploader:
        async def upload(self, *a):
            return "file_test"

    class Socket:
        sent = []

        async def send(self, message):
            self.sent.append(message)

    client = make_client(enabled, Uploader())
    client.snapshot = PreparedSnapshot(b"jpeg")
    client.audio.agent_speaking = True
    socket = Socket()

    async def scenario():
        task = asyncio.create_task(client._deliver_snapshot(socket, "conv_test", threading.Event()))
        await asyncio.sleep(0.01)
        assert not socket.sent
        client.audio.agent_speaking = False
        await asyncio.wait_for(task, 1)

    asyncio.run(scenario())
    assert len(socket.sent) == 1


@pytest.mark.parametrize("mode", ["failure", "timeout", "no_pause"])
def test_optional_image_failure_never_ends_voice(enabled, mode):
    enabled.vision_context_timeout_seconds = 0.02
    enabled.vision_context_delivery_wait_seconds = 0.02

    class Uploader:
        async def upload(self, *a):
            if mode == "failure":
                raise RuntimeError("private provider test-key body")
            if mode == "timeout":
                await asyncio.sleep(10)
            return "file_test"

    class Socket:
        sent = []

        async def send(self, message):
            self.sent.append(message)

    events = []
    client = make_client(enabled, Uploader())
    client.emit = events.append
    client.audio.user_speaking = mode == "no_pause"
    client.snapshot = PreparedSnapshot(b"jpeg")
    socket = Socket()
    asyncio.run(client._deliver_snapshot(socket, "conv_test", threading.Event()))
    assert not socket.sent
    assert events and all(e.kind == "scene" for e in events)
    assert all("test-key" not in e.detail for e in events)


def test_cancel_during_upload_releases_snapshot_and_never_delivers(enabled):
    class Slow:
        cancelled = False

        async def upload(self, *a):
            try:
                await asyncio.sleep(10)
            finally:
                self.cancelled = True

    class Socket:
        async def send(self, *a):
            raise AssertionError("No late image delivery")

    slow = Slow()
    client = make_client(enabled, slow)
    snapshot = PreparedSnapshot(b"jpeg")
    client.snapshot = snapshot

    async def scenario():
        task = asyncio.create_task(
            client._deliver_snapshot(Socket(), "conv_test", threading.Event())
        )
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
    assert slow.cancelled and snapshot.jpeg is None


@pytest.mark.parametrize("mode", ["disabled", "missing_frame", "invalid_frame"])
def test_snapshot_preparation_skips_safely(enabled, mode):
    if mode == "disabled":
        enabled.vision_context_enabled = False
    frame = None if mode == "missing_frame" else np.zeros((10, 10), np.uint8)
    manager = ConversationManager(enabled)
    assert manager._prepare_snapshot(frame) is None
    assert manager.failures == 0


def test_mock_demo_does_not_upload_even_if_configured(enabled):
    enabled.conversation_backend = "mock"
    manager = ConversationManager(enabled)
    with patch.object(
        manager, "_prepare_snapshot", side_effect=AssertionError("No offline upload")
    ):
        assert manager.start(np.zeros((20, 20, 3), np.uint8))
        manager.events.get(timeout=2)
        manager.shutdown()
    assert not manager.thread.is_alive()


def test_openai_key_is_not_required_or_used(enabled):
    assert "openai_api_key" not in type(enabled).model_fields
    snapshot = ConversationManager(enabled)._prepare_snapshot(np.zeros((20, 20, 3), np.uint8))
    assert snapshot is not None and snapshot.take().startswith(b"\xff\xd8")
