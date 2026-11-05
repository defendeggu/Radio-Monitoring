"""
SSB skimmer core (experimental): voice signals of a band segment → Whisper → callsigns → spots.

    segment IQ ─► ActivityDetector (2.4 kHz smoothing) ─► tracks (one per voice signal)
             └─► SsbChannel per track: ChannelReceiver USB/LSB on the estimated carrier
                    └─► speech segments (while the track is active, 1.5–8 s)
                           └─► TranscriptionQueue (one Whisper worker, highest score first)
                                  └─► phonetic.extract ─► SpotConfirmer ─► on_spot(spot)

Whisper is the bottleneck: on a CPU it keeps up with a few channels at most.
The queue is bounded; when it is full the segment with the lowest score is
dropped (a station already spotted scores lower than an unknown one). The
state reports pending, dropped and the mean transcription time, so the
operator sees whether the machine keeps up.

Measure precision and recall before trusting the spots (docs/contest.md, phase 0).
"""

import heapq
import itertools
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
from numpy.typing import NDArray
from scipy.io import wavfile

from radiomoni.contest import phonetic
from radiomoni.dsp import ChannelReceiver
from radiomoni.skimmer.activity import ActivityDetector, Track
from radiomoni.skimmer.confirm import SpotConfirmer
from radiomoni.skimmer.core import Validator, _structure_only

logger = logging.getLogger(__name__)

AUDIO_RATE = 8000
UPDATE_SECONDS = 0.5
MIN_SPEECH_S = 1.5
MAX_SEGMENT_S = 8.0
GAP_S = 1.0                  # track inactive this long ends a segment
MIN_DWELL_S = 30.0
VOICE_LOW_HZ = 300.0         # voice starts this far from the suppressed carrier

CONTEST_PROMPT = 'CQ contest, CQ contest, this is Hotel Bravo Nine X-ray Yankee Zulu, five nine zero zero one, QRZ.'
PHONETIC_HOTWORDS = ('Alfa Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliett Kilo Lima Mike November '
                     'Oscar Papa Quebec Romeo Sierra Tango Uniform Victor Whiskey X-ray Yankee Zulu CQ contest QRZ')

Transcriber = Callable[[NDArray[np.float32], int], str]


def sideband_for(frequency_hz: float) -> str:
    """Amateur convention: LSB below 10 MHz, USB above."""
    return 'LSB' if frequency_hz < 10_000_000 else 'USB'


# ------------------------------------------------------------------ transcription queue
@dataclass(order=True)
class _Job:
    sort_key: tuple[float, int]
    channel_id: int = field(compare=False)
    audio: NDArray[np.float32] = field(compare=False)
    meta: dict[str, Any] = field(compare=False)


class TranscriptionQueue:
    """One worker; highest score first; bounded (drops the lowest score when full)."""

    def __init__(self, transcribe: Transcriber, on_result: Callable[[dict[str, Any], str], None],
                 max_pending: int = 12, sync: bool = False):
        self.transcribe = transcribe
        self.on_result = on_result
        self.max_pending = max_pending
        self.sync = sync
        self._heap: list[_Job] = []
        self._order = itertools.count()
        self._cond = threading.Condition()
        self._stop = False
        self.done = 0
        self.dropped = 0
        self.failed = 0
        self.busy = False
        self._seconds: list[float] = []
        self._thread: Optional[threading.Thread] = None
        if not sync:
            self._thread = threading.Thread(target=self._worker, name='skimmer-whisper', daemon=True)
            self._thread.start()

    def submit(self, score: float, channel_id: int, audio: NDArray[np.float32], meta: dict[str, Any]) -> None:
        job = _Job((-score, next(self._order)), channel_id, audio, meta)
        if self.sync:
            self._run(job)
            return
        with self._cond:
            if len(self._heap) >= self.max_pending:
                worst = max(self._heap)                     # lowest score (keys are negated)
                if job < worst:
                    self._heap.remove(worst)
                    heapq.heapify(self._heap)
                    self.dropped += 1
                else:
                    self.dropped += 1
                    return
            heapq.heappush(self._heap, job)
            self._cond.notify()

    def _run(self, job: _Job) -> None:
        started = time.monotonic()
        self.busy = True
        try:
            text = self.transcribe(job.audio, AUDIO_RATE)
            self.done += 1
            self.on_result(job.meta, text)
        except Exception as e:
            self.failed += 1
            logger.warning(f"SSB skimmer: transcription failed: {e}")
        finally:
            self.busy = False
            self._seconds = (self._seconds + [time.monotonic() - started])[-20:]

    def _worker(self) -> None:
        while True:
            with self._cond:
                while not self._heap and not self._stop:
                    self._cond.wait(1.0)
                if self._stop:
                    return
                job = heapq.heappop(self._heap)
            self._run(job)

    def close(self) -> None:
        with self._cond:
            self._stop = True
            self._cond.notify_all()
        if self._thread:
            self._thread.join(timeout=30)

    def stats(self) -> dict[str, Any]:
        return {'pending': len(self._heap), 'done': self.done, 'dropped': self.dropped, 'failed': self.failed,
                'busy': self.busy,
                'mean_seconds': round(sum(self._seconds) / len(self._seconds), 2) if self._seconds else None}


