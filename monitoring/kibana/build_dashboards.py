#!/usr/bin/env python3
"""
Generate the Kibana dashboards (NDJSON) for the modules of the web UI.

    python3 monitoring/kibana/build_dashboards.py      # writes monitoring/kibana/dashboards/*.ndjson
    ./scripts/import-kibana-dashboards.sh              # imports them into Kibana

Every dashboard is called "RadioMoni · <module>" after the module in the web UI.
Charts are aggregation-based visualizations, maps are Kibana Maps (geo_point
field "position"), lists are saved searches. The column audio_url is shown as an
audio player (field format in index-patterns.ndjson, signed links, see
radiomoni/recording_links.py). IDs are stable, so a re-import
overwrites the previous version.
"""

import json
from pathlib import Path
from typing import Any, Optional

OUT = Path(__file__).resolve().parent / 'dashboards'
PREFIX = 'RadioMoni · '
CORE_VERSION = '8.8.0'

# data view IDs (index-patterns.ndjson)
CAPTURES, APRS, POCSAG, REPEATER = 'radio-captures-pattern', 'radio-aprs-pattern', 'radio-pocsag-pattern', \
    'radio-repeater-pattern'
ADSB, AIS, ISM, ALERTS = 'radio-adsb-pattern', 'radio-ais-pattern', 'radio-ism-pattern', 'radio-alerts-pattern'

Obj = dict[str, Any]


# --------------------------------------------------------------------------- building blocks
def _search_source(query: str = '', index: bool = True) -> dict[str, str]:
    source: dict[str, Any] = {'query': {'query': query, 'language': 'kuery'}, 'filter': []}
    if index:
        source['indexRefName'] = 'kibanaSavedObjectMeta.searchSourceJSON.index'
    return {'searchSourceJSON': json.dumps(source)}


def _index_ref(index: str) -> list[dict[str, str]]:
    return [{'id': index, 'name': 'kibanaSavedObjectMeta.searchSourceJSON.index', 'type': 'index-pattern'}]


def _vis(oid: str, title: str, index: str, vis_type: str, aggs: list[Obj], params: Obj,
         query: str = '') -> Obj:
    for i, agg in enumerate(aggs, start=1):
        agg.setdefault('id', str(i))
        agg.setdefault('enabled', True)
        agg.setdefault('params', {})
    return {
        'id': oid, 'type': 'visualization', 'coreMigrationVersion': CORE_VERSION, 'typeMigrationVersion': '8.5.0',
        'references': _index_ref(index),
        'attributes': {
            'title': title, 'description': '', 'version': 1, 'uiStateJSON': '{}',
            'visState': json.dumps({'title': title, 'type': vis_type, 'aggs': aggs, 'params': params}),
            'kibanaSavedObjectMeta': _search_source(query),
        },
    }


def _count() -> Obj:
    return {'type': 'count', 'schema': 'metric'}


def metric(oid: str, title: str, index: str, agg: Optional[Obj] = None, query: str = '') -> Obj:
    params = {'addTooltip': True, 'addLegend': False, 'type': 'metric',
              'metric': {'colorSchema': 'Green to Red', 'colorsRange': [{'from': 0, 'to': 10000}],
                         'labels': {'show': True}, 'invertColors': False,
                         'style': {'bgColor': False, 'fontSize': 48}}}
    return _vis(oid, title, index, 'metric', [agg or _count()], params, query)


def unique(field: str, label: str) -> Obj:
    return {'type': 'cardinality', 'schema': 'metric', 'params': {'field': field, 'customLabel': label}}


def total(field: str, label: str) -> Obj:
    return {'type': 'sum', 'schema': 'metric', 'params': {'field': field, 'customLabel': label}}


def count(label: str) -> Obj:
    return {'type': 'count', 'schema': 'metric', 'params': {'customLabel': label}}


