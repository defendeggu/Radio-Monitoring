"""
Offline evaluation of the skimmer (phase 0): precision and recall against reference spots.

    precision  share of the spotted callsigns that are right (target ≥ 90 %)
    recall     share of the reference callsigns that were found (target ≥ 30 % for SSB)

CW: an IQ recording of the skimmer (record_iq) with its sidecar; the reference is
the RBN log written next to it (<name>.rbn.jsonl) or a text file with one
callsign per line. A spot counts as right when the reference has the callsign
(within 1 kHz when the reference has frequencies).

    python -m radiomoni.skimmer.evaluate cw recordings/skimmer/skimmer_20261128_120000_14035kHz.wav

SSB: WAV files of SSB transmissions and a text file with the callsigns heard in
them. Each file is transcribed with faster-whisper (model, prompt and hotwords
selectable), the callsigns come from radiomoni.contest.phonetic. "confirmed"
only counts calls that are self-identified (after CQ, contest, this is …) or
heard at least twice.

    python -m radiomoni.skimmer.evaluate ssb --reference calls.txt --model turbo clips/*.wav

SSB on the skimmer's own IQ recording (mode SSB): the full SSB core (signal
detection, channels, Whisper, confirmation) runs offline, the reference is a
callsign list:

    python -m radiomoni.skimmer.evaluate ssb-iq recordings/skimmer/skimmer_…_14237kHz.wav --reference calls.txt

Results as a table, with --json as JSON.
"""

import argparse
import json
import os
import sys
import wave
from collections import Counter
from typing import Any, Iterable, Optional

import numpy as np

from radiomoni.contest import phonetic
from radiomoni.skimmer.core import SkimmerCore

CHUNK_SECONDS = 0.05
MATCH_HZ = 1000


def load_reference(path: str) -> list[dict[str, Any]]:
    """RBN JSONL ({callsign, frequency, …} per line) or plain text (one callsign per line, # comments)."""
    refs = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('{'):
                item = json.loads(line)
                refs.append({'callsign': item['callsign'].upper(), 'frequency': item.get('frequency')})
            else:
                refs.append({'callsign': line.split(',')[-1].strip().upper(), 'frequency': None})
    return refs


def score(spots: Iterable[dict[str, Any]], reference: list[dict[str, Any]]) -> dict[str, Any]:
    """Precision / recall over unique callsigns."""
    ref_calls = {r['callsign'] for r in reference}

    def right(spot: dict[str, Any]) -> bool:
        for r in reference:
            if r['callsign'] != spot['callsign']:
                continue
            if r.get('frequency') is None or spot.get('frequency') is None:
                return True
            if abs(int(r['frequency']) - int(spot['frequency'])) <= MATCH_HZ:
                return True
        return False

    spotted: dict[str, bool] = {}
    for s in spots:
        spotted[s['callsign']] = spotted.get(s['callsign'], False) or right(s)
    correct = sorted(c for c, ok in spotted.items() if ok)
    wrong = sorted(c for c, ok in spotted.items() if not ok)
    found = {c for c in correct if c in ref_calls}
    return {
        'spotted': len(spotted), 'correct': len(correct), 'wrong': wrong,
        'precision': round(len(correct) / len(spotted), 3) if spotted else None,
        'reference': len(ref_calls), 'found': len(found),
        'recall': round(len(found) / len(ref_calls), 3) if ref_calls else None,
        'missed': sorted(ref_calls - found),
    }


def _read_iq(wav_path: str, centre_hz: Optional[int], rate: Optional[float]) -> tuple[int, float, Any]:
    sidecar = os.path.splitext(wav_path)[0] + '.json'
    if os.path.isfile(sidecar):
        with open(sidecar) as f:
            meta = json.load(f)
        centre_hz = centre_hz or int(meta['centre_hz'])
        rate = rate or float(meta['rate'])
    if centre_hz is None:
        raise ValueError('centre frequency unknown: no sidecar JSON, pass --centre')
    w = wave.open(wav_path, 'rb')
    return centre_hz, rate or float(w.getframerate()), w


def _chunks(w: Any, rate: float) -> Iterable[tuple[np.ndarray, float]]:
    chunk = int(rate * CHUNK_SECONDS)
    position = 0
    while True:
        frames = w.readframes(chunk)
        if not frames:
            return
        pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
        iq = (pcm[0::2] + 1j * pcm[1::2]).astype(np.complex64)
        yield iq, position / rate
        position += len(iq)


def run_ssb_iq(wav_path: str, transcribe: Any, centre_hz: Optional[int] = None, rate: Optional[float] = None,
               max_channels: int = 8, validate: Any = None) -> list[dict[str, Any]]:
    """The SSB core on an IQ recording; transcription runs inline (no real-time limit)."""
    from radiomoni.skimmer.ssb import SsbCore
    centre_hz, rate, w = _read_iq(wav_path, centre_hz, rate)
    spots: list[dict[str, Any]] = []
    with w:
        core = SsbCore(rate, centre_hz, max_channels, on_spot=spots.append, validate=validate,
                       transcribe=transcribe, sync=True)
        for iq, now in _chunks(w, rate):
            core.feed(iq, now=now)
    for s in spots:
        s.pop('clip', None)
    return spots


