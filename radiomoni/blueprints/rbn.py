"""
Reverse Beacon Network: CW spots of the last 30 minutes (see radiomoni/rbn.py).
"""

from flask import Blueprint, Response, jsonify

from radiomoni import config
from radiomoni import rbn
from radiomoni.api_docs import api, parse_query
from radiomoni.schemas import RbnSpotsQuery

rbn_bp = Blueprint('rbn', __name__)


@rbn_bp.get('/rbn/spots')
@api('CW spots of the Reverse Beacon Network (last 30 minutes, merged per callsign and frequency)',
     tags=['RBN'], query=RbnSpotsQuery)
def get_spots() -> Response:
    q = parse_query(RbnSpotsQuery)
    spots = rbn.query(rbn.load_spots(), band=q.band, freq_min=q.freq_min, freq_max=q.freq_max, call=q.call,
                      max_age=q.max_age * 60, cq_only=q.cq_only, limit=q.limit)
    return jsonify({'status': 'success', 'enabled': config.RBN_ENABLED and bool(config.RBN_CALLSIGN),
                    'count': len(spots), 'spots': spots})


@rbn_bp.get('/rbn/status')
@api('Connection state of the RBN client', tags=['RBN'])
def get_status() -> Response:
    return jsonify({'status': 'success', **rbn.status()})
