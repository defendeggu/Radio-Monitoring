"""
Signed links to recordings, e.g. for the audio player in Kibana.

An <audio> element cannot send the X-API-Key header, so capture documents in
Elasticsearch carry audio_url = /api/recordings/<file>.wav?sig=<hmac>. The
signature is bound to the file name and only opens GET/HEAD of that one WAV
file. Without RECORDING_LINK_SECRET no links are created and none are accepted.

    python -m radiomoni.recording_links backfill   # add audio_url to existing documents
"""

import hashlib
import hmac
import logging
import sys
from typing import Optional

from radiomoni import config

logger = logging.getLogger(__name__)

ROUTE = '/recordings/'


def sign(filename: str) -> Optional[str]:
    """HMAC-SHA256 of the file name (128 bit, hex), or None without a secret."""
    if not config.RECORDING_LINK_SECRET:
        return None
    digest = hmac.new(config.RECORDING_LINK_SECRET.encode(), filename.encode(), hashlib.sha256)
    return digest.hexdigest()[:32]


def audio_url(filename: Optional[str]) -> Optional[str]:
    """Signed path of a WAV recording relative to the web UI, or None."""
    if not filename or '/' in filename or not filename.lower().endswith('.wav'):
        return None
    sig = sign(filename)
    return f'/api{ROUTE}{filename}?sig={sig}' if sig else None


def is_signed_request(path: str, sig: Optional[str]) -> bool:
    """True if path is /recordings/<file>.wav and sig is the signature of that file."""
    if not sig or not path.startswith(ROUTE):
        return False
    filename = path[len(ROUTE):]
    if not filename or '/' in filename or not filename.lower().endswith('.wav'):
        return False
    expected = sign(filename)
    return expected is not None and hmac.compare_digest(sig, expected)


def backfill() -> int:
    """Add audio_url to capture documents in Elasticsearch that have a WAV file but no link."""
    from elasticsearch import helpers

    from radiomoni.storage.elasticsearch import create_elasticsearch_service

    if not config.RECORDING_LINK_SECRET:
        raise SystemExit('RECORDING_LINK_SECRET is not set')
    es = create_elasticsearch_service().es_client
    query = {'query': {'bool': {'must': [{'exists': {'field': 'audio_file'}}],
                                'must_not': [{'exists': {'field': 'audio_url'}}]}}}
    actions = []
    for hit in helpers.scan(es, index='radio-captures-*', query=query, _source=['audio_file']):
        url = audio_url(hit['_source'].get('audio_file'))
        if url:
            actions.append({'_op_type': 'update', '_index': hit['_index'], '_id': hit['_id'],
                            'doc': {'audio_url': url}})
    if actions:
        helpers.bulk(es, actions)
    return len(actions)


if __name__ == '__main__':  # pragma: no cover
    if sys.argv[1:] != ['backfill']:
        raise SystemExit('Usage: python -m radiomoni.recording_links backfill')
    print(f'Added audio_url to {backfill()} capture documents')
