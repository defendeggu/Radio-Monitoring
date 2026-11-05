"""Contest skimmer: activity detector, confirmation, multi-signal CW core, recording, evaluation, session."""

import json
import subprocess
import time

import numpy as np
import pytest
from flask.testing import FlaskClient

from radiomoni import alerts, config, sdr_lock
from radiomoni.contest import engine, worked
from radiomoni.integrations import cluster, n1mm
from radiomoni.redis_client import get_redis
from radiomoni.session_store import session_manager
from radiomoni.skimmer import evaluate, session as skimmer_session
from radiomoni.skimmer.activity import ActivityDetector
from radiomoni.skimmer.confirm import SpotConfirmer
from radiomoni.skimmer.core import CwChannel, SkimmerCore
from radiomoni.skimmer.recorder import IqRecorder
from radiomoni.storage.base import get_storage

from tests.test_contest import contest_data  # noqa: F401 - fixture
from tests.test_morse import keying

SEG_RATE = 96_000
CENTRE = 14_035_000
STATIONS = [('HB9XYZ', -20_000, 22, 0.30), ('DL1ABC', -5_000, 28, 0.10), ('OK2PDT', 3_000, 18, 0.20),
            ('F5ABC', 12_000, 32, 0.05), ('G4XYZ', 25_000, 25, 0.15)]


def key_envelope(text: str, wpm: float, rate: float, length: int) -> np.ndarray:
    """Keying with 5 ms raised edges (like a real keyer), built at 8 kHz and repeated up to `rate`."""
    slow = 8000
    key = np.concatenate([np.full(int(ms * slow / 1000), 1.0 if down else 0.0, dtype=np.float32)
                          for down, ms in keying(text, wpm)])
    window = np.hanning(81)
    key = np.convolve(key, window / window.sum(), mode='same').astype(np.float32)
    key = np.interp(np.arange(int(len(key) * rate / slow)) * slow / rate, np.arange(len(key)), key).astype(np.float32)
    return np.pad(key, (0, max(0, length - len(key))))[:length]


def segment(stations, seconds: float, rate: float = SEG_RATE, noise: float = 0.01, seed: int = 1,
            text: str = 'CQ TEST {call} {call} TEST') -> np.ndarray:
    n = int(rate * seconds)
    t = np.arange(n) / rate
    x = np.zeros(n, dtype=np.complex64)
    for call, offset, wpm, amp in stations:
        x += (amp * key_envelope(text.format(call=call), wpm, rate, n) * np.exp(2j * np.pi * offset * t)).astype(
            np.complex64)
    rng = np.random.default_rng(seed)
    x += (noise * (rng.standard_normal(n) + 1j * rng.standard_normal(n))).astype(np.complex64)
    return x


def run_core(x: np.ndarray, rate: float = SEG_RATE, **kwargs) -> tuple[list[dict], SkimmerCore]:
    spots: list[dict] = []
    core = SkimmerCore(rate, CENTRE, on_spot=spots.append, **kwargs)
    chunk = int(rate * 0.05)
    for i in range(0, len(x), chunk):
        core.feed(x[i:i + chunk], now=i / rate)
    return spots, core