# ------------------------------------------------------------------ CW
def run_cw(wav_path: str, centre_hz: Optional[int] = None, rate: Optional[float] = None,
           max_decoders: int = 32, validate: Any = None) -> list[dict[str, Any]]:
    centre_hz, rate, w = _read_iq(wav_path, centre_hz, rate)
    spots: list[dict[str, Any]] = []
    with w:
        core = SkimmerCore(rate, centre_hz, max_decoders, on_spot=spots.append, validate=validate)
        for iq, now in _chunks(w, rate):
            core.feed(iq, now=now)
    return spots


# ------------------------------------------------------------------ SSB
def ssb_calls(text: str, confirmed: bool) -> list[str]:
    heard = phonetic.extract(text)
    if not confirmed:
        return [h.callsign for h in heard]
    counts = Counter(h.callsign for h in heard)
    return sorted({h.callsign for h in heard if h.self_identified or counts[h.callsign] >= 2})


def run_ssb(files: list[str], model: str, prompt: Optional[str], hotwords: Optional[str],
            language: Optional[str], device: str = 'cpu') -> list[dict[str, Any]]:
    from radiomoni.transcription_service import TranscriptionService
    service = TranscriptionService(model=model, device=device, compute_type='int8' if device == 'cpu' else 'float16')
    results = []
    for path in files:
        result = service.transcribe(path, language=language, initial_prompt=prompt, hotwords=hotwords)
        results.append({'file': os.path.basename(path), 'text': result['text']})
    return results


def main(argv: Optional[list[str]] = None) -> int:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description='Skimmer evaluation: precision and recall')
    sub = parser.add_subparsers(dest='kind', required=True)
    cw = sub.add_parser('cw', help='CW skimmer on an IQ recording')
    cw.add_argument('wav')
    cw.add_argument('--reference', help='RBN JSONL or callsign list (default: <name>.rbn.jsonl)')
    cw.add_argument('--centre', type=int)
    cw.add_argument('--rate', type=float)
    cw.add_argument('--decoders', type=int, default=32)
    ssb_iq = sub.add_parser('ssb-iq', help='SSB skimmer on an IQ recording (mode SSB)')
    ssb_iq.add_argument('wav')
    ssb_iq.add_argument('--reference', required=True, help='callsign list')
    ssb_iq.add_argument('--language', default='en')
    ssb_iq.add_argument('--channels', type=int, default=8)
    ssb = sub.add_parser('ssb', help='Whisper + phonetic parser on SSB clips')
    ssb.add_argument('files', nargs='+')
    ssb.add_argument('--reference', required=True)
    ssb.add_argument('--model', default='small')
    ssb.add_argument('--prompt', default=None, help='initial_prompt, e.g. contest phrases')
    ssb.add_argument('--hotwords', default=None, help='e.g. the phonetic alphabet')
    ssb.add_argument('--language', default=None)
    ssb.add_argument('--device', default='cpu')
    for p in (cw, ssb_iq, ssb):
        p.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    result: dict[str, Any]
    if args.kind == 'ssb-iq':
        from radiomoni.contest import refdata
        from radiomoni.skimmer.session import SkimmerSession
        from radiomoni.skimmer.ssb import whisper_transcriber
        spots = run_ssb_iq(args.wav, whisper_transcriber(args.language), max_channels=args.channels,
                           validate=SkimmerSession._validator(refdata.get()))
        result = {'kind': 'ssb-iq', 'file': args.wav, **score(spots, load_reference(args.reference)),
                  'spots': [{k: s.get(k) for k in ('callsign', 'khz', 'snr_db', 'text')} for s in spots]}
    elif args.kind == 'cw':
        from radiomoni.contest import refdata
        from radiomoni.skimmer.session import SkimmerSession
        reference = args.reference or os.path.splitext(args.wav)[0] + '.rbn.jsonl'
        spots = run_cw(args.wav, args.centre, args.rate, args.decoders,
                       validate=SkimmerSession._validator(refdata.get()))
        result = {'kind': 'cw', 'file': args.wav, **score(spots, load_reference(reference))}
        result['spots'] = [{k: s[k] for k in ('callsign', 'khz', 'wpm', 'snr_db', 'type')} for s in spots]
    else:
        transcripts = run_ssb(args.files, args.model, args.prompt, args.hotwords, args.language, args.device)
        reference = load_reference(args.reference)
        raw = [{'callsign': c, 'frequency': None} for t in transcripts for c in ssb_calls(t['text'], False)]
        confirmed = [{'callsign': c, 'frequency': None} for t in transcripts for c in ssb_calls(t['text'], True)]
        result = {'kind': 'ssb', 'model': args.model, 'prompt': args.prompt, 'hotwords': args.hotwords,
                  'raw': score(raw, reference), 'confirmed': score(confirmed, reference),
                  'transcripts': transcripts}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    blocks = [('', result)] if args.kind in ('cw', 'ssb-iq') else [('raw', result['raw']), ('confirmed', result['confirmed'])]
    for label, r in blocks:
        prefix = f'[{label}] ' if label else ''
        print(f"{prefix}precision {r['precision']}  ({r['correct']}/{r['spotted']} spotted calls right)")
        print(f"{prefix}recall    {r['recall']}  ({r['found']}/{r['reference']} reference calls found)")
        if r['wrong']:
            print(f"{prefix}wrong:  {' '.join(r['wrong'][:40])}")
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
