"""
APRS packets in TNC2 text form (as direwolf prints them) to structured fields.

    [0] SOURCE>DEST,PATH:info

The first character of the info field names the format (APRS 1.0.1 spec, plus
the Mic-E device extensions):

    ! =        position without timestamp (uncompressed or compressed)
    / @        position with timestamp
    ` '        Mic-E: latitude and status in the destination field,
               longitude, speed and course as bytes in the info field
    ;          object (name, live/killed, timestamp, position)
    )          item (like an object, without timestamp)
    :          message, ack/rej, bulletin, telemetry metadata
    >          status
    _          weather report without position
    T#         telemetry
    }          third-party packet (an iGate forwards an internet packet on RF)

direwolf writes bytes it cannot show as <0xNN>; they are part of the encoding
(Mic-E uses them) and are turned back into bytes before parsing.

`parse_line()` returns the fields RadioMoni stores. `message_text` is a short,
readable line (symbol, position, speed, comment); `raw_packet` keeps the line
as received. Altitude is in metres, speed in km/h.
"""

import math
import re
from typing import Any, Optional

KNOTS_TO_KMH = 1.852
FEET_TO_M = 0.3048
MPH_TO_KMH = 1.609344

LINE_RE = re.compile(r'^\s*(?:\[[^\]]*\]\s*)?([^>\s]+)>([^:]+):(.*)$', re.S)
HEX_ESCAPE_RE = re.compile(r'<0x([0-9a-fA-F]{2})>')
UNCOMPRESSED_RE = re.compile(r'^(\d{2})([\d ]{2}\.[\d ]{2})([NS])(.)(\d{3})([\d ]{2}\.[\d ]{2})([EW])(.)')
ALTITUDE_RE = re.compile(r'/A=(-?\d{5,6})')
COURSE_SPEED_RE = re.compile(r'^(\d{3}|\.{3}| {3})/(\d{3}|\.{3}| {3})')
PHG_RE = re.compile(r'^PHG(\d)(\d)(\d)(\d)')
RNG_RE = re.compile(r'^RNG(\d{4})')
STATUS_TIMESTAMP_RE = re.compile(r'^\d{6}z')

PRIMARY_SYMBOLS = {
    '!': 'Police', '#': 'Digipeater', '$': 'Phone', '%': 'DX cluster', '&': 'HF gateway',
    "'": 'Small aircraft', '(': 'Mobile satellite station', ')': 'Wheelchair', '*': 'Snowmobile',
    '+': 'Red Cross', ',': 'Boy Scouts', '-': 'House', '.': 'X', '/': 'Dot', ':': 'Fire',
    ';': 'Campground', '<': 'Motorcycle', '=': 'Railway engine', '>': 'Car', '?': 'File server',
    'A': 'Aid station', 'B': 'BBS', 'C': 'Canoe', 'E': 'Eyeball', 'F': 'Tractor', 'G': 'Grid square',
    'H': 'Hotel', 'I': 'TCP/IP', 'K': 'School', 'L': 'PC user', 'N': 'NTS station', 'O': 'Balloon',
    'P': 'Police', 'R': 'Recreational vehicle', 'S': 'Space shuttle', 'T': 'SSTV', 'U': 'Bus',
    'V': 'ATV', 'W': 'Weather service site', 'X': 'Helicopter', 'Y': 'Sailboat', '[': 'Jogger',
    '\\': 'DF triangle', ']': 'Mailbox', '^': 'Large aircraft', '_': 'Weather station',
    '`': 'Dish antenna', 'a': 'Ambulance', 'b': 'Bicycle', 'c': 'Incident command post',
    'd': 'Fire department', 'e': 'Horse', 'f': 'Fire truck', 'g': 'Glider', 'h': 'Hospital',
    'i': 'IOTA', 'j': 'Jeep', 'k': 'Truck', 'l': 'Laptop', 'm': 'Mic-E repeater', 'n': 'Node',
    'o': 'EOC', 'p': 'Dog', 'q': 'Grid square', 'r': 'Repeater', 's': 'Ship', 't': 'Truck stop',
    'u': 'Truck (18 wheels)', 'v': 'Van', 'w': 'Water station', 'y': 'Yagi at QTH', 'z': 'Shelter',
}
PRIMARY_SYMBOLS.update({str(n): f'Circle {n}' for n in range(10)})
ALTERNATE_SYMBOLS = {
    '#': 'Digipeater', '&': 'Gateway', '-': 'House', '>': 'Car', '_': 'Weather station',
    'R': 'Restaurant', 'a': 'ARES', 'k': 'SUV', 'u': 'Truck', 'v': 'Van', 'O': 'Balloon',
    'n': 'Triangle', 'W': 'Weather site', 'X': 'Pharmacy', 'h': 'Ham store',
}
GATEWAY_OVERLAYS = {'I': 'iGate', 'R': 'RX-only iGate', 'T': 'TX iGate'}

