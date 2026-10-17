import sys
from types import SimpleNamespace
import numpy as np
import pytest
from malachi.conversation.device_audio import SampleRateConverter, stream_options, device_id
from malachi.conversation.audio_input import AudioDuplex
from malachi.conversation.audio_output import PlaybackBuffer
from malachi.vision.capture import PiCameraCapture
from malachi.vision.detector_factory import OpenCVFaceDetector


def test_picamera_config_preserves_bgr_bytes_and_closes(settings, monkeypatch):
    frame = np.full((10, 20, 3), [10, 20, 230], np.uint8)
    log = []

    class Camera:
        def __init__(self, **kwargs):
            assert kwargs["camera_num"] == 0
            self.camera_controls = {"AfMode": None}

        def create_video_configuration(self, **kwargs):
            assert kwargs["main"]["format"] == "RGB888"
            assert kwargs["main"]["size"] == (1280, 720)
            return kwargs

        def configure(self, config):
            pass

        def set_controls(self, controls):
            assert controls == {"AfMode": 2}
            log.append("focus")

        def start(self):
            log.append("start")

        def capture_array(self, name):
            return frame

        def stop(self):
            log.append("stop")

        def close(self):
            log.append("close")

    monkeypatch.setitem(sys.modules, "picamera2", SimpleNamespace(Picamera2=Camera))
    monkeypatch.setitem(
        sys.modules,
        "libcamera",
        SimpleNamespace(controls=SimpleNamespace(AfModeEnum=SimpleNamespace(Continuous=2))),
    )
    capture = PiCameraCapture(settings)
    ok, image = capture.read()
    assert ok and image[0, 0].tolist() == [10, 20, 230]
    capture.release()
    assert log == ["focus", "start", "stop", "close"]


def test_pi_detector_normalizes_multi_face_boxes_without_fake_pose(settings):
    detector = OpenCVFaceDetector(settings)
    detector.cascade = SimpleNamespace(
        detectMultiScale=lambda *a, **kw: [(10, 20, 30, 40), (60, 20, 20, 30)]
    )
    faces = detector.detect(np.zeros((100, 100, 3), np.uint8), 0)
    assert len(faces) == 2 and faces[0].box == pytest.approx((0.1, 0.2, 0.4, 0.6))
    assert not faces[0].pose_available and faces[0].confidence == 0


def test_native_stereo_48k_device_fallback(settings):
    settings.audio_output_device = "4"

    def check(**kwargs):
        if kwargs["samplerate"] != 48000 or kwargs["channels"] != 2:
            raise ValueError("unsupported")

    sd = SimpleNamespace(
        query_devices=lambda *a: {"default_samplerate": 48000, "max_output_channels": 2},
        check_output_settings=check,
    )
    options = stream_options(sd, settings, "output")
    assert options["device"] == 4 and options["samplerate"] == 48000 and options["channels"] == 2
    assert device_id("") is None and device_id("USB microphone") == "USB microphone"


@pytest.mark.parametrize(
    "source,target", [(48000, 16000), (44100, 16000), (16000, 48000), (16000, 44100)]
)
def test_resampling_is_continuous_and_chunk_independent(source, target):
    samples = np.sin(2 * np.pi * 440 * np.arange(source) / source).astype(np.float32)
    whole = SampleRateConverter(source, target).process(samples)
    converter = SampleRateConverter(source, target)
    chunks = [converter.process(samples[i : i + 137]) for i in range(0, len(samples), 137)]
    joined = np.concatenate(chunks)
    assert abs(len(joined) - target) <= 3
    np.testing.assert_allclose(joined, whole, atol=1e-5)


def test_native_playback_has_no_gaps_or_pitch_change_and_interrupts(settings):
    settings.audio_playback_buffer_ms = 0
    playback = PlaybackBuffer(settings)
    audio = AudioDuplex(playback, lambda e: None, lambda *a: None)
    audio.output_rate = 48000
    audio.output_converter = SampleRateConverter(16000, 48000)
    waveform = (np.sin(2 * np.pi * 440 * np.arange(16000) / 16000) * 10000).astype("<i2")
    playback.push(waveform.tobytes())
    blocks = []
    for _ in range(49):
        block = np.zeros((960, 2), np.float32)
        audio._output(block, 960, SimpleNamespace(outputBufferDacTime=0, currentTime=0), False)
        np.testing.assert_array_equal(block[:, 0], block[:, 1])
        blocks.append(block[:, 0])
    heard = np.concatenate(blocks)
    frequency = np.fft.rfftfreq(len(heard), 1 / 48000)[np.argmax(abs(np.fft.rfft(heard)))]
    assert abs(frequency - 440) < 2
    assert sum(np.count_nonzero(b) for b in blocks) > len(heard) * 0.95
    playback.clear(interrupted=True)
    block = np.ones((960, 2), np.float32)
    audio._output(block, 960, SimpleNamespace(outputBufferDacTime=0, currentTime=0), False)
    assert not block.any()


def test_microphone_downmixes_and_sends_16k_pcm(settings):
    audio = AudioDuplex(PlaybackBuffer(settings), lambda e: None, lambda *a: None)
    audio.input_converter = SampleRateConverter(48000, 16000)
    for _ in range(4):
        audio._input(np.full((960, 2), 6000, np.int16), 960, None, False)
    packets = [np.frombuffer(audio.queue.get_nowait(), "<i2") for _ in range(4)]
    assert sum(map(len, packets)) == 1280
    assert np.mean(packets[-1]) == pytest.approx(6000, abs=2)


def test_downsampling_filters_aliasing():
    rate = 48000
    high = np.sin(2 * np.pi * 12000 * np.arange(rate // 10) / rate).astype(np.float32)
    low = np.sin(2 * np.pi * 1000 * np.arange(rate // 10) / rate).astype(np.float32)
    high_out = SampleRateConverter(rate, 16000).process(high)[50:]
    low_out = SampleRateConverter(rate, 16000).process(low)[50:]
    assert np.sqrt(np.mean(high_out**2)) < 0.05 * np.sqrt(np.mean(low_out**2))


def test_capture_backend_auto_and_usb_override(settings, monkeypatch):
    import malachi.vision.capture as module

    monkeypatch.setattr(module, "is_raspberry_pi", lambda: True)
    monkeypatch.setattr(module, "PiCameraCapture", lambda s: "CSI")
    monkeypatch.setattr(module, "OpenCVCapture", lambda s: "USB")
    assert module.open_capture(settings) == "CSI"
    settings.camera_backend = "opencv"
    assert module.open_capture(settings) == "USB"
