#!/usr/bin/env python3
"""
Unit tests for SSB demodulation: one sideband only, neighbours rejected
"""

import unittest
import numpy as np
from scipy import signal

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radiomoni.sdr_hardware import AirspyHFCapture, RTLSDRCapture


def tone_level_db(audio: np.ndarray, fs: int, freq: float) -> float:
    """Power of one audio tone relative to the strongest tone, in dB"""
    f, p = signal.periodogram(audio, fs)
    idx = int(np.argmin(np.abs(f - freq)))
    return float(10 * np.log10(p[idx - 2:idx + 3].sum() / p.max()))


class TestSSBDemodulation(unittest.TestCase):
    """USB station at +1000 Hz, LSB station at -1700 Hz, neighbour at +5000 Hz"""

    def _iq(self, fs: int) -> np.ndarray:
        n = np.arange(int(fs * 0.5))
        iq = (np.exp(2j * np.pi * 1000 * n / fs)           # USB voice tone 1000 Hz
              + np.exp(-2j * np.pi * 1700 * n / fs)        # LSB voice tone 1700 Hz
              + np.exp(2j * np.pi * 5000 * n / fs))        # neighbour 5 kHz up
        return iq.astype(np.complex64)

    def _check(self, sdr, wanted: float, unwanted: list) -> None:
        mode = 'USB' if wanted == 1000 else 'LSB'
        audio = sdr._demodulate(self._iq(sdr.sample_rate), mode)
        fs = sdr.audio_sample_rate
        self.assertGreater(tone_level_db(audio, fs, wanted), -1.0)
        for freq in unwanted:
            self.assertLess(tone_level_db(audio, fs, freq), -40.0, f"{mode}: {freq} Hz not rejected")

    def test_usb_hears_only_usb_station(self):
        self._check(AirspyHFCapture(7_100_000, sample_rate=768_000), 1000, [1700, 5000])

    def test_lsb_hears_only_lsb_station(self):
        self._check(AirspyHFCapture(7_100_000, sample_rate=768_000), 1700, [1000, 5000])

    def test_non_integer_ratio_sample_rate(self):
        """2.4 MS/s / 16 kHz = 150, 2.048 MS/s / 16 kHz = 128; both must work"""
        for fs in (2_400_000, 2_048_000):
            self._check(RTLSDRCapture(100_000_000, sample_rate=fs), 1000, [1700, 5000])

    def test_output_rate_and_normalisation(self):
        sdr = AirspyHFCapture(7_100_000, sample_rate=768_000)
        audio = sdr._demodulate(self._iq(768_000), 'USB')
        self.assertEqual(len(audio), 8000)  # 0.5 s at 16 kHz
        self.assertAlmostEqual(float(np.max(np.abs(audio))), 1.0, places=6)


if __name__ == '__main__':
    unittest.main()
