from types import SimpleNamespace
from unittest.mock import patch
import time
import wave
import cv2
import numpy as np
import pytest
from malachi.ambience.engine import AmbienceEngine, read_clip
from malachi.ambience.generate import generate_clip
from malachi.ambience.service import AmbienceService
from malachi.vision.motion_detector import MotionDetector
from malachi.conversation.audio_input import AudioDuplex
from malachi.conversation.audio_output import PlaybackBuffer


@pytest.fixture
def enabled(settings, tmp_path):
    settings.ambience_enabled = True
    settings.ambience_directory = tmp_path
    return settings


def engine(settings):
    clock = [0.0]
    e = AmbienceEngine(settings, [np.full(16000, 0.5, np.float32)], seed=1, clock=lambda: clock[0])
    return e, clock


def update(
    e, now, present=False, moving=False, conversation=False, guard=True, stopped=False, muted=False
):
    e.update(present, moving, conversation, guard, stopped, muted, now)


@pytest.mark.parametrize("source", ["face", "motion"])
def test_trigger_hold_burst_deadline_and_no_repeat(enabled, source):
    e, clock = engine(enabled)
    args = {"present": source == "face", "moving": source == "motion"}
    update(e, 0, **args)
    update(e, 0.299, **args)
    assert not e.active
    update(e, 0.3, **args)
    assert e.active and e.deadline == 25.3
    clock[0] = 0.5
    assert e.render(320).any()
    update(e, 25.3, **args)
    assert not e.active
    update(e, 40, **args)
    assert not e.active  # Same stationary visitor/motion cannot loop indefinitely.


def test_quiet_rearm_and_cooldown(enabled):
    e, clock = engine(enabled)
    update(e, 0, moving=True)
    update(e, 0.3, moving=True)
    update(e, 25.3)
    update(e, 29)
    update(e, 30, moving=True)
    update(e, 30.5, moving=True)
    assert not e.active
    update(e, 35.4, moving=True)
    assert e.active


def test_conversation_overlap_with_guard_mute_and_stop(enabled):
    e, clock = engine(enabled)
    update(e, 0, present=True)
    update(e, 0.3, present=True)
    clock[0] = 1
    enabled.ambience_during_conversation = False
    update(e, 1, present=True, conversation=True)
    assert not e.render(320).any()
    enabled.ambience_during_conversation = True
    update(e, 1, present=True, conversation=True, guard=True)
    assert e.render(320).any()
    update(e, 1, present=True, conversation=True, guard=False)
    assert e.render(320).any()
    update(e, 1, muted=True)
    assert not e.render(320).any()
    update(e, 1, stopped=True)
    assert not e.active and not e.render(320).any()


def test_shuffle_bag_uses_each_clip_and_avoids_boundary_repeat(enabled):
    e = AmbienceEngine(enabled, [np.ones(500) for _ in range(4)], seed=2)
    chosen = []
    for _ in range(12):
        e._choose()
        chosen.append(e.last_clip)
    for offset in range(0, 12, 4):
        assert len(set(chosen[offset : offset + 4])) == 4
    assert all(a != b for a, b in zip(chosen, chosen[1:]))


def test_background_ducks_without_driving_agent_jaw(enabled):
    enabled.audio_playback_buffer_ms = 0
    e, clock = engine(enabled)
    update(e, 0, present=True)
    update(e, 0.3, present=True)
    clock[0] = 1
    quiet = e.render(320)
    e.position = 0
    e.duck_gain = 1
    ducked = e.render(320, foreground=True)
    assert np.max(np.abs(ducked)) < np.max(np.abs(quiet))
    playback = PlaybackBuffer(enabled)
    jaws = []
    duplex = AudioDuplex(playback, lambda event: None, lambda *a: jaws.append(a))
    duplex.ambience = SimpleNamespace(
        render=lambda *a: np.full(320, 0.1), return_output=lambda: None
    )
    data = np.zeros((320, 1), np.float32)
    duplex._output(data, 320, SimpleNamespace(currentTime=0, outputBufferDacTime=0), False)
    assert data.max() == pytest.approx(0.1) and jaws[0][0] == 0
    assert not duplex.agent_speaking


def test_motion_detects_local_change_but_rejects_global_light_change(settings):
    m = MotionDetector(settings)
    still = np.zeros((120, 160, 3), np.uint8)
    assert not m.update(still)
    assert not m.update(still)
    changed = still.copy()
    cv2.rectangle(changed, (20, 20), (60, 60), (255, 255, 255), -1)
    assert m.update(changed)
    assert not m.update(changed)
    assert not m.update(np.full_like(still, 255))


def write_wav(path, rate=16000):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(np.full(1600, 5000, dtype="<i2").tobytes())


def test_validated_local_library(enabled, tmp_path):
    write_wav(tmp_path / "good.wav")
    write_wav(tmp_path / "bad.wav", rate=22050)
    e = AmbienceEngine(enabled)
    e.load()
    assert len(e.clips) == 1
    with pytest.raises(ValueError):
        read_clip(tmp_path / "bad.wav")


