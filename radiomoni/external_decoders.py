"""
External decoders that drive the SDR themselves (N7):

- ADS-B aircraft  — readsb   (1090 MHz)
- AIS ships       — rtl_ais  (161.975 / 162.025 MHz)
- ISM sensors     — rtl_433  (433.92 / 868 MHz weather stations, meters, ...)

readsb (built in the image) supports RTL-SDR and HackRF; rtl_ais and rtl_433
(Debian packages) only RTL-SDR dongles. Output is parsed into documents that
are stored, published live and checked against alert rules.
"""

import json
import logging
import os
import select
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import IO, Any, Optional

from radiomoni import alerts
from radiomoni import events
from radiomoni.sdr_hardware import RTLSDRCapture, SDRType, detect_sdr
from radiomoni.streaming_decoder_service import BaseStreamingDecoder, SessionManager

logger = logging.getLogger(__name__)

DEFAULT_FREQUENCIES = {'adsb': 1_090_000_000, 'ais': 162_000_000, 'ism': 433_920_000}
TOOLS = {'adsb': 'readsb', 'ais': 'rtl_ais', 'ism': 'rtl_433'}
SUPPORTED_SDRS = {
    'adsb': (SDRType.RTLSDR, SDRType.HACKRF),
    'ais': (SDRType.RTLSDR,),
    'ism': (SDRType.RTLSDR,),
}
SDR_NAMES = {SDRType.RTLSDR: 'RTL-SDR', SDRType.HACKRF: 'HackRF'}
# ADS-B: store a position at most every N seconds per aircraft (keeps the index small)
ADSB_STORE_INTERVAL = 30


def tool_available(decoder: str) -> bool:
    return shutil.which(TOOLS[decoder]) is not None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =========================================================================== parsers
def parse_rtl433_line(line: str) -> Optional[dict[str, Any]]:
    """rtl_433 -F json emits one JSON object per line."""
    line = line.strip()
    if not line.startswith('{'):
        return None
    try:
        data = json.loads(line)
    except ValueError:
        return None
    if not isinstance(data, dict) or 'model' not in data:
        return None
    doc: dict[str, Any] = {'uuid': str(uuid.uuid4()), 'timestamp': _now()}
    for key, value in data.items():
        if key == 'time':
            doc['device_time'] = value
        elif isinstance(value, (str, int, float, bool)) or value is None:
            doc[key.replace(' ', '_')] = value
    doc['sensor_id'] = f"{data.get('model')}:{data.get('id', '?')}:{data.get('channel', '')}"
    return doc


