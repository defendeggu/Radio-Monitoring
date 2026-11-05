"""Contest support: callsigns, reference data, rules, worked log, classification, phonetic parser."""

import json
import os

import pytest
from flask.testing import FlaskClient

from radiomoni import config
from radiomoni.contest import callsign as cs
from radiomoni.contest import engine, phonetic, refdata, rules, worked

# real lines of cty.csv (country-files.com), the US line shortened
CTY = """\
4X,Israel,336,AS,20,39,31.32,-34.82,-2.0,4X 4Z;
DL,Fed. Rep. of Germany,230,EU,14,28,51.00,-10.00,-1.0,DA DB DC DD DF DG DH DJ DK DL DM DN DO DP DQ DR;
F,France,227,EU,14,27,46.00,-2.00,-1.0,F HW HX HY TH TM TO TP TQ TV TX;
G,England,223,EU,14,27,52.77,1.47,0.0,2E G M;
HB,Switzerland,287,EU,14,28,46.87,-8.12,-1.0,HB HE;
HB0,Liechtenstein,251,EU,14,28,47.13,-9.57,-1.0,HB0 HE0;
K,United States,291,NA,5,8,37.60,91.87,5.0,AA AB K N W W6(3)[6] =4U1WB(5)[8];
OK,Czech Republic,503,EU,15,28,50.00,-16.00,-1.0,OK OL;
P5,DPR of Korea,344,AS,25,44,39.78,-126.30,-9.0,P5 P6 P7 P8 P9;
*TA1,European Turkey,390,EU,20,39,41.02,-28.97,-2.0,TA1 TB1 TC1 YM1 =TA3AC/1;
"""
SCP = "!!Order,1,1\n# Super Check Partial\nHB9XYZ\nDL1ABC\nOK2PDT\nK1ABC\n"
MOST_WANTED = json.dumps({'1': '344', '2': '123', '80': '336'})


@pytest.fixture
def contest_data():
    """Reference data files in CONTEST_DATA_DIR (removed afterwards)."""
    directory = config.CONTEST_DATA_DIR
    os.makedirs(directory, exist_ok=True)
    for name, text in (('cty.csv', CTY), ('MASTER.SCP', SCP), ('mostwanted.json', MOST_WANTED)):
        with open(os.path.join(directory, name), 'w') as f:
            f.write(text)
    refdata._cache = None
    yield refdata.get()
    for name in refdata.SOURCES:
        path = os.path.join(directory, name)
        if os.path.exists(path):
            os.remove(path)
    refdata._cache = None


class TestCallsign:
    @pytest.mark.parametrize('call', ['HB9XYZ', 'DL1ABC', 'K1A', '2E0ABC', '3DA0RS', 'DL/OK2PDT/P', 'HB9XYZ/P',
                                      'OK2PDT/QRP', 'N8BJQ/4', 'VP2E/W1AW'])
    def test_valid(self, call):
        assert cs.is_valid(call)

    @pytest.mark.parametrize('call', ['', 'CQ', 'TEST', '5NN', '599', 'HB9', 'ABCDEF', '12345', 'HB9XYZ/P/P/P'])
    def test_invalid(self, call):
        assert not cs.is_valid(call)

    def test_base_and_location(self):
        assert cs.base_call('DL/OK2PDT/P') == 'OK2PDT'
        assert cs.location_prefix('DL/OK2PDT/P') == 'DL'
        assert cs.location_prefix('HB9XYZ/P') is None
        assert cs.is_portable('HB9XYZ/P') and not cs.is_portable('HB9XYZ')

    @pytest.mark.parametrize('call, prefix', [('HB9XYZ', 'HB9'), ('N8BJQ', 'N8'), ('2E0ABC', '2E0'),
                                              ('PA/N8BJQ', 'PA0'), ('N8BJQ/4', 'N4'), ('3DA0RS', '3DA0'),
                                              ('HB9XYZ/P', 'HB9'), ('DL/OK2PDT', 'DL0')])
    def test_wpx_prefix(self, call, prefix):
        assert cs.wpx_prefix(call) == prefix


