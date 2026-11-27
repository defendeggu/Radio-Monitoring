"""
Read stored APRS packets again from raw_packet with the current parser
(radiomoni/aprs_parse.py), so that older packets get positions, symbols and
readable text too (Mic-E, objects, third-party, weather …).

    docker exec radio-transcription-api python -m radiomoni.aprs_reparse [--dry-run]
    docker exec radio-transcription-api python -m radiomoni.aprs_reparse --set-reception [--dry-run]

--set-reception only marks packets stored before 5.8.0 as heard over the air
(reception=rf, reception_source=rf); nothing else changes.

Works with both storage backends (Elasticsearch: partial updates in place,
SQLite: the JSON document of each row). Time, frequency, session and raw
packet stay as they are.

Up to 5.9 the ILM policy made older daily indices read-only (warm phase); the
API user may not change that, so their packets are reported as failed.
./scripts/setup-elk-users.sh lifts those blocks.
"""

import argparse
import json
import logging
from typing import Any, Iterator, Optional

from radiomoni.aprs_parse import parse_line
from radiomoni.storage.base import enrich_aprs, get_storage

logger = logging.getLogger(__name__)

# fields the parser owns; cleared when a new parse does not set them (e.g. a wrong old position)
PARSED_FIELDS = ('latitude', 'longitude', 'position', 'maidenhead', 'altitude', 'speed', 'course', 'symbol_table',
                 'symbol_code', 'symbol', 'symbol_id', 'comment', 'format', 'object_name', 'object_killed',
                 'addressee', 'message_id', 'device', 'mic_e_status', 'third_party_via', 'aprs_timestamp',
                 'weather', 'telemetry', 'phg', 'range_km')


def reparsed(doc: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Fields to write for one stored packet, or None when raw_packet cannot be parsed."""
    packet = parse_line(str(doc.get('raw_packet') or ''))
    if packet is None:
        return None
    packet.pop('raw_packet', None)
    packet.pop('maidenhead', None)
    enrich_aprs(packet)
    if packet.get('latitude') is not None and packet.get('longitude') is not None:
        packet['position'] = {'lat': packet['latitude'], 'lon': packet['longitude']}
    for field in PARSED_FIELDS:
        packet.setdefault(field, None)
    return packet


RECEPTION_RF = {'reception': 'rf', 'reception_source': 'rf'}


def _es(storage: Any, dry_run: bool, set_reception: bool = False) -> tuple[int, int]:
    from elasticsearch.helpers import bulk, scan

    def actions() -> Iterator[dict[str, Any]]:
        if set_reception:
            query = {'query': {'bool': {'must_not': [{'exists': {'field': 'reception'}}]}}}
            for hit in scan(storage.es_client, index='radio-aprs-*', query=query, _source=False):
                yield {'_op_type': 'update', '_index': hit['_index'], '_id': hit['_id'], 'doc': RECEPTION_RF}
            return
        for hit in scan(storage.es_client, index='radio-aprs-*', query={'query': {'exists': {'field': 'raw_packet'}}},
                        _source=['raw_packet']):
            fields = reparsed(hit['_source'])
            if fields is not None:
                yield {'_op_type': 'update', '_index': hit['_index'], '_id': hit['_id'], 'doc': fields}

    if dry_run:
        n = sum(1 for _ in actions())
        return n, 0
    ok, errors = bulk(storage.es_client, actions(), raise_on_error=False, chunk_size=500, refresh=True)
    failed = errors if isinstance(errors, list) else []
    blocked = sorted({e.get('update', {}).get('_index', '?') for e in failed
                      if 'cluster_block_exception' in str(e)})
    if blocked:
        print(f"read-only indices (ILM warm phase up to 5.9): {', '.join(blocked)} — "
              "run ./scripts/setup-elk-users.sh, then this again")
    return ok, len(failed) if isinstance(errors, list) else int(errors)


def _sqlite(storage: Any, dry_run: bool, set_reception: bool = False) -> tuple[int, int]:
    updated = 0
    with storage._conn() as conn:
        rows = conn.execute("SELECT uuid, data FROM docs WHERE kind = 'aprs'").fetchall()
        for uid, data in rows:
            doc = json.loads(data)
            if set_reception and 'reception' in doc:
                continue
            fields = dict(RECEPTION_RF) if set_reception else reparsed(doc)
            if fields is None:
                continue
            doc.update(fields)
            updated += 1
            if not dry_run:
                conn.execute('UPDATE docs SET data = ? WHERE uuid = ?', (json.dumps(doc, ensure_ascii=False), uid))
    return updated, 0


def main() -> None:
    parser = argparse.ArgumentParser(description='Re-read stored APRS packets with the current parser')
    parser.add_argument('--dry-run', action='store_true', help='only count, write nothing')
    parser.add_argument('--set-reception', action='store_true',
                        help='only mark packets stored before 5.8.0 as heard over the air (reception=rf)')
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    storage = get_storage()
    if storage.name == 'elasticsearch':
        done, failed = _es(storage, args.dry_run, args.set_reception)
    else:
        done, failed = _sqlite(storage, args.dry_run, args.set_reception)
    verb = 'would update' if args.dry_run else 'updated'
    print(f'APRS packets {verb}: {done}' + (f', failed: {failed}' if failed else ''))


if __name__ == '__main__':
    main()