def timeline(oid: str, title: str, index: str, query: str = '', split: Optional[str] = None,
             value: Optional[Obj] = None) -> Obj:
    aggs = [value or count('Anzahl'),
            {'type': 'date_histogram', 'schema': 'segment',
             'params': {'field': '@timestamp', 'interval': 'auto', 'min_doc_count': 1, 'customLabel': 'Zeit'}}]
    if split:
        aggs.append({'type': 'terms', 'schema': 'group',
                     'params': {'field': split, 'size': 8, 'order': 'desc', 'orderBy': '1'}})
    params = {'type': 'line', 'addTooltip': True, 'addLegend': bool(split), 'legendPosition': 'right',
              'showCircles': True, 'interpolate': 'linear', 'scale': 'linear', 'drawLinesBetweenPoints': True,
              'radiusRatio': 9, 'times': [], 'addTimeMarker': False}
    return _vis(oid, title, index, 'line', aggs, params, query)


def _terms(field: str, size: int, label: str, schema: str = 'segment') -> Obj:
    return {'type': 'terms', 'schema': schema,
            'params': {'field': field, 'size': size, 'order': 'desc', 'orderBy': '1', 'customLabel': label,
                       'missingBucket': False, 'otherBucket': False}}


def pie(oid: str, title: str, index: str, field: str, label: str, size: int = 10, query: str = '') -> Obj:
    params = {'type': 'pie', 'addTooltip': True, 'addLegend': True, 'legendPosition': 'right', 'isDonut': True,
              'labels': {'show': True, 'values': True, 'last_level': True, 'truncate': 100}}
    return _vis(oid, title, index, 'pie', [count('Anzahl'), _terms(field, size, label)], params, query)


def pie_filters(oid: str, title: str, index: str, filters: list[tuple[str, str]], query: str = '') -> Obj:
    """Pie over KQL filters — works across indices where a field has different mappings."""
    params = {'type': 'pie', 'addTooltip': True, 'addLegend': True, 'legendPosition': 'right', 'isDonut': True,
              'labels': {'show': True, 'values': True, 'last_level': True, 'truncate': 100}}
    agg = {'type': 'filters', 'schema': 'segment',
           'params': {'filters': [{'input': {'query': q, 'language': 'kuery'}, 'label': label}
                                  for label, q in filters]}}
    return _vis(oid, title, index, 'pie', [count('Anzahl'), agg], params, query)


def bars(oid: str, title: str, index: str, field: str, label: str, size: int = 15, query: str = '',
         value: Optional[Obj] = None) -> Obj:
    params = {'type': 'histogram', 'addTooltip': True, 'addLegend': False, 'legendPosition': 'right',
              'scale': 'linear', 'mode': 'stacked', 'times': [], 'addTimeMarker': False}
    return _vis(oid, title, index, 'horizontal_bar', [value or count('Anzahl'), _terms(field, size, label)],
                params, query)


def histogram(oid: str, title: str, index: str, field: str, interval: int, label: str, query: str = '') -> Obj:
    params = {'type': 'histogram', 'addTooltip': True, 'addLegend': False, 'legendPosition': 'right',
              'scale': 'linear', 'mode': 'stacked', 'times': [], 'addTimeMarker': False}
    agg = {'type': 'histogram', 'schema': 'segment',
           'params': {'field': field, 'interval': interval, 'min_doc_count': False, 'customLabel': label}}
    return _vis(oid, title, index, 'histogram', [count('Anzahl'), agg], params, query)


def table(oid: str, title: str, index: str, field: str, label: str, metrics: list[Obj], size: int = 20,
          query: str = '') -> Obj:
    params = {'perPage': 10, 'showPartialRows': False, 'showMetricsAtAllLevels': False, 'showTotal': False,
              'totalFunc': 'sum', 'percentageCol': ''}
    return _vis(oid, title, index, 'table', [*metrics, _terms(field, size, label, schema='bucket')], params, query)


def avg(field: str, label: str) -> Obj:
    return {'type': 'avg', 'schema': 'metric', 'params': {'field': field, 'customLabel': label}}


def maximum(field: str, label: str) -> Obj:
    return {'type': 'max', 'schema': 'metric', 'params': {'field': field, 'customLabel': label}}