class TestRefData:
    def test_lookup(self):
        cty = refdata.CtyData(CTY)
        assert len(cty) == 10
        assert cty.lookup('HB9XYZ').name == 'Switzerland'
        assert cty.lookup('HB0ABC').name == 'Liechtenstein'          # longest prefix wins
        assert cty.lookup('HE3ABC').adif == 287
        assert cty.lookup('DL/OK2PDT/P').name == 'Fed. Rep. of Germany'
        assert cty.lookup('OK2PDT/P').name == 'Czech Republic'
        assert cty.lookup('M0ABC').name == 'England'
        assert cty.lookup('TA1ABC').prefix == 'TA1'                  # WAE marker "*" dropped
        assert cty.lookup('XX9ABC') is None

    def test_zone_overrides(self):
        cty = refdata.CtyData(CTY)
        assert (cty.lookup('K1ABC').cq_zone, cty.lookup('K1ABC').itu_zone) == (5, 8)
        assert (cty.lookup('W6ABC').cq_zone, cty.lookup('W6ABC').itu_zone) == (3, 6)
        assert cty.lookup('4U1WB').cq_zone == 5 and cty.lookup('4U1WB').name == 'United States'

    def test_scp_and_most_wanted(self):
        scp = refdata.Scp(SCP)
        assert len(scp) == 4 and 'HB9XYZ' in scp and 'HB9XYZ/P' in scp and 'HB9ZZZ' not in scp
        assert refdata.parse_most_wanted(MOST_WANTED) == {344: 1, 123: 2, 336: 80}
        assert refdata.parse_most_wanted('not json') == {}

    def test_load_and_cache(self, contest_data):
        assert contest_data.info()['entities'] == 10 and contest_data.rank(344) == 1
        assert refdata.get() is contest_data                           # unchanged files → cached

    def test_update_keeps_old_files_on_errors(self, contest_data, monkeypatch, tmp_path):
        class Response:
            def __init__(self, body):
                self.content = body.encode()

            def raise_for_status(self):
                pass

        class Session:
            def get(self, url, **kwargs):
                return Response({'cty.csv': 'garbage', 'MASTER.SCP': SCP + 'F5ABC\n',
                                 'mostwanted.json': MOST_WANTED}[next(n for n, u in refdata.SOURCES.items()
                                                                      if u == url)])

        result = refdata.update(config.CONTEST_DATA_DIR, Session())
        assert result['cty.csv']['ok'] is False and result['MASTER.SCP']['ok'] is True
        fresh = refdata.get()
        assert len(fresh.cty) == 10 and 'F5ABC' in fresh.scp


class TestRules:
    def test_all_files_valid(self):
        everything = rules.all_rules()
        assert {'general', 'cq-ww-cw', 'iaru-r1-fieldday-cw', 'helvetia'} <= set(everything)
        assert rules.get('cq-ww-cw').multipliers[0].type == 'cq_zone'
        assert rules.get('nonexistent').id == 'general'

    def test_active_contest(self):
        assert engine.active_contest().id == 'general'
        assert engine.set_active_contest('cq-wpx-cw').id == 'cq-wpx-cw'
        assert engine.active_contest().id == 'cq-wpx-cw'
        with pytest.raises(ValueError):
            engine.set_active_contest('nope')


ADIF = """Contest log <ADIF_VER:5>3.1.4 <EOH>
<CALL:6>DL1ABC <BAND:3>20m <MODE:2>CW <QSO_DATE:8>20261128 <TIME_ON:4>1203 <EOR>
<CALL:6>OK2PDT <FREQ:6>7.0251 <MODE:2>CW <EOR>
<call:6>hb9xyz <band:3>40M <mode:3>SSB <eor>
<CALL:3>CQ? <BAND:3>20m <EOR>
"""
CABRILLO = """START-OF-LOG: 3.0
CONTEST: CQ-WW-CW
CALLSIGN: HB9XX
QSO: 14025 CW 2026-11-28 1203 HB9XX         599 14     DL1ABC        599 14
QSO:  7030 CW 2026-11-28 1210 HB9XX         599 14     K1ABC         599 05
QSO:  3525 PH 2026-11-28 1220 HB9XX         59  14     OK2PDT        59  15
END-OF-LOG:
"""


class TestWorked:
    def test_parse_adif(self):
        qsos = worked.parse_adif(ADIF)
        assert [(q['call'], q['band'], q['mode']) for q in qsos] == [
            ('DL1ABC', '20m', 'CW'), ('OK2PDT', '40m', 'CW'), ('HB9XYZ', '40m', 'SSB')]

    def test_parse_cabrillo(self):
        qsos = worked.parse_log(CABRILLO)
        assert [(q['call'], q['band'], q['mode']) for q in qsos] == [
            ('DL1ABC', '20m', 'CW'), ('K1ABC', '40m', 'CW'), ('OK2PDT', '80m', 'SSB')]

    @pytest.mark.parametrize('text, band', [('20m', '20m'), ('14', '20m'), ('3,5', '80m'), ('1.8', '160m'),
                                            ('10', '30m'), ('18', '17m'), ('x', None)])
    def test_band_from_text(self, text, band):
        assert worked.band_from_text(text) == band

    def test_log_in_redis(self):
        assert worked.import_log(ADIF) == 3
        worked.add({'call': 'F5ABC', 'band': '15m', 'mode': 'CW', 'source': 'n1mm'}, 'n1mm:abc')
        assert worked.summary()['qsos'] == 4
        assert worked.delete('n1mm:abc') and not worked.delete('n1mm:abc')
        assert worked.import_log(CABRILLO, replace=True) == 3 and worked.summary()['qsos'] == 3
        worked.clear()
        assert worked.summary()['qsos'] == 0


