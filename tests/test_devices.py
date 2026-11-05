"""Several SDRs: device list from sysfs, one lock per device, parallel jobs, per-device stop."""

import json
import subprocess
import time

import pytest
from flask.testing import FlaskClient

from radiomoni import config, devices, sdr_lock
from radiomoni.blueprints import sdr as sdr_blueprint
from radiomoni.decoders import external
from radiomoni.decoders.streaming import StreamSession
from radiomoni.redis_client import get_redis
from radiomoni.sdr_hardware import HackRFCapture, RTLSDRCapture, SDRType
from radiomoni.session_store import session_manager
from radiomoni.skimmer import session as skimmer_session

USB = {
    '1-1': ('1d50', '6089', 'a06063c8234e925f', 'HackRF One'),
    '1-2': ('0bda', '2838', '00000001', 'RTL2838UHIDIR'),
    '1-3': ('0bda', '2838', '00000001', 'RTL2838UHIDIR'),
    '2-1': ('03eb', '800c', '3b52ab5dac65f6d5', 'AIRSPY HF+'),
    '2-2': ('046d', 'c52b', None, 'Unifying Receiver'),        # not an SDR
}


@pytest.fixture
def usb(tmp_path, monkeypatch):
    """Fake /sys/bus/usb/devices with the given devices (default: all of USB)."""
    def build(entries=None):
        root = tmp_path / 'usb'
        root.mkdir(exist_ok=True)
        for name, (vid, pid, serial, product) in (USB if entries is None else entries).items():
            d = root / name
            d.mkdir()
            (d / 'idVendor').write_text(vid + '\n')
            (d / 'idProduct').write_text(pid + '\n')
            (d / 'product').write_text(product + '\n')
            if serial:
                (d / 'serial').write_text(serial + '\n')
            (root / f'{name}:1.0').mkdir()                         # an interface entry, skipped
        monkeypatch.setattr(config, 'SYSFS_USB_ROOT', str(root))
        devices.clear_cache()
        return {d.id: d for d in devices.list_devices()}
    return build


class TestDeviceList:
    def test_scan(self, usb):
        found = usb()
        assert list(found) == ['hackrf:a06063c8234e925f', 'airspyhf:3b52ab5dac65f6d5', 'rtlsdr:0', 'rtlsdr:1']
        rtl0, rtl1 = found['rtlsdr:0'], found['rtlsdr:1']
        assert rtl0.shared and not rtl0.serial_unique and rtl0.label == 'RTL-SDR #1'
        assert rtl0.args('rtl_sdr') == ['-d', '0'] and rtl1.args('rtl_433') == ['-d', '1']
        assert found['hackrf:a06063c8234e925f'].args('hackrf_transfer') == []       # the only HackRF

    def test_unique_rtl_serials(self, usb):
        found = usb({'1-2': ('0bda', '2838', 'RTL-A', 'x'), '1-3': ('0bda', '2838', 'RTL-B', 'x')})
        b = found['rtlsdr:RTL-B']
        assert b.args('rtl_sdr') == ['-d', 'RTL-B'] and b.args('rtl_433') == ['-d', ':RTL-B']
        assert b.args('readsb') == ['--device', 'RTL-B'] and b.args('rtl_ais') == ['-d', '1']

    def test_hackrf_running_from_ram_has_no_serial(self, usb):
        found = usb({'1-1': ('1d50', '6089', 'RunningFromRAM', 'HackRF One')})
        assert list(found) == ['hackrf:0'] and found['hackrf:0'].serial is None

    def test_two_hackrfs(self, usb):
        found = usb({'1-1': ('1d50', '6089', 'aaaa', 'HackRF One'), '1-2': ('1d50', '6089', 'bbbb', 'HackRF One')})
        assert found['hackrf:bbbb'].args('hackrf_transfer') == ['-d', 'bbbb']

    def test_resolve(self, usb):
        usb()
        assert devices.resolve('auto').id == 'hackrf:a06063c8234e925f'                 # HackRF > Airspy > RTL
        assert devices.resolve('rtlsdr').id == 'rtlsdr:0'
        assert devices.resolve(device_id='rtlsdr:1').index == 1
        assert devices.resolve('usrp', '192.168.10.2').id == 'usrp:192.168.10.2'
        assert devices.resolve(device_id='usrp:192.168.10.2').address == '192.168.10.2'
        with pytest.raises(ValueError, match='not connected'):
            devices.resolve(device_id='rtlsdr:9')
        with pytest.raises(ValueError, match='requires device_address'):
            devices.resolve('usrp')

    def test_no_sdr(self, usb, monkeypatch):
        usb({})
        monkeypatch.setattr(devices, 'detect_sdr', lambda *a, **k: SDRType.UNKNOWN)
        with pytest.raises(devices.NoSdrError):
            devices.resolve('auto')
        assert devices.default_id() == 'default'

    def test_fallback_without_sysfs(self, usb, monkeypatch):
        usb({})
        monkeypatch.setattr(devices, 'detect_sdr', lambda *a, **k: SDRType.HACKRF)
        assert devices.resolve('auto').id == 'hackrf:0' and devices.default_id() == 'hackrf:0'


