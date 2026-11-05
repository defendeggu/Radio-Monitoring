"""SSB contest skimmer: voice signal detection, carrier estimate, Whisper queue, spots, clips."""

import os
import threading
import time

import numpy as np
import pytest

from radiomoni.skimmer import session as skimmer_session
from radiomoni.skimmer.ssb import SsbCore, TranscriptionQueue, sideband_for

RATE = 96_000
CENTRE = 14_237_000

# carrier offset, identification tone (audio Hz), text the "transcriber" returns for that tone
STATIONS = [
    (-30_000, 700, 'CQ contest CQ contest, this is Hotel Bravo Nine X-ray Yankee Zulu'),
    (-5_000, 1300, 'QRZ contest de Delta Lima One Alfa Bravo Charlie'),
    (20_000, 1900, 'thank you, Oscar Kilo Two Papa Delta Tango contest'),
]


def ssb_segment(stations, seconds: float, sideband: str = 'USB', seed: int = 2,
                talk: tuple[float, float] = (3.0, 2.0)) -> np.ndarray:
    """Complex baseband: per station voice-like noise in 300–2700 Hz beside the carrier plus an id tone,
    keyed on and off like overs (`talk` = seconds on, seconds off)."""
    n = int(RATE * seconds)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / RATE
    freqs = np.fft.fftfreq(n, 1 / RATE)
    x = np.zeros(n, dtype=np.complex128)
    sign = 1 if sideband == 'USB' else -1
    on, off = talk
    envelope = ((t % (on + off)) < on).astype(float)
    for offset, tone, _ in stations:
        spectrum = np.fft.fft(rng.standard_normal(n) + 1j * rng.standard_normal(n))
        rel = sign * (freqs - offset)
        spectrum[(rel < 300) | (rel > 2700)] = 0
        voice = np.fft.ifft(spectrum)
        voice /= np.sqrt(np.mean(np.abs(voice) ** 2))
        voice = 0.05 * voice + 0.15 * np.exp(2j * np.pi * (offset + sign * tone) * t)
        x += envelope * voice
    x += 0.003 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    return x.astype(np.complex64)


def tone_transcriber(stations, calls: list | None = None):
    """Stand-in for Whisper: find the id tone in the demodulated audio, return that station's text."""
    def transcribe(audio, rate):
        spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio))))
        freqs = np.fft.rfftfreq(len(audio), 1 / rate)
        peak = freqs[np.argmax(spectrum)]
        tone, text = min(((tone, text) for _, tone, text in stations), key=lambda s: abs(s[0] - peak))
        if calls is not None:
            calls.append((tone, peak))
        return text if abs(tone - peak) < 150 else 'noise'
    return transcribe


def run(x, stations, sideband='USB', **kwargs):
    spots: list[dict] = []
    heard: list = []
    core = SsbCore(RATE, CENTRE, on_spot=spots.append, transcribe=tone_transcriber(stations, heard),
                   sideband=sideband, sync=True, **kwargs)
    chunk = int(RATE * 0.05)
    for i in range(0, len(x), chunk):
        core.feed(x[i:i + chunk], now=i / RATE)
    return spots, core, heard


class TestSsbCore:
    def test_three_stations_spotted(self):
        spots, core, heard = run(ssb_segment(STATIONS, 14), STATIONS)
        by_call = {s['callsign']: s for s in spots}
        assert set(by_call) == {'HB9XYZ', 'DL1ABC', 'OK2PDT'}
        for (offset, _, _), call in zip(STATIONS, ('HB9XYZ', 'DL1ABC', 'OK2PDT')):
            assert by_call[call]['frequency'] == pytest.approx(CENTRE + offset, abs=300)
            assert by_call[call]['mode'] == 'SSB' and by_call[call]['wpm'] is None
            assert len(by_call[call]['clip']) > 1.5 * 8000                    # the segment, for the play button
        # the demodulated audio has the id tone where it belongs: the carrier estimate is right
        assert all(abs(tone - peak) < 150 for tone, peak in heard)
        assert core.queue.stats()['done'] >= 6

    def test_lsb_below_10_mhz(self):
        assert sideband_for(7_100_000) == 'LSB' and sideband_for(14_200_000) == 'USB'
        stations = STATIONS[:2]
        spots, _, heard = run(ssb_segment(stations, 14, sideband='LSB'), stations, sideband='LSB')
        assert {s['callsign'] for s in spots} == {'HB9XYZ', 'DL1ABC'}
        assert all(abs(tone - peak) < 150 for tone, peak in heard)

    def test_calls_heard_once_or_not_self_identified_give_no_spot(self):
        stations = [(0, 1000, 'Delta Lima One Alfa Bravo Charlie, five nine zero zero one')]
        spots, core, _ = run(ssb_segment(stations, 10), stations)
        assert spots == [] and core.decodes >= 1
        stations = [(0, 1000, 'CQ contest this is Hotel Bravo Nine X-ray Yankee Zulu')]
        spots, _, _ = run(ssb_segment(stations, 4.5), stations)                # only one over
        assert spots == []

    def test_steady_carrier_gets_no_channel(self):
        t = np.arange(int(RATE * 6)) / RATE
        x = (0.2 * np.exp(2j * np.pi * 10_000 * t)).astype(np.complex64)
        _, core, _ = run(x, STATIONS)
        assert core.channels == {}