def search(oid: str, title: str, index: str, columns: list[str], query: str = '') -> Obj:
    source = json.loads(_search_source(query)['searchSourceJSON'])
    source.update({'highlightAll': True, 'version': True})
    return {
        'id': oid, 'type': 'search', 'coreMigrationVersion': CORE_VERSION, 'typeMigrationVersion': '8.0.0',
        'references': _index_ref(index),
        'attributes': {'title': title, 'description': '', 'columns': columns, 'sort': [['@timestamp', 'desc']],
                       'hideChart': True, 'grid': {'columns': {}}, 'rowsPerPage': 50, 'version': 1, 'hits': 0,
                       'kibanaSavedObjectMeta': {'searchSourceJSON': json.dumps(source)}},
    }


def geo_map(oid: str, title: str, index: str, label: str, tooltip: list[str], color: str,
            query: str = '') -> Obj:
    """Kibana Maps: EMS base map plus the documents with a 'position' geo_point."""
    layers = [
        {'id': 'basemap', 'label': None, 'type': 'EMS_VECTOR_TILE', 'visible': True, 'alpha': 1,
         'minZoom': 0, 'maxZoom': 24, 'sourceDescriptor': {'type': 'EMS_TMS', 'isAutoSelect': True,
                                                           'lightModeDefault': 'road_map_desaturated'},
         'style': {'type': 'EMS_VECTOR_TILE'}},
        {'id': f'{oid}-points', 'label': label, 'type': 'GEOJSON_VECTOR', 'visible': True, 'alpha': 0.85,
         'minZoom': 0, 'maxZoom': 24, 'includeInFitToBounds': True,
         'sourceDescriptor': {'type': 'ES_SEARCH', 'id': f'{oid}-source', 'geoField': 'position',
                              'indexPatternRefName': 'layer_1_source_index_pattern', 'scalingType': 'LIMIT',
                              'tooltipProperties': tooltip, 'sortField': '@timestamp', 'sortOrder': 'desc',
                              'topHitsSplitField': '', 'topHitsSize': 1, 'applyGlobalQuery': True,
                              'applyGlobalTime': True, 'applyForceRefresh': True, 'filterByMapBounds': True},
         'style': {'type': 'VECTOR', 'isTimeAware': True, 'properties': {
             'fillColor': {'type': 'STATIC', 'options': {'color': color}},
             'lineColor': {'type': 'STATIC', 'options': {'color': '#FFFFFF'}},
             'lineWidth': {'type': 'STATIC', 'options': {'size': 1}},
             'iconSize': {'type': 'STATIC', 'options': {'size': 6}}}},
         'query': {'query': query, 'language': 'kuery'}},
    ]
    map_state = {'zoom': 6.6, 'center': {'lon': 8.23, 'lat': 46.8},
                 'timeFilters': {'from': 'now-24h', 'to': 'now'}, 'refreshConfig': {'isPaused': True, 'interval': 0},
                 'query': {'query': '', 'language': 'kuery'}, 'filters': [], 'settings': {}}
    return {
        'id': oid, 'type': 'map', 'coreMigrationVersion': CORE_VERSION, 'typeMigrationVersion': '8.4.0',
        'references': [{'id': index, 'name': 'layer_1_source_index_pattern', 'type': 'index-pattern'}],
        'attributes': {'title': title, 'description': '', 'layerListJSON': json.dumps(layers),
                       'mapStateJSON': json.dumps(map_state),
                       'uiStateJSON': json.dumps({'isLayerTOCOpen': False, 'openTOCDetails': []})},
    }