MIC_E_STANDARD = ['Emergency', 'Priority', 'Special', 'Committed', 'Returning', 'In service', 'En route',
                  'Off duty']
MIC_E_CUSTOM = ['Emergency', 'Custom 6', 'Custom 5', 'Custom 4', 'Custom 3', 'Custom 2', 'Custom 1',
                'Custom 0']


def unescape(text: str) -> str:
    """direwolf's <0xNN> notation back to the original characters."""
    return HEX_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


def symbol_name(table: Optional[str], code: Optional[str]) -> Optional[str]:
    if not table or not code:
        return None
    if table == '/':
        return PRIMARY_SYMBOLS.get(code)
    name = ALTERNATE_SYMBOLS.get(code)
    if table != '\\':                      # overlay character on the alternate table
        if code == '&' and table in GATEWAY_OVERLAYS:
            return GATEWAY_OVERLAYS[table]
        if name:
            return f'{name} ({table})'
    return name


def symbol_id(table: Optional[str], code: Optional[str]) -> Optional[str]:
    """Name of the symbol image served by the web UI under /aprs-symbols/<id>.png.

    p-XX primary table, s-XX alternate table, o-YY-XX alternate symbol with the
    overlay character YY (frontend/scripts/aprs_symbols.py writes the files).
    """
    if not table or not code or not 33 <= ord(code) <= 126:
        return None
    if table == '/':
        return f'p-{ord(code):02x}'
    if table == '\\':
        return f's-{ord(code):02x}'
    if table.isascii() and (table.isdigit() or table.isupper()):
        return f'o-{ord(table):02x}-{ord(code):02x}'
    return None


def _base91(chars: str) -> int:
    value = 0
    for c in chars:
        value = value * 91 + ord(c) - 33
    return value


def _clean_comment(text: str) -> str:
    return ''.join(c for c in text if c.isprintable()).strip()


def _round(value: Optional[float], digits: int = 1) -> Optional[float]:
    return None if value is None else round(value, digits)


# ------------------------------------------------------------------ positions
def _uncompressed(data: str, out: dict[str, Any]) -> Optional[str]:
    """19-character position; returns the rest of the info field or None."""
    m = UNCOMPRESSED_RE.match(data)
    if not m:
        return None
    lat_deg, lat_min, ns, table, lon_deg, lon_min, ew, code = m.groups()
    # position ambiguity: spaces stand for the unknown digits
    lat = int(lat_deg) + float(lat_min.replace(' ', '0')) / 60.0
    lon = int(lon_deg) + float(lon_min.replace(' ', '0')) / 60.0
    if lat > 90 or lon > 180:
        return None
    out['latitude'] = round(-lat if ns == 'S' else lat, 6)
    out['longitude'] = round(-lon if ew == 'W' else lon, 6)
    out['symbol_table'], out['symbol_code'] = table, code
    out['format'] = 'uncompressed'
    return data[m.end():]


