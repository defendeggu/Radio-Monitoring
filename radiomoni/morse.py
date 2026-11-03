"""
CW (Morse) decoder for complex baseband.

The carrier of the station is expected near 0 Hz (within ±afc_range). The
decoder follows it (AFC), keeps only a narrow band around it, measures the
envelope and turns key-down / key-up times into dits, dahs, character and
word gaps. The dit length is learned from the signal (two clusters of mark
lengths), so it copes with different and changing speeds.

    baseband ─► AFC mixer ─► narrow filter ─► envelope (1 kHz) ─► threshold + debounce
             ─► mark/space lengths ─► dit/dah, gaps ─► Morse table ─► text

Morse code per ITU-R M.1677-1 (International Morse code), plus the common
prosigns AR, SK, KN and BT.
"""

import math
import re
from collections import deque
from typing import Optional

import numpy as np
from numpy.typing import NDArray
from scipy import signal

from radiomoni.dsp import ComplexFilter, Mixer

MORSE: dict[str, str] = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E', '..-.': 'F', '--.': 'G', '....': 'H',
    '..': 'I', '.---': 'J', '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O', '.--.': 'P',
    '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T', '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X',
    '-.--': 'Y', '--..': 'Z',
    '-----': '0', '.----': '1', '..---': '2', '...--': '3', '....-': '4', '.....': '5', '-....': '6',
    '--...': '7', '---..': '8', '----.': '9',
    '.-.-.-': '.', '--..--': ',', '..--..': '?', '.----.': "'", '-..-.': '/', '-.--.-': ')',
    '---...': ':', '-.-.-.': ';', '-...-': '=', '-....-': '-', '.-..-.': '"', '.--.-.': '@',
    '-.-.--': '!', '..--.-': '_', '.-...': '&',
    # prosigns (AR is "+" in ITU, KN is "(" — shown as prosigns, as operators use them)
    '.-.-.': '<AR>', '...-.-': '<SK>', '-.--.': '<KN>', '...-.': '<SN>', '........': '<HH>',
}
ENCODE: dict[str, str] = {v: k for k, v in MORSE.items()}
ENCODE['+'] = '.-.-.'

# Amateur callsigns: prefix (letters/digit+letter/letter+digit), a digit, 1–4 letters, optional /suffix
CALLSIGN_RE = re.compile(r'\b(?:[A-Z]{1,2}|[0-9][A-Z]|[A-Z][0-9])[0-9][A-Z]{1,4}(?:/[A-Z0-9]{1,4})?\b')


def callsigns(text: str) -> list[str]:
    """Callsigns in decoded text, in order of first appearance."""
    seen: list[str] = []
    for m in CALLSIGN_RE.findall(text.upper()):
        if m not in seen:
            seen.append(m)
    return seen


def wpm_to_dit_ms(wpm: float) -> float:
    return 1200.0 / wpm        # PARIS standard: dit = 1.2 s / WPM