def whisper_transcriber(language: Optional[str] = 'en') -> Transcriber:
    """Transcribe with the shared Whisper model (radiomoni.services), contest prompt and phonetic hotwords."""
    def transcribe(audio: NDArray[np.float32], rate: int) -> str:
        from radiomoni.services import get_transcription_service
        fd, path = tempfile.mkstemp(suffix='.wav', prefix='skimmer-')
        os.close(fd)
        try:
            wavfile.write(path, rate, (np.clip(audio, -1, 1) * 32767).astype(np.int16))
            result = get_transcription_service().transcribe(path, language=language or None,
                                                            initial_prompt=CONTEST_PROMPT, hotwords=PHONETIC_HOTWORDS)
            return str(result.get('text') or '')
        finally:
            os.unlink(path)
    return transcribe


# ------------------------------------------------------------------ channels
@dataclass
class SsbChannel:
    channel_id: int
    track_id: int
    carrier_offset: float          # suppressed carrier, relative to the segment centre
    sideband: str
    started: float
    seg_rate: float
    audio: list[NDArray[np.float64]] = field(default_factory=list)
    samples: int = 0
    segment_started: Optional[float] = None
    last_active: float = 0.0
    text: str = ''
    spotted: Optional[str] = None
    spotted_at: float = 0.0
    segments: int = 0

    def __post_init__(self) -> None:
        self.receiver = ChannelReceiver(int(round(self.seg_rate)), self.carrier_offset, self.sideband,
                                        audio_rate=AUDIO_RATE)

    @property
    def audio_rate(self) -> float:
        return self.receiver.audio_rate


