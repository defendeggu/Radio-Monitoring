"""APRS info field formats (radiomoni.aprs_parse), with payloads as heard on 144.800 MHz."""

import pytest

from radiomoni.aprs_parse import parse_line, symbol_id, symbol_name, unescape


def test_mic_e_yaesu_with_altitude():
    p = parse_line('[0.1] HB9AA-9>TWPQT0,HB9LU-10,WIDE1*,WIDE2-1:`~-vlqC>\\`"8t}_5<0x0d>')
    assert p is not None
    assert p['packet_type'] == 'position' and p['format'] == 'mic-e'
    assert p['latitude'] == pytest.approx(47.0233, abs=1e-4)
    assert p['longitude'] == pytest.approx(8.2983, abs=1e-4)
    assert p['speed'] == pytest.approx(14.8, abs=0.1) and p['course'] == 139
    assert p['altitude'] == 457 and p['device'] == 'Yaesu'
    assert p['symbol'] == 'Car' and p['symbol_id'] == 's-3e'
    assert p['mic_e_status'] == 'Off duty' and p['comment'] == ''
    assert p['message_text'] == 'Car · 47.0233 N 8.2983 E · 15 km/h 139° · 457 m'


def test_mic_e_kenwood_comment_and_status():
    p = parse_line("[0] HB9AB>TW0UV6,WIDE1-1:'~=#l <0x1c>-/]145.500MHz qrv=<0x0d>")
    assert p is not None and p['device'] == 'Kenwood TM-D710'
    assert p['symbol'] == 'House' and p['comment'] == '145.500MHz qrv'
    assert p['latitude'] == pytest.approx(47.0943, abs=1e-4)
    p = parse_line('[0] HB9AC-9>TW0RP9,WIDE1-1:`~-2mJ^>/`"8{}_ <0x0d>')
    assert p is not None and p['mic_e_status'] == 'En route' and p['device'] == 'Yaesu'
    assert p['comment'] == '' and 'En route' in p['message_text']


def test_uncompressed_position_with_course_speed_and_altitude():
    p = parse_line('[0] N0CALL>APRS,WIDE1-1:!4903.50N/07201.75W>088/036/A=001234 on the road')
    assert p is not None and p['format'] == 'uncompressed'
    assert p['latitude'] == pytest.approx(49.0583, abs=1e-4) and p['longitude'] == pytest.approx(-72.0292, abs=1e-4)
    assert p['course'] == 88 and p['speed'] == pytest.approx(66.7, abs=0.1)
    assert p['altitude'] == 376 and p['comment'] == 'on the road'


def test_timestamped_positions_and_igate_overlay():
    p = parse_line('[0] HB9AD-10>APMI06,WIDE2-1:@231031!4702.64NI00816.40E&U=13.5V,T=19.8C APRS iGATE')
    assert p is not None and p['packet_type'] == 'position'
    assert p['aprs_timestamp'] == '231031!' and p['symbol'] == 'iGate' and p['symbol_id'] == 'o-49-26'
    assert p['comment'] == 'U=13.5V,T=19.8C APRS iGATE'
    p = parse_line('[0] HB9AE-8>APMI0A,WIDE1-1:/051404z4705.75N/00821.83E>Voyager U=14.1V')
    assert p is not None and p['aprs_timestamp'] == '051404z' and p['latitude'] == pytest.approx(47.0958, abs=1e-4)


def test_compressed_position():
    # APRS spec example: 49°30'N 72°45'W, course 88°, 36.2 knots
    p = parse_line('[0] N0CALL>APRS:=/5L!!<*e7>7P[')
    assert p is not None and p['format'] == 'compressed'
    assert p['latitude'] == pytest.approx(49.5, abs=1e-3) and p['longitude'] == pytest.approx(-72.75, abs=1e-3)
    assert p['course'] == 88 and p['speed'] == pytest.approx(67.0, abs=0.5)