def _compressed(data: str, out: dict[str, Any]) -> Optional[str]:
    """13-character base-91 position; returns the rest of the info field or None."""
    if len(data) < 13:
        return None
    table, code = data[0], data[9]
    if not (table in '/\\' or (table.isalpha() and table.isascii())):
        return None
    if not all(33 <= ord(c) <= 123 for c in data[1:9]):
        return None
    out['latitude'] = round(90.0 - _base91(data[1:5]) / 380926.0, 6)
    out['longitude'] = round(-180.0 + _base91(data[5:9]) / 190463.0, 6)
    if table in 'abcdefghij':
        table = str(ord(table) - ord('a'))       # overlay digits are sent as a-j
    out['symbol_table'], out['symbol_code'] = table, code
    out['format'] = 'compressed'
    c, s, t = data[10], data[11], data[12]
    if c != ' ':
        cv, sv = ord(c) - 33, ord(s) - 33
        if ((ord(t) - 33) >> 3) & 3 == 2:        # GGA source: cs is the altitude
            out['altitude'] = round(1.002 ** (cv * 91 + sv) * FEET_TO_M)
        elif 0 <= cv <= 89:
            out['course'] = cv * 4 or None
            out['speed'] = _round((1.08 ** sv - 1) * KNOTS_TO_KMH)
        elif c == '{':
            out['range_km'] = _round(2 * 1.08 ** sv * MPH_TO_KMH)
    return data[13:]


def _position(data: str, out: dict[str, Any]) -> Optional[str]:
    if data[:1].isdigit():
        return _uncompressed(data, out)
    return _compressed(data, out)


def _extensions(comment: str, out: dict[str, Any]) -> str:
    """Course/speed, PHG, range and altitude from a position comment."""
    m = COURSE_SPEED_RE.match(comment)
    if m:
        course, speed = m.groups()
        if out.get('symbol_code') == '_':        # weather station: wind direction/speed
            out.setdefault('weather', {})
            if course.isdigit():
                out['weather']['wind_direction'] = int(course)
            if speed.isdigit():
                out['weather']['wind_speed_kmh'] = _round(int(speed) * MPH_TO_KMH)
        else:
            if course.isdigit() and 0 < int(course) <= 360:
                out['course'] = int(course)
            if speed.isdigit():
                out['speed'] = _round(int(speed) * KNOTS_TO_KMH)
        comment = comment[7:]
    elif (phg := PHG_RE.match(comment)):
        p, h, g, d = (int(x) for x in phg.groups())
        out['phg'] = {'power_w': p * p, 'height_m': round(10 * 2 ** h * FEET_TO_M), 'gain_db': g,
                      'directivity': d * 45 or None}
        comment = comment[7:]
    elif (rng := RNG_RE.match(comment)):
        out['range_km'] = _round(int(rng.group(1)) * MPH_TO_KMH)
        comment = comment[7:]
    alt = ALTITUDE_RE.search(comment)
    if alt:
        out['altitude'] = round(int(alt.group(1)) * FEET_TO_M)
        comment = comment[:alt.start()] + comment[alt.end():]
    if out.get('symbol_code') == '_':
        comment = _weather(comment, out)
    return comment


