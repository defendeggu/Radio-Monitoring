"""
Contest skimmer: contest rules, reference data, worked log, N1MM+ / cluster
status, skimmer start and its spots (see radiomoni/skimmer, radiomoni/contest).

Stopping the skimmer goes through DELETE /stream-decode/<id>; its waterfall comes
over GET /spectrum/<id>/stream like every other session.
"""

import time
from typing import Any

from flask import Blueprint, Response, jsonify

from radiomoni import actions
from radiomoni.api_docs import api, parse_body, parse_query
from radiomoni.contest import engine
from radiomoni.contest import refdata
from radiomoni.contest import rules
from radiomoni.contest import worked
from radiomoni.errors import ApiError, call_action
from radiomoni.integrations import cluster, n1mm
from radiomoni.schemas import (ContestActiveRequest, LookupQuery, SkimmerRequest, SkimmerSpotsQuery,
                               WorkedImportRequest)
from radiomoni.skimmer import session as skimmer_session

contest_bp = Blueprint('contest', __name__)


def _rules(r: rules.ContestRules) -> dict[str, Any]:
    return r.model_dump()


@contest_bp.get('/contest/contests')
@api('Available contest rules (multipliers, bands, dupe scope)', tags=['Contest'])
def list_contests() -> Response:
    active = engine.active_contest().id
    return jsonify({'status': 'success', 'active': active,
                    'contests': [_rules(r) for r in rules.all_rules().values()]})


@contest_bp.put('/contest/active')
@api('Select the contest whose rules classify the spots', tags=['Contest'], body=ContestActiveRequest,
     responses={404: 'Unknown contest'})
def set_active() -> Response:
    req = parse_body(ContestActiveRequest)
    try:
        selected = engine.set_active_contest(req.contest)
    except ValueError as e:
        raise ApiError(str(e), 404)
    return jsonify({'status': 'success', 'active': selected.id, 'contest': _rules(selected)})


@contest_bp.get('/contest/status')
@api('Contest status: active contest, reference data, worked log, N1MM+, DX cluster', tags=['Contest'])
def get_status() -> Response:
    active = engine.active_contest()
    return jsonify({'status': 'success', 'contest': _rules(active), 'refdata': refdata.get().info(),
                    'worked': worked.summary(), 'n1mm': n1mm.status(), 'cluster': cluster.status()})


@contest_bp.post('/contest/refdata/update')
@api('Download cty.csv, MASTER.SCP and the Club Log Most Wanted list', tags=['Contest'])
def update_refdata() -> Response:
    result = refdata.update()
    return jsonify({'status': 'success', 'files': result, 'refdata': refdata.get().info()})


@contest_bp.get('/contest/lookup')
@api('Classify a callsign against the active contest (country, zones, new multiplier, dupe)', tags=['Contest'],
     query=LookupQuery)
def lookup() -> Response:
    q = parse_query(LookupQuery)
    return jsonify({'status': 'success', **engine.classify(q.call, q.frequency, q.mode)})


@contest_bp.get('/contest/worked')
@api('Summary of the worked log (QSOs per band)', tags=['Contest'])
def get_worked() -> Response:
    return jsonify({'status': 'success', **worked.summary()})


@contest_bp.post('/contest/worked/import')
@api('Import the worked log from an ADIF or Cabrillo file', tags=['Contest'], body=WorkedImportRequest)
def import_worked() -> Response:
    req = parse_body(WorkedImportRequest)
    count = worked.import_log(req.text, replace=req.replace)
    if count == 0:
        raise ApiError('No QSOs found (ADIF or Cabrillo expected)', 400)
    return jsonify({'status': 'success', 'imported': count, **worked.summary()})


@contest_bp.delete('/contest/worked')
@api('Clear the worked log', tags=['Contest'])
def clear_worked() -> Response:
    worked.clear()
    return jsonify({'status': 'success', **worked.summary()})


@contest_bp.post('/skimmer/start')
@api('Start the contest skimmer on a band segment (CW)', tags=['Contest'], body=SkimmerRequest,
     responses={409: 'SDR busy', 400: 'Invalid segment or no SDR'})
def start_skimmer() -> Response:
    req = parse_body(SkimmerRequest)
    result = call_action(actions.start_skimmer, req)
    return jsonify({'status': 'success', 'message': 'Skimmer started', **result})


@contest_bp.get('/skimmer/spots')
@api('Spots of the skimmer (and forwarded RBN spots), newest first, classified', tags=['Contest'],
     query=SkimmerSpotsQuery)
def get_spots() -> Response:
    q = parse_query(SkimmerSpotsQuery)
    now = time.time()
    result = []
    for s in skimmer_session.load_spots():
        if now - s['last_seen'] > q.max_age * 60:
            continue
        if q.band and s.get('band') != q.band:
            continue
        if q.priority and s.get('priority') != q.priority:
            continue
        if q.source and q.source not in (s.get('sources') or [s.get('source')]):
            continue
        result.append({**s, 'age_seconds': int(now - s['last_seen'])})
        if len(result) >= q.limit:
            break
    return jsonify({'status': 'success', 'count': len(result), 'spots': result})
