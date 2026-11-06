"""SDRplay RSP: device list, sdrplay_rx command line, RSPduo master/slave and its dependency rules."""

import subprocess
import time

import numpy as np
import pytest
from flask.testing import FlaskClient

from radiomoni import config, devices, sdr_lock, sdrplay
from radiomoni.decoders.streaming import StreamSession
from radiomoni.sdr_hardware import SDRType, SdrplayCapture, get_sdr_instance
from radiomoni.session_store import session_manager

from tests.test_devices import usb  # noqa: F401 - fixture

DUO = {'1-4': ('1df7', '3020', '1811000E5D', 'RSPduo')}
A, B = 'sdrplay:1811000E5D:A', 'sdrplay:1811000E5D:B'


def opts(cmd: list[str], flag: str) -> list[str]:
    return [cmd[i + 1] for i, a in enumerate(cmd) if a == flag]


class TestDevices:
    def test_rspduo_is_two_devices(self, usb):  # noqa: F811
        found = usb({**DUO, '1-5': ('1df7', '3000', '2207AB', 'RSP1A')})
        assert list(found) == [A, B, 'sdrplay:2207AB']
        assert found[A].label == 'RSPduo Tuner A' and found[B].tuner == 'B'
        assert found['sdrplay:2207AB'].label == 'RSP1A' and found['sdrplay:2207AB'].tuner is None
        assert found[B].args('sdrplay_rx') == ['--device', '1811000E5D:B']
        assert devices.resolve('sdrplay').id == A
        assert devices.resolve('auto').id == A                # the only SDR

    def test_auto_prefers_the_others(self, usb):  # noqa: F811
        usb({**DUO, '1-1': ('1d50', '6089', 'aa11', 'HackRF One')})
        assert devices.resolve('auto').type == SDRType.HACKRF


class TestCommand:
    def test_master_on_tuner_a_hf(self, monkeypatch):
        cmd, facts = sdrplay.command(['--device', '1811000E5D:A'], 7_030_000, 2_000_000, 40, samples=100)
        assert cmd[:5] == ['sdrplay_rx', '--device', '1811000E5D:A', '--mode', 'MA']
        assert opts(cmd, '--antenna') == ['Tuner 1 Hi-Z'] and 'rfnotch_ctrl=true' in opts(cmd, '--setting')
        assert opts(cmd, '-f') == ['7030000'] and opts(cmd, '-n') == ['100'] and opts(cmd, '-o') == ['-']
        assert '--agc' in cmd and facts == {'sdrplay_mode': 'MA', 'antenna': 'Tuner 1 Hi-Z'}
        assert int(opts(cmd, '--lna')[0]) <= 4                         # Hi-Z port: states 0–4

    def test_slave_when_the_other_tuner_runs(self):
        sdr_lock.acquire('master-job', 'skimmer', device_id=A)
        cmd, facts = sdrplay.command(['--device', '1811000E5D:B'], 14_025_000, 2_000_000, 30)
        assert facts['sdrplay_mode'] == 'SL' and opts(cmd, '--antenna') == ['Tuner 2 50 ohm']
        assert 'biasT_ctrl=false' in opts(cmd, '--setting')

    def test_vhf_and_single_rsp(self, monkeypatch):
        cmd, facts = sdrplay.command(['--device', '1811000E5D:A'], 144_800_000, 2_000_000, 76)
        assert opts(cmd, '--antenna') == ['Tuner 1 50 ohm'] and opts(cmd, '--lna') == ['0']
        assert not any('notch' in s for s in opts(cmd, '--setting'))
        cmd, facts = sdrplay.command(['--device', '2207AB'], 433_920_000, 6_000_000, 0)
        assert facts['sdrplay_mode'] == 'ST' and '--antenna' not in cmd and opts(cmd, '--lna') == ['9']
        monkeypatch.setattr(config, 'SDRPLAY_NOTCH', 'on')
        monkeypatch.setattr(config, 'SDRPLAY_HIZ', False)
        monkeypatch.setattr(config, 'SDRPLAY_AGC', False)
        cmd, _ = sdrplay.command(['--device', '1811000E5D:A'], 7_030_000, 2_000_000, 30)
        assert opts(cmd, '--antenna') == ['Tuner 1 50 ohm'] and '--agc' not in cmd
        assert {'rfnotch_ctrl=true', 'dabnotch_ctrl=true'} <= set(opts(cmd, '--setting'))

    @pytest.mark.parametrize('gain, frequency, hiz, state', [
        (76, 7_000_000, False, 0), (0, 7_000_000, False, 6), (0, 7_000_000, True, 4),
        (0, 145_000_000, False, 9), (0, 1_296_000_000, False, 8), (38, 145_000_000, False, 4)])
    def test_lna_state(self, gain, frequency, hiz, state):
        assert sdrplay.lna_state(gain, frequency, hiz) == state


