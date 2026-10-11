import asyncio
import base64
import json
import time
import cv2
import numpy as np
import pytest
from malachi.vision.scene_context import SceneAnalyzer, encode_snapshot
from malachi.vision.camera import CameraService
from malachi.conversation.conversation_manager import ConversationManager


@pytest.fixture
def enabled(settings):
    settings.conversation_backend = "elevenlabs"
    settings.vision_context_enabled = True
    settings.openai_api_key = "test-vision-key-not-real"
    return settings


def test_official_openai_sdk_request_and_resize(enabled):
    import httpx2
    from openai import AsyncOpenAI

    requests = []

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        assert request.url.path == "/v1/responses"
        return httpx2.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "model": "gpt-4.1-mini",
                "status": "completed",
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "One visitor near a bookshelf.",
                                "annotations": [],
                            }
                        ],
                    }
                ],
            },
        )

    def factory(**kwargs):
        assert kwargs["max_retries"] == 0
        return AsyncOpenAI(
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handle)), **kwargs
        )

    analyzer = SceneAnalyzer(enabled, factory)
    result = asyncio.run(analyzer.analyze(np.zeros((1080, 1920, 3), np.uint8)))
    assert result == "One visitor near a bookshelf."
    assert len(requests) == 1 and requests[0]["store"] is False
    content = requests[0]["input"][0]["content"]
    image = next(p for p in content if p["type"] == "input_image")
    raw = base64.b64decode(image["image_url"].split(",", 1)[1])
    decoded = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[:2] == (360, 640) and image["detail"] == "low"
    assert requests[0]["max_output_tokens"] == 250


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


def test_analysis_occurs_once_and_is_reused_across_connection_retries(enabled):
    class Analyzer:
        calls = 0

        def __init__(self, settings):
            pass

        async def analyze(self, frame):
            Analyzer.calls += 1
            return "A visitor in a red hoodie."

    class Voice:
        scenes = []

        def __init__(self, *a):
            pass

        async def run(self, stop):
            Voice.scenes.append(self.scene_context)
            if len(Voice.scenes) == 1:
                raise OSError("network test")

    manager = ConversationManager(enabled, Voice, Analyzer)
    asyncio.run(manager._live(np.zeros((20, 20, 3), np.uint8)))
    assert Analyzer.calls == 1 and Voice.scenes == ["A visitor in a red hoodie."] * 2
    assert manager.failures == 1
    assert all("red hoodie" not in e.detail for e in list(manager.events.queue))


def test_timeout_cancels_analysis_and_still_starts_voice(enabled):
    enabled.vision_context_timeout_seconds = 0.02

    class Slow:
        cancelled = False

        def __init__(self, *a):
            pass

        async def analyze(self, frame):
            try:
                await asyncio.sleep(10)
            finally:
                Slow.cancelled = True

    class Voice:
        called = False

        def __init__(self, *a):
            pass

        async def run(self, stop):
            Voice.called = True
            assert not getattr(self, "scene_context", "")

    manager = ConversationManager(enabled, Voice, Slow)
    asyncio.run(manager._live(np.zeros((20, 20, 3), np.uint8)))
    assert Slow.cancelled and Voice.called
    assert any("Timed out" in e.detail for e in list(manager.events.queue))
    assert manager.failures == 0


def test_stop_cancels_image_request_and_never_connects_voice(enabled):
    class Slow:
        cancelled = False

        def __init__(self, *a):
            pass

        async def analyze(self, frame):
            try:
                await asyncio.sleep(10)
            finally:
                Slow.cancelled = True

    class Voice:
        def __init__(self, *a):
            raise AssertionError("Voice must not start after stop")

    manager = ConversationManager(enabled, Voice, Slow)

    async def scenario():
        request = asyncio.create_task(manager._live(np.zeros((20, 20, 3), np.uint8)))
        await asyncio.sleep(0.01)
        manager.end()
        await asyncio.wait_for(request, 1)

    asyncio.run(scenario())
    assert Slow.cancelled


@pytest.mark.parametrize("mode", ["disabled", "missing_key", "missing_frame", "failure"])
def test_analysis_skips_fail_safely(enabled, mode):
    if mode == "disabled":
        enabled.vision_context_enabled = False
    if mode == "missing_key":
        enabled.openai_api_key = ""

    class Broken:
        calls = 0

        def __init__(self, *a):
            pass

        async def analyze(self, frame):
            Broken.calls += 1
            raise RuntimeError("private provider error with secret-test-key")

    manager = ConversationManager(enabled, scene_factory=Broken)
    frame = None if mode == "missing_frame" else np.zeros((20, 20, 3), np.uint8)
    assert asyncio.run(manager._prepare_scene(frame)) == ""
    assert Broken.calls == (1 if mode == "failure" else 0)
    assert all("secret-test-key" not in e.detail for e in list(manager.events.queue))


def test_mock_demo_does_not_upload_even_if_configured(enabled):
    enabled.conversation_backend = "mock"

    class Forbidden:
        def __init__(self, *a):
            raise AssertionError("Offline mode must never upload")

    manager = ConversationManager(enabled, scene_factory=Forbidden)
    assert manager.start(np.zeros((20, 20, 3), np.uint8))
    manager.events.get(timeout=2)
    manager.shutdown()
    assert not manager.thread.is_alive()


def test_openai_secret_is_redacted(enabled):
    assert "test-vision-key-not-real" not in repr(enabled)
