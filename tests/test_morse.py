"""CW decoder: synthetic Morse at different speeds, noise, frequency offsets and fading."""

import numpy as np
import pytest

from radiomoni.morse import ENCODE, MORSE, CwDecoder, callsigns, wpm_to_dit_ms

RATE = 4000


def keying(text: str, wpm: float) -> list[tuple[bool, float]]:
    """(key down?, milliseconds) for `text` with standard PARIS timing."""
    dit = wpm_to_dit_ms(wpm)
    out: list[tuple[bool, float]] = [(False, 7 * dit)]
    for word in text.split(' '):
        for ci, ch in enumerate(word):
            code = ENCODE[ch] if len(ch) == 1 else ENCODE[ch]
            for ei, el in enumerate(code):
                out.append((True, dit if el == '.' else 3 * dit))
                if ei < len(code) - 1:
                    out.append((False, dit))
            if ci < len(word) - 1:
                out.append((False, 3 * dit))
        out.append((False, 7 * dit))
    out.append((False, 1500))
    return out


def cw_signal(text: str, wpm: float, offset_hz: float = 0.0, snr_db: float = 20.0, fading_db: float = 0.0,
              seed: int = 0) -> np.ndarray:
    """Complex baseband: keyed carrier (5 ms raised-cosine edges) + white noise at `snr_db` (in RATE)."""
    key = np.concatenate([np.full(int(ms * RATE / 1000), 1.0 if down else 0.0) for down, ms in keying(text, wpm)])
    edge = int(0.005 * RATE)
    window = np.hanning(2 * edge + 1)
    envelope = np.convolve(key, window / window.sum(), mode='same')
    t = np.arange(len(envelope)) / RATE
    if fading_db:
        envelope *= 10 ** (-fading_db / 20 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.25 * t)))
    carrier = envelope * np.exp(2j * np.pi * offset_hz * t)
    rng = np.random.default_rng(seed)
    noise_amp = 10 ** (-snr_db / 20) / np.sqrt(2)
    noise = noise_amp * (rng.standard_normal(len(t)) + 1j * rng.standard_normal(len(t)))
    return (carrier + noise).astype(np.complex64)


def decode(x: np.ndarray, chunk: int = 200, **kwargs) -> tuple[str, CwDecoder]:
    decoder = CwDecoder(RATE, **kwargs)
    text = ''.join(decoder.process(x[i:i + chunk]) for i in range(0, len(x), chunk))
    return text.strip(), decoder


def cer(expected: str, got: str) -> float:
    """Character error rate (Levenshtein distance / length)."""
    a, b = expected, got
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(1, len(a))


TEXT = 'CQ CQ DE HB9XYZ HB9XYZ K'


class TestTable:
    def test_table_round_trip(self):
        assert all(MORSE[ENCODE[ch]] == ch for ch in 'ABCXYZ0123456789/?=')
        assert MORSE['.-.-.'] == '<AR>' and MORSE['...-.-'] == '<SK>'

    def test_callsigns(self):
        assert callsigns('CQ DE HB9XYZ HB9XYZ = UR 5NN TU DL1ABC/P 4X6TU K') == ['HB9XYZ', 'DL1ABC/P', '4X6TU']
        assert callsigns('5NN TU 73 QRZ') == []


class TestDecoder:
    @pytest.mark.parametrize('wpm', [12, 20, 30])
    def test_speeds(self, wpm):
        text, decoder = decode(cw_signal(TEXT, wpm), wpm_guess=20)
        assert cer(TEXT, text) < 0.05, text
        assert decoder.wpm == pytest.approx(wpm, rel=0.15)

    def test_noise(self):
        text, decoder = decode(cw_signal(TEXT, 22, snr_db=-3))    # -3 dB in 4 kHz ≈ +10 dB in 200 Hz
        assert cer(TEXT, text) < 0.08, text
        assert decoder.snr_db > 6

    def test_afc_follows_an_offset_carrier(self):
        # the AFC needs about a second of keyed carrier to lock: "VVV" lets it settle, as beacons do
        text, decoder = decode(cw_signal('VVV VVV ' + TEXT, 20, offset_hz=180, snr_db=10))
        assert text.endswith('K') and cer(TEXT, text[-len(TEXT):]) < 0.05, text
        assert decoder.offset_hz == pytest.approx(180, abs=15)

    def test_fading(self):
        text, _ = decode(cw_signal(TEXT, 20, snr_db=10, fading_db=8))
        assert cer(TEXT, text) < 0.1, text

    def test_noise_only_gives_no_text(self):
        rng = np.random.default_rng(3)
        x = (rng.standard_normal(RATE * 5) + 1j * rng.standard_normal(RATE * 5)).astype(np.complex64)
        text, decoder = decode(x)
        assert len(text.replace(' ', '')) <= 2, text

    def test_chunk_size_does_not_matter(self):
        x = cw_signal(TEXT, 25, snr_db=15)
        assert decode(x, chunk=97)[0] == decode(x, chunk=1000)[0]

    def test_reset_relearns_speed(self):
        decoder = CwDecoder(RATE)
        x = cw_signal('TEST TEST', 35)
        for i in range(0, len(x), 200):
            decoder.process(x[i:i + 200])
        decoder.reset()
        assert decoder.wpm == pytest.approx(20)