def test_official_tts_generation_and_cache_without_repeated_api_calls(enabled, tmp_path):
    import httpx
    from elevenlabs.client import ElevenLabs

    requests = []

    def handle(request):
        import json

        requests.append(request)
        assert request.url.path == "/v1/text-to-speech/voice_test"
        assert request.url.params["output_format"] == "pcm_16000"
        assert json.loads(request.content)["text"] == "Who is there?"
        return httpx.Response(200, content=np.full(1600, 5000, dtype="<i2").tobytes())

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        client = ElevenLabs(api_key="test-only", httpx_client=transport)
        path, made = generate_clip(
            client, "voice_test", "Who is there?", "eleven_multilingual_v2", tmp_path
        )
        assert made and len(read_clip(path)) == 1600
        same, made = generate_clip(
            client, "voice_test", "Who is there?", "eleven_multilingual_v2", tmp_path
        )
        assert same == path and not made
    assert len(requests) == 1


def test_no_network_on_detection_and_no_clips(enabled):
    e = AmbienceEngine(enabled)
    update(e, 0, moving=True)
    update(e, 1, moving=True)
    assert not e.active and "No clips" in e.status


def test_idle_output_handover_is_exclusive_and_shutdown_clean(enabled, tmp_path):
    import sys

    write_wav(tmp_path / "clip.wav")
    streams = []

    class Stream:
        def __init__(self, **kwargs):
            self.active = False
            streams.append(self)

        def start(self):
            self.active = True

        def stop(self):
            self.active = False

        def close(self):
            self.active = False

    fake = SimpleNamespace(
        OutputStream=Stream,
        query_devices=lambda *a: {"default_samplerate": 16000, "max_output_channels": 1},
        check_output_settings=lambda **kw: None,
    )
    with patch.dict(sys.modules, {"sounddevice": fake}):
        service = AmbienceService(enabled, lambda event: None)
        deadline = time.monotonic() + 2
        while not service.engine.clips and time.monotonic() < deadline:
            time.sleep(0.005)
        update(service.engine, 0, present=True)
        update(service.engine, 0.3, present=True)
        deadline = time.monotonic() + 2
        while not streams and time.monotonic() < deadline:
            time.sleep(0.005)
        assert streams and streams[0].active
        service.release_output()
        assert not streams[0].active
        time.sleep(0.05)
        assert len(streams) == 1  # Idle output remains closed while voice owns device.
        service.return_output()
        deadline = time.monotonic() + 2
        while len(streams) < 2 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert len(streams) == 2
        service.close()
        assert not service.thread.is_alive() and not any(s.active for s in streams)


def test_background_handover_keeps_acoustic_tail_guard(enabled):
    service = object.__new__(AmbienceService)
    e, clock = engine(enabled)
    update(e, 0, present=True)
    update(e, 0.3, present=True)
    clock[0] = 1
    service.engine = e
    service.last_audible_until = 0
    from malachi.conversation.device_audio import SampleRateConverter

    service.converter = SampleRateConverter(16000, 16000)
    service.pending = np.zeros(0, np.float32)
    service.output_rate = 16000
    data = np.zeros((320, 1), np.float32)
    before = time.monotonic()
    service._callback(data, 320, SimpleNamespace(outputBufferDacTime=1.1, currentTime=1), False)
    assert data.any() and service.last_audible_until >= before + 0.419


def test_each_new_burst_uses_remaining_variations_before_repeating(enabled):
    e = AmbienceEngine(enabled, [np.ones(500) for _ in range(3)], seed=3)
    choices = []
    for _ in range(6):
        e._choose()
        choices.append(e.last_clip)
        e.stop()
    assert len(set(choices[:3])) == 3 and len(set(choices[3:])) == 3
    assert all(a != b for a, b in zip(choices, choices[1:]))


def test_conversation_is_thirty_percent_even_between_replies(enabled):
    e, clock = engine(enabled)
    e.clips = [np.full(16000 * 5, 0.5, np.float32)]
    update(e, 0, present=True)
    update(e, 0.3, present=True)
    clock[0] = 1
    e.position = 200
    e.current = e.clips[0]
    normal = e.render(320)[-1]
    update(e, 1, present=True, conversation=True)
    for _ in range(30):
        e.render(320)
    reduced = e.render(320)[-1]
    assert reduced == pytest.approx(normal * 0.3, rel=0.001)
    # Continue past the original 25-second burst until the conversation ends.
    clock[0] = 60
    update(e, 60, present=True, conversation=True)
    assert e.active and e.render(320).any()
    update(e, 61, present=True, conversation=False)
    clock[0] = 61
    for _ in range(30):
        e.render(320)
    assert e.render(320)[-1] == pytest.approx(normal, rel=0.001)
    update(e, 86, present=True)
    assert not e.active


def test_background_does_not_permanently_mute_microphone(enabled):
    playback = PlaybackBuffer(enabled)
    duplex = AudioDuplex(playback, lambda e: None, lambda *args: None)
    duplex.ambience = SimpleNamespace(render=lambda *a: np.full(320, 0.1))
    data = np.zeros((320, 1), np.float32)
    timing = SimpleNamespace(currentTime=0, outputBufferDacTime=0)
    duplex._output(data, 320, timing, False)
    assert data.any() and duplex.speaker_guard_until == 0
    duplex._input(np.full((320, 1), 3000, np.int16), 320, timing, False)
    assert any(duplex.queue.get_nowait()) and duplex.user_speaking
    playback.settings.audio_playback_buffer_ms = 0
    playback.push(np.full(320, 3000, dtype="<i2").tobytes())
    duplex._output(data, 320, timing, False)
    assert duplex.speaker_guard_until > time.monotonic()
