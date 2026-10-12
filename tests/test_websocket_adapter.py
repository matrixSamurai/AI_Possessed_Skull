import asyncio
import base64
import json
import threading
from types import SimpleNamespace
import pytest
from malachi.conversation.audio_output import PlaybackBuffer
from malachi.conversation.elevenlabs_client import ElevenLabsClient


def run_adapter(monkeypatch, settings, messages, greeting_config=None):
    import elevenlabs.client
    import malachi.diagnostics
    import websockets.asyncio.client

    monkeypatch.setattr(
        malachi.diagnostics,
        "check_agent",
        lambda settings: greeting_config
        or {"first_message_override_allowed": True, "first_message_empty": False},
    )
    stop = threading.Event()
    sent = []
    events = []
    audio = SimpleNamespace(start=lambda send: None)

    class Socket:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def send(self, data):
            sent.append(json.loads(data))

        async def recv(self):
            if messages:
                return json.dumps(messages.pop(0))
            stop.set()
            return json.dumps({"type": "unknown"})

    fake = SimpleNamespace(
        conversational_ai=SimpleNamespace(
            conversations=SimpleNamespace(
                get_signed_url=lambda **kw: SimpleNamespace(signed_url="wss://example.invalid/mock")
            )
        )
    )
    monkeypatch.setattr(elevenlabs.client, "ElevenLabs", lambda **kw: fake)
    monkeypatch.setattr(websockets.asyncio.client, "connect", lambda *a, **kw: Socket())
    settings.elevenlabs_agent_id = "test-agent"
    settings.elevenlabs_api_key = "test-only-not-a-real-key"
    buffer = PlaybackBuffer(settings)
    client = ElevenLabsClient(settings, buffer, audio, events.append)
    asyncio.run(client.run(stop))
    return buffer, events, sent


def metadata(format="pcm_16000"):
    return {
        "type": "conversation_initiation_metadata",
        "conversation_initiation_metadata_event": {
            "conversation_id": "conv_test",
            "agent_output_audio_format": format,
            "user_input_audio_format": "pcm_16000",
        },
    }


def audio(identifier):
    return {
        "type": "audio",
        "audio_event": {
            "event_id": identifier,
            "audio_base_64": base64.b64encode(b"\x01\x02" * 320).decode(),
        },
    }


def test_documented_metadata_audio_interruption_ping_goodbye(monkeypatch, settings):
    buffer, events, sent = run_adapter(
        monkeypatch,
        settings,
        [
            metadata(),
            audio(1),
            {"type": "interruption", "interruption_event": {"event_id": 2}},
            audio(1),
            audio(3),
            {"type": "ping", "ping_event": {"event_id": 7}},
            {
                "type": "user_transcript",
                "user_transcription_event": {"user_transcript": "Goodbye!"},
            },
        ],
    )
    assert buffer.samples == 320  # old audio was cleared and ignored
    assert [e.kind for e in events].count("connected") == 1
    assert any(e.kind == "goodbye" for e in events)
    assert {"type": "pong", "event_id": 7} in sent
    assert sent[0]["type"] == "conversation_initiation_client_data"
    assert "Use the attached image once received" in sent[0]["dynamic_variables"]["visual_context"]
    assert all("Goodbye" not in e.detail for e in events)


def test_reject_unsupported_audio(monkeypatch, settings):
    with pytest.raises(ValueError, match="PCM 16000"):
        run_adapter(monkeypatch, settings, [metadata("mp3_44100_128")])


def test_goodbye_is_not_substring_match(monkeypatch, settings):
    _, events, _ = run_adapter(
        monkeypatch,
        settings,
        [
            metadata(),
            {
                "type": "user_transcript",
                "user_transcription_event": {"user_transcript": "Don't say goodbye yet"},
            },
        ],
    )
    assert not any(e.kind == "goodbye" for e in events)


def test_audio_and_ping_continue_during_native_image_upload(monkeypatch, settings):
    import elevenlabs.client
    import websockets.asyncio.client
    from malachi.vision.scene_context import PreparedSnapshot

    settings.audio_playback_buffer_ms = 0
    settings.elevenlabs_agent_id = "test-agent"
    settings.elevenlabs_api_key = "test-key"
    stop = threading.Event()
    sent, events = [], []
    playback = PlaybackBuffer(settings)
    duplex = SimpleNamespace(start=lambda send: None, agent_speaking=False, user_speaking=False)

    class Uploader:
        calls = 0

        def __init__(self):
            self.release = asyncio.Event()

        async def upload(self, conversation_id, jpeg):
            self.calls += 1
            assert conversation_id == "conv_test" and jpeg == b"jpeg"
            await self.release.wait()
            return "file_test"

    class Socket:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def send(self, data):
            packet = json.loads(data)
            sent.append(packet)
            if packet.get("type") == "pong":
                assert uploader.calls == 1  # Upload pending, receive loop still live.
                assert playback.samples == 320
                playback.render(320)
                client.last_audio_received = asyncio.get_running_loop().time() - 1
                uploader.release.set()
            if packet.get("type") == "multimodal_message":
                stop.set()

        async def recv(self):
            await asyncio.sleep(0.01)
            return json.dumps(messages.pop(0) if messages else {"type": "unknown"})

    uploader = Uploader()
    fake = SimpleNamespace(
        conversational_ai=SimpleNamespace(
            conversations=SimpleNamespace(
                get_signed_url=lambda **kw: SimpleNamespace(signed_url="wss://example.invalid/mock")
            )
        )
    )
    monkeypatch.setattr(elevenlabs.client, "ElevenLabs", lambda **kw: fake)
    monkeypatch.setattr(websockets.asyncio.client, "connect", lambda *a, **kw: Socket())
    client = ElevenLabsClient(settings, playback, duplex, events.append, uploader)
    snapshot = PreparedSnapshot(b"jpeg")
    client.snapshot = snapshot
    messages = [metadata(), audio(1), {"type": "ping", "ping_event": {"event_id": 9}}]
    asyncio.run(asyncio.wait_for(client.run(stop), 2))
    assert uploader.calls == 1 and snapshot.jpeg is None
    assert any(p.get("type") == "multimodal_message" for p in sent)
    assert any(e.kind == "connected" for e in events)
    assert any(e.kind == "scene" and "sent" in e.detail for e in events)


def test_image_greeting_suppresses_configured_first_message(monkeypatch, settings):
    settings.vision_context_enabled = True
    settings.vision_greeting_enabled = True
    _, _, sent = run_adapter(monkeypatch, settings, [metadata()])
    assert sent[0]["conversation_config_override"] == {"agent": {"first_message": ""}}


@pytest.mark.parametrize("empty", [False, True])
def test_no_unpermitted_override_is_sent(monkeypatch, settings, empty):
    settings.vision_context_enabled = True
    settings.vision_greeting_enabled = True
    _, events, sent = run_adapter(
        monkeypatch,
        settings,
        [metadata()],
        greeting_config={"first_message_override_allowed": False, "first_message_empty": empty},
    )
    assert "conversation_config_override" not in sent[0]
    assert any(event.kind == "connected" for event in events)
    if not empty:
        assert any("Visual greeting disabled" in event.detail for event in events)