# ------------------------------------------------------------------ weather
def _weather(text: str, out: dict[str, Any]) -> str:
    """Weather fields (c s g t r p P h b L l); returns what is left as comment."""
    wx = out.setdefault('weather', {})
    pos = 0
    widths = {'c': 3, 's': 3, 'g': 3, 't': 3, 'r': 3, 'p': 3, 'P': 3, 'h': 2, 'b': 5, 'L': 3, 'l': 3}
    while pos < len(text) and text[pos] in widths:
        key, width = text[pos], widths[text[pos]]
        raw = text[pos + 1:pos + 1 + width]
        if len(raw) < width:
            break
        pos += 1 + width
        try:
            value = int(raw)
        except ValueError:
            continue                              # "..." or spaces: no value
        if key == 'c':
            wx['wind_direction'] = value
        elif key == 's':
            wx['wind_speed_kmh'] = _round(value * MPH_TO_KMH)
        elif key == 'g':
            wx['wind_gust_kmh'] = _round(value * MPH_TO_KMH)
        elif key == 't':
            wx['temperature_c'] = _round((value - 32) / 1.8)
        elif key == 'r':
            wx['rain_1h_mm'] = _round(value * 0.254)
        elif key == 'p':
            wx['rain_24h_mm'] = _round(value * 0.254)
        elif key == 'P':
            wx['rain_since_midnight_mm'] = _round(value * 0.254)
        elif key == 'h':
            wx['humidity'] = 100 if value == 0 else value
        elif key == 'b':
            wx['pressure_hpa'] = _round(value / 10.0)
        elif key == 'L':
            wx['luminosity'] = value
        elif key == 'l':
            wx['luminosity'] = value + 1000
    if not wx:
        out.pop('weather', None)
    return text[pos:]


# ------------------------------------------------------------------ Mic-E
def _mic_e_device(comment: str) -> tuple[str, Optional[str]]:
    """Strip the manufacturer prefix/suffix of a Mic-E comment."""
    device = None
    if comment[:1] in ('>', ']'):
        first = comment[0]
        comment = comment[1:]
        if comment.endswith('='):
            device, comment = ('Kenwood TH-D72' if first == '>' else 'Kenwood TM-D710'), comment[:-1]
        elif comment.endswith('^'):
            device, comment = 'Kenwood TH-D74', comment[:-1]
        elif comment.endswith('&'):
            device, comment = 'Kenwood TH-D75', comment[:-1]
        else:
            device = 'Kenwood TH-D7A' if first == '>' else 'Kenwood TM-D700'
    elif comment[:1] in ('`', "'"):
        comment = comment[1:]
        if len(comment) >= 2 and comment[-2] == '_':
            device, comment = 'Yaesu', comment[:-2]
    return comment, device


def _mic_e_char(c: str) -> Optional[tuple[str, int, Optional[str]]]:
    """Destination character: (latitude digit, message/flag bit, 'standard'|'custom'|None)."""
    if c.isdigit():
        return c, 0, None
    if 'A' <= c <= 'J':
        return str(ord(c) - ord('A')), 1, 'custom'
    if 'P' <= c <= 'Y':
        return str(ord(c) - ord('P')), 1, 'standard'
    if c == 'K':                                   # spaces (position ambiguity)
        return '0', 1, 'custom'
    if c == 'L':
        return '0', 0, None
    if c == 'Z':
        return '0', 1, 'standard'
    return None


