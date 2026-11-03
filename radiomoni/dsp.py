"""
Streaming DSP building blocks for live IQ.

Every block keeps its state (filter memory, oscillator phase) between calls,
so a signal processed in chunks gives the same result as in one piece — no
clicks at chunk boundaries. Used by the spectrum/waterfall session (live
listening) and the CW decoder.

    iq ──► Mixer (tune) ──► Decimator (channel filter) ──► Demodulator ──► Agc ──► audio
    iq ──► SpectrumAnalyzer (averaged FFT) ──► dBFS row for the waterfall
"""

import math
from typing import Optional

import numpy as np
from numpy.typing import NDArray
from scipy import signal

ComplexArray = NDArray[np.complex128]
FloatArray = NDArray[np.float64]

MODULATIONS = ('FM', 'AM', 'USB', 'LSB', 'CW')


class Mixer:
    """Shift the spectrum by -offset_hz (moves a signal at +offset to 0 Hz); phase is continuous."""

    def __init__(self, sample_rate: float, offset_hz: float = 0.0):
        self.sample_rate = float(sample_rate)
        self.offset_hz = float(offset_hz)
        self._phase = 0.0

    def set_offset(self, offset_hz: float) -> None:
        self.offset_hz = float(offset_hz)

    def process(self, x: NDArray[np.complexfloating]) -> ComplexArray:
        y: ComplexArray = np.asarray(x, dtype=np.complex128)
        if self.offset_hz == 0.0 or len(y) == 0:
            return y
        step = -2.0 * math.pi * self.offset_hz / self.sample_rate
        phases = self._phase + step * np.arange(len(y))
        self._phase = float((self._phase + step * len(y)) % (2.0 * math.pi))
        out: ComplexArray = y * np.exp(1j * phases)
        return out


class DecimationStage:
    """IIR low-pass followed by decimation; filter state and decimation phase
    carry over between chunks."""

    def __init__(self, input_rate: float, cutoff_hz: float, factor: int, order: int):
        self.factor = factor
        self.sos = signal.butter(order, cutoff_hz, fs=input_rate, output='sos')
        self.zi = np.zeros((self.sos.shape[0], 2), dtype=np.complex128)
        self.offset = 0  # index in the next chunk of the next sample to keep

    def process(self, x: ComplexArray) -> ComplexArray:
        y, self.zi = signal.sosfilt(self.sos, x, zi=self.zi)
        out: ComplexArray = y[self.offset::self.factor]
        self.offset = (self.offset - len(y)) % self.factor
        return out


def _prime_factors(n: int) -> list[int]:
    factors, p = [], 2
    while p * p <= n:
        while n % p == 0:
            factors.append(p)
            n //= p
        p += 1
    if n > 1:
        factors.append(n)
    return factors


def decimation_factors(input_rate: int, target_rate: int, max_stage: int = 10) -> list[int]:
    """
    Split the decimation input_rate → ~target_rate into stages of at most `max_stage`.

    The total factor is the integer closest to input/target whose prime factors
    are all small (≤ 7), so every stage stays cheap and well-behaved. The output
    rate is input_rate / prod(factors) — close to, not exactly, the target.
    """
    ideal = max(1.0, input_rate / target_rate)
    best = 1
    for total in range(max(1, int(ideal * 0.8)), int(ideal * 1.25) + 2):
        if max(_prime_factors(total) or [1]) <= 7 and abs(total - ideal) < abs(best - ideal):
            best = total
    stages: list[int] = []
    current = 1
    for p in sorted(_prime_factors(best), reverse=True):
        if current * p <= max_stage:
            current *= p
        else:
            stages.append(current)
            current = p
    if current > 1:
        stages.append(current)
    return sorted(stages, reverse=True) or [1]


class Decimator:
    """Channel filter + decimation from the SDR rate down to about `target_rate`."""

    def __init__(self, input_rate: int, target_rate: int, bandwidth_hz: Optional[float] = None):
        self.input_rate = int(input_rate)
        self._stages: list[DecimationStage] = []
        rate = float(input_rate)
        factors = decimation_factors(int(input_rate), int(target_rate))
        for i, factor in enumerate(factors):
            out_rate = rate / factor
            last = i == len(factors) - 1
            cutoff = 0.4 * out_rate
            if last and bandwidth_hz:
                cutoff = min(cutoff, bandwidth_hz / 2.0)
            if factor > 1 or (last and bandwidth_hz):
                self._stages.append(DecimationStage(rate, cutoff, factor, order=6 if last else 5))
            rate = out_rate
        self.output_rate = rate

    def process(self, iq: NDArray[np.complexfloating]) -> ComplexArray:
        x: ComplexArray = np.asarray(iq, dtype=np.complex128)
        for stage in self._stages:
            x = stage.process(x)
        return x


