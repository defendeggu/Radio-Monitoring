"""
User-managed objects: frequency bookmarks (N4), alert rules (N3) and
schedules (N2).
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, Response, jsonify, request

from radiomoni import alerts
from radiomoni import scheduler
from radiomoni.api_docs import api, parse_body
from radiomoni.errors import ApiError
from radiomoni.redis_client import get_redis
from radiomoni.schemas import AlertRuleModel, BookmarkModel, ScheduleModel

library_bp = Blueprint('library', __name__)

BOOKMARKS_KEY = 'bookmarks'
MAX_BOOKMARKS = 500

# Shipped presets, shown when the user has no bookmarks yet
DEFAULT_BOOKMARKS: list[dict[str, Any]] = [
    {'name': 'APRS Europe', 'frequency': 144_800_000, 'modulation': 'FM', 'mode': 'aprs', 'tags': ['aprs']},
    {'name': 'APRS North America', 'frequency': 144_390_000, 'modulation': 'FM', 'mode': 'aprs', 'tags': ['aprs']},
    {'name': 'Amateur 2m calling', 'frequency': 145_500_000, 'modulation': 'FM', 'mode': 'voice', 'tags': ['ham']},
    {'name': 'Amateur 70cm calling', 'frequency': 433_500_000, 'modulation': 'FM', 'mode': 'voice', 'tags': ['ham']},
    {'name': 'PMR446 channel 1', 'frequency': 446_006_250, 'modulation': 'FM', 'mode': 'vox', 'tags': ['pmr']},
    {'name': 'Air band 118.000', 'frequency': 118_000_000, 'modulation': 'AM', 'mode': 'voice', 'tags': ['air']},
    {'name': 'ADS-B 1090', 'frequency': 1_090_000_000, 'modulation': 'FM', 'mode': 'adsb', 'tags': ['air']},
    {'name': 'AIS', 'frequency': 162_000_000, 'modulation': 'FM', 'mode': 'ais', 'tags': ['marine']},
    {'name': 'ISM 433.92', 'frequency': 433_920_000, 'modulation': 'FM', 'mode': 'ism', 'tags': ['sensors']},
]


def _uuid_ok(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ApiError('Invalid id', 400)


# ================================================================ bookmarks
def _bookmarks() -> list[dict[str, Any]]:
    items = [json.loads(v) for v in get_redis().hgetall(BOOKMARKS_KEY).values()]
    return sorted(items, key=lambda b: (b.get('frequency', 0), b.get('name', '')))


@library_bp.get('/bookmarks')
@api('List frequency bookmarks', tags=['Bookmarks'])
def list_bookmarks() -> Response:
    items = _bookmarks()
    return jsonify({'bookmarks': items, 'defaults': DEFAULT_BOOKMARKS if not items else []})


@library_bp.post('/bookmarks')
@api('Create a bookmark', tags=['Bookmarks'], body=BookmarkModel, responses={201: 'Created'})
def create_bookmark() -> tuple[Response, int]:
    data = parse_body(BookmarkModel).model_dump()
    if get_redis().hlen(BOOKMARKS_KEY) >= MAX_BOOKMARKS:
        raise ApiError(f'Maximum of {MAX_BOOKMARKS} bookmarks reached', 400)
    item = {**data, 'id': str(uuid.uuid4()), 'created_at': datetime.now(timezone.utc).isoformat()}
    get_redis().hset(BOOKMARKS_KEY, item['id'], json.dumps(item))
    return jsonify(item), 201


@library_bp.put('/bookmarks/<bookmark_id>')
@api('Update a bookmark', tags=['Bookmarks'], body=BookmarkModel, responses={404: 'Not found'})
def update_bookmark(bookmark_id: str) -> Response:
    bookmark_id = _uuid_ok(bookmark_id)
    raw = get_redis().hget(BOOKMARKS_KEY, bookmark_id)
    if not raw:
        raise ApiError('Bookmark not found', 404)
    item = {**json.loads(raw), **parse_body(BookmarkModel).model_dump(), 'id': bookmark_id}
    get_redis().hset(BOOKMARKS_KEY, bookmark_id, json.dumps(item))
    return jsonify(item)


@library_bp.delete('/bookmarks/<bookmark_id>')
@api('Delete a bookmark', tags=['Bookmarks'], responses={404: 'Not found'})
def delete_bookmark(bookmark_id: str) -> Response:
    if not get_redis().hdel(BOOKMARKS_KEY, _uuid_ok(bookmark_id)):
        raise ApiError('Bookmark not found', 404)
    return jsonify({'status': 'deleted'})


@library_bp.get('/bookmarks/export')
@api('Export all bookmarks as JSON', tags=['Bookmarks'])
def export_bookmarks() -> Response:
    response = jsonify({'bookmarks': _bookmarks()})
    response.headers['Content-Disposition'] = 'attachment; filename=radiomoni-bookmarks.json'
    return response


@library_bp.post('/bookmarks/import')
@api('Import bookmarks (JSON {"bookmarks": [...]})', tags=['Bookmarks'])
def import_bookmarks() -> Response:
    payload = request.get_json(silent=True) or {}
    items = payload.get('bookmarks') if isinstance(payload, dict) else None
    if not isinstance(items, list) or len(items) > MAX_BOOKMARKS:
        raise ApiError('Expected {"bookmarks": [...]} with at most 500 entries', 400)
    imported = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        data = BookmarkModel.model_validate({k: v for k, v in raw.items() if k not in ('id', 'created_at')})
        item = {**data.model_dump(), 'id': str(uuid.uuid4()), 'created_at': datetime.now(timezone.utc).isoformat()}
        get_redis().hset(BOOKMARKS_KEY, item['id'], json.dumps(item))
        imported += 1
    return jsonify({'imported': imported})


# ================================================================ alerts
@library_bp.get('/alerts/rules')
@api('List alert rules', tags=['Alerts'])
def list_alert_rules() -> Response:
    return jsonify({'rules': alerts.list_rules(), 'channels': alerts.configured_channels()})


@library_bp.post('/alerts/rules')
@api('Create an alert rule', tags=['Alerts'], body=AlertRuleModel, responses={201: 'Created'})
def create_alert_rule() -> tuple[Response, int]:
    return jsonify(alerts.save_rule(parse_body(AlertRuleModel).model_dump())), 201


@library_bp.put('/alerts/rules/<rule_id>')
@api('Update an alert rule', tags=['Alerts'], body=AlertRuleModel, responses={404: 'Not found'})
def update_alert_rule(rule_id: str) -> Response:
    rule_id = _uuid_ok(rule_id)
    if not alerts.get_rule(rule_id):
        raise ApiError('Rule not found', 404)
    return jsonify(alerts.save_rule(parse_body(AlertRuleModel).model_dump(), rule_id))


@library_bp.delete('/alerts/rules/<rule_id>')
@api('Delete an alert rule', tags=['Alerts'], responses={404: 'Not found'})
def delete_alert_rule(rule_id: str) -> Response:
    if not alerts.delete_rule(_uuid_ok(rule_id)):
        raise ApiError('Rule not found', 404)
    return jsonify({'status': 'deleted'})


@library_bp.get('/alerts/recent')
@api('Recently fired alerts', tags=['Alerts'])
def recent_alerts() -> Response:
    limit = min(max(request.args.get('limit', 50, type=int) or 50, 1), 200)
    return jsonify({'alerts': alerts.recent_alerts(limit)})


@library_bp.post('/alerts/test')
@api('Send a test notification to the configured channels', tags=['Alerts'])
def test_notification() -> Response:
    payload = request.get_json(silent=True) or {}
    channels = [c for c in payload.get('channels', list(alerts.configured_channels())) if
                c in ('ntfy', 'telegram', 'webhook', 'email')] if isinstance(payload, dict) else []
    return jsonify({'results': alerts.notify(channels, 'RadioMoni test', 'Test notification from RadioMoni')})


# ================================================================ schedules
@library_bp.get('/schedules')
@api('List schedules', tags=['Schedules'])
def list_schedules() -> Response:
    return jsonify({'schedules': scheduler.list_schedules()})


@library_bp.post('/schedules')
@api('Create a schedule', tags=['Schedules'], body=ScheduleModel, responses={201: 'Created'})
def create_schedule() -> tuple[Response, int]:
    return jsonify(scheduler.save_schedule(parse_body(ScheduleModel).model_dump())), 201


@library_bp.put('/schedules/<schedule_id>')
@api('Update a schedule', tags=['Schedules'], body=ScheduleModel, responses={404: 'Not found'})
def update_schedule(schedule_id: str) -> Response:
    schedule_id = _uuid_ok(schedule_id)
    if not scheduler.get_schedule(schedule_id):
        raise ApiError('Schedule not found', 404)
    return jsonify(scheduler.save_schedule(parse_body(ScheduleModel).model_dump(), schedule_id))


@library_bp.delete('/schedules/<schedule_id>')
@api('Delete a schedule', tags=['Schedules'], responses={404: 'Not found'})
def delete_schedule(schedule_id: str) -> Response:
    if not scheduler.delete_schedule(_uuid_ok(schedule_id)):
        raise ApiError('Schedule not found', 404)
    return jsonify({'status': 'deleted'})


@library_bp.post('/schedules/<schedule_id>/run')
@api('Run a schedule now', tags=['Schedules'], responses={404: 'Not found'})
def run_schedule_now(schedule_id: str) -> Response:
    schedule_id = _uuid_ok(schedule_id)
    if not scheduler.get_schedule(schedule_id):
        raise ApiError('Schedule not found', 404)
    return jsonify(scheduler.run_schedule(schedule_id, wait=0))
