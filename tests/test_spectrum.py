"""Spectrum / waterfall: frames, live listening, retune, preemption by other jobs."""

import subprocess
import threading
import time

import numpy as np
import pytest
from flask.testing import FlaskClient

from radiomoni import sdr_lock
from radiomoni.decoders import spectrum
from radiomoni.decoders.spectrum import FRAME_AUDIO, FRAME_JSON, FRAME_SPECTRUM, unpack_frames
from radiomoni.redis_client import get_redis_raw
from radiomoni.session_store import session_manager

RATE = 2_000_000
CENTRE = 145_000_000


def hackrf_bytes(offset_hz: float, seconds: float) -> bytes:
    """Interleaved int8 IQ (HackRF format) with a carrier at centre + offset."""
    t = np.arange(int(RATE * seconds)) / RATE
    iq = 0.4 * np.exp(2j * np.pi * offset_hz * t)
    raw = np.empty(2 * len(iq), dtype=np.int8)
    raw[0::2] = np.round(iq.real * 127)
    raw[1::2] = np.round(iq.imag * 127)
    return raw.tobytes()


@pytest.fixture
def fake_sdr(monkeypatch, tmp_path, mock_sdr_hardware):
    """The SDR process is `cat` of a prepared IQ file (or /dev/zero for an endless stream)."""
    source = {'path': None}

    def start(self):
        path = source['path'] or '/dev/zero'
        return subprocess.Popen(['cat', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    monkeypatch.setattr(spectrum.SpectrumSession, '_start_sdr_capture', start)

    def use(data: bytes | None) -> None:
        if data is None:
            source['path'] = None
        else:
            path = tmp_path / 'iq.bin'
            path.write_bytes(data)
            source['path'] = str(path)
    return use


class Collector:
    """Subscribe to a session's frame channel in the background."""

    def __init__(self, session_id: str):
        self.frames: list[tuple[int, object]] = []
        self._pubsub = get_redis_raw().pubsub(ignore_subscribe_messages=True)
        self._pubsub.subscribe(spectrum.channel_name(session_id))
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            message = self._pubsub.get_message(timeout=0.1)
            if message and isinstance(message.get('data'), bytes):
                self.frames.extend(unpack_frames(message['data']))

    def kinds(self, kind: int) -> list:
        return [f for k, f in self.frames if k == kind]

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        self._pubsub.close()


def wait_for(cond, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError('condition not met in time')


def start(client: FlaskClient, **body) -> str:
    response = client.post('/spectrum', json={'frequency': CENTRE, 'sample_rate': RATE, **body})
    assert response.status_code == 200, response.get_json()
    return response.get_json()['session_id']


def wait_finished(session_id: str) -> str:
    wait_for(lambda: session_manager.get_session(session_id).status not in ('starting', 'running'), 25)
    wait_for(lambda: sdr_lock.current_holder() is None, 10)
    return session_manager.get_session(session_id).status


class TestFrames:
    def test_round_trip(self):
        bins = np.arange(256, dtype=np.uint8)
        pcm = np.array([-32768, 0, 32767], dtype=np.int16)
        data = (spectrum.pack_spectrum(CENTRE, RATE, 1.5, bins) + spectrum.pack_audio(12_000, 2.5, pcm)
                + spectrum.pack_json({'end': 'completed'}))
        (k1, s), (k2, a), (k3, j) = list(unpack_frames(data))
        assert (k1, k2, k3) == (FRAME_SPECTRUM, FRAME_AUDIO, FRAME_JSON)
        assert s['centre'] == CENTRE and s['span'] == RATE and list(s['bins']) == list(bins)
        assert a['rate'] == 12_000 and list(a['pcm']) == [-32768, 0, 32767]
        assert j == {'end': 'completed'}


class TestSession:
    def test_waterfall_shows_the_carrier(self, client: FlaskClient, fake_sdr):
        fake_sdr(hackrf_bytes(300_000, 3.0))
        sid = start(client)
        collector = Collector(sid)
        try:
            spectrum.touch_viewer(sid, listening=False)
            wait_for(lambda: collector.kinds(FRAME_SPECTRUM))
        finally:
            assert wait_finished(sid) == 'completed'   # file ends → "SDR stream ended"
            collector.close()
        row = collector.kinds(FRAME_SPECTRUM)[0]
        bins = row['bins']
        peak_offset = (int(np.argmax(bins)) - len(bins) // 2) * RATE / len(bins)
        assert peak_offset == pytest.approx(300_000, abs=2 * RATE / len(bins))
        assert row['centre'] == CENTRE and row['span'] == RATE
        state = client.get(f'/spectrum/{sid}').get_json()['state']
        assert state['centre'] == CENTRE and state['tunable'] is True

    def test_no_frames_without_viewers(self, client: FlaskClient, fake_sdr):
        fake_sdr(hackrf_bytes(300_000, 1.0))
        sid = start(client)
        collector = Collector(sid)
        wait_finished(sid)
        collector.close()
        assert collector.kinds(FRAME_SPECTRUM) == []

    def test_listening_sends_audio(self, client: FlaskClient, fake_sdr):
        fake_sdr(hackrf_bytes(100_000 + 700, 3.0))
        sid = start(client)
        collector = Collector(sid)
        try:
            spectrum.touch_viewer(sid, listening=True)
            assert client.post(f'/spectrum/{sid}/tune',
                               json={'channel': CENTRE + 100_000, 'modulation': 'USB'}).status_code == 200
            wait_for(lambda: collector.kinds(FRAME_AUDIO))
        finally:
            wait_finished(sid)
            collector.close()
        audio = np.concatenate([f['pcm'] for f in collector.kinds(FRAME_AUDIO)]).astype(float)
        assert np.max(np.abs(audio)) > 1000    # the USB tone at +700 Hz is audible
        states = [f['state'] for f in collector.kinds(FRAME_JSON) if 'state' in f]
        assert states[-1]['modulation'] == 'USB' and states[-1]['channel'] == CENTRE + 100_000

    def test_tune_outside_the_bandwidth_is_rejected(self, client: FlaskClient, fake_sdr):
        fake_sdr(None)
        sid = start(client)
        try:
            wait_for(lambda: session_manager.get_session(sid).status == 'running')
            response = client.post(f'/spectrum/{sid}/tune', json={'channel': CENTRE + 5_000_000})
            assert response.status_code == 400
            ok = client.post(f'/spectrum/{sid}/tune', json={'centre': CENTRE + 5_000_000})
            assert ok.status_code == 200 and ok.get_json()['state']['channel'] == CENTRE + 5_000_000
        finally:
            client.delete(f'/stream-decode/{sid}')
            wait_finished(sid)

    def test_validation(self, client: FlaskClient):
        assert client.post('/spectrum', json={'frequency': CENTRE, 'fft_size': 1000}).status_code == 400
        assert client.post('/spectrum', json={'frequency': CENTRE, 'sample_rate': 50_000_000}).status_code == 400
        assert client.post('/spectrum/nope/tune', json={'channel': CENTRE}).status_code == 409
        assert client.get('/spectrum/nope').status_code == 404
        assert client.get('/spectrum/nope/stream').status_code == 404


class TestPreemption:
    def test_another_job_stops_the_waterfall(self, client: FlaskClient, fake_sdr):
        fake_sdr(None)                     # endless stream
        sid = start(client)
        wait_for(lambda: session_manager.get_session(sid).status == 'running')
        status = client.get('/sdr/status').get_json()
        assert status['busy'] is True and status['preemptible'] is True

        lease = sdr_lock.SdrLease('capture:test', 'capture').acquire()   # would raise SdrBusyError otherwise
        try:
            session = session_manager.get_session(sid)
            assert session.status == 'preempted'
            assert 'capture' in session.error
            assert sdr_lock.current_holder()['owner'] == 'capture:test'
        finally:
            lease.release()

    def test_a_second_waterfall_does_not_preempt_the_first(self, client: FlaskClient, fake_sdr):
        fake_sdr(None)
        sid = start(client)
        try:
            wait_for(lambda: session_manager.get_session(sid).status == 'running')
            assert client.post('/spectrum', json={'frequency': CENTRE}).status_code == 409
        finally:
            client.delete(f'/stream-decode/{sid}')
            wait_finished(sid)

    def test_idle_session_frees_the_sdr(self, client: FlaskClient, fake_sdr, monkeypatch):
        monkeypatch.setattr(spectrum, 'IDLE_TIMEOUT', 0.5)
        fake_sdr(None)
        sid = start(client)
        assert wait_finished(sid) == 'completed'
        assert 'nobody' in session_manager.get_session(sid).error
