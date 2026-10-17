"""PortAudio device negotiation and bounded streaming sample-rate conversion."""

import math
import numpy as np


def device_id(value):
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    return int(text) if text.isdecimal() else text


def stream_options(sd, settings, direction):
    device = device_id(getattr(settings, f"audio_{direction}_device"))
    info = sd.query_devices(device, direction)
    check = getattr(sd, f"check_{direction}_settings")
    maximum = int(info[f"max_{direction}_channels"])
    dtype = "int16" if direction == "input" else "float32"
    rates = list(dict.fromkeys([16000, int(info["default_samplerate"]), 48000, 44100]))
    for rate in rates:
        for channels in (1, 2):
            if channels > maximum or rate <= 0:
                continue
            try:
                check(device=device, samplerate=rate, channels=channels, dtype=dtype)
                return {
                    "device": device,
                    "samplerate": rate,
                    "channels": channels,
                    "dtype": dtype,
                    "blocksize": max(1, round(rate / 50)),
                    "latency": "high",
                }
            except Exception:
                continue
    raise ValueError(
        f"No supported {direction} format; select another AUDIO_{direction.upper()}_DEVICE"
    )


class SampleRateConverter:
    """Continuous linear interpolation with an FIR low-pass before downsampling."""

    def __init__(self, source_rate, target_rate):
        self.source_rate, self.target_rate = source_rate, target_rate
        self.step = source_rate / target_rate
        self.count = 0
        self.position = 0.0
        self.last = 0.0
        self.taps = None
        self.history = np.zeros(32, np.float32)
        if source_rate > target_rate:
            cutoff = 0.45 * target_rate / source_rate
            taps = 2 * cutoff * np.sinc(2 * cutoff * (np.arange(33) - 16)) * np.hamming(33)
            self.taps = taps / taps.sum()

    def input_needed(self, output_count):
        if self.source_rate == self.target_rate:
            return output_count
        end = self.position + (output_count - 1) * self.step
        return max(0, math.ceil(end - self.count + 1 - 1e-8))

    def process(self, samples):
        samples = np.asarray(samples, dtype=np.float32)
        if self.source_rate == self.target_rate or not len(samples):
            return samples
        if self.taps is not None:
            extended = np.concatenate((self.history, samples))
            samples = np.convolve(extended, self.taps, mode="valid").astype(np.float32)
            self.history = extended[-32:].copy()
        end = self.count + len(samples) - 1
        number = max(0, math.floor((end - self.position) / self.step + 1e-8) + 1)
        positions = self.position + np.arange(number) * self.step
        result = np.interp(
            positions, np.arange(self.count - 1, end + 1), np.concatenate(([self.last], samples))
        ).astype(np.float32)
        self.position += number * self.step
        self.count += len(samples)
        self.last = samples[-1]
        return result
