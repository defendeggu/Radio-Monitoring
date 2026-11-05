"""
Callsigns from transcribed SSB speech.

Whisper writes callsigns in many shapes: "HB9XYZ", "H B 9 X Y Z", "Hotel Bravo
Nine X-ray Yankee Zulu", "hotel bravo niner x-ray yankee zulu stroke portable".
The parser turns phonetic words (NATO plus common contest variants such as
"Kilowatt", "Japan", "Portugal") and spoken digits (English, German, French,
Italian) into characters, collects runs of characters and finds callsigns in
them. A callsign is "self-identified" when it follows CQ, contest, test,
field day, this is, de or QRZ, or is followed by contest, test or QRZ —
that is the station on the frequency.
"""

import re
from dataclasses import dataclass

from radiomoni.contest.callsign import is_valid

LETTERS: dict[str, str] = {}
for _letter, _words in {
    'A': 'alfa alpha able america amsterdam', 'B': 'bravo baker boston brazil',
    'C': 'charlie canada chile', 'D': 'delta denmark david',
    'E': 'echo easy england edward', 'F': 'foxtrot fox france florida frank',
    'G': 'golf germany george', 'H': 'hotel honolulu henry holland',
    'I': 'india italy item', 'J': 'juliett juliet japan john',
    'K': 'kilo kilowatt king kentucky', 'L': 'lima london love lithuania',
    'M': 'mike mexico mary madagascar', 'N': 'november norway nancy nicaragua',
    'O': 'oscar ontario ocean', 'P': 'papa portugal peter pacific',
    'Q': 'quebec queen', 'R': 'romeo radio roger robert',
    'S': 'sierra sugar santiago spain sweden', 'T': 'tango texas tokyo',
    'U': 'uniform united uncle uruguay', 'V': 'victor venezuela victoria virginia',
    'W': 'whiskey whisky washington william', 'X': 'xray x-ray xylophone',
    'Y': 'yankee yokohama young', 'Z': 'zulu zanzibar zebra zealand',
}.items():
    for _w in _words.split():
        LETTERS[_w] = _letter

DIGITS: dict[str, str] = {}
for _digit, _words in {
    '0': 'zero null nul zéro', '1': 'one wun eins un uno', '2': 'two zwei zwo deux due',
    '3': 'three tree drei trois tre', '4': 'four fower vier quatre quattro',
    '5': 'five fife fünf fuenf cinq cinque', '6': 'six sechs sei', '7': 'seven sieben sept sette',
    '8': 'eight ait acht huit otto', '9': 'nine niner neun neuf nove',
}.items():
    for _w in _words.split():
        DIGITS[_w] = _digit

STROKE = {'stroke': '/', 'slash': '/', 'strich': '/', 'portable': '/P', 'mobile': '/M'}
SELF_ID = re.compile(r'\b(cq|contest|test|field ?day|fieldday|this is|de|qrz)\s*$')
# a run station ends a QSO with "thank you, HB9XYZ contest" / "HB9XYZ QRZ"
SELF_ID_AFTER = re.compile(r'^\s*\|?\s*(contest|test|qrz|field ?day)\b')
CALL_IN_RUN = re.compile(r'[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z](?:/[A-Z0-9]{1,4})?')


@dataclass
class Heard:
    callsign: str
    self_identified: bool
    position: int          # word index in the text


def _tokens(text: str) -> list[str]:
    text = re.sub(r'\bx[\s-]ray\b', 'xray', text.lower())
    text = re.sub(r'[.,;:!?()]+', ' | ', text)          # punctuation ends a run of characters
    return [t for t in re.split(r"[\s\"'-]+", text) if t]


def _convert(token: str) -> str | None:
    """Characters for one spoken token, None when it is an ordinary word."""
    if token in LETTERS:
        return LETTERS[token]
    if token in DIGITS:
        return DIGITS[token]
    if token in STROKE:
        return STROKE[token]
    if re.fullmatch(r'[a-z]', token) or re.fullmatch(r'[0-9]+', token):
        return token.upper()
    if re.fullmatch(r'[a-z0-9/]+', token) and any(c.isdigit() for c in token) and any(c.isalpha() for c in token):
        return token.upper()            # already written as a callsign
    return None


def extract(text: str) -> list[Heard]:
    """Callsigns in a transcript, in order of appearance."""
    tokens = _tokens(text)
    found: list[Heard] = []
    run: list[str] = []
    start = 0

    def flush(end: int) -> None:
        joined = ''.join(run).replace('//', '/')
        before = ' '.join(tokens[max(0, start - 3):start])
        after = ' '.join(tokens[end:end + 3])
        self_id = bool(SELF_ID.search(before)) or bool(SELF_ID_AFTER.search(after))
        for m in CALL_IN_RUN.finditer(joined):
            call = m.group(0)
            if is_valid(call):
                found.append(Heard(call, self_id, start))
                self_id = False

    for i, token in enumerate(tokens):
        chars = _convert(token)
        if chars is None:
            if run:
                flush(i)
            run = []
            continue
        if not run:
            start = i
        run.append(chars)
    if run:
        flush(len(tokens))
    return found
