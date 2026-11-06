"""Reverse Beacon Network: parser, filter, merging, telnet client, API, alerts."""

import json
import socket
import threading
import time

import pytest
from flask.testing import FlaskClient

from radiomoni import alerts, config, rbn
from radiomoni.redis_client import get_redis

LINES = {
    'cq': 'DX de EA5WU-#:   14014.0  OH6BG          CW    22 dB  27 WPM  CQ      1234Z',
    'ssid': 'DX de KM3T-2-#:  7023.40  DL1ABC         CW    15 dB  24 WPM  CQ      0938Z',
    'suffix': 'DX de DF4UE-RP-#: 14069.40  CT1EXR         CW    14 dB  15 WPM  CQ      0709Z',
    # CC Cluster (GB7DXG), seen live: no blank after long skimmer calls, beacons as "NCDXF BCN"
    'cluster': 'DX de DL8LAS-3-#:21020.6  RN0SZ        CW  6 dB 16 WPM CQ             0747Z',
    'cluster_bcn': 'DX de EI4HQ-#:   14100.0  OH2B         CW 27 dB 19 WPM NCDXF BCN      0746Z',
    'ncdxf': 'DX de DK9IP-#:   14100.0  4X6TU          CW    12 dB  22 WPM  NCDXF B 1234Z',
    'beacon': 'DX de HB9DCO-#:  28263.9  DK0TEN         CW     8 dB  12 WPM  BEACON  1801Z',
    'rtty': 'DX de DL8LAS-#:  14085.0  RA3XYZ         RTTY  18 dB  45 BPS  CQ      1300Z',
}


class TestParser:
    def test_cq_spot(self):
        spot = rbn.parse_spot(LINES['cq'])
        assert spot == {'spotter': 'EA5WU', 'callsign': 'OH6BG', 'frequency': 14_014_000, 'khz': 14014.0,
                        'mode': 'CW', 'snr_db': 22, 'wpm': 27, 'type': 'CQ', 'utc': '1234', 'band': '20m'}

    def test_variants(self):
        assert rbn.parse_spot(LINES['ssid'])['spotter'] == 'KM3T-2'
        assert rbn.parse_spot(LINES['ssid'])['frequency'] == 7_023_400
        assert rbn.parse_spot(LINES['suffix'])['spotter'] == 'DF4UE-RP'  # letter suffix, seen live
        assert rbn.parse_spot(LINES['suffix'])['callsign'] == 'CT1EXR'
        cluster = rbn.parse_spot(LINES['cluster'])
        assert (cluster['spotter'], cluster['callsign'], cluster['khz']) == ('DL8LAS-3', 'RN0SZ', 21020.6)
        assert rbn.parse_spot(LINES['cluster_bcn'])['type'] == 'NCDXF B'
        assert rbn.parse_spot(LINES['ncdxf'])['type'] == 'NCDXF B'
        assert rbn.parse_spot(LINES['beacon'])['band'] == '10m'
        rtty = rbn.parse_spot(LINES['rtty'])
        assert rtty['mode'] == 'RTTY' and rtty['wpm'] is None

    @pytest.mark.parametrize('line', ['', 'Please enter your call:', 'Welcome to RBN', 'DX de garbage',
                                      'DX de EA6AOJ:    14305.0  EA6KB        EA6/MA-060 SOTA                0752Z'])
    def test_other_lines(self, line):
        assert rbn.parse_spot(line) is None


class TestFilter:
    def test_cw_hf_and_prefixes(self):
        assert rbn.accept(rbn.parse_spot(LINES['cq']), ['EA'])
        assert not rbn.accept(rbn.parse_spot(LINES['cq']), ['DL', 'HB'])
        assert rbn.accept(rbn.parse_spot(LINES['cq']), [])           # empty = every skimmer
        assert not rbn.accept(rbn.parse_spot(LINES['rtty']), [])     # only CW
        vhf = rbn.parse_spot(LINES['cq'].replace('14014.0', '50090.0'))
        assert not rbn.accept(vhf, [])                                # only HF