def _mic_e(destination: str, info: str, out: dict[str, Any]) -> bool:
    dest = destination.split('-')[0]
    if len(dest) != 6 or len(info) < 9:
        return False
    decoded = [_mic_e_char(c) for c in dest]
    if any(x is None for x in decoded):
        return False
    digits = [x[0] for x in decoded if x]
    bits = [x[1] for x in decoded if x]
    kinds = [x[2] for x in decoded if x]
    lat = int(''.join(digits[:2])) + float(''.join(digits[2:4]) + '.' + ''.join(digits[4:6])) / 60.0
    if bits[3] == 0:
        lat = -lat
    d = ord(info[1]) - 28 + (100 if bits[4] else 0)
    if 180 <= d <= 189:
        d -= 80
    elif 190 <= d <= 199:
        d -= 190
    m = ord(info[2]) - 28
    if m >= 60:
        m -= 60
    h = ord(info[3]) - 28
    lon = d + (m + h / 100.0) / 60.0
    if bits[5]:
        lon = -lon
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return False
    sp, dc, se = ord(info[4]) - 28, ord(info[5]) - 28, ord(info[6]) - 28
    speed = sp * 10 + dc // 10
    course = (dc % 10) * 100 + se
    if speed >= 800:
        speed -= 800
    if course >= 400:
        course -= 400
    out['latitude'], out['longitude'] = round(lat, 6), round(lon, 6)
    out['symbol_code'], out['symbol_table'] = info[7], info[8]
    out['format'] = 'mic-e'
    if speed:
        out['speed'] = _round(speed * KNOTS_TO_KMH)
    if 0 < course <= 360:
        out['course'] = course
    index = bits[0] * 4 + bits[1] * 2 + bits[2]
    used = {k for k in kinds[:3] if k}
    if len(used) > 1:
        out['mic_e_status'] = 'Unknown'
    else:
        out['mic_e_status'] = (MIC_E_CUSTOM if used == {'custom'} else MIC_E_STANDARD)[index]
    comment, device = _mic_e_device(info[9:].rstrip('\r\n'))
    if len(comment) >= 4 and comment[3] == '}':
        out['altitude'] = _base91(comment[:3]) - 10000
        comment = comment[4:]
    if device:
        out['device'] = device
    alt = ALTITUDE_RE.search(comment)
    if alt and 'altitude' not in out:
        out['altitude'] = round(int(alt.group(1)) * FEET_TO_M)
        comment = comment[:alt.start()] + comment[alt.end():]
    out['comment'] = _clean_comment(comment)
    return True


# ------------------------------------------------------------------ info field
def _timestamp(data: str, out: dict[str, Any]) -> str:
    """The 7-character timestamp in front of a position (DDHHMMz, DDHHMM/, HHMMSSh).

    Some trackers send another last character (e.g. "@231031!4702.64N…"); the
    length is fixed, so it is skipped all the same."""
    out['aprs_timestamp'] = data[:7]
    return data[7:]


def _parse_info(source: str, destination: str, info: str, out: dict[str, Any]) -> None:
    kind = info[:1]
    if kind in ('!', '='):
        rest = _position(info[1:], out)
        out['packet_type'] = 'position'
        if rest is None:
            out['packet_type'], out['comment'] = 'unknown', _clean_comment(info)
        else:
            out['comment'] = _clean_comment(_extensions(rest, out))
    elif kind in ('/', '@'):
        rest = _position(_timestamp(info[1:], out), out)
        out['packet_type'] = 'position'
        if rest is None:
            out['packet_type'], out['comment'] = 'unknown', _clean_comment(info)
        else:
            out['comment'] = _clean_comment(_extensions(rest, out))
    elif kind in ('`', "'", '\x1c', '\x1d'):
        out['packet_type'] = 'position'
        if not _mic_e(destination, info, out):
            out['packet_type'], out['comment'] = 'unknown', _clean_comment(info)
    elif kind == ';' and len(info) >= 18:
        out['packet_type'] = 'object'
        out['object_name'] = info[1:10].strip()
        out['object_killed'] = info[10] == '_'
        rest = _position(_timestamp(info[11:], out), out)
        out['comment'] = _clean_comment(_extensions(rest, out) if rest is not None else info[18:])
    elif kind == ')':
        m = re.match(r'\)([^!_]{3,9})([!_])', info)
        out['packet_type'] = 'item'
        if m:
            out['object_name'], out['object_killed'] = m.group(1).strip(), m.group(2) == '_'
            rest = _position(info[m.end():], out)
            out['comment'] = _clean_comment(_extensions(rest, out) if rest is not None else info[m.end():])
        else:
            out['comment'] = _clean_comment(info[1:])
    elif kind == ':' and len(info) >= 11 and info[10] == ':':
        _message(info[1:10].strip(), info[11:], out)
    elif kind == '>':
        out['packet_type'] = 'status'
        text = info[1:]
        if STATUS_TIMESTAMP_RE.match(text):
            out['aprs_timestamp'], text = text[:7], text[7:]
        out['comment'] = _clean_comment(text)
    elif kind == '_':
        out['packet_type'] = 'weather'
        out['aprs_timestamp'] = info[1:9]
        out['comment'] = _clean_comment(_weather(info[9:], out))
    elif info.startswith('T#'):
        out['packet_type'] = 'telemetry'
        parts = info[2:].split(',')
        out['telemetry'] = {'sequence': parts[0], 'values': [p for p in parts[1:6]],
                            'bits': parts[6][:8] if len(parts) > 6 else None}
        out['comment'] = _clean_comment(parts[6][8:]) if len(parts) > 6 else ''
    elif kind == '}':
        inner = parse_line(info[1:])
        if inner:
            via = out['source_callsign']
            out.update({k: v for k, v in inner.items() if k not in ('raw_packet', 'aprs_data')})
            out['third_party_via'] = via
        else:
            out['packet_type'], out['comment'] = 'third-party', _clean_comment(info[1:])
    elif kind == '<':
        out['packet_type'], out['comment'] = 'capabilities', _clean_comment(info[1:])
    elif kind == '?':
        out['packet_type'], out['comment'] = 'query', _clean_comment(info[1:])
    elif kind == '$':
        out['packet_type'], out['comment'] = 'nmea', _clean_comment(info)
    else:
        # A position may start anywhere in the first 40 characters after "!" (old TNCs)
        bang = info.find('!', 0, 40)
        if bang > 0 and _position(info[bang + 1:], out) is not None:
            out['packet_type'] = 'position'
            out['comment'] = _clean_comment(info[:bang])
        else:
            out['packet_type'], out['comment'] = 'unknown', _clean_comment(info)


