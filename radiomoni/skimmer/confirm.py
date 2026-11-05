"""
Spot confirmation: a decoded callsign becomes a spot only after repeated hits.

A wrong spot costs the operator more than a missed one (see docs/contest.md),
so a single decode never reaches the bandmap:

- the call must resolve to a DXCC entity (cty.csv) when that file is loaded,
- it needs `min_hits` hits on (nearly) the same frequency within `window_s`,
- one hit more when MASTER.SCP is loaded and does not know the call,
- a single hit suffices when MASTER.SCP knows the call and it was sent after CQ/TEST.

A confirmed station is spotted again after `respot_s` (like RBN skimmers).
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Candidate:
    callsign: str
    frequency: int
    hits: int
    first: float
    last: float
    cq: bool
    spotted_at: Optional[float] = None


class SpotConfirmer:
    def __init__(self, min_hits: int = 2, window_s: float = 600.0, freq_tol_hz: float = 200.0,
                 respot_s: float = 600.0):
        self.min_hits = min_hits
        self.window_s = window_s
        self.freq_tol_hz = freq_tol_hz
        self.respot_s = respot_s
        self.candidates: list[Candidate] = []

    def add(self, callsign: str, frequency: int, now: float, cq: bool, valid: bool = True,
            in_scp: Optional[bool] = None) -> Optional[dict[str, Any]]:
        """Register one decode; returns a spot when the call is (re)confirmed."""
        self.candidates = [c for c in self.candidates if now - c.last <= self.window_s]
        if not valid:
            return None
        cand = next((c for c in self.candidates
                     if c.callsign == callsign and abs(c.frequency - frequency) <= self.freq_tol_hz), None)
        if cand is None:
            cand = Candidate(callsign, frequency, 0, now, now, cq)
            self.candidates.append(cand)
        cand.hits += 1
        cand.last = now
        cand.frequency = frequency
        cand.cq = cand.cq or cq
        needed = self.min_hits
        if in_scp is False:
            needed += 1
        elif in_scp and cq:
            needed = 1
        if cand.hits < needed:
            return None
        if cand.spotted_at is not None and now - cand.spotted_at < self.respot_s:
            return None
        respot = cand.spotted_at is not None
        cand.spotted_at = now
        return {'callsign': callsign, 'frequency': frequency, 'type': 'CQ' if cand.cq else 'DX',
                'hits': cand.hits, 'respot': respot}