class TestMasterSlave:
    def test_dependents_and_preemption(self, monkeypatch):
        stopped: list[str] = []
        monkeypatch.setitem(sdr_lock._preempt_handlers, 'wf-test',
                            lambda holder, by: stopped.append(holder['owner']))
        sdr_lock.acquire('waterfall', 'wf-test', device_id=A)
        sdr_lock.annotate(A, {'sdrplay_mode': 'MA'})
        assert sdrplay.dependents(A) == []                      # no slave yet
        sdr_lock.acquire('skimmer', 'skimmer', device_id=B)
        sdr_lock.annotate(B, {'sdrplay_mode': 'SL'})
        assert [h['owner'] for h in sdrplay.dependents(A)] == ['skimmer']
        assert sdrplay.dependents(B) == []                      # a slave has no dependents
        with pytest.raises(sdr_lock.SdrBusyError):              # the master waterfall does not give way
            sdr_lock.SdrLease('vox', 'vox', device_id=A).acquire()
        assert stopped == []
        assert sdr_lock.current_holder(A)['details']['sdrplay_mode'] == 'MA'

    def test_stopping_the_master_needs_force(self, client: FlaskClient, usb):  # noqa: F811
        usb(DUO)
        sessions = {}
        for device_id, mode in ((A, 'MA'), (B, 'SL')):
            s = StreamSession('skimmer', 14_035_000, 0, 30, 2_000_000)
            s.status, s.device_id = 'running', device_id
            session_manager.save_session(s)
            sessions[device_id] = s.session_id
            sdr_lock.acquire(f'stream:{device_id}', 'skimmer', device_id=device_id)
            sdr_lock.annotate(device_id, {'sdrplay_mode': mode})
        r = client.delete(f'/stream-decode/{sessions[A]}')
        assert r.status_code == 409
        assert r.get_json()['dependent_sessions'] == [sessions[B]] and r.get_json()['dependent_devices'] == [B]
        assert client.delete(f'/stream-decode/{sessions[B]}').status_code == 200    # the slave: no question
        assert client.delete(f'/stream-decode/{sessions[A]}?force=1').status_code == 200


class TestCapture:
    def test_tuner_rate_limit(self):
        duo = get_sdr_instance(145_000_000, 8_000_000, 30, SDRType.SDRPLAY, device_args=['--device', 'S:A'])
        assert isinstance(duo, SdrplayCapture) and duo.sample_rate == 2_000_000
        single = get_sdr_instance(145_000_000, 8_000_000, 30, SDRType.SDRPLAY, device_args=['--device', 'S'])
        assert single.sample_rate == 8_000_000
        with pytest.raises(ValueError, match='does not support'):
            get_sdr_instance(2_500_000_000, 2_000_000, 30, SDRType.SDRPLAY)

    def test_capture_iq_reads_int16(self, monkeypatch, tmp_path):
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            out = cmd[cmd.index('-o') + 1]
            np.array([16384, -16384] * 1000, dtype=np.int16).tofile(out)
            return subprocess.CompletedProcess(cmd, 0, '', '')
        monkeypatch.setattr(subprocess, 'run', fake_run)
        cap = get_sdr_instance(7_030_000, 2_000_000, 30, SDRType.SDRPLAY, device_args=['--device', 'S:A'])
        cap.capture_iq(1, str(tmp_path / 'x.iq'))
        iq = np.fromfile(tmp_path / 'x.iq', dtype=np.complex64)
        assert len(iq) == 1000 and iq[0] == pytest.approx(0.5 - 0.5j)
        assert calls[0][0] == 'sdrplay_rx' and opts(calls[0], '-n') == ['2000000']

    def test_stream_command_and_conversion(self, usb, monkeypatch, mock_sdr_hardware):  # noqa: F811
        from radiomoni.decoders import spectrum
        usb(DUO)
        started: list[list[str]] = []

        class FakeProc:
            stdout = None
            pid = 4242

        monkeypatch.setattr(subprocess, 'Popen', lambda cmd, **kw: started.append(cmd) or FakeProc())
        s = spectrum.SpectrumSession(145_000_000, 8_000_000, 30, 60, device_id=B)
        assert s.sample_rate == 2_000_000                       # an RSPduo tuner: 2 MS/s
        s._start_sdr_capture()
        assert started[0][:5] == ['sdrplay_rx', '--device', '1811000E5D:B', '--mode', 'MA']
        raw = np.array([32767, 0, 0, -32768], dtype=np.int16).tobytes()
        iq = s._bytes_to_iq(raw)
        assert iq[0] == pytest.approx(1.0, abs=1e-3) and iq[1] == pytest.approx(-1j, abs=1e-3)


def test_annotate_keeps_the_ttl():
    from radiomoni.redis_client import get_redis
    sdr_lock.acquire('a', 'capture', device_id=A)
    time.sleep(0.01)
    assert sdr_lock.annotate(A, {'sdrplay_mode': 'MA'}) and not sdr_lock.annotate(B, {'x': 1})
    assert 0 < get_redis().ttl(sdr_lock.LOCK_PREFIX + A) <= sdr_lock.LOCK_TTL
