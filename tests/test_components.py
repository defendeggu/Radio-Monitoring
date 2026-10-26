"""Unit tests: SDR lock, storage backends, VOX squelch, external decoder parsers, schemas."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import numpy as np
import pytest

import sdr_lock
from storage_sqlite import SQLiteStorage


# ============================================================================ SDR lock
class TestSdrLock:
    def test_exclusive(self):
        assert sdr_lock.acquire('a', 'capture')
        assert not sdr_lock.acquire('b', 'stream')
        assert sdr_lock.current_holder()['owner'] == 'a'

    def test_release_only_by_owner(self):
        sdr_lock.acquire('a', 'capture')
        assert not sdr_lock.release('b')
        assert sdr_lock.current_holder() is not None
        assert sdr_lock.release('a')
        assert sdr_lock.current_holder() is None

    def test_lease_context_manager(self):
        with sdr_lock.SdrLease('job', 'capture'):
            with pytest.raises(sdr_lock.SdrBusyError) as e:
                sdr_lock.SdrLease('other', 'scan').acquire()
            assert e.value.holder['owner'] == 'job'
        assert sdr_lock.current_holder() is None

    def test_refresh_and_ttl(self):
        from redis_client import get_redis
        sdr_lock.acquire('a', 'capture')
        assert 0 < get_redis().ttl(sdr_lock.LOCK_KEY) <= sdr_lock.LOCK_TTL
        assert sdr_lock.refresh('a')
        assert not sdr_lock.refresh('b')

    def test_wait_until_free(self):
        assert sdr_lock.wait_until_free(0)
        sdr_lock.acquire('a', 'capture')
        assert not sdr_lock.wait_until_free(0)


# ============================================================================ storage
class TestSQLiteStorage:
    @pytest.fixture
    def db(self, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'x.db'))
        yield storage
        storage.close()

    def test_captures(self, db):
        uid = db.index_capture({'frequency': 145_500_000, 'modulation': 'FM', 'transcription': 'Hello World',
                                'detected_language': 'en', 'mode': 'voice'})
        assert db.get_capture_by_id(uid)['frequency_mhz'] == 145.5
        assert db.search_captures(query='world')['total'] == 1
        assert db.search_captures(frequency_min=146_000_000)['total'] == 0
        assert db.search_captures(language='de')['total'] == 0
        assert db.get_frequency_usage()[0]['modulations'] == ['FM']

    def test_time_window(self, db):
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        db.index_aprs({'source_callsign': 'OLD', 'timestamp': old})
        db.index_aprs({'source_callsign': 'new'})
        assert db.search_aprs(hours=24)['total'] == 1
        assert db.search_aprs(callsign='NEW')['total'] == 1
        assert db.get_aprs_stats(hours=72)['unique_callsigns'] == 2

    def test_aprs_gets_maidenhead_locator(self, db):
        db.index_aprs({'source_callsign': 'HB9TST', 'latitude': 47.37, 'longitude': 8.54})
        db.index_aprs({'source_callsign': 'NOPOS'})
        hits = {h['source_callsign']: h for h in db.search_aprs()['hits']}
        assert hits['HB9TST']['maidenhead'] == 'JN47gi'
        assert 'maidenhead' not in hits['NOPOS']

    def test_pocsag_stats(self, db):
        for addr in (1, 1, 2):
            db.index_pocsag({'address': addr, 'message_type': 'alpha', 'baud_rate': 1200})
        stats = db.get_pocsag_stats()
        assert stats['total_messages'] == 3
        assert stats['top_addresses'][0] == {'address': 1, 'count': 2}
        assert db.search_pocsag(address=2)['total'] == 1

    def test_repeaters(self, db):
        db.index_repeater({'id': 5, 'callsign': 'HB9X', 'band': '2m', 'canton': 'BE', 'mode': 'FM', 'status': 'active'})
        assert db.get_repeater_by_id(5)['callsign'] == 'HB9X'
        assert db.get_repeaters(band='2m', canton='be')[0]['callsign'] == 'HB9X'
        assert db.get_repeaters(band='70cm') == []
        db.index_repeater_activity({'repeater_callsign': 'HB9X', 'carrier_detected': True,
                                    'activity_percentage': 10.0, 'transmission_count': 3})
        db.index_repeater_activity({'repeater_callsign': 'HB9X', 'carrier_detected': True,
                                    'activity_percentage': 20.0, 'transmission_count': 1})
        summary = db.get_repeater_activity_summary()
        assert summary[0]['avg_activity_pct'] == 15.0
        assert summary[0]['total_transmissions'] == 4

    def test_events(self, db):
        db.index_event('adsb', {'icao': 'ABC123'})
        assert db.search_events('adsb', term={'icao': 'ABC123'})['total'] == 1
        with pytest.raises(ValueError):
            db.index_event('unknown', {})
        with pytest.raises(ValueError):
            db.search_events('adsb', term={"icao') OR 1=1 --": 'x'})

    def test_dashboard_and_overall(self, db):
        db.index_capture({'frequency': 1})
        stats = db.get_dashboard_stats(hours=3)
        assert stats['counts']['captures'] == 1
        assert len(stats['timeline']) == 3
        assert db.get_overall_stats()['total_captures'] == 1
        assert db.health_check()['status'] == 'green'


class TestElasticsearchStorage:
    @pytest.fixture
    def es(self, monkeypatch):
        from elasticsearch_service import ElasticsearchService
        svc = ElasticsearchService(hosts=['http://es:9200'], logstash_auth=('radio', 'pw'))
        svc.es_client = MagicMock()
        svc._http = MagicMock()
        svc._http.post.return_value = MagicMock(status_code=200)
        return svc

    def test_index_capture_via_logstash_with_auth(self, es):
        es.index_capture({'frequency': 144_800_000})
        args, kwargs = es._http.post.call_args
        assert kwargs['auth'] == ('radio', 'pw')
        assert kwargs['json']['frequency_mhz'] == 144.8
        assert kwargs['json']['uuid']

    def test_logstash_error_raises(self, es):
        es._http.post.return_value = MagicMock(status_code=401)
        with pytest.raises(RuntimeError):
            es.index_aprs({'source_callsign': 'X'})

    def test_aprs_position(self, es):
        es.index_aprs({'latitude': 47.0, 'longitude': 8.0})
        assert es._http.post.call_args.kwargs['json']['position'] == {'lat': 47.0, 'lon': 8.0}

    def test_search_aprs_query(self, es):
        es.es_client.search.return_value = {'hits': {'hits': [{'_source': {'a': 1}}], 'total': {'value': 1}}}
        result = es.search_aprs(callsign='hb9x', hours=5)
        query = es.es_client.search.call_args.kwargs['query']
        assert {'term': {'source_callsign': 'HB9X'}} in query['bool']['must']
        assert result == {'hits': [{'a': 1}], 'total': 1}

    def test_index_event_direct(self, es):
        es.index_event('adsb', {'icao': 'ABC', 'latitude': 1.0, 'longitude': 2.0})
        kwargs = es.es_client.index.call_args.kwargs
        assert kwargs['index'].startswith('radio-adsb-')
        assert kwargs['document']['position'] == {'lat': 1.0, 'lon': 2.0}

    def test_health_error_hides_details(self, es):
        es.es_client.cluster.health.side_effect = RuntimeError('connection to secret-host refused')
        assert 'secret' not in json.dumps(es.health_check())

    def test_kind_from_index(self):
        from elasticsearch_service import _kind_from_index
        assert _kind_from_index('radio-captures-2026.10.16') == 'captures'
        assert _kind_from_index('radio-repeater-activity-2026.10.16') == 'repeater-activity'


# ============================================================================ VOX
class TestSquelchGate:
    def test_opens_and_closes_with_hysteresis(self):
        from vox_recorder import SquelchGate
        gate = SquelchGate(squelch_db=10, hang_time=0.2, chunk_seconds=0.05)
        transitions = [gate.update(-80.0) for _ in range(20)]
        assert 'open' not in transitions
        assert gate.update(-60.0) == 'open'
        assert gate.update(-60.0) is None
        closes = [gate.update(-80.0) for _ in range(10)]
        assert closes.count('close') == 1
        assert not gate.is_open

    def test_short_dropout_keeps_gate_open(self):
        from vox_recorder import SquelchGate
        gate = SquelchGate(squelch_db=10, hang_time=0.5, chunk_seconds=0.05)
        for _ in range(20):
            gate.update(-80.0)
        gate.update(-60.0)
        assert gate.update(-80.0) is None   # dropout shorter than hang time
        assert gate.update(-60.0) is None
        assert gate.is_open

    def test_chunk_power(self):
        from vox_recorder import chunk_power_db
        assert chunk_power_db(np.ones(100, dtype=np.complex64)) == pytest.approx(0.0, abs=1e-6)
        assert chunk_power_db(np.array([], dtype=np.complex64)) < -100


class TestVoxRecorder:
    def test_segment_written_and_stored(self, mock_sdr_hardware, tmp_path):
        from session_store import session_manager
        from storage import get_storage
        from vox_recorder import VoxRecorder
        rec = VoxRecorder(frequency=145_500_000, duration=60, gain=20, sample_rate=2_000_000,
                          transcribe=False, min_segment_ms=100, hang_time_ms=100, output_dir=str(tmp_path))
        session_manager.create_session('vox', rec, 145_500_000, rec.sample_rate, 20)
        n = int(rec.sample_rate * 0.05)
        rng = np.random.default_rng(1)
        noise = lambda: (rng.normal(size=n) + 1j * rng.normal(size=n)).astype(np.complex64) * 0.001  # noqa: E731
        t = np.arange(n) / rec.sample_rate
        carrier = (np.exp(2j * np.pi * 1000 * t) * 0.5).astype(np.complex64)
        for _ in range(20):
            rec.process_chunk(noise(), session_manager)
        for _ in range(10):
            rec.process_chunk(carrier, session_manager)
        for _ in range(10):
            rec.process_chunk(noise(), session_manager)
        assert rec.segment_count == 1
        assert len(list(tmp_path.glob('vox_*.wav'))) == 1
        docs = get_storage().search_captures(mode='vox')['hits']
        assert docs and docs[0]['peak_power_db'] > docs[0]['noise_floor_db']


# ============================================================================ external decoders
class TestExternalDecoderParsers:
    def test_rtl433(self):
        from external_decoders import parse_rtl433_line
        line = '{"time":"2026-10-16T10:00:00Z","model":"Acurite-Tower","id":1234,"channel":"A",' \
               '"battery_ok":1,"temperature_C":21.4,"humidity":45,"nested":{"x":1}}'
        doc = parse_rtl433_line(line)
        assert doc['model'] == 'Acurite-Tower'
        assert doc['sensor_id'] == 'Acurite-Tower:1234:A'
        assert doc['temperature_C'] == 21.4
        assert 'nested' not in doc
        assert parse_rtl433_line('Found Rafael Micro R820T tuner') is None
        assert parse_rtl433_line('{"no_model": 1}') is None
        assert parse_rtl433_line('{broken') is None

    def test_readsb(self):
        from external_decoders import parse_readsb_aircraft
        payload = {'now': 1, 'aircraft': [
            {'hex': '4b1234', 'flight': 'SWR123  ', 'alt_baro': 35000, 'gs': 450.1, 'lat': 47.4, 'lon': 8.5, 'seen': 1},
            {'hex': '4b9999', 'alt_baro': 'ground', 'seen': 2},
            {'hex': 'old', 'seen': 120},
            {'flight': 'nohex'},
        ]}
        aircraft = parse_readsb_aircraft(payload)
        assert [a['icao'] for a in aircraft] == ['4B1234', '4B9999']
        assert aircraft[0]['flight'] == 'SWR123'
        assert aircraft[1]['altitude_ft'] is None

    def test_ais_single_and_multipart(self):
        from external_decoders import AisAssembler
        asm = AisAssembler()
        doc = asm.feed('!AIVDM,1,1,,B,15M67FC000G?ufbE`FepT@3n00Sa,0*5C')
        assert doc['mmsi'] == '366053209'
        assert doc['msg_type'] == 1
        assert 'latitude' in doc
        assert asm.feed('!AIVDM,2,1,4,A,55O0W7`00001L@gCWGA2uItLth@DqtL5@F22220j1h742t0Ht0000000,0*08') is None
        doc = asm.feed('!AIVDM,2,2,4,A,000000000000000,2*20')
        assert doc['msg_type'] == 5
        assert asm.feed('garbage') is None

    def test_command_lines(self, monkeypatch):
        import external_decoders
        from sdr_hardware import SDRType
        monkeypatch.setattr(external_decoders, 'tool_available', lambda d: True)
        monkeypatch.setattr(external_decoders, 'detect_sdr', lambda *a, **k: SDRType.RTLSDR)
        ism = external_decoders.ExternalDecoderSession('ism', 60, gain=30, frequency=868_300_000, ppm=5)
        cmd = ism.build_command()
        assert cmd[:3] == ['rtl_433', '-f', '868300000'] and '-g' in cmd and '5' in cmd
        adsb = external_decoders.ExternalDecoderSession('adsb', 60)
        assert adsb.frequency == 1_090_000_000
        assert 'auto' in adsb.build_command()
        ais = external_decoders.ExternalDecoderSession('ais', 60, gain=10)
        assert ais.build_command()[:2] == ['rtl_ais', '-n']

    @staticmethod
    def _hackrf_only(monkeypatch, rtlsdr_present=False):
        import external_decoders
        from sdr_hardware import SDRType
        monkeypatch.setattr(external_decoders, 'tool_available', lambda d: True)
        monkeypatch.setattr(external_decoders, 'detect_sdr', lambda *a, **k: SDRType.HACKRF)
        monkeypatch.setattr(external_decoders.RTLSDRCapture, 'is_available', lambda self: rtlsdr_present)
        return external_decoders

    def test_adsb_with_hackrf(self, monkeypatch):
        ext = self._hackrf_only(monkeypatch)
        auto = ext.ExternalDecoderSession('adsb', 60).build_command()
        assert auto[auto.index('--device-type') + 1] == 'hackrf'
        assert '--gain' not in auto and '--ppm' not in auto  # readsb defaults: LNA 40, VGA 48

        cmd = ext.ExternalDecoderSession('adsb', 60, gain=35).build_command()
        assert cmd[cmd.index('--gain') + 1] == '32'           # LNA in 8 dB steps
        assert cmd[cmd.index('--hackrf-vgagain') + 1] == '34'  # VGA in 2 dB steps

    def test_ais_and_ism_still_require_rtlsdr(self, monkeypatch):
        ext = self._hackrf_only(monkeypatch)
        for decoder in ('ais', 'ism'):
            with pytest.raises(ValueError, match='RTL-SDR'):
                ext.ExternalDecoderSession(decoder, 60)

    def test_ais_uses_rtlsdr_next_to_hackrf(self, monkeypatch):
        from sdr_hardware import SDRType
        ext = self._hackrf_only(monkeypatch, rtlsdr_present=True)
        assert ext.ExternalDecoderSession('ais', 60).sdr_type == SDRType.RTLSDR


# ============================================================================ schemas
class TestSchemas:
    def test_whisper_options(self):
        from schemas import CaptureRequest
        req = CaptureRequest.model_validate({'frequency': '100000000', 'language': '', 'beam_size': 3,
                                             'initial_prompt': 'HB9 callsigns'})
        assert req.frequency == 100_000_000
        assert req.language is None
        with pytest.raises(ValueError):
            CaptureRequest.model_validate({'frequency': 100.5})

    def test_multichannel_limits(self):
        from schemas import MultiChannelRequest
        base = {'device_address': '192.168.10.2', 'center_freq': 146_000_000,
                'channels': [{'mode': 'aprs', 'frequency': 144_800_000}]}
        with pytest.raises(ValueError):
            MultiChannelRequest.model_validate(base)  # needs 2 channels
        with pytest.raises(ValueError):
            MultiChannelRequest.model_validate({**base, 'device_address': 'evil;rm'})
