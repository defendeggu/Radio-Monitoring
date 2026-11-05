"""
Skimmer core, independent of the SDR: complex baseband of one band segment in,
confirmed spots out. Used live by SkimmerSession and offline by the evaluation.

    segment IQ ─► ActivityDetector (every 0.5 s) ─► tracks
             └─► one CwChannel per scheduled track: Mixer → Decimator (4 kHz) → CwDecoder
                    └─► complete words → callsign after CQ/TEST/DE/TU or repeated
                           └─► SpotConfirmer ─► on_spot(spot)

Scheduling: at most `max_decoders` channels. A free channel goes to the
strongest unassigned track; when all are busy, a stronger new track replaces
a channel whose station was already spotted (after a minimum dwell time).
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
from numpy.typing import NDArray

from radiomoni.contest import callsign as cs
from radiomoni.dsp import Decimator, Mixer
from radiomoni.morse import CwDecoder
from radiomoni.skimmer.activity import ActivityDetector, Track
from radiomoni.skimmer.confirm import SpotConfirmer

DECODER_RATE = 4000
UPDATE_SECONDS = 0.5
MIN_DWELL_S = 20.0          # a channel decodes at least this long before it can be reassigned
MIN_TRACK_HITS = 2          # a peak must come back once before it gets a decoder (noise peaks do not)
SELF_ID_WORDS = {'CQ', 'TEST', 'DE', 'TU', 'QRZ', 'CFM'}
CQ_WORDS = {'CQ', 'TEST'}
NOISE_CHARS = set('EISHT*')  # what a CW decoder makes of noise
REAL_NOISE_WORDS = {'TEST', 'TES'}   # real words made of those characters only

Validator = Callable[[str], tuple[bool, Optional[bool]]]      # call → (resolves to DXCC, in MASTER.SCP)


def _structure_only(call: str) -> tuple[bool, Optional[bool]]:
    return cs.is_valid(call), None


@dataclass
class CwChannel:
    track_id: int
    offset_hz: float
    started: float
    seg_rate: float
    wpm_guess: float = 25.0
    text: str = ''
    words: list[str] = field(default_factory=list)
    spotted: Optional[str] = None
    spotted_at: float = 0.0

    def __post_init__(self) -> None:
        self.mixer = Mixer(self.seg_rate, self.offset_hz)
        self.decimator = Decimator(int(round(self.seg_rate)), DECODER_RATE)
        self.decoder = CwDecoder(self.decimator.output_rate, bandwidth_hz=200.0, afc_range_hz=80.0,
                                 wpm_guess=self.wpm_guess)

    def process(self, iq: NDArray[np.complexfloating]) -> list[tuple[str, list[str]]]:
        """Decode a block; returns the newly completed words with the words before them."""
        out = self.decoder.process(self.decimator.process(self.mixer.process(iq)))
        if not out:
            return []
        self.text += out
        if ' ' not in self.text:
            return []
        *complete, self.text = self.text.split(' ')
        result = []
        for word in complete:
            if not word:
                continue
            result.append((word, self.words[-4:]))
            self.words = (self.words + [word])[-8:]
        return result

    @property
    def useful(self) -> bool:
        """Decoded at least one real word (not only the dits and dahs that noise produces)."""
        return any(len(w) >= 3 and (set(w) - NOISE_CHARS or w in REAL_NOISE_WORDS) for w in self.words)

    @property
    def frequency_offset(self) -> float:
        return self.offset_hz + self.decoder.offset_hz


class SkimmerCore:
    def __init__(self, seg_rate: float, centre_hz: int, max_decoders: int = 24,
                 on_spot: Optional[Callable[[dict[str, Any]], None]] = None,
                 validate: Optional[Validator] = None, wpm_guess: float = 25.0,
                 detector: Optional[ActivityDetector] = None, confirmer: Optional[SpotConfirmer] = None):
        self.seg_rate = float(seg_rate)
        self.centre_hz = int(centre_hz)
        self.max_decoders = max_decoders
        self.on_spot = on_spot
        self.validate = validate or _structure_only
        self.wpm_guess = wpm_guess
        self.detector = detector or ActivityDetector(self.seg_rate)
        self.confirmer = confirmer or SpotConfirmer()
        self.channels: dict[int, CwChannel] = {}
        self.tracks: list[Track] = []
        self._last_update: Optional[float] = None
        self.spots = 0
        self.decodes = 0

    # ------------------------------------------------------------------ scheduling
    def _score(self, track: Track, now: float) -> float:
        score = track.snr_db + min(track.age(now), 60.0) / 6.0
        ch = self.channels.get(track.id)
        if ch is not None and ch.spotted and now - ch.spotted_at < 120:
            score -= 15.0                     # known station: give the decoder to someone new
        if ch is not None and not ch.useful and now - ch.started >= MIN_DWELL_S:
            score -= 10.0                     # nothing but noise decoded so far
        return score

    def _schedule(self, now: float) -> None:
        live = {t.id: t for t in self.tracks if not t.steady}       # carriers get no decoder
        for tid in [tid for tid in self.channels if tid not in live]:
            del self.channels[tid]
        waiting = sorted((t for t in live.values() if t.id not in self.channels and t.hits >= MIN_TRACK_HITS),
                         key=lambda t: self._score(t, now), reverse=True)
        for track in waiting:
            if len(self.channels) < self.max_decoders:
                self._open(track, now)
                continue
            replaceable = [ch for ch in self.channels.values()
                           if now - ch.started >= MIN_DWELL_S and ch.track_id in live]
            if not replaceable:
                break
            worst = min(replaceable, key=lambda ch: self._score(live[ch.track_id], now))
            if self._score(track, now) <= self._score(live[worst.track_id], now) + 3.0:
                break
            del self.channels[worst.track_id]
            self._open(track, now)

    def _open(self, track: Track, now: float) -> None:
        self.channels[track.id] = CwChannel(track.id, track.offset_hz, now, self.seg_rate, self.wpm_guess)

    # ------------------------------------------------------------------ processing
    def feed(self, iq: NDArray[np.complexfloating], now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        self.detector.feed(iq)
        if self._last_update is None:
            self._last_update = now
        if now - self._last_update >= UPDATE_SECONDS:
            self._last_update = now
            self.tracks = self.detector.update(now)
            self._schedule(now)
        for ch in list(self.channels.values()):
            for word, before in ch.process(iq):
                self._word(ch, word, before, now)

    def _word(self, ch: CwChannel, word: str, before: list[str], now: float) -> None:
        if not cs.is_valid(word) or not any(c.isdigit() for c in word):
            return
        self.decodes += 1
        self_id = bool(SELF_ID_WORDS & set(before[-2:])) or (bool(before) and before[-1] == word)
        if not self_id:
            return                      # a call sent by the run station to its partner, not the station itself
        valid, in_scp = self.validate(word)
        frequency = int(round(self.centre_hz + ch.frequency_offset))
        cq = bool(CQ_WORDS & set(before))
        spot = self.confirmer.add(word, frequency, now, cq, valid, in_scp)
        if spot is None:
            return
        ch.spotted, ch.spotted_at = word, now
        track = next((t for t in self.tracks if t.id == ch.track_id), None)
        spot.update({'mode': 'CW', 'khz': round(frequency / 1000.0, 1), 'wpm': ch.decoder.wpm,
                     'snr_db': round(track.snr_db if track else ch.decoder.snr_db, 1), 'time': now,
                     'source': 'skimmer', 'in_scp': in_scp})
        self.spots += 1
        if self.on_spot:
            self.on_spot(spot)

    def state(self) -> list[dict[str, Any]]:
        """The busy decoders (for the page)."""
        return [{'frequency': int(round(self.centre_hz + ch.frequency_offset)), 'wpm': ch.decoder.wpm,
                 'snr_db': round(ch.decoder.snr_db, 1), 'callsign': ch.spotted,
                 'text': ' '.join(ch.words[-4:] + ([ch.text] if ch.text else []))[-40:]}
                for ch in sorted(self.channels.values(), key=lambda c: c.offset_hz)]