BLOCK = 256   # granularity of the level trackers (AM DC, AGC)


def _blocks(n: int, pos: int) -> list[tuple[int, int]]:
    """Slices of [0, n) aligned to the running sample count `pos`, so block edges
    do not depend on how the input is chunked."""
    edges, start = [], 0
    first = BLOCK - (pos % BLOCK)
    while start < n:
        end = min(n, start + (first if start == 0 else BLOCK))
        edges.append((start, end))
        start = end
    return edges


class ComplexFilter:
    """Real-coefficient FIR applied to complex samples, with state."""

    def __init__(self, taps: NDArray[np.float64]):
        self.taps = taps
        self.zi = np.zeros(len(taps) - 1, dtype=np.complex128)

    def process(self, x: ComplexArray) -> ComplexArray:
        y, self.zi = signal.lfilter(self.taps, 1.0, x, zi=self.zi)
        out: ComplexArray = np.asarray(y, dtype=np.complex128)
        return out


class Demodulator:
    """
    Demodulate complex baseband (signal at 0 Hz) at `rate` into real audio.

    FM: narrowband discriminator (5 kHz deviation → ±1)
    AM: envelope with DC block
    USB/LSB: one sideband, 300–2700 Hz
    CW: narrow filter around the carrier, heard as a tone at `bfo_hz`
    """

    def __init__(self, modulation: str, rate: float, cw_bandwidth_hz: float = 500.0, bfo_hz: float = 700.0):
        self.modulation = modulation.upper()
        if self.modulation not in MODULATIONS:
            raise ValueError(f"Unsupported modulation: {modulation}")
        self.rate = float(rate)
        self.bfo_hz = float(bfo_hz)
        self._n = 0              # sample counter for the SSB/CW oscillators
        self._last: Optional[complex] = None
        self._dc: Optional[float] = None
        self._block_sum = 0.0      # AM: running sum/count of the current level block
        self._block_count = 0
        self._filter: Optional[ComplexFilter] = None
        if self.modulation in ('USB', 'LSB'):
            self._filter = ComplexFilter(signal.firwin(127, 1200.0, fs=self.rate))
        elif self.modulation == 'CW':
            self._filter = ComplexFilter(signal.firwin(255, cw_bandwidth_hz / 2.0, fs=self.rate))

    def _oscillator(self, freq: float, n: int) -> ComplexArray:
        t = (self._n + np.arange(n)) / self.rate
        out: ComplexArray = np.exp(2j * math.pi * freq * t)
        return out

    def process(self, x: ComplexArray) -> FloatArray:
        n = len(x)
        if n == 0:
            return np.zeros(0, dtype=np.float64)
        if self.modulation == 'FM':
            if self._last is None:
                self._last = complex(x[0])
            prev = np.concatenate(([self._last], x[:-1]))
            self._last = complex(x[-1])
            fm: FloatArray = np.angle(x * np.conj(prev)) * (self.rate / (2.0 * math.pi * 5000.0))
            return fm
        if self.modulation == 'AM':
            # envelope minus its slowly tracked mean (~0.2 s); the mean is updated
            # once per BLOCK samples of the running count
            env = np.abs(x).astype(np.float64)
            out = np.empty(n, dtype=np.float64)
            alpha = 1.0 - math.exp(-BLOCK / (0.2 * self.rate))
            dc = self._dc if self._dc is not None else float(env[:BLOCK].mean())
            for a, b in _blocks(n, self._n):
                out[a:b] = env[a:b] - dc
                self._block_sum += float(env[a:b].sum())
                self._block_count += b - a
                if self._block_count >= BLOCK:
                    dc += alpha * (self._block_sum / self._block_count - dc)
                    self._block_sum, self._block_count = 0.0, 0
            self._dc = dc
            self._n += n
            return out
        assert self._filter is not None
        if self.modulation in ('USB', 'LSB'):
            centre = 1500.0 if self.modulation == 'USB' else -1500.0
            down = x * self._oscillator(-centre, n)
            band = self._filter.process(down)
            audio: FloatArray = (band * self._oscillator(centre, n)).real
        else:  # CW: keep ±bw/2 around the carrier, then beat it to an audible tone
            band = self._filter.process(x)
            audio = (band * self._oscillator(self.bfo_hz, n)).real
        self._n += n
        return audio