class TestClassify:
    def test_new_multiplier_dupe_rare(self, contest_data):
        engine.set_active_contest('cq-ww-cw')
        worked.import_log(CABRILLO)                     # DL1ABC 20m, K1ABC 40m (CW), OK2PDT 80m (SSB)
        dupe = engine.classify('DL1ABC', 14_030_000, 'CW')
        assert dupe['priority'] == 'dupe' and dupe['dupe']
        same_country = engine.classify('DK2XX', 14_030_000, 'CW')
        assert same_country['priority'] == 'normal' and same_country['new_mults'] == []
        other_band = engine.classify('DK2XX', 7_010_000, 'CW')
        assert [m['type'] for m in other_band['new_mults']] == ['cq_zone', 'dxcc']
        assert other_band['priority'] == 'high' and other_band['new_mults'][1]['label'] == 'DXCC Fed. Rep. of Germany'
        rare = engine.classify('P5ABC', 14_030_000, 'CW')
        assert rare['rare'] and rare['rank'] == 1 and rare['continent'] == 'AS'
        assert engine.describe(rare).startswith('MULT') and 'RARE #1' in engine.describe(rare)
        assert engine.classify('XX9ABC', 14_030_000)['priority'] == 'invalid'

    def test_wpx_per_contest_and_scp(self, contest_data):
        engine.set_active_contest('cq-wpx-cw')
        worked.import_log(CABRILLO)
        assert engine.classify('DL1XYZ', 7_010_000)['new_mults'] == []          # DL1 already worked
        assert engine.classify('DL2XYZ', 7_010_000)['new_mults'][0]['value'] == 'DL2'
        assert engine.classify('HB9XYZ', 14_030_000)['in_scp'] is True
        assert engine.classify('HB9QQQ', 14_030_000)['in_scp'] is False

    def test_band_mode_dupes_and_highlight(self, contest_data):
        engine.set_active_contest('helvetia')
        worked.import_log(CABRILLO)
        assert engine.classify('OK2PDT', 3_525_000, 'SSB')['dupe']
        assert not engine.classify('OK2PDT', 3_525_000, 'CW')['dupe']             # dupe per band and mode
        swiss = engine.classify('HB9XYZ/P', 14_030_000, 'CW')
        assert swiss['swiss'] and swiss['portable'] and swiss['highlight'] == ['swiss']

    def test_api(self, client: FlaskClient, contest_data):
        assert client.get('/contest/contests').get_json()['active'] == 'general'
        assert client.put('/contest/active', json={'contest': 'cq-ww-cw'}).status_code == 200
        assert client.put('/contest/active', json={'contest': 'nope'}).status_code == 404
        r = client.post('/contest/worked/import', json={'text': ADIF})
        assert r.status_code == 200 and r.get_json()['imported'] == 3
        assert client.post('/contest/worked/import', json={'text': 'nothing'}).status_code == 400
        lookup = client.get('/contest/lookup?call=dl1abc&frequency=14030000').get_json()
        assert lookup['priority'] == 'dupe' and lookup['country'] == 'Fed. Rep. of Germany'
        status = client.get('/contest/status').get_json()
        assert status['contest']['id'] == 'cq-ww-cw' and status['worked']['qsos'] == 3
        assert status['refdata']['entities'] == 10 and status['n1mm']['enabled'] is False
        assert client.delete('/contest/worked').get_json()['qsos'] == 0


class TestPhonetic:
    @pytest.mark.parametrize('text, calls', [
        ('CQ contest, CQ contest, this is Hotel Bravo Nine X-ray Yankee Zulu', [('HB9XYZ', True)]),
        ('cq field day hotel bravo niner x ray yankee zulu stroke portable', [('HB9XYZ/P', True)]),
        ('Delta Lima One Alfa Bravo Charlie, five nine zero zero one', [('DL1ABC', False)]),
        ('QRZ de Kilowatt One Alpha Bravo Charlie', [('K1ABC', True)]),
        ('Thank you. HB9XYZ contest.', [('HB9XYZ', False)]),
        ('Oscar Kilo zwei Papa Delta Tango', [('OK2PDT', False)]),
        ('Japan Alfa One X-ray Yankee Zulu, you are five nine', [('JA1XYZ', False)]),
        ('Good morning everybody, nice weather today', []),
    ])
    def test_extract(self, text, calls):
        assert [(h.callsign, h.self_identified) for h in phonetic.extract(text)] == calls
