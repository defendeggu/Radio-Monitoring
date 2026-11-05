"""
Contest skimmer session (mode "skimmer"): one band segment, all its CW signals.

    SDR ─► blank? (N1MM+ IsTransmitting, ADC clipping) ─► Mixer → Decimator (segment)
              ├─► SpectrumTap (waterfall of the segment)      ├─► IqRecorder (optional)
              └─► SkimmerCore ─► spot ─► engine.classify (contest, worked log)
                                      ├─► spot list (Redis, GET /skimmer/spots)
                                      ├─► DX cluster (N1MM+ bandmap) ├─► event "skimmer"
                                      ├─► index radio-skimmer-*     └─► alerts (priority high)

The SDR is tuned beside the segment on zero-IF receivers (DC spike), like the
CW session. With include_rbn the RBN spots of the contest bands go to the
cluster as well (only where the contest category allows assistance).
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray

from radiomoni import alerts
from radiomoni import config
from radiomoni import events
from radiomoni.contest import engine
from radiomoni.contest import refdata as refdata_module
from radiomoni.contest import rules as rules_module
from radiomoni.decoders import spectrum
from radiomoni.decoders.cw import SAMPLE_RATES
from radiomoni.decoders.streaming import BaseStreamingDecoder, SessionManager
from radiomoni.dsp import Decimator, Mixer
from radiomoni.rbn import SpotBook
from radiomoni.redis_client import get_redis
from radiomoni.sdr_hardware import SDRType, detect_sdr, get_sdr_instance
from radiomoni.skimmer.core import SkimmerCore
from radiomoni.skimmer.recorder import IqRecorder

logger = logging.getLogger(__name__)

CHUNK_SECONDS = 0.05
EDGE = 0.45
CLIP_LEVEL = 0.98            # |I| or |Q| of the normalised samples
CLIP_FRACTION = 0.005        # share of clipped samples that blanks a chunk
SPOTS_KEY = 'skimmer:spots'
SPOTS_TTL = 3600
RBN_FORWARD_S = 10.0

# CW segments of the IARU Region 1 HF band plan (same as frontend/src/lib/bands.ts), Hz
CW_SEGMENTS: dict[str, tuple[int, int]] = {
    '160m': (1_810_000, 1_838_000), '80m': (3_500_000, 3_570_000), '60m': (5_351_500, 5_354_000),
    '40m': (7_000_000, 7_040_000), '30m': (10_100_000, 10_130_000), '20m': (14_000_000, 14_070_000),
    '17m': (18_068_000, 18_095_000), '15m': (21_000_000, 21_070_000), '12m': (24_890_000, 24_915_000),
    '10m': (28_000_000, 28_070_000),
}


def segment_rate(width_hz: int) -> int:
    """IQ rate for a segment of `width_hz`: some headroom for the filter edges."""
    return int(width_hz * 1.3)


def load_spots() -> list[dict[str, Any]]:
    raw = get_redis().get(SPOTS_KEY)
    return json.loads(raw) if raw else []


class SkimmerSession(BaseStreamingDecoder):
    def __init__(self, freq_low: int, freq_high: int, gain: int, duration: int = 0, mode: str = 'CW',
                 contest: Optional[str] = None, max_decoders: int = 24, sample_rate: Optional[int] = None,
                 record_iq: bool = False, include_rbn: bool = False, device_type: Optional[str] = None,
                 device_address: Optional[str] = None, output_dir: str = './recordings'):
        if mode != 'CW':
            raise ValueError('Only CW is supported so far (SSB follows after the phase 0 evaluation)')
        sdr_type = detect_sdr(preferred_type=device_type, device_address=device_address)
        if sdr_type == SDRType.UNKNOWN:
            raise ValueError("No SDR hardware detected")
        rate = int(sample_rate or SAMPLE_RATES.get(sdr_type, 1_000_000))
        if sdr_type == SDRType.HACKRF:
            rate = max(rate, 2_000_000)
        self.freq_low, self.freq_high = int(freq_low), int(freq_high)
        width = self.freq_high - self.freq_low
        self.seg_centre = (self.freq_low + self.freq_high) // 2
        self.dc_offset = int(rate / 4) if sdr_type in (SDRType.HACKRF, SDRType.RTLSDR) else 0
        if width / 2 + self.dc_offset > EDGE * rate:
            raise ValueError(f'Segment of {width / 1000:.0f} kHz is too wide for {rate / 1000:.0f} kS/s')
        super().__init__(self.seg_centre + self.dc_offset, duration, gain, rate)
        self.sdr_type = sdr_type
        self.device_address = device_address
        get_sdr_instance(frequency=int(self.frequency), sample_rate=rate, gain=gain, sdr_type=sdr_type,
                         device_address=device_address)
        self.mode = mode
        self.contest = rules_module.get(contest).id if contest else engine.active_contest().id
        self.max_decoders = max_decoders
        self.record_iq = record_iq
        self.include_rbn = include_rbn
        self.output_dir = output_dir
        self.mixer = Mixer(rate, self.seg_centre - self.frequency)
        self.decimator = Decimator(rate, segment_rate(width), bandwidth_hz=width * 1.1)
        self.seg_rate = self.decimator.output_rate
        refdata = refdata_module.get()
        self.core = SkimmerCore(self.seg_rate, self.seg_centre, max_decoders, on_spot=self._on_spot,
                                validate=self._validator(refdata))
        self.book = SpotBook()
        self.tap: Optional[spectrum.SpectrumTap] = None
        self.recorder: Optional[IqRecorder] = None
        self.blanked = False
        self.blanked_seconds = 0.0
        self._tx_checked = 0.0
        self._tx = False
        self._last_flush = 0.0
        self._last_rbn = time.time()
        self.spot_count = 0
        self._data_time: Optional[float] = None    # time of the IQ (start + samples / rate) for the core

    @staticmethod
    def _validator(refdata: refdata_module.RefData) -> Any:
        def validate(call: str) -> tuple[bool, Optional[bool]]:
            if len(refdata.cty) and refdata.cty.lookup(call) is None:
                return False, None
            return True, (call in refdata.scp) if len(refdata.scp) else None
        return validate

    # abstract members (no external decoder process)
    def _start_decoder(self) -> Any:  # pragma: no cover - not used
        raise NotImplementedError

    def _parse_decoder_line(self, line: str) -> Optional[dict[str, Any]]:  # pragma: no cover
        return None

    def _index_packet(self, packet: dict[str, Any]) -> None:  # pragma: no cover
        pass

    def _get_mode(self) -> str:
        return 'skimmer'

    def state(self) -> dict[str, Any]:
        return {
            'session_id': self.session.session_id if self.session else None, 'mode': 'skimmer',
            'centre': int(self.seg_centre), 'span': int(self.seg_rate), 'channel': None, 'tunable': False,
            'freq_low': self.freq_low, 'freq_high': self.freq_high, 'contest': self.contest,
            'skimmer_mode': self.mode, 'sdr_type': self.sdr_type.value, 'max_decoders': self.max_decoders,
            'decoders': self.core.state(), 'blanked': self.blanked, 'blanked_seconds': round(self.blanked_seconds),
            'spots': self.spot_count, 'include_rbn': self.include_rbn,
            'recording': self.recorder.info() if self.recorder else None,
        }

    def _publish_state(self) -> None:
        if self.session is None:
            return
        state = self.state()
        spectrum.save_state(self.session.session_id, state)
        spectrum.publish(self.session.session_id, spectrum.pack_json({'state': state}))

    # ------------------------------------------------------------------ pipeline
    def _stream_worker_simple(self, session_manager: SessionManager) -> None:
        assert self.session is not None
        sid = self.session.session_id
        flags = spectrum._Flags(sid)
        self.tap = spectrum.SpectrumTap(sid, self.seg_centre, int(self.seg_rate), fft_size=4096, flags=flags)
        if self.record_iq:
            from radiomoni.services import recording_dir
            self.recorder = IqRecorder(os.path.join(recording_dir(), 'skimmer'), self.seg_centre, self.seg_rate,
                                       self.freq_low, self.freq_high, sid)
        try:
            self.session.status = 'running'
            self.session.frequency = self.seg_centre
            session_manager.save_session(self.session)
            self._publish_state()
            self.sdr_proc = self._start_sdr_capture()
            self._run(session_manager)
        except Exception as e:
            logger.error(f"Skimmer session failed: {e}", exc_info=True)
            self.session.status = 'failed'
            self.session.error = str(e)
            session_manager.save_session(self.session)
        finally:
            if self.recorder:
                self.recorder.close()
            self._flush(force=True)
            self.session.packet_count = self.spot_count
            self._cleanup()
            self._finish_session(session_manager)
            spectrum.publish(sid, spectrum.pack_json({'end': self.session.status, 'reason': self.session.error}))

    def _run(self, session_manager: SessionManager) -> None:
        assert self.sdr_proc is not None and self.sdr_proc.stdout is not None and self.session is not None
        bytes_per_value = 2 if self.sdr_type in (SDRType.AIRSPYHF, SDRType.USRP) else 1
        chunk_bytes = int(self.sample_rate * CHUNK_SECONDS) * 2 * bytes_per_value
        started = self.session.start_time.timestamp()
        last_save = last_state = time.time()
        while not self.stop_event.is_set():
            if self.duration and time.time() - started >= self.duration:
                return
            raw = self._read_with_timeout(self.sdr_proc.stdout, chunk_bytes, timeout=5.0)
            if not raw:
                logger.info("Skimmer: SDR stream ended")
                return
            self.process_chunk(self._bytes_to_iq(raw))
            now = time.time()
            if now - last_state > 2:
                self._publish_state()
                last_state = now
            if now - last_save > 5:
                self.session.packet_count = self.spot_count
                session_manager.save_session(self.session)
                last_save = now
            if self.include_rbn and now - self._last_rbn >= RBN_FORWARD_S:
                self._forward_rbn(now)

    def _transmitting(self) -> bool:
        if not config.N1MM_ENABLED:
            return False
        now = time.monotonic()
        if now - self._tx_checked >= 0.25:
            self._tx_checked = now
            try:
                from radiomoni.integrations import n1mm
                self._tx = n1mm.is_transmitting()
            except Exception:
                self._tx = False
        return self._tx

    def process_chunk(self, iq: NDArray[np.complex64], now: Optional[float] = None) -> None:
        """One SDR chunk (public for tests)."""
        clipped = np.mean((np.abs(iq.real) >= CLIP_LEVEL) | (np.abs(iq.imag) >= CLIP_LEVEL)) > CLIP_FRACTION
        segment = self.decimator.process(self.mixer.process(iq))
        if self.tap is not None:
            self.tap.feed(segment)
        if self.recorder is not None:
            self.recorder.write(segment)
        if now is None:                           # the core runs on IQ time, not on the wall clock
            if self._data_time is None:
                self._data_time = time.time()
            now = self._data_time
            self._data_time += len(iq) / self.sample_rate
        self.blanked = bool(clipped) or self._transmitting()
        if self.blanked:
            self.blanked_seconds += len(iq) / self.sample_rate
            return
        self.core.feed(segment, now)
        self._flush()

    # ------------------------------------------------------------------ spots
    def _on_spot(self, spot: dict[str, Any], source: str = 'skimmer', spotter: Optional[str] = None) -> None:
        info = engine.classify(spot['callsign'], spot['frequency'], self.mode, rules_module.get(self.contest))
        if info['priority'] == 'invalid':
            return
        now = time.time()
        full = {**spot, **info, 'source': source, 'spotter': spotter or f'{config.SKIMMER_CALLSIGN}-#'}
        entry = self.book.add({'callsign': full['callsign'], 'khz': full['frequency'] / 1000.0,
                               'frequency': full['frequency'], 'band': info['band'], 'mode': self.mode,
                               'snr_db': int(round(full.get('snr_db') or 0)), 'wpm': full.get('wpm'),
                               'type': full.get('type', 'CQ'), 'spotter': full['spotter']}, now)
        entry.update({k: info[k] for k in ('country', 'adif', 'continent', 'cq_zone', 'itu_zone', 'wpx', 'in_scp',
                                           'portable', 'swiss', 'dupe', 'new_mults', 'rank', 'rare', 'priority',
                                           'in_contest')})
        entry['sources'] = sorted(set(entry.get('sources', [])) | {source})
        entry['source'] = 'skimmer' if 'skimmer' in entry['sources'] else 'rbn'
        if source == 'skimmer':
            self.spot_count += 1
        try:
            from radiomoni.integrations import cluster
            cluster.publish_spot(full, spotter=(spotter or config.SKIMMER_CALLSIGN).removesuffix('-#'))
        except Exception as e:
            logger.debug(f"Cluster spot not sent: {e}")
        sid = self.session.session_id if self.session else None
        doc = {'uuid': str(uuid.uuid4()), 'timestamp': datetime.now(timezone.utc).isoformat(), 'session_id': sid,
               'callsign': full['callsign'], 'frequency': full['frequency'], 'frequency_mhz': full['frequency'] / 1e6,
               'band': info['band'], 'mode': self.mode, 'source': source, 'spotter': full['spotter'],
               'snr_db': full.get('snr_db'), 'wpm': full.get('wpm'), 'type': full.get('type'),
               'contest': self.contest, 'country': info['country'], 'continent': info['continent'],
               'cq_zone': info['cq_zone'], 'itu_zone': info['itu_zone'], 'priority': info['priority'],
               'new_mults': [m['label'] for m in info['new_mults']], 'rare': info['rare'], 'rank': info['rank'],
               'dupe': info['dupe'], 'in_scp': info['in_scp']}
        events.publish('skimmer', doc)
        if source == 'skimmer':
            try:
                from radiomoni.storage.base import get_storage
                get_storage().index_event('skimmer', dict(doc))
            except Exception as e:
                logger.warning(f"Could not store skimmer spot: {e}")
        if info['priority'] == 'high':
            alerts.evaluate('skimmer', {'callsign': full['callsign'], 'frequency': full['frequency'],
                                        'text': engine.describe(info) or full.get('type', ''),
                                        'priority': info['priority'], 'band': info['band']})
        self._flush(force=True)

    def _forward_rbn(self, now: float) -> None:
        """New RBN spots on the bands of the contest → classified, into the list and the cluster."""
        since, self._last_rbn = self._last_rbn, now
        try:
            from radiomoni import rbn
            spots = rbn.load_spots()
        except Exception:
            return
        bands = set(rules_module.get(self.contest).bands)
        for s in spots:
            if s.get('first_seen', 0) <= since or s.get('band') not in bands:
                continue
            self._on_spot({'callsign': s['callsign'], 'frequency': s['frequency'], 'snr_db': s['snr_db'],
                           'wpm': s['wpm'], 'type': s['type']}, source='rbn', spotter=s.get('best_skimmer'))

    def _flush(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_flush < 2.0:
            return
        self._last_flush = now
        self.book.prune(now)
        try:
            get_redis().set(SPOTS_KEY, json.dumps(self.book.snapshot()), ex=SPOTS_TTL)
        except Exception as e:
            logger.debug(f"Skimmer spots not saved: {e}")

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)
