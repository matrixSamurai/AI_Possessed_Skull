import numpy as np
import pytest
from malachi.motion.jaw_sync import JawSync
from malachi.conversation.audio_output import PlaybackBuffer


def test_pcm_speech_silence_and_gate():
    jaw = JawSync()
    silence = np.zeros(320)
    assert jaw.process(silence) == 0
    assert jaw.process(np.ones(320) * 0.005) == 0
    tone = 0.25 * np.sin(2 * np.pi * 180 * np.arange(320) / 16000)
    for _ in range(20):
        jaw.process(tone)
    assert 0.5 < jaw.position < 1
    for _ in range(50):
        jaw.process(silence)
    assert jaw.position == 0


def test_playback_timeline_interruption_and_mute(settings):
    b = PlaybackBuffer(settings)
    b.push((np.ones(640) * 8000).astype("<i2").tobytes())
    assert b.jaw.position == 0  # Enqueue does not animate.
    samples, jaw, generation = b.render(320)
    assert jaw > 0 and samples.max() > 0
    assert b.samples == 320
    b.clear()
    samples, jaw, new = b.render(320)
    assert new > generation and jaw == 0 and not samples.any()
    b.push((np.ones(320) * 8000).astype("<i2").tobytes())
    b.muted = True
    samples, jaw, _ = b.render(320)
    assert not samples.any() and jaw == 0


def test_pcm_validation_and_bound(settings):
    b = PlaybackBuffer(settings)
    with pytest.raises(ValueError):
        b.push(b"a")
    with pytest.raises(BufferError):
        b.push(bytes(16000 * 16 * 2))