class TestSpotBook:
    def test_merges_repeats_and_keeps_the_best_snr(self):
        book = rbn.SpotBook()
        a = rbn.parse_spot(LINES['cq'])
        b = {**a, 'spotter': 'DK9IP', 'snr_db': 30, 'khz': 14014.2, 'frequency': 14_014_200}
        book.add(a, now=1000)
        entry = book.add(b, now=1030)
        assert len(book.entries) == 1
        assert entry['skimmer_count'] == 2 and entry['snr_db'] == 30 and entry['best_skimmer'] == 'DK9IP'
        assert entry['first_seen'] == 1000 and entry['last_seen'] == 1030

    def test_new_entry_after_the_merge_window_or_far_away(self):
        book = rbn.SpotBook()
        a = rbn.parse_spot(LINES['cq'])
        book.add(a, now=1000)
        book.add({**a, 'khz': 14030.0, 'frequency': 14_030_000}, now=1001)
        assert len(book.entries) == 2
        later = book.add(a, now=1000 + rbn.MERGE_WINDOW + 1)
        assert later['skimmer_count'] == 1 and later['first_seen'] == 1000 + rbn.MERGE_WINDOW + 1

    def test_prune(self):
        book = rbn.SpotBook()
        book.add(rbn.parse_spot(LINES['cq']), now=0)
        book.add(rbn.parse_spot(LINES['ssid']), now=rbn.MAX_AGE)
        book.prune(now=rbn.MAX_AGE + 10)
        assert [e['callsign'] for e in book.snapshot()] == ['DL1ABC']


class TestQuery:
    def spots(self):
        book = rbn.SpotBook()
        for key, t in (('cq', 100), ('ssid', 200), ('ncdxf', 300)):
            book.add(rbn.parse_spot(LINES[key]), now=t)
        return book.snapshot()

    def test_filters(self):
        spots = self.spots()
        assert [s['callsign'] for s in rbn.query(spots, now=400)] == ['4X6TU', 'DL1ABC', 'OH6BG']
        assert [s['callsign'] for s in rbn.query(spots, band='20m', now=400)] == ['4X6TU', 'OH6BG']
        assert [s['callsign'] for s in rbn.query(spots, cq_only=True, band='20m', now=400)] == ['OH6BG']
        assert [s['callsign'] for s in rbn.query(spots, call='dl1', now=400)] == ['DL1ABC']
        assert [s['callsign'] for s in rbn.query(spots, freq_min=14_050_000, now=400)] == ['4X6TU']
        assert [s['callsign'] for s in rbn.query(spots, max_age=200, now=400)] == ['4X6TU', 'DL1ABC']
        assert rbn.query(spots, now=400)[0]['age_seconds'] == 100


class FakeTelnet:
    """Server side of a socketpair: prompt, read the callsign, send lines, then close."""

    def __init__(self, lines: list[str], hold: float = 0.0, login_lines: int = 1):
        self.client_side, self.server_side = socket.socketpair()
        self.login = b''
        self.login_lines = login_lines   # callsign plus login commands
        self.lines = lines
        self.hold = hold
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        s = self.server_side
        s.sendall(b'Welcome to the RBN\r\nPlease enter your call: ')
        while self.login.count(b'\r\n') < self.login_lines:
            self.login += s.recv(64)
        for line in self.lines:
            s.sendall(line.encode() + b'\r\n')
        time.sleep(self.hold)
        s.close()

    def connect(self, host: str, port: int) -> socket.socket:
        return self.client_side