class SsbCore:
    def __init__(self, seg_rate: float, centre_hz: int, max_channels: int = 8,
                 on_spot: Optional[Callable[[dict[str, Any]], None]] = None, validate: Optional[Validator] = None,
                 transcribe: Optional[Transcriber] = None, sideband: Optional[str] = None, sync: bool = False,
                 max_pending: int = 12):
        self.seg_rate = float(seg_rate)
        self.centre_hz = int(centre_hz)
        self.max_channels = max_channels
        self.on_spot = on_spot
        self.validate = validate or _structure_only
        self.sideband = sideband or sideband_for(centre_hz)
        self.detector = ActivityDetector(self.seg_rate, resolution_hz=50.0, threshold_db=6.0, min_spacing_hz=2500.0,
                                         match_hz=400.0, lifetime_s=20.0, mask_hz=0.0, smooth_hz=2400.0,
                                         block_hz=20_000.0)      # floor over blocks much wider than a signal
        self.confirmer = SpotConfirmer(freq_tol_hz=1000.0)
        self.queue = TranscriptionQueue(transcribe or whisper_transcriber(), self._on_transcript,
                                        max_pending=max_pending, sync=sync)
        self.channels: dict[int, SsbChannel] = {}
        self.tracks: list[Track] = []
        self._ids = itertools.count(1)
        self._last_update: Optional[float] = None
        self._lock = threading.Lock()
        self.spots = 0
        self.decodes = 0
        self.recent: list[dict[str, Any]] = []        # last transcripts (for the page)

    # ------------------------------------------------------------------ carrier estimate
    def _carrier(self, track: Track) -> float:
        """Suppressed carrier from the edge of the voice energy (USB: lower edge − 300 Hz)."""
        db, floor = self.detector.raw_db, self.detector.floor_db
        if db is None or floor is None:
            return track.offset_hz - 1200.0 if self.sideband == 'USB' else track.offset_hz + 1200.0
        light = np.convolve(db, np.ones(5) / 5, mode='same')       # ~250 Hz
        freqs = self.detector.freqs
        centre = int(np.argmin(np.abs(freqs - track.offset_hz)))
        step = -1 if self.sideband == 'USB' else 1
        core = int(round(800 / self.detector.bin_hz))
        plateau = float(np.median(light[max(0, centre - core):centre + core + 1]))   # level of the voice
        i, limit = centre, int(round(3000 / self.detector.bin_hz))
        while 0 < i < len(db) - 1 and abs(i - centre) < limit and light[i] > max(floor[i] + 3.0, plateau - 10.0):
            i += step
        edge = float(freqs[i])
        return edge - VOICE_LOW_HZ if self.sideband == 'USB' else edge + VOICE_LOW_HZ

    # ------------------------------------------------------------------ scheduling
    def _score(self, track: Track, now: float, ch: Optional[SsbChannel] = None) -> float:
        score = track.snr_db + min(track.age(now), 60.0) / 6.0
        if ch is not None and ch.spotted and now - ch.spotted_at < 300:
            score -= 15.0
        return score

    def _schedule(self, now: float) -> None:
        live = {t.id: t for t in self.tracks if not t.steady}
        by_track = {ch.track_id: ch for ch in self.channels.values()}
        for ch in [c for c in self.channels.values() if c.track_id not in live]:
            self._end_segment(ch, now)
            del self.channels[ch.channel_id]
        waiting = sorted((t for t in live.values() if t.id not in by_track and t.hits >= 2),
                         key=lambda t: self._score(t, now), reverse=True)
        for track in waiting:
            if len(self.channels) >= self.max_channels:
                replaceable = [c for c in self.channels.values() if now - c.started >= MIN_DWELL_S
                               and c.track_id in live]
                if not replaceable:
                    break
                worst = min(replaceable, key=lambda c: self._score(live[c.track_id], now, c))
                if self._score(track, now) <= self._score(live[worst.track_id], now, worst) + 3.0:
                    break
                self._end_segment(worst, now)
                del self.channels[worst.channel_id]
            cid = next(self._ids)
            self.channels[cid] = SsbChannel(cid, track.id, self._carrier(track), self.sideband, now, self.seg_rate)

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
        tracks = {t.id: t for t in self.tracks}
        for ch in list(self.channels.values()):
            audio = ch.receiver.process(iq)
            track = tracks.get(ch.track_id)
            active = track is not None and now - track.last_seen <= 1.5 * UPDATE_SECONDS
            if active:
                ch.last_active = now
                if ch.segment_started is None:
                    ch.segment_started = now
            if ch.segment_started is not None:
                ch.audio.append(audio)
                ch.samples += len(audio)
                if now - ch.last_active >= GAP_S or ch.samples >= MAX_SEGMENT_S * ch.audio_rate:
                    self._end_segment(ch, now)

    def _end_segment(self, ch: SsbChannel, now: float) -> None:
        audio, ch.audio, samples, ch.samples = ch.audio, [], ch.samples, 0
        ch.segment_started = None
        if samples < MIN_SPEECH_S * ch.audio_rate:
            return
        track = next((t for t in self.tracks if t.id == ch.track_id), None)
        score = self._score(track, now, ch) if track else 0.0
        clip = np.concatenate(audio).astype(np.float32)
        ch.segments += 1
        meta = {'channel_id': ch.channel_id, 'frequency': int(round(self.centre_hz + ch.carrier_offset)),
                'snr_db': round(track.snr_db, 1) if track else None, 'time': now, 'rate': int(round(ch.audio_rate)),
                'clip': clip}
        self.queue.submit(score, ch.channel_id, self._resample(clip, ch.audio_rate), meta)

    @staticmethod
    def _resample(audio: NDArray[np.float32], rate: float) -> NDArray[np.float32]:
        if abs(rate - AUDIO_RATE) < 1:
            return audio
        n = int(round(len(audio) * AUDIO_RATE / rate))
        return np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)

    def _on_transcript(self, meta: dict[str, Any], text: str) -> None:
        with self._lock:
            ch = self.channels.get(meta['channel_id'])
            if ch is not None:
                ch.text = text.strip()[-120:]
            self.recent = ([{'frequency': meta['frequency'], 'text': text.strip()[:200], 'time': meta['time']}]
                           + self.recent)[:20]
            for heard in phonetic.extract(text):
                self.decodes += 1
                if not heard.self_identified:
                    continue        # a call the run station repeats to its partner
                valid, in_scp = self.validate(heard.callsign)
                spot = self.confirmer.add(heard.callsign, meta['frequency'], meta['time'], True, valid, in_scp)
                if spot is None:
                    continue
                if ch is not None:
                    ch.spotted, ch.spotted_at = heard.callsign, meta['time']
                spot.update({'mode': 'SSB', 'khz': round(meta['frequency'] / 1000.0, 1), 'wpm': None,
                             'snr_db': meta['snr_db'], 'time': meta['time'], 'source': 'skimmer',
                             'in_scp': in_scp, 'text': text.strip()[:300], 'clip': meta['clip'],
                             'clip_rate': meta['rate']})
                self.spots += 1
                if self.on_spot:
                    self.on_spot(spot)

    def state(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{'frequency': int(round(self.centre_hz + ch.carrier_offset)), 'sideband': ch.sideband,
                     'wpm': None, 'snr_db': None, 'callsign': ch.spotted, 'text': ch.text[-60:],
                     'segments': ch.segments}
                    for ch in sorted(self.channels.values(), key=lambda c: c.carrier_offset)]

    def close(self) -> None:
        self.queue.close()