def _message(addressee: str, text: str, out: dict[str, Any]) -> None:
    out['addressee'] = addressee
    m = re.match(r'^(ack|rej)([A-Za-z0-9}]{1,10})\s*$', text)
    if m:
        out['packet_type'] = 'ack' if m.group(1) == 'ack' else 'rej'
        out['message_id'] = m.group(2).rstrip('}')
        out['comment'] = ''
        return
    if text.startswith(('PARM.', 'UNIT.', 'EQNS.', 'BITS.')):
        out['packet_type'] = 'telemetry-meta'
        out['comment'] = _clean_comment(text)
        return
    out['packet_type'] = 'bulletin' if addressee.upper().startswith(('BLN', 'NWS')) else 'message'
    m = re.search(r'\{([A-Za-z0-9]{1,5})(?:\}[A-Za-z0-9]{0,5})?\s*$', text)
    if m:
        out['message_id'] = m.group(1)
        text = text[:m.start()]
    out['comment'] = _clean_comment(text)


# ------------------------------------------------------------------ summary
TYPE_LABELS = {'position': 'Position', 'object': 'Object', 'item': 'Item', 'message': 'Message',
               'bulletin': 'Bulletin', 'ack': 'Ack', 'rej': 'Reject', 'status': 'Status',
               'weather': 'Weather', 'telemetry': 'Telemetry', 'telemetry-meta': 'Telemetry setup',
               'capabilities': 'Capabilities', 'query': 'Query', 'nmea': 'NMEA'}


def _coordinates(lat: float, lon: float) -> str:
    return f"{abs(lat):.4f} {'N' if lat >= 0 else 'S'} {abs(lon):.4f} {'E' if lon >= 0 else 'W'}"