class TestQueue:
    def test_keeps_the_best_when_full(self):
        release = threading.Event()
        order: list[str] = []

        def slow(audio, rate):
            release.wait(5)
            return ''

        q = TranscriptionQueue(slow, lambda meta, text: order.append(meta['name']), max_pending=2)
        q.submit(1.0, 1, np.zeros(10, np.float32), {'name': 'first'})          # taken by the worker
        time.sleep(0.2)
        for score, name in ((1.0, 'low'), (5.0, 'high'), (3.0, 'mid')):
            q.submit(score, 1, np.zeros(10, np.float32), {'name': name})
        q.submit(0.5, 1, np.zeros(10, np.float32), {'name': 'lowest'})        # full and worse: dropped
        assert q.stats()['dropped'] == 2 and q.stats()['pending'] == 2
        release.set()
        deadline = time.time() + 5
        while len(order) < 3 and time.time() < deadline:
            time.sleep(0.02)
        q.close()
        assert order == ['first', 'high', 'mid']

    def test_failures_are_counted(self):
        def broken(audio, rate):
            raise RuntimeError('no model')
        q = TranscriptionQueue(broken, lambda meta, text: None, sync=True)
        q.submit(1.0, 1, np.zeros(10, np.float32), {})
        assert q.stats()['failed'] == 1 and q.stats()['done'] == 0


class TestSsbSession:
    def test_segments_and_mode(self, mock_sdr_hardware):
        s = skimmer_session.SkimmerSession(*skimmer_session.SSB_SEGMENTS['20m'], gain=30, mode='SSB',
                                           transcriber=lambda audio, rate: '')
        try:
            assert s.state()['skimmer_mode'] == 'SSB' and s.state()['transcriber']['pending'] == 0
            assert s.core.sideband == 'USB'
        finally:
            s.core.close()
        s = skimmer_session.SkimmerSession(*skimmer_session.SSB_SEGMENTS['80m'], gain=30, mode='SSB',
                                           transcriber=lambda audio, rate: '')
        try:
            assert s.core.sideband == 'LSB'
        finally:
            s.core.close()

    def test_spot_keeps_text_and_clip(self, mock_sdr_hardware, tmp_path):
        s = skimmer_session.SkimmerSession(*skimmer_session.SSB_SEGMENTS['20m'], gain=30, mode='SSB',
                                           transcriber=lambda audio, rate: '', output_dir=str(tmp_path))
        try:
            s._on_spot({'callsign': 'HB9XYZ/P', 'frequency': 14_240_000, 'type': 'CQ', 'hits': 2, 'respot': False,
                        'mode': 'SSB', 'khz': 14240.0, 'wpm': None, 'snr_db': 18.0, 'time': time.time(),
                        'source': 'skimmer', 'in_scp': None, 'text': 'CQ contest this is HB9XYZ portable',
                        'clip': np.zeros(16000, np.float32), 'clip_rate': 8000})
        finally:
            s.core.close()
        spot = skimmer_session.load_spots()[0]
        assert spot['callsign'] == 'HB9XYZ/P' and spot['mode'] == 'SSB'
        assert spot['text'].startswith('CQ contest') and spot['audio_file'].startswith('skimmer_ssb_')
        assert os.path.exists(tmp_path / spot['audio_file']) and '/' not in spot['audio_file']