def test_objects_and_items():
    p = parse_line('[0] HB9AF-10>APMI06,WIDE2-1:;438.875-L*111111z4702.72N/00818.65Er T71.9 -7600kHz R12.5k')
    assert p is not None and p['packet_type'] == 'object' and p['object_name'] == '438.875-L'
    assert p['symbol'] == 'Repeater' and not p['object_killed']
    assert p['message_text'].startswith('Object 438.875-L · Repeater · 47.0453 N 8.3108 E')
    p = parse_line('[0] HB9AF-10>APMI06:;LU-Stamm-*111111z4706.72N\\00821.88ERRegulars table')
    assert p is not None and p['symbol'] == 'Restaurant' and p['symbol_id'] == 's-52'
    p = parse_line('[0] N0CALL>APRS:)AID #2!4903.50N/07201.75WA')
    assert p is not None and p['packet_type'] == 'item' and p['object_name'] == 'AID #2'


def test_messages_acks_and_bulletins():
    p = parse_line('[0] N0CALL>APRS::HB9AA-7  :Hello there{42')
    assert p is not None and p['packet_type'] == 'message'
    assert p['addressee'] == 'HB9AA-7' and p['message_id'] == '42' and p['comment'] == 'Hello there'
    assert p['message_text'] == '→ HB9AA-7: Hello there'
    p = parse_line('[0] N0CALL>APRS::HB9AA-7  :ack42')
    assert p is not None and p['packet_type'] == 'ack' and p['message_id'] == '42'
    p = parse_line('[0] N0CALL>APRS::BLN1     :Net tonight 20:00')
    assert p is not None and p['packet_type'] == 'bulletin'
    p = parse_line('[0] N0CALL>APRS::N0CALL   :PARM.Battery,Temp')
    assert p is not None and p['packet_type'] == 'telemetry-meta'


def test_third_party_packet_is_unwrapped():
    p = parse_line('[0] HB9AD-10>APMI06,WIDE2-1:}DB0AA-2>APPIC3,TCPIP,HB9AD-10*::DL0AA-7  :Firmware update')
    assert p is not None and p['source_callsign'] == 'DB0AA-2' and p['third_party_via'] == 'HB9AD-10'
    assert p['packet_type'] == 'message' and p['addressee'] == 'DL0AA-7'
    assert p['message_text'] == '→ DL0AA-7: Firmware update · (via HB9AD-10)'
    assert p['raw_packet'].startswith('[0] HB9AD-10>')


def test_weather_status_and_telemetry():
    p = parse_line('[0] N0CALL>APRS:_10090556c220s004g005t077r000p000P000h50b09900wRSW')
    assert p is not None and p['packet_type'] == 'weather'
    wx = p['weather']
    assert wx['wind_direction'] == 220 and wx['temperature_c'] == 25.0
    assert wx['humidity'] == 50 and wx['pressure_hpa'] == 990.0
    p = parse_line('[0] N0CALL>APRS:@092345z4903.50N/07201.75W_220/004g005t-07r000p000P000h50b09900')
    assert p is not None and p['symbol'] == 'Weather station'
    assert p['weather']['temperature_c'] == pytest.approx(-21.7) and p['weather']['wind_direction'] == 220
    p = parse_line('[0] N0CALL>APRS:>092345zNet control')
    assert p is not None and p['packet_type'] == 'status' and p['comment'] == 'Net control'
    p = parse_line('[0] N0CALL>APRS:T#005,199,000,255,073,123,01101001')
    assert p is not None and p['telemetry']['sequence'] == '005' and p['telemetry']['bits'] == '01101001'


@pytest.mark.parametrize('line', ['', 'Garbage', '# comment', '[0] >APRS:x', '[0] N0CALL>:x'])
def test_not_a_packet(line):
    assert parse_line(line) is None


