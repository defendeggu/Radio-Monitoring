"""
Activity detector: which frequencies of the segment carry a signal.

An averaged power spectrum (Hann window, ~12 Hz bins) is compared with a noise
floor taken per 1 kHz block (30th percentile, so signals do not lift it).
Local maxima above floor + threshold are peaks (key clicks next to a much stronger signal are
masked); peaks that come back on (nearly)
the same frequency form a track. A CW station keys on and off, so one interval
averages ~0.5 s of keying; a run station keeps its track for a long time.
"""

import itertools
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from numpy.typing import NDArray


STEADY_UPDATES = 8         # ~4 s of updates
STEADY_DB = 1.5


@dataclass
class Track:
    id: int
    offset_hz: float
    snr_db: float
    first_seen: float
    last_seen: float
    hits: int = 1
    levels: list[float] = field(default_factory=list)      # SNR of the last updates

    def age(self, now: float) -> float:
        return now - self.first_seen

    @property
    def steady(self) -> bool:
        """An unkeyed carrier (spur, tuning carrier): seen in every update at a constant level.
        Keying makes the level of a CW signal jump by several dB from one update to the next."""
        recent = self.levels[-STEADY_UPDATES:]
        return len(recent) == STEADY_UPDATES and max(recent) - min(recent) < STEADY_DB


class ActivityDetector:
    def __init__(self, rate: float, resolution_hz: float = 12.0, threshold_db: float = 13.0,
                 min_spacing_hz: float = 60.0, edge: float = 0.45, match_hz: float = 30.0, lifetime_s: float = 20.0,
                 block_hz: float = 1000.0, mask_hz: float = 400.0, mask_db: float = 15.0, smooth_hz: float = 0.0):
        self.rate = float(rate)
        self.fft_size = int(2 ** np.ceil(np.log2(self.rate / resolution_hz)))
        self.bin_hz = self.rate / self.fft_size
        self.threshold_db = threshold_db
        self.spacing_bins = max(1, int(round(min_spacing_hz / self.bin_hz)))
        self.edge_hz = edge * self.rate
        self.match_hz = match_hz
        self.lifetime_s = lifetime_s
        self.block_bins = max(16, int(block_hz / self.bin_hz))
        # key clicks of a strong signal: weaker peaks this close and this much lower are ignored
        self.mask_bins = int(round(mask_hz / self.bin_hz))
        self.mask_db = mask_db
        # SSB: average the power over the width of a voice signal, so one signal is one peak
        self.smooth_bins = max(1, int(round(smooth_hz / self.bin_hz)))
        self.raw_db: Optional[NDArray[np.float64]] = None      # last averaged spectrum, unsmoothed
        self.window = np.hanning(self.fft_size).astype(np.float64)
        self.freqs = np.fft.fftshift(np.fft.fftfreq(self.fft_size, 1.0 / self.rate))
        self._carry = np.zeros(0, dtype=np.complex128)
        self._power = np.zeros(self.fft_size, dtype=np.float64)
        self._frames = 0
        self.tracks: dict[int, Track] = {}
        self._ids = itertools.count(1)
        self.floor_db: Optional[NDArray[np.float64]] = None
        self._last_update: Optional[float] = None
        self._interval = 0.5

    def feed(self, iq: NDArray[np.complexfloating]) -> None:
        x = np.concatenate([self._carry, np.asarray(iq, dtype=np.complex128)])
        n = len(x) // self.fft_size
        if n:
            frames = x[:n * self.fft_size].reshape(n, self.fft_size) * self.window
            spectra = np.fft.fft(frames, axis=1)
            self._power += np.sum(spectra.real ** 2 + spectra.imag ** 2, axis=0)
            self._frames += n
        self._carry = x[n * self.fft_size:]

    def _floor(self, db: NDArray[np.float64]) -> NDArray[np.float64]:
        blocks = [np.percentile(db[i:i + self.block_bins], 30) for i in range(0, len(db), self.block_bins)]
        centres = np.arange(len(blocks)) * self.block_bins + self.block_bins / 2
        return np.interp(np.arange(len(db)), centres, blocks)

    def peaks(self) -> list[tuple[float, float]]:
        """(offset Hz, SNR dB) of the peaks since the last call, strongest first."""
        if not self._frames:
            return []
        power = np.fft.fftshift(self._power / self._frames)
        self.raw_db = 10 * np.log10(power + 1e-20)
        if self.smooth_bins > 1:
            power = np.convolve(power, np.ones(self.smooth_bins) / self.smooth_bins, mode='same')
        db = 10 * np.log10(power + 1e-20)
        self._power[:] = 0.0
        self._frames = 0
        floor = self._floor(db)
        self.floor_db = floor
        excess = db - floor
        found: list[tuple[int, float]] = []
        candidates = np.flatnonzero(excess > self.threshold_db)
        for i in candidates[np.argsort(excess[candidates])[::-1]]:
            if abs(self.freqs[i]) > self.edge_hz:
                continue
            if 0 < i < len(db) - 1 and not (db[i] >= db[i - 1] and db[i] >= db[i + 1]):
                continue
            if any(abs(i - j) <= self.spacing_bins for j, _ in found):
                continue
            if any(abs(i - j) <= self.mask_bins and level - excess[i] > self.mask_db for j, level in found):
                continue
            found.append((int(i), float(excess[i])))
        result = []
        for i, snr in found:
            delta = 0.0
            if 0 < i < len(db) - 1:          # parabolic interpolation of the peak
                a, b, c = db[i - 1], db[i], db[i + 1]
                denom = a - 2 * b + c
                delta = 0.5 * (a - c) / denom if denom else 0.0
            result.append((float(self.freqs[i] + delta * self.bin_hz), snr))
        return result

    def update(self, now: float) -> list[Track]:
        """Match the latest peaks to tracks; returns the live tracks."""
        if self._last_update is not None:
            self._interval = max(1e-3, now - self._last_update)
        self._last_update = now
        for offset, snr in self.peaks():
            best = min(self.tracks.values(), key=lambda t: abs(t.offset_hz - offset), default=None)
            if best is not None and abs(best.offset_hz - offset) <= self.match_hz:
                best.offset_hz += 0.2 * (offset - best.offset_hz)
                best.snr_db = max(snr, 0.8 * best.snr_db + 0.2 * snr)
                best.hits += 1
                # a gap (no peak in one or more updates) means keying: restart the level history
                if now - best.last_seen > 1.5 * self._interval:
                    best.levels = []
                best.levels = (best.levels + [snr])[-2 * STEADY_UPDATES:]
                best.last_seen = now
            else:
                track = Track(next(self._ids), offset, snr, now, now, levels=[snr])
                self.tracks[track.id] = track
        for tid in [tid for tid, t in self.tracks.items() if now - t.last_seen > self.lifetime_s]:
            del self.tracks[tid]
        return list(self.tracks.values())
