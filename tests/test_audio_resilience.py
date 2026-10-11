import threading
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from malachi.conversation.audio_output import PlaybackBuffer
from malachi.conversation.audio_input import AudioDuplex


def pcm(count, value=8000):
    return np.full(count, value, dtype="<i2").tobytes()


def test_jitter_buffer_preserves_every_sample_without_midstream_gaps(settings):
    now = [0.0]
    buffer = PlaybackBuffer(settings, clock=lambda: now[0])
    schedule = {0: 960, 2: 640, 4: 1280, 7: 640, 12: 960}
    heard = []
    started = False
    for tick in range(25):
        now[0] = tick * 0.02
        if tick in schedule:
            buffer.push(pcm(schedule[tick]))
        output, jaw, _ = buffer.render(320)
        if output.any():
            started = True
            heard.extend(output[output != 0])
        elif started and len(heard) < sum(schedule.values()):
            raise AssertionError("Gap within jitter-buffered speech")
        if tick < 4:
            assert jaw == 0
    assert len(heard) == sum(schedule.values())
    np.testing.assert_array_equal(heard, np.full(sum(schedule.values()), 8000 / 32768))


def test_short_audio_tail_drains_after_bounded_wait(settings):
    now = [0.0]
    buffer = PlaybackBuffer(settings, clock=lambda: now[0])
    buffer.push(pcm(100))
    assert not buffer.render(320)[0].any()
    now[0] = 0.251
    output, _, _ = buffer.render(320)
    assert np.count_nonzero(output) == 100 and buffer.samples == 0


def test_interruption_discards_prebuffer_and_jaw_immediately(settings):
    buffer = PlaybackBuffer(settings)
    buffer.push(pcm(320))
    generation = buffer.generation
    buffer.clear(interrupted=True)
    output, jaw, new_generation = buffer.render(320)
    assert not output.any() and jaw == 0 and new_generation > generation
    assert buffer.stats()["interruptions"] == 1


def test_speaker_echo_guard_sends_silence_and_reopens_after_tail(settings):
    settings.audio_playback_buffer_ms = 0
    settings.audio_suppress_mic_during_playback = True
    buffer = PlaybackBuffer(settings)
    events = []
    duplex = AudioDuplex(buffer, events.append, lambda *args: None)
    microphone = np.full((320, 1), 9000, dtype=np.int16)
    timing = SimpleNamespace(outputBufferDacTime=1.1, currentTime=1.0)
    with patch("malachi.conversation.audio_input.time.monotonic", return_value=10):
        buffer.push(pcm(640))
        duplex._input(microphone, 320, timing, False)
        assert not np.frombuffer(duplex.queue.get(), "<i2").any()
        duplex._output(np.zeros((640, 1)), 640, timing, False)
    assert buffer.samples == 0
    with patch("malachi.conversation.audio_input.time.monotonic", return_value=10.2):
        duplex._input(microphone, 320, timing, False)
        assert not np.frombuffer(duplex.queue.get(), "<i2").any()
    with patch("malachi.conversation.audio_input.time.monotonic", return_value=10.5):
        duplex._input(microphone, 320, timing, False)
        np.testing.assert_array_equal(np.frombuffer(duplex.queue.get(), "<i2"), microphone[:, 0])
    assert any(e.kind == "user_start" for e in events)


def test_full_duplex_still_allows_user_interruptions(settings):
    settings.audio_suppress_mic_during_playback = False
    buffer = PlaybackBuffer(settings)
    duplex = AudioDuplex(buffer, lambda event: None, lambda *a: None)
    buffer.push(pcm(640))
    duplex._input(np.full((320, 1), 9000, dtype=np.int16), 320, None, False)
    assert np.frombuffer(duplex.queue.get(), "<i2").any()


def test_microphone_batching_preserves_order_and_reduces_packets(settings):
    duplex = AudioDuplex(PlaybackBuffer(settings), lambda event: None, lambda *a: None)
    sent = []
    complete = threading.Event()

    def send(packet):
        sent.append(packet)
        if len(sent) == 2:
            duplex.stop_event.set()
            complete.set()

    duplex.send = send
    blocks = [pcm(320, value=i + 1) for i in range(10)]
    for block in blocks:
        duplex.queue.put(block)
    worker = threading.Thread(target=duplex._sender)
    worker.start()
    assert complete.wait(2)
    worker.join(1)
    assert len(sent) == 2 and all(len(p) == 3200 for p in sent)
    assert b"".join(sent) == b"".join(blocks)


def test_device_underruns_are_counted_and_not_flooded(settings):
    events = []
    duplex = AudioDuplex(PlaybackBuffer(settings), events.append, lambda *a: None)
    status = SimpleNamespace(output_underflow=True)
    timing = SimpleNamespace(outputBufferDacTime=0, currentTime=0)
    for _ in range(10):
        duplex._output(np.zeros((320, 1)), 320, timing, status)
    assert duplex.output_underruns == 10
    assert len([e for e in events if e.kind == "summary"]) == 1