@pytest.mark.parametrize('info', ['!', '`', ';short', ')x', '!99999.99N/00000.00E-', '`abc', '_', 'T#'])
def test_malformed_info_stays_readable(info):
    p = parse_line(f'[0] N0CALL>APRS:{info}')
    assert p is not None and p['raw_packet'] == f'[0] N0CALL>APRS:{info}'
    assert isinstance(p['message_text'], str)


def test_symbols():
    assert symbol_name('/', '>') == 'Car' and symbol_id('/', '>') == 'p-3e'
    assert symbol_name('\\', '&') == 'Gateway' and symbol_name('D', '&') == 'Gateway (D)'
    assert symbol_id('3', '#') == 'o-33-23' and symbol_id('a', '>') is None and symbol_id(None, '>') is None
    assert unescape('a<0x1c>b<0x0d>') == 'a\x1cb\r'


# ------------------------------------------------------------------ storage, map, POCSAG filter
def test_reparse_updates_stored_packets(monkeypatch):
    import sys

    from radiomoni import aprs_reparse
    from radiomoni.storage.base import get_storage

    storage = get_storage()
    storage.index_aprs({'source_callsign': 'HB9AA-9', 'packet_type': 'unknown', 'latitude': 1.0, 'longitude': 2.0,
                        'message_text': '`~-vlqC>\\`"8t}_5',
                        'raw_packet': '[0] HB9AA-9>TWPQT0,WIDE1-1:`~-vlqC>\\`"8t}_5<0x0d>'})
    storage.index_aprs({'source_callsign': 'N0CALL', 'raw_packet': 'garbage'})
    monkeypatch.setattr(sys, 'argv', ['aprs_reparse'])
    aprs_reparse.main()
    hits = {h['source_callsign']: h for h in storage.search_aprs(hours=1)['hits']}
    p = hits['HB9AA-9']
    assert p['packet_type'] == 'position' and p['symbol_id'] == 's-3e' and p['maidenhead'] == 'JN47da'
    assert p['latitude'] == pytest.approx(47.0233, abs=1e-4) and p['message_text'].startswith('Car · 47.0233 N')
    assert hits['N0CALL'].get('symbol_id') is None


def test_map_shows_objects_as_stations(client):
    from radiomoni.storage.base import get_storage

    for line in ('[0] HB9AF-10>APMI06:;438.875-L*111111z4702.72N/00818.65Er T71.9',
                 '[0] HB9AF-10>APMI06:;LU-Stamm-*111111z4706.72N\\00821.88ERStamm',
                 '[0] HB9AF-10>APMI06:!4702.64N/00816.40E#Digi'):
        packet = parse_line(line)
        assert packet is not None
        get_storage().index_aprs(packet)
    features = client.get('/aprs/map?hours=1').get_json()['features']
    names = {f['properties']['callsign']: f['properties'] for f in features}
    assert set(names) == {'438.875-L', 'LU-Stamm-', 'HB9AF-10'}
    assert names['438.875-L']['symbol_id'] == 'p-72' and names['438.875-L']['source_callsign'] == 'HB9AF-10'
    killed = parse_line('[0] HB9AF-10>APMI06:;438.875-L_111111z4702.72N/00818.65Er')
    assert killed is not None and killed['object_killed']
    get_storage().index_aprs(killed)
    names = {f['properties']['callsign'] for f in client.get('/aprs/map?hours=1').get_json()['features']}
    assert '438.875-L' not in names


def test_pocsag_search_hides_tone_only(client):
    from radiomoni.storage.base import get_storage

    for text, kind in (('', 'tone'), (None, 'tone'), ('ALARM Feuer', 'alpha'), ('  ', 'tone')):
        get_storage().index_pocsag({'address': 1234, 'message_type': kind, 'message_text': text})
    assert client.get('/pocsag/search?hours=1').get_json()['count'] == 4
    r = client.get('/pocsag/search?hours=1&text_only=true').get_json()
    assert [m['message_text'] for m in r['results']] == ['ALARM Feuer']
