"""
Data export (N9): CSV for all data types, GeoJSON/KML for APRS and AIS/ADS-B
positions, and a ZIP bundle (audio + transcript + metadata) per capture.

CSV cells that start with = + - @ are prefixed with ' so spreadsheet programs
do not execute them as formulas (data comes from arbitrary radio senders).
"""

import csv
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from typing import Any, Iterable
from xml.sax.saxutils import escape

from flask import Blueprint, Response, jsonify

from api_docs import api, parse_query
from blueprints.aprs import to_geojson
from errors import ApiError
from schemas import HoursLimitQuery
from services import safe_recording_path
from storage import get_storage

export_bp = Blueprint('export', __name__)

MAX_ROWS = 10_000  # Elasticsearch max_result_window

COLUMNS: dict[str, list[str]] = {
    'captures': ['@timestamp', 'uuid', 'mode', 'frequency', 'modulation', 'duration_seconds', 'sdr_type',
                 'detected_language', 'transcription', 'audio_file'],
    'aprs': ['@timestamp', 'source_callsign', 'destination_callsign', 'path', 'aprs_type', 'packet_type',
             'latitude', 'longitude', 'altitude', 'speed', 'course', 'message_text', 'frequency'],
    'pocsag': ['@timestamp', 'address', 'function_code', 'message_type', 'baud_rate', 'message_text', 'frequency'],
    'adsb': ['@timestamp', 'icao', 'flight', 'altitude_ft', 'ground_speed_kt', 'track', 'squawk', 'latitude',
             'longitude', 'rssi'],
    'ais': ['@timestamp', 'mmsi', 'msg_type', 'shipname', 'callsign', 'ship_type', 'speed', 'course', 'heading',
            'latitude', 'longitude', 'destination'],
    'ism': ['@timestamp', 'sensor_id', 'model', 'id', 'channel', 'battery_ok', 'temperature_C', 'humidity',
            'pressure_hPa', 'wind_avg_km_h', 'rain_mm'],
    'alerts': ['@timestamp', 'rule_name', 'source', 'summary'],
}


class ExportQuery(HoursLimitQuery):
    limit: int = 10_000


def _safe_cell(value: Any) -> Any:
    if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + value
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return value


def _fetch(kind: str, hours: int, limit: int) -> list[dict[str, Any]]:
    storage = get_storage()
    limit = min(limit, MAX_ROWS)
    if kind == 'captures':
        return list(storage.search_captures(hours=hours, limit=limit)['hits'])
    if kind == 'aprs':
        return list(storage.search_aprs(hours=hours, limit=limit)['hits'])
    if kind == 'pocsag':
        return list(storage.search_pocsag(hours=hours, limit=limit)['hits'])
    return list(storage.search_events(kind, hours=hours, limit=limit)['hits'])


def _filename(kind: str, ext: str) -> str:
    return f"radiomoni-{kind}-{datetime.now(timezone.utc):%Y%m%d-%H%M}.{ext}"


def _csv(kind: str, rows: Iterable[dict[str, Any]]) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    cols = COLUMNS[kind]
    writer.writerow(cols)
    for row in rows:
        writer.writerow([_safe_cell(row.get(c)) for c in cols])
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={_filename(kind, "csv")}'})


@export_bp.get('/export/<kind>.csv')
@api('Export as CSV (captures, aprs, pocsag, adsb, ais, ism, alerts)', tags=['Export'], query=ExportQuery)
def export_csv(kind: str) -> Response:
    if kind not in COLUMNS:
        raise ApiError('Unknown export type', 404)
    q = parse_query(ExportQuery)
    return _csv(kind, _fetch(kind, q.hours, q.limit))


@export_bp.get('/export/<kind>.geojson')
@api('Export positions as GeoJSON (aprs, adsb, ais)', tags=['Export'], query=ExportQuery)
def export_geojson(kind: str) -> Response:
    if kind not in ('aprs', 'adsb', 'ais'):
        raise ApiError('GeoJSON export is available for aprs, adsb and ais', 404)
    q = parse_query(ExportQuery)
    rows = _fetch(kind, q.hours, q.limit)
    if kind == 'aprs':
        data = to_geojson(rows)
    else:
        data = {'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [r['longitude'], r['latitude']]},
             'properties': {k: r.get(k) for k in COLUMNS[kind] if k not in ('latitude', 'longitude')}}
            for r in rows if r.get('latitude') is not None and r.get('longitude') is not None]}
    response = jsonify(data)
    response.headers['Content-Disposition'] = f'attachment; filename={_filename(kind, "geojson")}'
    return response


@export_bp.get('/export/aprs.kml')
@api('Export APRS stations as KML (Google Earth)', tags=['Export'], query=ExportQuery)
def export_kml() -> Response:
    q = parse_query(ExportQuery)
    features = to_geojson(_fetch('aprs', q.hours, q.limit))['features']
    placemarks = []
    for f in features:
        lon, lat = f['geometry']['coordinates']
        props = f['properties']
        placemarks.append(
            f"<Placemark><name>{escape(str(props['callsign']))}</name>"
            f"<description>{escape(str(props.get('message') or ''))} ({escape(str(props.get('timestamp') or ''))})</description>"
            f"<Point><coordinates>{float(lon)},{float(lat)},0</coordinates></Point></Placemark>")
    kml = ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           f"<name>RadioMoni APRS</name>{''.join(placemarks)}</Document></kml>")
    return Response(kml, mimetype='application/vnd.google-earth.kml+xml',
                    headers={'Content-Disposition': f'attachment; filename={_filename("aprs", "kml")}'})


@export_bp.get('/export/capture/<capture_id>.zip')
@api('Download a capture as ZIP (audio, transcript, metadata)', tags=['Export'], responses={404: 'Not found'})
def export_capture_zip(capture_id: str) -> Response:
    capture = get_storage().get_capture_by_id(capture_id)
    if not capture:
        raise ApiError('Capture not found', 404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('metadata.json', json.dumps(capture, indent=2, default=str))
        if capture.get('transcription'):
            zf.writestr('transcript.txt', str(capture['transcription']))
        for key in ('audio_file', 'json_file'):
            name = capture.get(key)
            if not name:
                continue
            try:
                path = safe_recording_path(os.path.basename(str(name)))
            except ValueError:
                continue
            if os.path.isfile(path):
                zf.write(path, arcname=os.path.basename(path))
    return Response(buf.getvalue(), mimetype='application/zip',
                    headers={'Content-Disposition': f'attachment; filename=capture-{capture_id[:8]}.zip'})