def dashboard(oid: str, module: str, description: str, rows: list[list[tuple[Obj, int, int]]]) -> list[Obj]:
    """rows: [(object, width of 48, height)] per row. Returns dashboard plus its panels."""
    panels, refs, objects = [], [], []
    y = 0
    n = 0
    for row in rows:
        x = 0
        for obj, w, h in row:
            n += 1
            panels.append({'version': CORE_VERSION, 'type': obj['type'],
                           'gridData': {'x': x, 'y': y, 'w': w, 'h': h, 'i': str(n)},
                           'panelIndex': str(n), 'embeddableConfig': {'enhancements': {}},
                           'panelRefName': f'panel_{n}'})
            refs.append({'id': obj['id'], 'name': f'panel_{n}', 'type': obj['type']})
            objects.append(obj)
            x += w
        y += max(h for _, _, h in row)
    dash = {
        'id': oid, 'type': 'dashboard', 'coreMigrationVersion': CORE_VERSION, 'typeMigrationVersion': '8.9.0',
        'references': refs,
        'attributes': {'title': PREFIX + module, 'description': description, 'version': 1,
                       'panelsJSON': json.dumps(panels), 'optionsJSON': json.dumps({'useMargins': True,
                                                                                    'hidePanelTitles': False}),
                       'timeRestore': True, 'timeFrom': 'now-24h', 'timeTo': 'now', 'refreshInterval':
                           {'pause': False, 'value': 60000},
                       'kibanaSavedObjectMeta': _search_source(index=False)},
    }
    return [*objects, dash]


# --------------------------------------------------------------------------- dashboards
VOICE, VOX = 'mode : "voice"', 'mode : "vox"'


def overview() -> list[Obj]:
    return dashboard('rm-dash-overview', 'Übersicht', 'Alle Betriebsarten auf einen Blick', [
        [(metric('rm-ov-captures', 'Aufnahmen', CAPTURES, count('Aufnahmen')), 8, 7),
         (metric('rm-ov-aprs', 'APRS-Pakete', APRS, count('APRS-Pakete')), 8, 7),
         (metric('rm-ov-pocsag', 'POCSAG-Meldungen', POCSAG, count('POCSAG')), 8, 7),
         (metric('rm-ov-adsb', 'Flugzeuge (ADS-B)', ADSB, unique('icao', 'Flugzeuge')), 8, 7),
         (metric('rm-ov-ais', 'Schiffe (AIS)', AIS, unique('mmsi', 'Schiffe')), 8, 7),
         (metric('rm-ov-alerts', 'Alarme', ALERTS, count('Alarme')), 8, 7)],
        [(timeline('rm-ov-captures-tl', 'Aufnahmen nach Betriebsart', CAPTURES, split='mode'), 24, 12),
         (timeline('rm-ov-aprs-tl', 'APRS-Pakete', APRS), 24, 12)],
        [(timeline('rm-ov-pocsag-tl', 'POCSAG-Meldungen', POCSAG), 24, 12),
         (timeline('rm-ov-adsb-tl', 'ADS-B-Flugzeuge', ADSB, value=unique('icao', 'Flugzeuge')), 24, 12)],
    ])


def voice() -> list[Obj]:
    return dashboard('rm-dash-voice', 'Sprache', 'Einzelaufnahmen mit Whisper-Transkription (Seite „Sprache“)', [
        [(metric('rm-voice-count', 'Aufnahmen', CAPTURES, count('Aufnahmen'), VOICE), 12, 7),
         (metric('rm-voice-transcribed', 'Mit Transkription', CAPTURES, count('Transkribiert'),
                 f'{VOICE} and transcription : *'), 12, 7),
         (metric('rm-voice-duration', 'Aufnahmedauer (s)', CAPTURES, total('duration_seconds', 'Sekunden'), VOICE),
          12, 7),
         (metric('rm-voice-freqs', 'Frequenzen', CAPTURES, unique('frequency', 'Frequenzen'), VOICE), 12, 7)],
        [(timeline('rm-voice-tl', 'Aufnahmen über die Zeit', CAPTURES, VOICE, split='modulation'), 24, 12),
         (bars('rm-voice-top-freq', 'Häufigste Frequenzen (MHz)', CAPTURES, 'frequency_mhz', 'MHz', 15, VOICE), 12, 12),
         (pie('rm-voice-lang', 'Erkannte Sprache', CAPTURES, 'detected_language', 'Sprache', 10, VOICE), 12, 12)],
        [(search('rm-voice-list', 'Sprache – Aufnahmen', CAPTURES,
                 ['frequency_mhz', 'modulation', 'duration_seconds', 'detected_language', 'transcription',
                  'audio_url'], VOICE),
          48, 16)],
    ])


