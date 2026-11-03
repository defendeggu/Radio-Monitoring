"""CW decoding session: transmissions, storage, alerts, recording, retune."""

import os
import subprocess
import time

import numpy as np
import pytest
from flask.testing import FlaskClient

from radiomoni import alerts, sdr_lock
from radiomoni.decoders import cw, spectrum
from radiomoni.session_store import session_manager
from radiomoni.storage.base import get_storage

from tests.test_morse import keying

RATE = 2_000_000
TARGET = 14_025_000


def hackrf_cw(text: str, wpm: float, offset_hz: float, tail_seconds: float = 4.0) -> bytes:
    """HackRF int8 IQ: keyed carrier at centre + offset, then silence."""
    key = np.concatenate([np.full(int(ms * RATE / 1000), 1.0 if down else 0.0, dtype=np.float32)
                          for down, ms in keying(text, wpm)] + [np.zeros(int(RATE * tail_seconds), np.float32)])
    t = np.arange(len(key)) / RATE
    rng = np.random.default_rng(0)
    iq = 0.5 * key * np.exp(2j * np.pi * offset_hz * t) + 0.02 * (rng.standard_normal(len(t))
                                                                 + 1j * rng.standard_normal(len(t)))
    raw = np.empty(2 * len(iq), dtype=np.int8)
    raw[0::2] = np.clip(np.round(iq.real * 127), -127, 127)
    raw[1::2] = np.clip(np.round(iq.imag * 127), -127, 127)
    return raw.tobytes()


@pytest.fixture
def fake_sdr(monkeypatch, tmp_path, mock_sdr_hardware):
    source = {'path': None}

    def start(self):
        return subprocess.Popen(['cat', source['path'] or '/dev/zero'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

    monkeypatch.setattr(cw.CwSession, '_start_sdr_capture', start)

    def use(data):
        if data is None:
            source['path'] = None
        else:
            path = tmp_path / 'cw.bin'
            path.write_bytes(data)
            source['path'] = str(path)
    return use


def wait_for(cond, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError('condition not met in time')


def wait_finished(session_id: str) -> str:
    wait_for(lambda: session_manager.get_session(session_id).status not in ('starting', 'running'), 60)
    wait_for(lambda: sdr_lock.current_holder() is None, 10)
    return session_manager.get_session(session_id).status


def start(client: FlaskClient, **body) -> str:
    response = client.post('/cw/start', json={'frequency': TARGET, **body})
    assert response.status_code == 200, response.get_json()
    return response.get_json()['session_id']


class TestTransmission:
    def test_decodes_stores_and_alerts(self, client: FlaskClient, fake_sdr, temp_recording_dir):
        alerts.save_rule({'name': 'HB9XYZ', 'source': 'cw', 'field': 'callsign', 'match_type': 'contains',
                          'pattern': 'HB9XYZ', 'channels': [], 'cooldown_seconds': 0})
        fake_sdr(hackrf_cw('CQ CQ DE HB9XYZ HB9XYZ K', 25, offset_hz=-RATE / 4))
        sid = start(client, record=True)
        assert wait_finished(sid) == 'completed'
        docs = get_storage().search_events('cw', hours=1)['hits']
        assert len(docs) == 1
        doc = docs[0]
        assert 'CQ DE HB9XYZ HB9XYZ K' in doc['text'], doc['text']
        assert doc['callsigns'] == ['HB9XYZ'] and doc['frequency'] == TARGET
        assert doc['wpm'] == pytest.approx(25, rel=0.15)
        assert os.path.exists(os.path.join(temp_recording_dir, doc['audio_file']))
        assert session_manager.get_session(sid).packet_count == 1
        fired = alerts.recent_alerts()
        assert fired and fired[0]['source'] == 'cw'
        listed = client.get('/cw/transmissions?call=hb9').get_json()
        assert listed['count'] == 1 and listed['transmissions'][0]['uuid'] == doc['uuid']

    def test_state_for_the_waterfall(self, client: FlaskClient, fake_sdr):
        fake_sdr(None)
        sid = start(client)
        try:
            wait_for(lambda: (spectrum.load_state(sid) or {}).get('mode') == 'cw')
            state = client.get(f'/spectrum/{sid}').get_json()['state']
            assert state['channel'] == TARGET and state['centre'] == TARGET + RATE // 4
            assert state['tunable'] is True and state['modulation'] == 'CW'
        finally:
            client.delete(f'/stream-decode/{sid}')
            wait_finished(sid)


class TestTune:
    def test_inside_and_outside_the_bandwidth(self, client: FlaskClient, fake_sdr):
        fake_sdr(None)
        sid = start(client)
        try:
            wait_for(lambda: session_manager.get_session(sid).status == 'running')
            inside = client.post(f'/cw/{sid}/tune', json={'channel': TARGET + 100_000}).get_json()['state']
            assert inside['centre'] == TARGET + RATE // 4 and inside['channel'] == TARGET + 100_000
            wait_for(lambda: spectrum.load_state(sid)['channel'] == TARGET + 100_000)
            outside = client.post(f'/cw/{sid}/tune', json={'channel': 7_020_000}).get_json()['state']
            assert outside['channel'] == 7_020_000 and outside['centre'] == 7_020_000 + RATE // 4
            wait_for(lambda: spectrum.load_state(sid)['centre'] == 7_020_000 + RATE // 4)
            assert session_manager.get_session(sid).status == 'running'
            wait_for(lambda: session_manager.get_session(sid).frequency == 7_020_000)
        finally:
            client.delete(f'/stream-decode/{sid}')
            wait_finished(sid)

    def test_validation(self, client: FlaskClient):
        assert client.post('/cw/start', json={'frequency': TARGET, 'cw_bandwidth': 150}).status_code == 400
        assert client.post('/cw/start', json={'frequency': TARGET, 'wpm': 99}).status_code == 400
        assert client.post('/cw/nope/tune', json={'channel': TARGET}).status_code == 409
        assert client.get('/cw/transmissions?call=<x>').status_code == 400