class TestClient:
    def test_login_spots_snapshot_and_reconnect(self):
        server = FakeTelnet([LINES['cq'], LINES['rtty'], LINES['ssid'], 'DX de BROKEN line'])
        client = rbn.RbnClient('HB9XYZ', 'host', 7000, prefixes=[], connect=server.connect)
        with pytest.raises(ConnectionError):
            client._session()                       # ends when the server closes the connection
        client._flush(force=True)
        assert server.login == b'HB9XYZ\r\n'
        spots = rbn.load_spots()
        assert sorted(s['callsign'] for s in spots) == ['DL1ABC', 'OH6BG']   # RTTY filtered out
        state = rbn.status()
        assert state['connected'] is False and state['total'] == 2 and state['spots_per_minute'] == 2

    def test_human_cluster_spots_are_ignored_quietly(self, caplog):
        client = rbn.RbnClient('HB9XYZ', 'h', 1, prefixes=[])
        assert client.handle_line('DX de IZ0EIK:     7058.0  IZ0MQN       DTMBAI-032 PG                  0753Z') is None
        assert 'unknown spot format' not in caplog.text
        client.handle_line('DX de EA5WU-#: garbage')
        assert 'unknown spot format' in caplog.text

    def test_login_commands_follow_the_callsign(self):
        server = FakeTelnet([LINES['cq']], login_lines=3)
        client = rbn.RbnClient('HB9XYZ', 'host', 7373, prefixes=[], connect=server.connect,
                               login_commands=['SET/SKIMMER', 'SET/NOFT8'])
        with pytest.raises(ConnectionError):
            client._session()
        assert server.login == b'HB9XYZ\r\nSET/SKIMMER\r\nSET/NOFT8\r\n'

    def test_only_one_leader(self):
        a = rbn.RbnClient('HB9XYZ', 'h', 1, [])
        b = rbn.RbnClient('HB9XYZ', 'h', 1, [])
        assert a._lead() and a._lead()
        assert not b._lead()
        get_redis().delete(rbn.LEADER_KEY)
        assert b._lead()

    def test_run_loop_stops(self):
        server = FakeTelnet([LINES['cq']], hold=5)
        client = rbn.RbnClient('HB9XYZ', 'h', 1, [], connect=server.connect)
        client.start()
        deadline = time.time() + 5
        while time.time() < deadline and not rbn.load_spots():
            time.sleep(0.05)
        client.stop()
        assert rbn.load_spots()[0]['callsign'] == 'OH6BG'
        assert get_redis().get(rbn.LEADER_KEY) is None

    def test_new_spots_reach_the_alert_rules_once(self):
        alerts.save_rule({'name': 'OH6BG', 'source': 'rbn', 'field': 'callsign', 'match_type': 'equals',
                          'pattern': 'OH6BG', 'channels': [], 'cooldown_seconds': 0})
        client = rbn.RbnClient('HB9XYZ', 'h', 1, prefixes=[])
        client.handle_line(LINES['cq'])
        client.handle_line(LINES['cq'].replace('EA5WU', 'DK9IP'))   # merged repeat: no second alert
        fired = alerts.recent_alerts()
        assert len(fired) == 1 and fired[0]['source'] == 'rbn' and 'OH6BG' in fired[0]['summary']

    def test_start_needs_a_callsign(self, monkeypatch):
        monkeypatch.setattr(config, 'RBN_ENABLED', True)
        monkeypatch.setattr(config, 'RBN_CALLSIGN', '')
        monkeypatch.setattr(rbn, '_client', None)
        assert rbn.start_if_enabled() is None


class TestApi:
    def test_spots_endpoint(self, client: FlaskClient):
        book = rbn.SpotBook()
        now = time.time()
        book.add(rbn.parse_spot(LINES['cq']), now=now)
        book.add(rbn.parse_spot(LINES['ssid']), now=now)
        get_redis().set(rbn.SNAPSHOT_KEY, json.dumps(book.snapshot()))
        data = client.get('/rbn/spots?band=40m').get_json()
        assert data['count'] == 1 and data['spots'][0]['callsign'] == 'DL1ABC'
        assert data['enabled'] is False
        assert client.get('/rbn/spots?band=2m').status_code == 400
        assert client.get('/rbn/spots?call=<x>').status_code == 400

    def test_status_endpoint(self, client: FlaskClient):
        data = client.get('/rbn/status').get_json()
        assert data['enabled'] is False and data['connected'] is False and data['host']