def summary(p: dict[str, Any]) -> str:
    """One readable line: what the packet says, without the encoding."""
    parts: list[str] = []
    ptype = p.get('packet_type')
    if ptype in ('message', 'bulletin'):
        parts.append(f"→ {p.get('addressee', '?')}: {p.get('comment', '')}")
    elif ptype in ('ack', 'rej'):
        parts.append(f"{TYPE_LABELS[ptype]} → {p.get('addressee', '?')} #{p.get('message_id', '')}")
    else:
        if p.get('object_name'):
            parts.append(f"{TYPE_LABELS.get(ptype or '', 'Object')} {p['object_name']}"
                         + (' (deleted)' if p.get('object_killed') else ''))
        name = symbol_name(p.get('symbol_table'), p.get('symbol_code'))
        if name:
            parts.append(name)
        if p.get('mic_e_status') and p['mic_e_status'] not in ('Off duty', 'In service'):
            parts.append(p['mic_e_status'])
        if p.get('latitude') is not None and p.get('longitude') is not None:
            parts.append(_coordinates(p['latitude'], p['longitude']))
        motion = []
        if p.get('speed'):
            motion.append(f"{p['speed']:.0f} km/h")
        if p.get('course'):
            motion.append(f"{p['course']}°")
        if motion:
            parts.append(' '.join(motion))
        if p.get('altitude') is not None:
            parts.append(f"{p['altitude']} m")
        wx = p.get('weather') or {}
        if wx:
            w = []
            if 'temperature_c' in wx:
                w.append(f"{wx['temperature_c']} °C")
            if 'humidity' in wx:
                w.append(f"{wx['humidity']} %")
            if 'pressure_hpa' in wx:
                w.append(f"{wx['pressure_hpa']} hPa")
            if 'wind_speed_kmh' in wx:
                w.append(f"wind {wx.get('wind_direction', '?')}° {wx['wind_speed_kmh']:.0f} km/h")
            if 'rain_1h_mm' in wx:
                w.append(f"rain {wx['rain_1h_mm']} mm/h")
            if w:
                parts.append(', '.join(w))
        if ptype == 'telemetry' and p.get('telemetry'):
            tm = p['telemetry']
            parts.append(f"#{tm['sequence']} " + ','.join(tm['values']))
        if p.get('comment'):
            parts.append(p['comment'])
        if not parts and ptype in TYPE_LABELS:
            parts.append(TYPE_LABELS[ptype])
    if p.get('third_party_via'):
        parts.append(f"(via {p['third_party_via']})")
    return ' · '.join(x for x in parts if x)


# ------------------------------------------------------------------ entry point
def parse_line(line: str) -> Optional[dict[str, Any]]:
    """A direwolf/TNC2 line to packet fields, or None when it is not a packet."""
    if not line:
        return None
    m = LINE_RE.match(line.rstrip('\r\n'))
    if not m:
        return None
    source, dest_path, info = m.groups()
    parts = [x.strip() for x in dest_path.split(',')]
    if not source.strip() or not parts[0]:
        return None
    info = unescape(info)
    out: dict[str, Any] = {
        'source_callsign': source.strip().upper(),
        'destination_callsign': parts[0].upper(),
        'path': ','.join(parts[1:]),
        'raw_packet': line.strip(),
        'aprs_data': {'payload': info},
    }
    channel = re.match(r'^\s*\[([^\]]*)\]', line)
    if channel:
        out['aprs_data']['channel'] = channel.group(1)
    try:
        _parse_info(out['source_callsign'], out['destination_callsign'], info, out)
    except (ValueError, IndexError) as e:                  # malformed packet: keep it readable
        out['packet_type'], out['comment'] = 'unknown', _clean_comment(info)
        out['aprs_data']['parse_error'] = str(e)[:200]
    lat, lon = out.get('latitude'), out.get('longitude')
    if lat is None or lon is None or not (math.isfinite(lat) and math.isfinite(lon)):
        out.pop('latitude', None)
        out.pop('longitude', None)
    out['aprs_type'] = out['packet_type']
    out['symbol'] = symbol_name(out.get('symbol_table'), out.get('symbol_code'))
    out['symbol_id'] = symbol_id(out.get('symbol_table'), out.get('symbol_code'))
    out['message_text'] = summary(out) or out.get('comment') or info.strip()
    return out