class CwDecoder:
    """
    Streaming CW decoder. process(baseband) returns the newly decoded text
    (characters and single spaces between words).
    """

    ENV_RATE = 1000.0          # Hz of the envelope (1 ms resolution)
    HISTORY_S = 4.0            # window for the noise floor
    WARMUP_MS = 500.0          # no decisions before this much signal was seen
    MIN_DIT_MS, MAX_DIT_MS = 20.0, 240.0      # 60 … 5 WPM

    def __init__(self, rate: float, bandwidth_hz: float = 200.0, afc_range_hz: float = 300.0,
                 wpm_guess: float = 20.0, min_snr_db: float = 10.0):
        self.rate = float(rate)
        self.afc_range = afc_range_hz
        self.min_snr = 10 ** (min_snr_db / 20.0)      # amplitude ratio
        self.mixer = Mixer(self.rate, 0.0)
        self.filter = ComplexFilter(signal.firwin(int(self.rate / 25) | 1, bandwidth_hz / 2.0, fs=self.rate))
        self._env_factor = max(1, int(round(self.rate / self.ENV_RATE)))
        self._env_dt = 1000.0 * self._env_factor / self.rate        # ms per envelope sample
        self._env_carry = np.zeros(0, dtype=np.float64)
        self._smooth_taps = 0
        self._smooth_zi = np.zeros(0, dtype=np.float64)
        self._history: deque[float] = deque(maxlen=int(self.HISTORY_S * 1000 / self._env_dt))
        self._afc_buffer = np.zeros(0, dtype=np.complex128)
        self._afc_every = int(self.rate * 0.25)
        self._afc_count = 0
        self._afc_power: Optional[NDArray[np.float64]] = None     # averaged spectrum
        self._level_decay = math.exp(-self._env_dt / 1000.0)        # signal level falls with τ = 1 s
        self._noise_every = max(1, int(round(100.0 / self._env_dt)))
        self.wpm_guess = wpm_guess
        self.reset()

    def reset(self) -> None:
        """Forget timing and levels (after retuning to another station)."""
        self.dit = wpm_to_dit_ms(self.wpm_guess)
        self._marks: deque[float] = deque(maxlen=24)
        self._key = False
        self._run = 0.0              # ms in the current state
        self._pending = 0.0          # ms the opposite state has lasted (debounce)
        self._elements = ''
        self._space_emitted = True
        self._history.clear()
        self._samples = 0
        self.offset_hz = 0.0
        self.mixer.set_offset(0.0)
        self._afc_power = None
        self.noise = 0.0
        self.level = 0.0
        self.signal = False
        self.time_ms = 0.0
        self.last_mark_ms: Optional[float] = None
        self._snr = 0.0

    # ------------------------------------------------------------------ properties
    @property
    def wpm(self) -> float:
        return round(1200.0 / self.dit, 1)

    @property
    def snr_db(self) -> float:
        """Signal-to-noise ratio (envelope, dB) measured at the end of the last mark."""
        return self._snr

    # ------------------------------------------------------------------ AFC
    def _afc(self, x: NDArray[np.complex128]) -> None:
        """
        Every 0.25 s: move the strongest carrier within ±afc_range to 0 Hz.

        Decisions use a spectrum averaged over the last seconds: a keyed carrier
        adds up, noise peaks do not, so the AFC does not jump to noise.
        """
        keep = int(self.rate * 0.5)
        self._afc_buffer = np.concatenate((self._afc_buffer, x))[-keep:]
        self._afc_count += len(x)
        if self._afc_count < self._afc_every or len(self._afc_buffer) < keep:
            return
        self._afc_count = 0
        n = 1 << int(math.ceil(math.log2(len(self._afc_buffer))))
        spectrum = np.abs(np.fft.fft(self._afc_buffer * np.hanning(len(self._afc_buffer)), n)) ** 2
        freqs = np.fft.fftfreq(n, 1.0 / self.rate)
        band = np.abs(freqs) <= self.afc_range
        current = spectrum[band]
        if self._afc_power is None or len(self._afc_power) != len(current):
            self._afc_power = current
            return
        self._afc_power = 0.8 * self._afc_power + 0.2 * current
        power, f = self._afc_power, freqs[band]
        peak = int(np.argmax(power))
        if power[peak] < 20.0 * float(np.median(power)):     # no clear carrier: keep the offset
            return
        target = float(f[peak])
        if abs(target - self.offset_hz) > 15.0:
            self.offset_hz += 0.7 * (target - self.offset_hz)
            self.mixer.set_offset(self.offset_hz)

    # ------------------------------------------------------------------ envelope
    def _envelope(self, x: NDArray[np.complex128]) -> NDArray[np.float64]:
        env = np.concatenate((self._env_carry, np.abs(self.filter.process(self.mixer.process(x)))))
        usable = len(env) - len(env) % self._env_factor
        self._env_carry = env[usable:]
        blocks = env[:usable].reshape(-1, self._env_factor).mean(axis=1)
        # moving average over ~1/5 dit: smooths noise, keeps the shortest gaps
        taps = max(2, int(round(0.2 * self.dit / self._env_dt)))
        if abs(taps - self._smooth_taps) > max(1, 0.3 * self._smooth_taps):
            self._smooth_taps = taps
            self._smooth_zi = np.zeros(taps - 1, dtype=np.float64)
        n = self._smooth_taps
        result, self._smooth_zi = signal.lfilter(np.full(n, 1.0 / n), 1.0, blocks, zi=self._smooth_zi)
        out: NDArray[np.float64] = np.asarray(result, dtype=np.float64)
        return out

    # ------------------------------------------------------------------ timing
    def _learn(self, mark: float) -> None:
        """Update the dit estimate from the recent marks (two clusters: dits and dahs)."""
        self._marks.append(mark)
        marks = np.array(self._marks)
        if len(marks) >= 4:
            short, long_ = float(marks.min()), float(marks.max())
            for _ in range(6):
                is_long = np.abs(marks - long_) < np.abs(marks - short)
                if is_long.all() or not is_long.any():
                    break
                short, long_ = float(marks[~is_long].mean()), float(marks[is_long].mean())
            if long_ / max(short, 1e-6) >= 2.0:
                self.dit = 0.5 * short + 0.5 * long_ / 3.0
            elif mark < 2.0 * self.dit:
                self.dit = 0.7 * self.dit + 0.3 * float(marks.mean())
            else:
                self.dit = 0.7 * self.dit + 0.3 * float(marks.mean()) / 3.0
        else:
            self.dit = 0.7 * self.dit + 0.3 * (mark if mark < 2.0 * self.dit else mark / 3.0)
        self.dit = min(max(self.dit, self.MIN_DIT_MS), self.MAX_DIT_MS)

    def _end_mark(self, mark: float) -> None:
        self._learn(mark)
        self._elements += '.' if mark < 2.0 * self.dit else '-'
        if len(self._elements) > 9:           # garbage: no symbol is that long
            self._elements = self._elements[-9:]

    def _flush_char(self, out: list[str]) -> None:
        if self._elements:
            out.append(MORSE.get(self._elements, '*'))
            self._elements = ''
            self._space_emitted = False

    def process(self, baseband: NDArray[np.complexfloating]) -> str:
        x = np.asarray(baseband, dtype=np.complex128)
        if len(x) == 0:
            return ''
        self._afc(x)
        env = self._envelope(x)
        out: list[str] = []
        if len(env) == 0:
            return ''
        debounce = max(4.0, 0.25 * self.dit)
        dt = self._env_dt
        warmup = len(self._history) * dt < self.WARMUP_MS
        for v in env:
            self.time_ms += dt
            self._run += dt
            self._history.append(float(v))
            self._samples += 1
            if self._samples % self._noise_every == 0:
                # noise floor every 100 ms of signal time (independent of the chunk size)
                self.noise = float(np.percentile(np.fromiter(self._history, dtype=np.float64), 20))
                warmup = len(self._history) * dt < self.WARMUP_MS
            if warmup:
                continue
            floor = self.noise * self.min_snr
            # signal level: follows peaks at once, falls slowly (fading, word gaps)
            self.level = max(float(v), self.level * self._level_decay, self.noise)
            self.signal = self.level > floor
            span = self.level - self.noise
            threshold = self.noise + (0.40 if self._key else 0.55) * span
            want = bool(v > threshold) if self.signal else False
            if want != self._key:
                self._pending += dt
                if self._pending >= debounce:
                    length = self._run - self._pending        # the state ended when the change began
                    if self._key:
                        self._end_mark(length)
                        self.last_mark_ms = self.time_ms
                        if self.noise > 0:
                            self._snr = round(20.0 * math.log10(max(self.level / self.noise, 1e-9)), 1)
                    self._key = want
                    self._run = self._pending
                    self._pending = 0.0
            else:
                self._pending = 0.0
            if not self._key:
                if self._run >= 2.0 * self.dit:
                    self._flush_char(out)
                if self._run >= 5.0 * self.dit and not self._space_emitted:
                    out.append(' ')
                    self._space_emitted = True
        return ''.join(out)

    def seconds_since_mark(self) -> float:
        """Seconds since the last key-down ended (inf before the first one)."""
        if self._key:
            return 0.0
        return math.inf if self.last_mark_ms is None else (self.time_ms - self.last_mark_ms) / 1000.0