class TestLocks:
    def test_one_lock_per_device(self, usb):
        usb()
        with sdr_lock.SdrLease('job-a', 'capture', device_id='rtlsdr:0'):
            with sdr_lock.SdrLease('job-b', 'vox', device_id='rtlsdr:1'):           # other device: fine
                held = sdr_lock.holders()
                assert set(held) == {'rtlsdr:0', 'rtlsdr:1'} and held['rtlsdr:1']['device_id'] == 'rtlsdr:1'
                with pytest.raises(sdr_lock.SdrBusyError, match='rtlsdr:0'):
                    sdr_lock.SdrLease('job-c', 'scan', device_id='rtlsdr:0').acquire()
                assert sdr_lock.current_holder() is None                            # default (HackRF) is free
                assert sdr_lock.find_holder('job-b')['device_id'] == 'rtlsdr:1'
        assert sdr_lock.holders() == {}

    def test_default_device_is_the_auto_device(self, usb):
        usb()
        with sdr_lock.SdrLease('job', 'capture'):
            assert sdr_lock.current_holder('hackrf:a06063c8234e925f')['owner'] == 'job'
            with pytest.raises(sdr_lock.SdrBusyError):                              # same device by its id
                sdr_lock.SdrLease('other', 'vox', device_id='hackrf:a06063c8234e925f').acquire()

    def test_force_release_one_device(self, usb):
        usb()
        sdr_lock.acquire('a', 'capture', device_id='rtlsdr:0')
        sdr_lock.acquire('b', 'capture', device_id='rtlsdr:1')
        sdr_lock.force_release('rtlsdr:0')
        assert set(sdr_lock.holders()) == {'rtlsdr:1'}
        sdr_lock.force_release()
        assert sdr_lock.holders() == {}

    def test_preemption_only_on_that_device(self, usb, monkeypatch):
        usb()
        stopped: list[str] = []

        def handler(holder, by_kind):
            stopped.append(holder['owner'])
            sdr_lock.release(holder['owner'], holder['device_id'])
        monkeypatch.setitem(sdr_lock._preempt_handlers, 'waterfall-test', handler)
        sdr_lock.acquire('wf-hackrf', 'waterfall-test', device_id='hackrf:a06063c8234e925f')
        sdr_lock.acquire('wf-rtl', 'waterfall-test', device_id='rtlsdr:0')
        with sdr_lock.SdrLease('vox', 'vox', device_id='rtlsdr:0'):
            assert stopped == ['wf-rtl']
            assert sdr_lock.current_holder('hackrf:a06063c8234e925f')['owner'] == 'wf-hackrf'

    def test_wait_until_free_per_device(self, usb):
        usb()
        sdr_lock.acquire('a', 'capture', device_id='rtlsdr:0')
        assert sdr_lock.wait_until_free(0.1, 'rtlsdr:1')
        assert not sdr_lock.wait_until_free(0.1, 'rtlsdr:0')


def fake_stream(monkeypatch):
    """Every streaming SDR process reads /dev/zero."""
    from radiomoni.decoders import cw, spectrum
    start = lambda self: subprocess.Popen(['cat', '/dev/zero'], stdout=subprocess.PIPE,  # noqa: E731
                                          stderr=subprocess.PIPE)
    for cls in (spectrum.SpectrumSession, cw.CwSession):
        monkeypatch.setattr(cls, '_start_sdr_capture', start)
    monkeypatch.setattr(HackRFCapture, 'is_available', lambda self: True)
    monkeypatch.setattr(RTLSDRCapture, 'is_available', lambda self: True)