class TestActivity:
    def test_finds_carriers_and_masks_clicks(self):
        rate = SEG_RATE
        t = np.arange(rate) / rate
        rng = np.random.default_rng(0)
        x = 0.3 * np.exp(2j * np.pi * -10_000 * t) + 0.003 * np.exp(2j * np.pi * 7_000 * t)
        x += 0.3 * np.exp(2j * np.pi * -10_200 * t) * 0.01              # 40 dB down, 200 Hz away: masked
        x += 0.001 * (rng.standard_normal(rate) + 1j * rng.standard_normal(rate))
        detector = ActivityDetector(rate)
        detector.feed(x)
        peaks = detector.peaks()
        assert len(peaks) == 2
        assert peaks[0][0] == pytest.approx(-10_000, abs=3) and peaks[1][0] == pytest.approx(7_000, abs=3)

    def test_tracks_follow_and_expire(self):
        detector = ActivityDetector(SEG_RATE, lifetime_s=5)
        t = np.arange(SEG_RATE // 2) / SEG_RATE
        tone = 0.3 * np.exp(2j * np.pi * 1_000 * t)
        for second in range(4):
            detector.feed(tone)
            tracks = detector.update(float(second))
        assert len(tracks) == 1 and tracks[0].hits == 4
        detector.feed(np.zeros(SEG_RATE))
        detector.update(10.0)                                           # rest of the tone in the buffer
        assert detector.update(20.0) == []


class TestConfirm:
    def test_needs_two_hits_and_respots(self):
        c = SpotConfirmer(respot_s=600)
        assert c.add('HB9XYZ', 14_025_000, 0, cq=True) is None
        spot = c.add('HB9XYZ', 14_025_050, 5, cq=False)
        assert spot['type'] == 'CQ' and spot['hits'] == 2 and not spot['respot']
        assert c.add('HB9XYZ', 14_025_000, 10, cq=True) is None                  # not again within respot_s
        assert c.add('HB9XYZ', 14_025_000, 400, cq=True) is None
        assert c.add('HB9XYZ', 14_025_000, 700, cq=True)['respot']

    def test_scp_and_validity(self):
        c = SpotConfirmer()
        assert c.add('DL1ABC', 7_010_000, 0, cq=True, in_scp=True)['hits'] == 1      # known contester after CQ
        assert c.add('XX1XX', 7_011_000, 0, cq=True, valid=False) is None
        for now in (0, 1):
            assert c.add('QQ9QQ', 7_012_000, now, cq=True, in_scp=False) is None       # unknown: three hits
        assert c.add('QQ9QQ', 7_012_000, 2, cq=True, in_scp=False) is not None
        assert c.add('OK2PDT', 7_013_000, 0, cq=True) is None
        assert c.add('OK2PDT', 7_020_000, 1, cq=True) is None                    # other frequency: new candidate


class TestCore:
    def test_five_stations_no_false_spots(self):
        spots, core = run_core(segment(STATIONS, 16))
        heard = {s['callsign']: s for s in spots}
        assert set(heard) == {call for call, *_ in STATIONS}
        for call, offset, wpm, _ in STATIONS:
            assert heard[call]['frequency'] == pytest.approx(CENTRE + offset, abs=50)
            assert heard[call]['wpm'] == pytest.approx(wpm, rel=0.15)
            assert heard[call]['type'] == 'CQ'
        assert len(core.tracks) == len(STATIONS)

    def test_weak_signals_in_noise(self):
        stations = [('HB9XYZ', -8_000, 24, 0.02), ('DL1ABC', 9_000, 26, 0.015)]
        spots, _ = run_core(segment(stations, 16, noise=0.02))       # ≈ +10 dB in 200 Hz
        assert {s['callsign'] for s in spots} == {'HB9XYZ', 'DL1ABC'}

    def test_calls_without_self_identification_are_not_spotted(self):
        # the run station sends its partner's call with the report: that is not a spot for the partner
        spots, core = run_core(segment([('HB9XYZ', 0, 25, 0.3)], 12, text='DL1ABC 5NN 14 DL1ABC 5NN 14'))
        assert spots == [] and core.decodes >= 1

    def test_carriers_get_no_decoder(self):
        rate = SEG_RATE
        x = segment([('HB9XYZ', -8_000, 25, 0.2)], 16)
        t = np.arange(len(x)) / rate
        x = x + (0.2 * np.exp(2j * np.pi * 14_000 * t)).astype(np.complex64)      # an SDR spur: steady carrier
        spots, core = run_core(x)
        assert {s['callsign'] for s in spots} == {'HB9XYZ'}
        carrier = next(tr for tr in core.tracks if abs(tr.offset_hz - 14_000) < 20)
        assert carrier.steady and carrier.id not in core.channels
        keyed = next(tr for tr in core.tracks if abs(tr.offset_hz + 8_000) < 20)
        assert not keyed.steady

    def test_noise_text_is_not_useful(self):
        ch = CwChannel(1, 0.0, 0.0, SEG_RATE)
        ch.words = ['E', 'EI', 'TEE', 'IIS*']
        assert not ch.useful
        ch.words.append('CQ')            # too short to count
        assert not ch.useful
        ch.words.append('TEST')
        assert ch.useful

    def test_decoder_limit_and_validation(self):
        spots, core = run_core(segment(STATIONS, 16), max_decoders=2)
        assert len(core.channels) <= 2 and {s['callsign'] for s in spots} <= {c for c, *_ in STATIONS}
        spots, _ = run_core(segment(STATIONS[:2], 16), validate=lambda call: (call != 'DL1ABC', None))
        assert {s['callsign'] for s in spots} == {'HB9XYZ'}


class TestRecordingAndEvaluation:
    def test_recorder_writes_wav_sidecar_and_rbn_log(self, tmp_path):
        get_redis().set('rbn:spots', json.dumps([
            {'callsign': 'HB9XYZ', 'frequency': CENTRE - 20_000, 'khz': 14015.0, 'band': '20m', 'mode': 'CW',
             'snr_db': 20, 'wpm': 22, 'type': 'CQ', 'skimmers': ['DL8LAS'], 'skimmer_count': 1,
             'best_skimmer': 'DL8LAS', 'first_seen': time.time(), 'last_seen': time.time()},
            {'callsign': 'W1AW', 'frequency': 7_030_000, 'khz': 7030.0, 'band': '40m', 'mode': 'CW', 'snr_db': 9,
             'wpm': 20, 'type': 'CQ', 'skimmers': ['DL8LAS'], 'skimmer_count': 1, 'best_skimmer': 'DL8LAS',
             'first_seen': time.time(), 'last_seen': time.time()}]))
        x = segment(STATIONS, 16)
        rec = IqRecorder(str(tmp_path), CENTRE, SEG_RATE, 14_000_000, 14_070_000)
        for i in range(0, len(x), 4800):
            rec.write(x[i:i + 4800])
        rec.close()
        assert rec.info()['seconds'] == pytest.approx(16, abs=0.1)
        base = tmp_path / rec.name
        meta = json.loads((tmp_path / f'{rec.name}.json').read_text())
        assert meta['centre_hz'] == CENTRE and meta['rate'] == SEG_RATE
        reference = evaluate.load_reference(str(base) + '.rbn.jsonl')
        assert [r['callsign'] for r in reference] == ['HB9XYZ']                 # only inside the segment

        spots = evaluate.run_cw(str(base) + '.wav')
        result = evaluate.score(spots, reference)
        assert result['found'] == 1 and result['recall'] == 1.0
        assert result['precision'] == pytest.approx(0.2) and 'DL1ABC' in result['wrong']

    def test_score(self):
        reference = [{'callsign': 'HB9XYZ', 'frequency': 14_015_000}, {'callsign': 'DL1ABC', 'frequency': None},
                     {'callsign': 'OK2PDT', 'frequency': 7_010_000}]
        spots = [{'callsign': 'HB9XYZ', 'frequency': 14_015_400}, {'callsign': 'DL1ABC', 'frequency': 21_000_000},
                 {'callsign': 'OK2PDT', 'frequency': 14_010_000}, {'callsign': 'XX9XX', 'frequency': 1}]
        result = evaluate.score(spots, reference)
        assert result['correct'] == 2 and result['wrong'] == ['OK2PDT', 'XX9XX'] and result['precision'] == 0.5
        assert result['recall'] == pytest.approx(0.667, abs=0.001) and result['missed'] == ['OK2PDT']

    def test_ssb_calls(self):
        text = 'CQ contest this is Hotel Bravo Nine X-ray Yankee Zulu. Delta Lima One Alfa Bravo Charlie five nine.'
        assert evaluate.ssb_calls(text, confirmed=False) == ['HB9XYZ', 'DL1ABC']
        assert evaluate.ssb_calls(text, confirmed=True) == ['HB9XYZ']


# ------------------------------------------------------------------ session (HackRF IQ through the SDR pipe)
RATE = 2_000_000
HW_CENTRE = CENTRE + RATE // 4          # zero-IF: tuned beside the segment


RUN_TEXT = 'CQ {call} {call} TEST CQ {call} {call} TEST'      # a run station calling CQ in a loop


def hackrf_bytes(stations, seconds: float, path) -> None:
    """int8 IQ like hackrf_transfer, written in 1 s blocks (memory)."""
    n_total = int(RATE * seconds)
    rng = np.random.default_rng(0)
    with open(path, 'wb') as f:
        envelopes = {call: key_envelope(RUN_TEXT.format(call=call), wpm, RATE, n_total)
                     for call, _, wpm, _ in stations}
        for start in range(0, n_total, RATE):
            n = min(RATE, n_total - start)
            t = (start + np.arange(n)) / RATE
            x = 0.02 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
            for call, offset, _, amp in stations:
                x = x + amp * envelopes[call][start:start + n] * np.exp(2j * np.pi * (CENTRE + offset - HW_CENTRE) * t)
            raw = np.empty(2 * n, dtype=np.int8)
            raw[0::2] = np.clip(np.round(x.real * 127), -127, 127)
            raw[1::2] = np.clip(np.round(x.imag * 127), -127, 127)
            f.write(raw.tobytes())


@pytest.fixture
def fake_sdr(monkeypatch, tmp_path, mock_sdr_hardware):
    source = {'path': None}

    def start(self):
        return subprocess.Popen(['cat', source['path'] or '/dev/zero'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

    monkeypatch.setattr(skimmer_session.SkimmerSession, '_start_sdr_capture', start)

    def use(stations, seconds):
        path = tmp_path / 'skimmer.bin'
        hackrf_bytes(stations, seconds, path)
        source['path'] = str(path)
    return use


def wait_for(cond, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError('condition not met in time')


class TestSession:
    def test_spots_through_the_api(self, client: FlaskClient, fake_sdr, contest_data):  # noqa: F811
        engine.set_active_contest('cq-ww-cw')
        worked.add({'call': 'OK1XX', 'band': '20m', 'mode': 'CW'})                 # Czech Republic worked on 20 m
        alerts.save_rule({'name': 'mult', 'source': 'skimmer', 'field': 'text', 'match_type': 'contains',
                          'pattern': 'MULT', 'channels': [], 'cooldown_seconds': 0})
        fake_sdr([('HB9XYZ', -20_000, 30, 0.3), ('OK2PDT', 10_000, 28, 0.3)], 17)
        response = client.post('/skimmer/start', json={'band': '20m', 'max_decoders': 8})
        assert response.status_code == 200, response.get_json()
        sid = response.get_json()['session_id']
        assert response.get_json()['centre'] == CENTRE and response.get_json()['freq_low'] == 14_000_000
        wait_for(lambda: session_manager.get_session(sid).status not in ('starting', 'running'))
        wait_for(lambda: sdr_lock.current_holder() is None, 10)

        spots = {s['callsign']: s for s in client.get('/skimmer/spots').get_json()['spots']}
        assert set(spots) == {'HB9XYZ', 'OK2PDT'}
        assert spots['HB9XYZ']['frequency'] == pytest.approx(CENTRE - 20_000, abs=60)
        assert spots['HB9XYZ']['priority'] == 'high' and spots['OK2PDT']['priority'] == 'normal'
        assert spots['HB9XYZ']['country'] == 'Switzerland' and spots['OK2PDT']['new_mults'] == []
        assert client.get('/skimmer/spots?priority=high').get_json()['count'] == 1
        stored = get_storage().search_events('skimmer', hours=1)['hits']
        assert {d['callsign'] for d in stored} == {'HB9XYZ', 'OK2PDT'}
        lines = get_redis().lrange(cluster.RECENT_KEY, 0, -1)
        assert any('HB9XYZ' in line and 'MULT' in line for line in lines)
        assert [a['source'] for a in alerts.recent_alerts()] == ['skimmer']
        assert session_manager.get_session(sid).packet_count == 2

    def test_validation(self, client: FlaskClient):
        assert client.post('/skimmer/start', json={}).status_code == 400
        assert client.post('/skimmer/start', json={'freq_low': 14_000_000, 'freq_high': 14_001_000}).status_code == 400
        assert client.post('/skimmer/start', json={'band': '20m', 'mode': 'SSB'}).status_code == 400

    def test_too_wide_for_the_sdr(self, mock_sdr_hardware):
        with pytest.raises(ValueError, match='too wide'):
            skimmer_session.SkimmerSession(14_000_000, 14_900_000, gain=30)

    def test_blanking(self, mock_sdr_hardware, monkeypatch):
        s = skimmer_session.SkimmerSession(14_000_000, 14_070_000, gain=30)
        quiet = np.zeros(100_000, dtype=np.complex64)
        s.process_chunk(quiet, now=0)
        assert not s.blanked
        loud = np.full(100_000, 1 + 1j, dtype=np.complex64)                   # ADC clipping
        s.process_chunk(loud, now=1)
        assert s.blanked and s.blanked_seconds == pytest.approx(0.05)
        monkeypatch.setattr(config, 'N1MM_ENABLED', True)
        n1mm.handle({'type': 'radio', 'station': 'PC', 'radio': '1', 'freq_khz': 14025.0, 'tx_freq_khz': 14025.0,
                     'mode': 'CW', 'transmitting': True, 'running': True})
        s._tx_checked = 0
        s.process_chunk(quiet, now=2)
        assert s.blanked
        assert s.state()['blanked_seconds'] == 0                               # rounded seconds
