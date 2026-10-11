from types import SimpleNamespace
import time
import numpy as np
from malachi.conversation.audio_input import AudioDuplex
from malachi.conversation.audio_output import PlaybackBuffer


def test_dac_timestamp_jaw_and_speech_events(settings):
    settings.audio_playback_buffer_ms = 0
    buffer = PlaybackBuffer(settings)
    events, jaws = [], []
    audio = AudioDuplex(buffer, events.append, lambda *a: jaws.append(a))
    buffer.push((np.ones(320) * 8000).astype("<i2").tobytes())
    data = np.zeros((320, 1), np.float32)
    before = time.monotonic()
    audio._output(data, 320, SimpleNamespace(outputBufferDacTime=11, currentTime=10.9), False)
    assert data.max() > 0 and jaws[0][0] > 0
    assert before + 0.099 <= jaws[0][1] <= time.monotonic() + 0.101
    assert events[0].kind == "agent_start"
    audio._output(data, 320, SimpleNamespace(outputBufferDacTime=11, currentTime=11), False)
    assert events[-1].kind == "agent_end"


def test_device_stop_reports_failure_only_when_unexpected(settings):
    events = []
    audio = AudioDuplex(PlaybackBuffer(settings), events.append, lambda *a: None)
    audio._finished()
    assert events[-1].kind == "error"
    events.clear()
    audio.stop()
    audio._finished()
    assert not events