def wait_for(cond, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError('condition not met in time')


class TestParallelJobs:
    def test_two_sessions_on_two_devices(self, client: FlaskClient, usb, monkeypatch):
        usb()
        fake_stream(monkeypatch)
        cw = client.post('/cw/start', json={'frequency': 14_025_000, 'device_id': 'hackrf:a06063c8234e925f'})
        assert cw.status_code == 200, cw.get_json()
        wf = client.post('/spectrum', json={'frequency': 145_000_000, 'sample_rate': 2_000_000,
                                            'device_id': 'rtlsdr:1'})
        assert wf.status_code == 200, wf.get_json()
        busy = client.post('/spectrum', json={'frequency': 145_000_000, 'sample_rate': 2_000_000,
                                              'device_id': 'rtlsdr:1'})
        assert busy.status_code == 409          # that device is taken (a waterfall does not preempt a waterfall)
        cw_sid, wf_sid = cw.get_json()['session_id'], wf.get_json()['session_id']
        try:
            wait_for(lambda: session_manager.get_session(cw_sid).status == 'running')
            assert session_manager.get_session(cw_sid).device_id == 'hackrf:a06063c8234e925f'
            assert session_manager.get_session(wf_sid).device_label == 'RTL-SDR #2'
            status = client.get('/sdr/devices').get_json()
            by_id = {d['id']: d for d in status['devices']}
            assert by_id['hackrf:a06063c8234e925f']['busy'] and by_id['rtlsdr:1']['preemptible']
            assert not by_id['rtlsdr:0']['busy'] and cw_sid in by_id['hackrf:a06063c8234e925f']['sessions']
            assert status['default'] == 'hackrf:a06063c8234e925f'
            legacy = client.get('/sdr/status').get_json()
            assert legacy['busy'] and legacy['holder']['kind'] == 'cw' and len(legacy['devices']) == 4
        finally:
            for sid in (cw_sid, wf_sid):
                client.delete(f'/stream-decode/{sid}')
            wait_for(lambda: sdr_lock.holders() == {}, 20)

    def test_unknown_device_is_400(self, client: FlaskClient, usb):
        usb()
        r = client.post('/cw/start', json={'frequency': 14_025_000, 'device_id': 'rtlsdr:7'})
        assert r.status_code == 400 and 'not connected' in r.get_json()['error']
        assert client.post('/cw/start', json={'frequency': 14_025_000, 'device_id': 'bad id'}).status_code == 400

    def test_ais_takes_a_free_rtl(self, usb, monkeypatch):
        usb()
        monkeypatch.setattr(external, 'tool_available', lambda d: True)
        sdr_lock.acquire('busy', 'capture', device_id='rtlsdr:0')
        ais = external.ExternalDecoderSession('ais', 60)
        assert ais.device.id == 'rtlsdr:1' and ais.build_command()[:3] == ['rtl_ais', '-d', '1']
        ism = external.ExternalDecoderSession('ism', 60, device_id='rtlsdr:0')
        assert ism.build_command()[:3] == ['rtl_433', '-d', '0']
        with pytest.raises(ValueError, match='requires'):
            external.ExternalDecoderSession('ais', 60, device_id='hackrf:a06063c8234e925f')


class TestForceStop:
    def test_only_the_given_device(self, client: FlaskClient, usb, monkeypatch):
        usb()
        killed: list = []
        monkeypatch.setattr(sdr_blueprint, 'kill_sdr_processes', lambda device_id=None: killed.append(device_id) or [])
        sessions = {}
        for device_id in ('rtlsdr:0', 'rtlsdr:1'):
            s = StreamSession('vox', 145_000_000, 60, 20, 2_000_000)
            s.status, s.device_id = 'running', device_id
            session_manager.save_session(s)
            sessions[device_id] = s.session_id
            sdr_lock.acquire(f'owner-{device_id}', 'vox', device_id=device_id)
        r = client.post('/sdr/force-stop?device_id=rtlsdr:0')
        assert r.status_code == 200 and killed == ['rtlsdr:0']
        assert set(sdr_lock.holders()) == {'rtlsdr:1'}
        assert session_manager.get_session(sessions['rtlsdr:0']).status == 'completed'
        assert session_manager.get_session(sessions['rtlsdr:1']).status == 'running'

    @pytest.mark.parametrize('exe, args, device_id, expected', [
        ('rtl_sdr', ['-d', '1', '-f', '145000000'], 'rtlsdr:1', True),
        ('rtl_sdr', ['-d', '0', '-f', '145000000'], 'rtlsdr:1', False),
        ('rtl_433', ['-d', '1', '-f', '433920000'], 'rtlsdr:1', True),
        ('hackrf_transfer', ['-r', '-'], 'hackrf:a06063c8234e925f', True),          # the only HackRF
        ('hackrf_transfer', ['-r', '-'], 'rtlsdr:1', False),
        ('direwolf', ['-r', '48000'], 'rtlsdr:1', False),                          # decoders end with their input
        ('direwolf', ['-r', '48000'], None, True),                                 # stop everything
    ])
    def test_process_matching(self, usb, exe, args, device_id, expected):
        usb()
        device = devices.resolve(device_id=device_id) if device_id else None
        assert sdr_blueprint._matches_device(exe, args, device) is expected


class TestSkimmerSessions:
    def test_spots_of_several_sessions_are_merged(self):
        r = get_redis()
        r.set(skimmer_session.SPOTS_KEY + 'a', json.dumps([{'callsign': 'DL1ABC', 'last_seen': 10}]))
        r.set(skimmer_session.SPOTS_KEY + 'b', json.dumps([{'callsign': 'HB9XYZ', 'last_seen': 20}]))
        spots = skimmer_session.load_spots()
        assert [(s['callsign'], s['session_id']) for s in spots] == [('HB9XYZ', 'b'), ('DL1ABC', 'a')]