def vox() -> list[Obj]:
    return dashboard('rm-dash-vox', 'VOX-Aufnahme', 'Durchgänge der VOX-Überwachung (Seite „VOX-Aufnahme“)', [
        [(metric('rm-vox-count', 'Durchgänge', CAPTURES, count('Durchgänge'), VOX), 12, 7),
         (metric('rm-vox-duration', 'Sprechzeit (s)', CAPTURES, total('duration_seconds', 'Sekunden'), VOX), 12, 7),
         (metric('rm-vox-transcribed', 'Mit Transkription', CAPTURES, count('Transkribiert'),
                 f'{VOX} and transcription : *'), 12, 7),
         (metric('rm-vox-failed', 'Transkription fehlgeschlagen', CAPTURES, count('Fehlgeschlagen'),
                 f'{VOX} and transcription_error : *'), 12, 7)],
        [(timeline('rm-vox-tl', 'Durchgänge über die Zeit', CAPTURES, VOX, split='frequency_mhz'), 24, 12),
         (histogram('rm-vox-length', 'Länge der Durchgänge (s)', CAPTURES, 'duration_seconds', 2, 'Sekunden', VOX),
          12, 12),
         (pie('rm-vox-lang', 'Erkannte Sprache', CAPTURES, 'detected_language', 'Sprache', 10, VOX), 12, 12)],
        [(search('rm-vox-list', 'VOX – Durchgänge', CAPTURES,
                 ['frequency_mhz', 'duration_seconds', 'peak_power_db', 'detected_language', 'transcription',
                  'audio_url'], VOX), 48, 16)],
    ])


def aprs() -> list[Obj]:
    return dashboard('rm-dash-aprs', 'APRS', 'APRS-Pakete mit Stationskarte (Seite „APRS“)', [
        [(metric('rm-aprs-count', 'Pakete', APRS, count('Pakete')), 16, 7),
         (metric('rm-aprs-calls', 'Stationen', APRS, unique('source_callsign', 'Rufzeichen')), 16, 7),
         (metric('rm-aprs-pos', 'Pakete mit Position', APRS, count('Mit Position'), 'position : *'), 16, 7)],
        [(geo_map('rm-aprs-map', 'APRS-Stationen', APRS, 'APRS-Stationen',
                  ['source_callsign', 'packet_type', 'message_text', '@timestamp'], '#54B399'), 30, 22),
         (bars('rm-aprs-top', 'Aktivste Stationen', APRS, 'source_callsign', 'Rufzeichen', 15), 18, 22)],
        [(timeline('rm-aprs-tl', 'Pakete über die Zeit', APRS), 24, 12),
         (pie('rm-aprs-types', 'Pakettypen', APRS, 'packet_type', 'Typ'), 12, 12),
         (pie('rm-aprs-path', 'Digipeater-Pfade', APRS, 'path', 'Pfad', 8), 12, 12)],
        [(search('rm-aprs-list', 'APRS – Pakete', APRS,
                 ['source_callsign', 'destination_callsign', 'packet_type', 'maidenhead', 'message_text']), 48, 16)],
    ])


def pocsag() -> list[Obj]:
    types = [('Alpha', 'message_type : "alpha"'), ('Numerisch', 'message_type : "numeric"'),
             ('Ton', 'message_type : "tone"'), ('Unbekannt', 'message_type : "unknown"')]
    return dashboard('rm-dash-pocsag', 'POCSAG', 'Pager-Meldungen (Seite „POCSAG“)', [
        [(metric('rm-pocsag-count', 'Meldungen', POCSAG, count('Meldungen')), 16, 7),
         (metric('rm-pocsag-addr', 'Adressen', POCSAG, unique('address', 'Adressen')), 16, 7),
         (metric('rm-pocsag-text', 'Mit Text', POCSAG, count('Mit Text'), 'message_type : "alpha"'), 16, 7)],
        [(timeline('rm-pocsag-tl', 'Meldungen über die Zeit', POCSAG), 24, 12),
         (pie_filters('rm-pocsag-types', 'Meldungsarten', POCSAG, types), 12, 12),
         (pie('rm-pocsag-baud', 'Baudrate', POCSAG, 'baud_rate', 'Baud'), 12, 12)],
        [(bars('rm-pocsag-top', 'Häufigste Adressen', POCSAG, 'address', 'Adresse', 15), 16, 16),
         (search('rm-pocsag-list', 'POCSAG – Meldungen', POCSAG,
                 ['address', 'function_code', 'message_type', 'message_text', 'baud_rate']), 32, 16)],
    ])


