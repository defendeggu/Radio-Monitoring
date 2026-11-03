"""Streaming DSP blocks: continuity across chunks, sideband selection, spectrum."""

import numpy as np
import pytest

from radiomoni.dsp import (ChannelReceiver, Decimator, Mixer, SpectrumAnalyzer, decimation_factors, mask_dc,
                           to_uint8)

RATE = 2_000_000


def tone(freq: float, seconds: float, rate: int = RATE, amplitude: float = 0.5) -> np.ndarray:
    t = np.arange(int(rate * seconds)) / rate
    return (amplitude * np.exp(2j * np.pi * freq * t)).astype(np.complex64)


def in_chunks(block, x: np.ndarray, size: int) -> np.ndarray:
    return np.concatenate([block.process(x[i:i + size]) for i in range(0, len(x), size)])


def peak_hz(audio: np.ndarray, rate: float) -> float:
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio))))
    return float(np.fft.rfftfreq(len(audio), 1.0 / rate)[np.argmax(spectrum)])


class TestDecimation:
    def test_factors_are_small_and_close(self):
        factors = decimation_factors(RATE, 12_000)
        assert all(f <= 10 for f in factors)
        assert RATE / np.prod(factors) == pytest.approx(12_000, rel=0.1)

    def test_no_decimation_needed(self):
        assert decimation_factors(12_000, 12_000) == [1]

    def test_decimator_output_rate(self):
        d = Decimator(RATE, 12_000)
        out = d.process(tone(1000, 0.1))
        assert len(out) == pytest.approx(0.1 * d.output_rate, abs=2)


class TestContinuity:
    """A signal processed in chunks must equal the same signal in one piece."""

    @pytest.mark.parametrize('modulation', ['FM', 'AM', 'USB', 'LSB', 'CW'])
    def test_receiver_chunked_equals_whole(self, modulation):
        rng = np.random.default_rng(1)
        x = (tone(30_000, 0.2) + 0.05 * (rng.standard_normal(int(RATE * 0.2))
                                          + 1j * rng.standard_normal(int(RATE * 0.2)))).astype(np.complex64)
        whole = ChannelReceiver(RATE, 30_000, modulation).process(x)
        chunked = in_chunks(ChannelReceiver(RATE, 30_000, modulation), x, 100_000)
        assert np.allclose(whole, chunked, atol=1e-6)

    def test_mixer_phase_is_continuous(self):
        x = np.ones(1000, dtype=np.complex64)
        whole = Mixer(RATE, 12_345).process(x)
        chunked = in_chunks(Mixer(RATE, 12_345), x, 333)
        assert np.allclose(whole, chunked)


class TestDemodulation:
    def test_usb_keeps_upper_and_rejects_lower(self):
        upper = tone(100_000 + 1000, 0.3)   # 1 kHz above the channel
        lower = tone(100_000 - 1000, 0.3)   # 1 kHz below
        usb_up = ChannelReceiver(RATE, 100_000, 'USB')
        usb_low = ChannelReceiver(RATE, 100_000, 'USB')
        # skip the AGC so the levels stay comparable
        usb_up.agc = usb_low.agc = None
        p_up = np.mean(usb_up.process(upper)[2000:] ** 2)
        p_low = np.mean(usb_low.process(lower)[2000:] ** 2)
        assert p_up > 100 * p_low

    def test_cw_carrier_is_heard_at_the_bfo_tone(self):
        rx = ChannelReceiver(RATE, -250_000, 'CW', bfo_hz=700)
        audio = rx.process(tone(-250_000 + 20, 0.5))   # carrier 20 Hz off the dial
        assert peak_hz(audio[3000:], rx.audio_rate) == pytest.approx(720, abs=15)

    def test_fm_recovers_modulating_tone(self):
        t = np.arange(int(RATE * 0.3)) / RATE
        phase = 2 * np.pi * 50_000 * t + (3000 / 1000) * np.sin(2 * np.pi * 1000 * t)   # 3 kHz deviation
        rx = ChannelReceiver(RATE, 50_000, 'FM')
        audio = rx.process((0.5 * np.exp(1j * phase)).astype(np.complex64))
        assert peak_hz(audio[2000:], rx.audio_rate) == pytest.approx(1000, abs=20)

    def test_unknown_modulation(self):
        with pytest.raises(ValueError):
            ChannelReceiver(RATE, 0, 'WFM')


class TestSpectrum:
    def test_tone_lands_in_the_right_bin(self):
        analyzer = SpectrumAnalyzer(fft_size=2048)
        analyzer.feed(tone(250_000, 0.05))
        db = analyzer.frame()
        assert db is not None and len(db) == 2048
        bin_hz = RATE / 2048
        assert (np.argmax(db) - 1024) * bin_hz == pytest.approx(250_000, abs=bin_hz)

    def test_needs_enough_samples(self):
        analyzer = SpectrumAnalyzer(fft_size=2048)
        analyzer.feed(tone(0, 100 / RATE))
        assert analyzer.frame() is None

    def test_dc_mask_and_uint8(self):
        db = np.full(64, -100.0)
        db[32] = -10.0
        masked = mask_dc(db)
        assert masked[32] == pytest.approx(-100.0)
        assert list(to_uint8(np.array([-130.0, -70.0, -10.0, 0.0]), -130, -10)) == [0, 128, 255, 255]