class Agc:
    """Automatic gain control: fast attack, slow decay, output peak ≈ `target`."""

    def __init__(self, rate: float, target: float = 0.5, attack_s: float = 0.01, decay_s: float = 0.8,
                 floor: float = 1e-4):
        self.target = target
        self.floor = floor
        self._attack = 1.0 - math.exp(-BLOCK / (attack_s * rate))
        self._decay = 1.0 - math.exp(-BLOCK / (decay_s * rate))
        self._level = floor
        self._peak = 0.0     # peak of the current (unfinished) block
        self._pos = 0

    def process(self, audio: FloatArray) -> FloatArray:
        """The gain follows the peak of each finished BLOCK of the running sample count."""
        out = np.empty_like(audio)
        level = self._level
        for a, b in _blocks(len(audio), self._pos):
            out[a:b] = audio[a:b] * (self.target / level)
            self._peak = max(self._peak, float(np.max(np.abs(audio[a:b]))))
            if (self._pos + b) % BLOCK == 0:
                level += (self._attack if self._peak > level else self._decay) * (self._peak - level)
                level = max(level, self.floor)
                self._peak = 0.0
        self._pos += len(audio)
        self._level = level
        result: FloatArray = np.clip(out, -1.0, 1.0)
        return result


class ChannelReceiver:
    """
    One narrow receive channel inside the SDR bandwidth: tune, filter, demodulate, AGC.

    `offset_hz` is the channel frequency minus the SDR centre frequency.
    Output audio rate is about `audio_rate` (exact value in .audio_rate).
    """

    def __init__(self, input_rate: int, offset_hz: float, modulation: str = 'FM',
                 audio_rate: int = 12_000, cw_bandwidth_hz: float = 500.0, bfo_hz: float = 700.0):
        self.modulation = modulation.upper()
        self.mixer = Mixer(input_rate, offset_hz)
        bandwidth = {'FM': 12_500.0, 'AM': 8_000.0}.get(self.modulation)
        self.decimator = Decimator(input_rate, audio_rate, bandwidth)
        self.audio_rate = self.decimator.output_rate
        self.demod = Demodulator(self.modulation, self.audio_rate, cw_bandwidth_hz, bfo_hz)
        self.agc = Agc(self.audio_rate) if self.modulation != 'FM' else None

    def set_offset(self, offset_hz: float) -> None:
        self.mixer.set_offset(offset_hz)

    def process(self, iq: NDArray[np.complexfloating]) -> FloatArray:
        audio = self.demod.process(self.decimator.process(self.mixer.process(iq)))
        if self.agc is not None:
            audio = self.agc.process(audio)
        result: FloatArray = np.clip(audio, -1.0, 1.0)
        return result


class SpectrumAnalyzer:
    """
    Averaged power spectrum (Welch, Hann window) for the waterfall.

    feed() any amount of IQ; frame() returns the mean spectrum in dBFS
    (DC in the middle) of everything fed since the last frame, or None.
    At most `max_blocks` FFTs are computed per frame, spread over the input,
    so wide bandwidths stay cheap.
    """

    def __init__(self, fft_size: int = 2048, max_blocks: int = 16):
        self.fft_size = int(fft_size)
        self.max_blocks = max_blocks
        self.window = np.hanning(self.fft_size).astype(np.float64)
        self._norm = float(np.sum(self.window) ** 2)
        self._chunks: list[NDArray[np.complexfloating]] = []
        self._samples = 0

    def feed(self, iq: NDArray[np.complexfloating]) -> None:
        if len(iq):
            self._chunks.append(iq)
            self._samples += len(iq)

    def frame(self) -> Optional[FloatArray]:
        if self._samples < self.fft_size:
            return None
        data = np.concatenate(self._chunks)
        self._chunks, self._samples = [], 0
        blocks = len(data) // self.fft_size
        step = max(1, blocks // self.max_blocks)
        picked = data[:blocks * self.fft_size].reshape(blocks, self.fft_size)[::step][:self.max_blocks]
        spectra = np.fft.fft(picked * self.window, axis=1)
        power = np.mean(np.abs(spectra) ** 2, axis=0) / self._norm
        db: FloatArray = 10.0 * np.log10(np.fft.fftshift(power) + 1e-20)
        return db


def mask_dc(db: FloatArray, width: int = 2) -> FloatArray:
    """Replace the bins around DC (centre) by the mean of their neighbours (HackRF DC spike)."""
    centre = len(db) // 2
    lo, hi = max(0, centre - width), min(len(db), centre + width + 1)
    neighbours = np.concatenate((db[max(0, lo - width):lo], db[hi:hi + width]))
    out = db.copy()
    if len(neighbours):
        out[lo:hi] = float(np.mean(neighbours))
    return out


def to_uint8(db: FloatArray, db_min: float, db_max: float) -> NDArray[np.uint8]:
    """Map dB values to 0..255 for transport (db_min → 0, db_max → 255)."""
    scaled = (db - db_min) * (255.0 / max(1e-6, db_max - db_min))
    out: NDArray[np.uint8] = np.clip(np.round(scaled), 0, 255).astype(np.uint8)
    return out