def adsb() -> list[Obj]:
    return dashboard('rm-dash-adsb', 'ADS-B', 'Flugzeuge auf 1090 MHz (Seite „ADS-B · AIS · ISM“, Reiter ADS-B)', [
        [(metric('rm-adsb-aircraft', 'Flugzeuge', ADSB, unique('icao', 'Flugzeuge')), 12, 7),
         (metric('rm-adsb-flights', 'Flugnummern', ADSB, unique('flight', 'Flugnummern')), 12, 7),
         (metric('rm-adsb-pos', 'Meldungen mit Position', ADSB, count('Mit Position'), 'position : *'), 12, 7),
         (metric('rm-adsb-alt', 'Höchste Flughöhe (ft)', ADSB, maximum('altitude_ft', 'Fuss')), 12, 7)],
        [(geo_map('rm-adsb-map', 'ADS-B-Flugzeuge', ADSB, 'Flugzeuge',
                  ['flight', 'icao', 'altitude_ft', 'ground_speed_kt', 'squawk', '@timestamp'], '#6092C0'), 30, 22),
         (table('rm-adsb-top', 'Flugzeuge', ADSB, 'icao', 'ICAO',
                [count('Meldungen'), maximum('altitude_ft', 'Max. Höhe (ft)'), maximum('rssi', 'Max. RSSI')]), 18, 22)],
        [(timeline('rm-adsb-tl', 'Flugzeuge über die Zeit', ADSB, value=unique('icao', 'Flugzeuge')), 24, 12),
         (histogram('rm-adsb-alt-hist', 'Flughöhen (ft)', ADSB, 'altitude_ft', 5000, 'Fuss'), 24, 12)],
        [(search('rm-adsb-list', 'ADS-B – Meldungen', ADSB,
                 ['icao', 'flight', 'altitude_ft', 'ground_speed_kt', 'track', 'squawk', 'rssi']), 48, 16)],
    ])


def ais() -> list[Obj]:
    return dashboard('rm-dash-ais', 'AIS', 'Schiffe auf 161.975/162.025 MHz (Seite „ADS-B · AIS · ISM“, Reiter AIS)', [
        [(metric('rm-ais-ships', 'Schiffe', AIS, unique('mmsi', 'Schiffe')), 16, 7),
         (metric('rm-ais-count', 'Meldungen', AIS, count('Meldungen')), 16, 7),
         (metric('rm-ais-pos', 'Meldungen mit Position', AIS, count('Mit Position'), 'position : *'), 16, 7)],
        [(geo_map('rm-ais-map', 'AIS-Schiffe', AIS, 'Schiffe',
                  ['shipname', 'mmsi', 'callsign', 'speed', 'course', 'destination', '@timestamp'], '#D36086'), 30, 22),
         (bars('rm-ais-top', 'Schiffe nach Meldungen', AIS, 'shipname', 'Schiff', 15), 18, 22)],
        [(timeline('rm-ais-tl', 'Schiffe über die Zeit', AIS, value=unique('mmsi', 'Schiffe')), 24, 12),
         (pie('rm-ais-types', 'Nachrichtentypen', AIS, 'msg_type', 'Typ'), 24, 12)],
        [(search('rm-ais-list', 'AIS – Meldungen', AIS,
                 ['mmsi', 'shipname', 'callsign', 'speed', 'course', 'destination']), 48, 16)],
    ])


