"""
Recurring jobs (N2): user schedules plus housekeeping.

User schedules ("every day 07:00 start APRS for 2 h") are stored in Redis and
registered with an APScheduler BackgroundScheduler. Each fire time runs only
once even if several API processes run a scheduler (Redis NX dedupe key).
When the SDR is busy at fire time the run waits up to 60 s, then is skipped
and the reason is recorded on the schedule.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from radiomoni import config
from radiomoni import events
from radiomoni.redis_client import get_redis

logger = logging.getLogger(__name__)

SCHEDULES_KEY = 'schedules'
_scheduler: Optional[BackgroundScheduler] = None


# ----------------------------------------------------------------- storage
def list_schedules() -> list[dict[str, Any]]:
    items = [json.loads(v) for v in get_redis().hgetall(SCHEDULES_KEY).values()]
    for item in items:
        item['next_run'] = _next_run(item['id'])
    return sorted(items, key=lambda s: s.get('created_at', ''))


def get_schedule(schedule_id: str) -> Optional[dict[str, Any]]:
    raw = get_redis().hget(SCHEDULES_KEY, schedule_id)
    if not raw:
        return None
    item: dict[str, Any] = json.loads(raw)
    item['next_run'] = _next_run(schedule_id)
    return item


def save_schedule(data: dict[str, Any], schedule_id: Optional[str] = None) -> dict[str, Any]:
    existing = get_schedule(schedule_id) if schedule_id else None
    item = {
        **(existing or {}), **data,
        'id': schedule_id or str(uuid.uuid4()),
        'created_at': (existing or {}).get('created_at') or datetime.now(timezone.utc).isoformat(),
    }
    item.pop('next_run', None)
    get_redis().hset(SCHEDULES_KEY, item['id'], json.dumps(item))
    _register(item)
    item['next_run'] = _next_run(item['id'])
    return item


def delete_schedule(schedule_id: str) -> bool:
    removed = bool(get_redis().hdel(SCHEDULES_KEY, schedule_id))
    if _scheduler and _scheduler.get_job(schedule_id):
        _scheduler.remove_job(schedule_id)
    return removed


def _update_status(schedule_id: str, status: str, detail: Optional[dict[str, Any]] = None) -> None:
    raw = get_redis().hget(SCHEDULES_KEY, schedule_id)
    if not raw:
        return
    item = json.loads(raw)
    item['last_run'] = datetime.now(timezone.utc).isoformat()
    item['last_status'] = status
    item['last_detail'] = detail
    get_redis().hset(SCHEDULES_KEY, schedule_id, json.dumps(item))


# ----------------------------------------------------------------- execution
def run_schedule(schedule_id: str, fire_key: Optional[str] = None, wait: float = 60) -> dict[str, Any]:
    """Execute a schedule now (waiting up to `wait` s for a busy SDR). Returns {'status': ..., ...}."""
    from radiomoni.actions import run_action
    from radiomoni.sdr_lock import wait_until_free

    item = get_schedule(schedule_id)
    if not item:
        return {'status': 'missing'}
    if fire_key and not get_redis().set(f"schedule_run:{schedule_id}:{fire_key}", '1', nx=True, ex=3600):
        return {'status': 'duplicate'}
    if not wait_until_free(wait):
        _update_status(schedule_id, 'skipped', {'reason': 'SDR busy'})
        events.publish('schedule', {'id': schedule_id, 'name': item.get('name'), 'status': 'skipped'})
        return {'status': 'skipped', 'reason': 'SDR busy'}
    try:
        result = run_action(item['action'], item['params'])
        _update_status(schedule_id, 'started', result)
        events.publish('schedule', {'id': schedule_id, 'name': item.get('name'), 'status': 'started', **result})
        logger.info(f"Schedule '{item.get('name')}' started: {result}")
        return {'status': 'started', **result}
    except Exception as e:
        logger.error(f"Schedule '{item.get('name')}' failed: {e}", exc_info=True)
        _update_status(schedule_id, 'failed', {'error': str(e)[:300]})
        events.publish('schedule', {'id': schedule_id, 'name': item.get('name'), 'status': 'failed'})
        return {'status': 'failed', 'error': str(e)[:300]}


def _fire(schedule_id: str) -> None:
    # dedupe key = current minute (cron resolution)
    run_schedule(schedule_id, fire_key=datetime.now(timezone.utc).strftime('%Y%m%d%H%M'))


def _register(item: dict[str, Any]) -> None:
    if _scheduler is None:
        return
    if _scheduler.get_job(item['id']):
        _scheduler.remove_job(item['id'])
    if item.get('enabled', True):
        _scheduler.add_job(_fire, CronTrigger.from_crontab(item['cron'], timezone=config.TIMEZONE),
                           id=item['id'], args=[item['id']], max_instances=1, coalesce=True,
                           misfire_grace_time=120)


def _next_run(schedule_id: str) -> Optional[str]:
    if _scheduler is None:
        return None
    job = _scheduler.get_job(schedule_id)
    return job.next_run_time.isoformat() if job and job.next_run_time else None


# ----------------------------------------------------------------- lifecycle
def start() -> Optional[BackgroundScheduler]:
    """Start the scheduler with all stored schedules and housekeeping jobs."""
    global _scheduler
    if not config.SCHEDULER_ENABLED or _scheduler is not None:
        return _scheduler
    from radiomoni.jobs import cleanup_recordings, cleanup_scan_sessions

    _scheduler = BackgroundScheduler(timezone=config.TIMEZONE, daemon=True)
    _scheduler.add_job(cleanup_recordings, CronTrigger(hour=3, minute=30, timezone=config.TIMEZONE),
                       id='housekeeping:recordings', max_instances=1, coalesce=True)
    _scheduler.add_job(cleanup_scan_sessions, CronTrigger(minute=15, timezone=config.TIMEZONE),
                       id='housekeeping:scan-sessions', max_instances=1, coalesce=True)
    _scheduler.start()
    try:
        for item in list_schedules():
            _register(item)
    except Exception as e:
        logger.error(f"Could not load schedules: {e}")
    logger.info(f"Scheduler started ({len(_scheduler.get_jobs())} jobs)")
    return _scheduler


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
