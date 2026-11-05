"""
IQ recording of the skimmer segment for the offline evaluation (Phase 0).

Writes the decimated segment as a stereo 16-bit WAV (I left, Q right) — about
1.4 GB per hour for a 70 kHz CW segment — next to a JSON sidecar (centre, exact
rate, start) and, while RBN runs, a JSONL file with the RBN spots heard in the
segment as reference: <name>.wav, <name>.json, <name>.rbn.jsonl.

Recording stops (the session keeps running) when the disk gets below MIN_FREE_DISK_MB.
"""

import json
import logging
import os
import shutil
import time
import wave
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray

from radiomoni import config

logger = logging.getLogger(__name__)

DISK_CHECK_S = 60.0
RBN_POLL_S = 30.0


class IqRecorder:
    def __init__(self, directory: str, centre_hz: int, rate: float, freq_low: int, freq_high: int,
                 session_id: Optional[str] = None):
        os.makedirs(directory, exist_ok=True)
        started = datetime.now(timezone.utc)
        self.name = f'skimmer_{started:%Y%m%d_%H%M%S}_{centre_hz // 1000}kHz'
        self.directory = directory
        self.path = os.path.join(directory, self.name + '.wav')
        self.rate = float(rate)
        self.centre_hz = int(centre_hz)
        self.freq_low, self.freq_high = int(freq_low), int(freq_high)
        self._wav: Optional[wave.Wave_write] = wave.open(self.path, 'wb')
        self._wav.setnchannels(2)
        self._wav.setsampwidth(2)
        self._wav.setframerate(int(round(self.rate)))
        self.samples = 0
        self.stopped_reason: Optional[str] = None
        self._last_disk = time.monotonic()
        self._last_rbn = 0.0
        self._rbn_seen: set[tuple[str, int]] = set()
        with open(os.path.join(directory, self.name + '.json'), 'w') as f:
            json.dump({'centre_hz': self.centre_hz, 'rate': self.rate, 'freq_low': self.freq_low,
                       'freq_high': self.freq_high, 'started': started.isoformat(), 'session_id': session_id,
                       'format': 'WAV stereo int16, I left, Q right, full scale = 1.0'}, f, indent=2)

    @property
    def active(self) -> bool:
        return self._wav is not None

    def write(self, iq: NDArray[np.complexfloating]) -> None:
        if self._wav is None:
            return
        frames = np.empty(2 * len(iq), dtype=np.int16)
        frames[0::2] = np.clip(np.real(iq) * 32767, -32768, 32767)
        frames[1::2] = np.clip(np.imag(iq) * 32767, -32768, 32767)
        self._wav.writeframes(frames.tobytes())
        self.samples += len(iq)
        now = time.monotonic()
        if now - self._last_disk >= DISK_CHECK_S:
            self._last_disk = now
            free_mb = shutil.disk_usage(self.directory).free / 1e6
            if free_mb < config.MIN_FREE_DISK_MB:
                logger.warning(f"Skimmer recording stopped: only {free_mb:.0f} MB free")
                self.close('disk full')
        if now - self._last_rbn >= RBN_POLL_S:
            self._last_rbn = now
            self._log_rbn()

    def _log_rbn(self) -> None:
        """Append the RBN spots inside the segment that were not logged yet (reference for the evaluation)."""
        try:
            from radiomoni import rbn
            spots = rbn.query(rbn.load_spots(), freq_min=self.freq_low, freq_max=self.freq_high, limit=1000)
        except Exception:
            return
        lines = []
        for s in spots:
            key = (s['callsign'], int(s['first_seen']))
            if key in self._rbn_seen:
                continue
            self._rbn_seen.add(key)
            lines.append(json.dumps({'callsign': s['callsign'], 'frequency': s['frequency'],
                                     'first_seen': s['first_seen'], 'last_seen': s['last_seen'],
                                     'snr_db': s['snr_db'], 'wpm': s['wpm'], 'type': s['type'],
                                     'skimmers': s['skimmer_count']}))
        if lines:
            with open(os.path.join(self.directory, self.name + '.rbn.jsonl'), 'a') as f:
                f.write('\n'.join(lines) + '\n')

    def close(self, reason: Optional[str] = None) -> None:
        if self._wav is not None:
            self._log_rbn()
            self._wav.close()
            self._wav = None
            self.stopped_reason = reason

    def info(self) -> dict[str, Any]:
        return {'file': self.name + '.wav', 'seconds': round(self.samples / self.rate, 1), 'active': self.active,
                'stopped': self.stopped_reason}