def parse_readsb_aircraft(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert readsb aircraft.json into a list of normalized aircraft docs."""
    out = []
    for ac in payload.get('aircraft', []):
        if not isinstance(ac, dict) or not ac.get('hex'):
            continue
        if float(ac.get('seen', 0) or 0) > 60:
            continue
        out.append({
            'icao': str(ac['hex']).upper(),
            'flight': (ac.get('flight') or '').strip() or None,
            'altitude_ft': ac.get('alt_baro') if isinstance(ac.get('alt_baro'), (int, float)) else None,
            'ground_speed_kt': ac.get('gs'),
            'track': ac.get('track'),
            'vertical_rate': ac.get('baro_rate'),
            'squawk': ac.get('squawk'),
            'category': ac.get('category'),
            'latitude': ac.get('lat'),
            'longitude': ac.get('lon'),
            'rssi': ac.get('rssi'),
            'messages': ac.get('messages'),
            'seen': ac.get('seen'),
        })
    return out


class AisAssembler:
    """Reassemble multi-part !AIVDM sentences and decode them with pyais."""

    def __init__(self) -> None:
        self._parts: dict[str, list[str]] = {}

    def feed(self, line: str) -> Optional[dict[str, Any]]:
        line = line.strip()
        if not line.startswith(('!AIVDM', '!AIVDO')):
            return None
        fields = line.split(',')
        if len(fields) < 7:
            return None
        try:
            total, number = int(fields[1]), int(fields[2])
        except ValueError:
            return None
        key = fields[3] or 'single'
        if total > 1:
            self._parts.setdefault(key, []).append(line)
            if number < total:
                return None
            parts = self._parts.pop(key, [])
            if len(parts) != total:
                return None
        else:
            parts = [line]
        return decode_ais(parts)


def decode_ais(parts: list[str]) -> Optional[dict[str, Any]]:
    try:
        from pyais import decode
        msg = decode(*[p.encode() for p in parts])
        data = msg.asdict()
    except Exception as e:
        logger.debug(f"AIS decode failed: {e}")
        return None
    doc: dict[str, Any] = {'uuid': str(uuid.uuid4()), 'timestamp': _now(), 'raw': ' '.join(parts)}
    for key in ('msg_type', 'mmsi', 'speed', 'course', 'heading', 'status', 'shipname', 'callsign',
                'ship_type', 'destination', 'imo', 'turn'):
        value = data.get(key)
        if value is None:
            continue
        doc[key] = value.value if hasattr(value, 'value') else value
        if isinstance(doc[key], str):
            doc[key] = doc[key].strip('@ ').strip() or None
    lat, lon = data.get('lat'), data.get('lon')
    # 91/181 mean "not available" in AIS
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and abs(lat) <= 90 and abs(lon) <= 180:
        doc['latitude'], doc['longitude'] = float(lat), float(lon)
    if 'mmsi' in doc:
        doc['mmsi'] = str(doc['mmsi'])
    return doc


# =========================================================================== session
class ExternalDecoderSession(BaseStreamingDecoder):
    """Runs one external decoder tool for the session duration."""

    def __init__(self, decoder: str, duration: int, gain: Optional[int] = None,
                 frequency: Optional[int] = None, ppm: int = 0):
        if decoder not in TOOLS:
            raise ValueError(f"Unknown decoder: {decoder}")
        freq = frequency if (decoder == 'ism' and frequency) else DEFAULT_FREQUENCIES[decoder]
        super().__init__(frequency=freq, duration=duration, gain=gain if gain is not None else -1,
                         sample_rate=2_000_000)
        self.decoder = decoder
        self.ppm = ppm
        self.auto_gain = gain is None
        if not tool_available(decoder):
            raise RuntimeError(f"{TOOLS[decoder]} is not installed")
        self.sdr_type = self._pick_sdr(decoder)
        self._workdir: Optional[str] = None
        self._last_stored: dict[str, float] = {}

    @staticmethod
    def _pick_sdr(decoder: str) -> SDRType:
        """Use the detected SDR if the tool supports it. Auto-detection prefers a
        HackRF, so for RTL-SDR-only tools also look for a dongle next to it."""
        supported = SUPPORTED_SDRS[decoder]
        detected = detect_sdr()
        if detected in supported:
            return detected
        if SDRType.RTLSDR in supported and RTLSDRCapture(frequency=100_000_000).is_available():
            return SDRType.RTLSDR
        names = ' or '.join(SDR_NAMES[t] for t in supported)
        raise ValueError(f"{decoder.upper()} decoding requires {names} (detected: {detected.value})")

    def _get_mode(self) -> str:
        return self.decoder

    def _start_decoder(self) -> subprocess.Popen[bytes]:  # pragma: no cover - not used
        raise NotImplementedError

    def _parse_decoder_line(self, line: str) -> Optional[dict[str, Any]]:
        if self.decoder == 'ism':
            return parse_rtl433_line(line)
        return None

    def _index_packet(self, packet: dict[str, Any]) -> None:
        try:
            from radiomoni.storage import get_storage
            get_storage().index_event(self.decoder, packet)
        except Exception as e:
            logger.warning(f"Could not store {self.decoder} document: {e}")

    def build_command(self) -> list[str]:
        if self.decoder == 'ism':
            cmd = ['rtl_433', '-f', str(self.frequency), '-F', 'json', '-M', 'time:iso:utc', '-M', 'level',
                   '-p', str(self.ppm)]
            if not self.auto_gain:
                cmd += ['-g', str(self.gain)]
            return cmd
        if self.decoder == 'ais':
            cmd = ['rtl_ais', '-n', '-p', str(self.ppm)]
            if not self.auto_gain:
                cmd += ['-g', str(self.gain)]
            return cmd
        # adsb
        self._workdir = tempfile.mkdtemp(prefix='readsb-')
        cmd = ['readsb', '--quiet', '--write-json', self._workdir, '--write-json-every', '2']
        if self.sdr_type == SDRType.HACKRF:
            cmd += ['--device-type', 'hackrf']
            # No AGC on the HackRF: without a gain readsb uses LNA 40 dB / VGA 48 dB.
            # Otherwise the same mapping as the IQ streams: LNA in 8 dB steps, VGA = gain.
            if not self.auto_gain:
                cmd += ['--gain', str(min(40, round(self.gain / 8) * 8)),
                        '--hackrf-vgagain', str(min(62, self.gain // 2 * 2))]
            return cmd
        return cmd + ['--device-type', 'rtlsdr', '--ppm', str(self.ppm),
                      '--gain', 'auto' if self.auto_gain else str(self.gain)]

    def _stream_worker_simple(self, session_manager: SessionManager) -> None:
        assert self.session is not None
        try:
            self.session.status = 'running'
            session_manager.save_session(self.session)
            cmd = self.build_command()
            logger.info(f"Starting {self.decoder} decoder: {cmd}")
            self.sdr_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             start_new_session=True)
            if self.decoder == 'adsb':
                self._poll_readsb(session_manager)
            else:
                self._read_lines(self.sdr_proc.stdout, session_manager)
            if self.sdr_proc.poll() not in (None, 0) and not self.stop_event.is_set():
                err = (self.sdr_proc.stderr.read() if self.sdr_proc.stderr else b'').decode(errors='ignore')
                raise RuntimeError(f"{TOOLS[self.decoder]} exited: {err.strip()[-300:] or 'see log'}")
        except Exception as e:
            logger.error(f"{self.decoder} session failed: {e}", exc_info=True)
            self.session.status = 'failed'
            self.session.error = str(e)
            session_manager.save_session(self.session)
        finally:
            self._cleanup()
            if self._workdir:
                shutil.rmtree(self._workdir, ignore_errors=True)
            self._finish_session(session_manager)

    def _deadline_reached(self, started: float) -> bool:
        return bool(self.duration) and time.time() - started >= self.duration

    def _handle(self, doc: dict[str, Any], session_manager: SessionManager) -> None:
        assert self.session is not None
        doc['session_id'] = self.session.session_id
        doc.setdefault('frequency', int(self.frequency))
        self._index_packet(doc)
        events.publish(self.decoder, doc)
        alerts.evaluate(self.decoder, doc)
        self.session.packet_count += 1
        self.session.last_packet_time = datetime.now(timezone.utc)

    def _read_lines(self, stream: Optional[IO[bytes]], session_manager: SessionManager) -> None:
        assert stream is not None and self.session is not None
        assembler = AisAssembler()
        started = last_save = time.time()
        while not self.stop_event.is_set() and not self._deadline_reached(started):
            ready, _, _ = select.select([stream], [], [], 1.0)
            if not ready:
                if self.sdr_proc and self.sdr_proc.poll() is not None:
                    break
                continue
            raw = stream.readline()
            if not raw:
                break
            line = raw.decode('utf-8', errors='ignore')
            doc = parse_rtl433_line(line) if self.decoder == 'ism' else assembler.feed(line)
            if doc:
                self._handle(doc, session_manager)
            if time.time() - last_save > 5:
                session_manager.save_session(self.session)
                last_save = time.time()

    def _poll_readsb(self, session_manager: SessionManager) -> None:
        assert self.session is not None and self._workdir is not None
        path = os.path.join(self._workdir, 'aircraft.json')
        started = time.time()
        while not self.stop_event.wait(2.0) and not self._deadline_reached(started):
            if self.sdr_proc and self.sdr_proc.poll() is not None:
                break
            try:
                with open(path) as f:
                    aircraft = parse_readsb_aircraft(json.load(f))
            except (OSError, ValueError):
                continue
            events.publish('adsb_snapshot', {'session_id': self.session.session_id, 'aircraft': aircraft})
            now = time.time()
            for ac in aircraft:
                if now - self._last_stored.get(ac['icao'], 0) < ADSB_STORE_INTERVAL:
                    continue
                self._last_stored[ac['icao']] = now
                self._handle({'uuid': str(uuid.uuid4()), 'timestamp': _now(), **ac}, session_manager)
            session_manager.save_session(self.session)

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)