def ism() -> list[Obj]:
    return dashboard('rm-dash-ism', 'ISM-Sensoren', 'Funksensoren 433/868 MHz (Seite „ADS-B · AIS · ISM“, Reiter ISM)', [
        [(metric('rm-ism-sensors', 'Sensoren', ISM, unique('sensor_id', 'Sensoren')), 16, 7),
         (metric('rm-ism-models', 'Gerätemodelle', ISM, unique('model', 'Modelle')), 16, 7),
         (metric('rm-ism-count', 'Meldungen', ISM, count('Meldungen')), 16, 7)],
        [(timeline('rm-ism-temp', 'Temperatur (°C) je Sensor', ISM, 'temperature_C : *', split='sensor_id',
                   value=avg('temperature_C', '°C')), 24, 14),
         (timeline('rm-ism-hum', 'Luftfeuchte (%) je Sensor', ISM, 'humidity : *', split='sensor_id',
                   value=avg('humidity', '%')), 24, 14)],
        [(bars('rm-ism-top', 'Häufigste Gerätemodelle', ISM, 'model', 'Modell', 15), 16, 16),
         (search('rm-ism-list', 'ISM – Meldungen', ISM,
                 ['model', 'id', 'channel', 'temperature_C', 'humidity', 'battery_ok', 'rssi']), 32, 16)],
    ])


def repeater() -> list[Obj]:
    return dashboard('rm-dash-repeater', 'Repeater-Scan', 'Aktivität der Schweizer FM-Relais (Seite „Repeater-Scan“)', [
        [(metric('rm-rep-scans', 'Messungen', REPEATER, count('Messungen')), 16, 7),
         (metric('rm-rep-repeaters', 'Gemessene Relais', REPEATER, unique('repeater_callsign', 'Relais')), 16, 7),
         (metric('rm-rep-active', 'Messungen mit Träger', REPEATER, count('Mit Träger'), 'carrier_detected : true'),
          16, 7)],
        [(table('rm-rep-top', 'Aktivste Relais', REPEATER, 'repeater_callsign', 'Relais',
                [avg('activity_percentage', 'Ø Aktivität %'), total('transmission_count', 'Durchgänge'),
                 maximum('peak_signal_strength', 'Max. Signal dB')]), 24, 16),
         (pie('rm-rep-band', 'Messungen nach Band', REPEATER, 'band', 'Band'), 12, 16),
         (pie('rm-rep-canton', 'Messungen nach Kanton', REPEATER, 'canton', 'Kanton', 26), 12, 16)],
        [(timeline('rm-rep-tl', 'Messungen über die Zeit', REPEATER, split='band'), 24, 12),
         (search('rm-rep-list', 'Repeater-Scan – Messungen', REPEATER,
                 ['repeater_callsign', 'frequency_mhz', 'band', 'canton', 'carrier_detected', 'transmission_count',
                  'activity_percentage']), 24, 12)],
    ])


def alerts() -> list[Obj]:
    return dashboard('rm-dash-alerts', 'Alarme', 'Ausgelöste Alarmregeln (Seite „Alarme“)', [
        [(metric('rm-alert-count', 'Alarme', ALERTS, count('Alarme')), 24, 7),
         (metric('rm-alert-rules', 'Ausgelöste Regeln', ALERTS, unique('rule_id', 'Regeln')), 24, 7)],
        [(timeline('rm-alert-tl', 'Alarme über die Zeit', ALERTS, split='source'), 24, 12),
         (bars('rm-alert-top', 'Häufigste Regeln', ALERTS, 'rule_name', 'Regel', 15), 12, 12),
         (pie('rm-alert-source', 'Quelle', ALERTS, 'source', 'Quelle'), 12, 12)],
        [(search('rm-alert-list', 'Alarme – Liste', ALERTS, ['rule_name', 'source', 'summary']), 48, 16)],
    ])


DASHBOARDS = {
    'overview': overview, 'voice': voice, 'vox': vox, 'aprs': aprs, 'pocsag': pocsag, 'adsb': adsb,
    'ais': ais, 'ism': ism, 'repeater': repeater, 'alerts': alerts,
}


def main() -> None:
    for name, build in DASHBOARDS.items():
        objects = build()
        path = OUT / f'{name}-dashboard.ndjson'
        path.write_text(''.join(json.dumps(o, ensure_ascii=False) + '\n' for o in objects), encoding='utf-8')
        print(f'{path.name}: {objects[-1]["attributes"]["title"]} ({len(objects) - 1} panels)')


if __name__ == '__main__':
    main()
