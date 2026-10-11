import asyncio
import base64
import json
import threading
from types import SimpleNamespace
import pytest
from malachi.conversation.audio_output import PlaybackBuffer
from malachi.conversation.elevenlabs_client import ElevenLabsClient


def run_adapter(monkeypatch, settings, messages, scene=""):
    import elevenlabs.client
    import websockets.asyncio.client

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
    client.scene_context = scene
    asyncio.run(client.run(stop))
    return buffer, events, sent


def metadata(format="pcm_16000"):
    return {
        "type": "conversation_initiation_metadata",
        "conversation_initiation_metadata_event": {
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
    assert "No visual context" in sent[0]["dynamic_variables"]["visual_context"]
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


def test_scene_description_uses_context_update_not_user_message(monkeypatch, settings):
    scene = "A visitor in a red hoodie beside a bookshelf."
    _, events, sent = run_adapter(monkeypatch, settings, [metadata()], scene=scene)
    assert sent[0]["dynamic_variables"] == {"visual_context": scene}
    updates = [p for p in sent if p.get("type") == "contextual_update"]
    assert len(updates) == 1 and scene in updates[0]["text"]
    assert "untrusted visual data" in updates[0]["text"]
    assert not any(p.get("type") == "user_message" for p in sent)
    assert any(e.kind == "scene" and "sent" in e.detail for e in events)
