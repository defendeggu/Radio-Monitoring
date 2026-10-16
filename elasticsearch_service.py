#!/usr/bin/env python3
"""
Elasticsearch storage backend.

Captures, APRS, POCSAG and repeater activity are sent to Logstash (HTTP input,
basic auth), which enriches them and writes daily indices. ADS-B, AIS, ISM and
alert documents are indexed directly. Reads always go to Elasticsearch.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import requests
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

import config
from storage import EVENT_KINDS, StorageBackend, enrich_aprs

logger = logging.getLogger(__name__)

# index pattern per data type (daily indices)
INDEX_PATTERNS = {
    'captures': 'radio-captures-*',
    'aprs': 'radio-aprs-*',
    'pocsag': 'radio-pocsag-*',
    'repeater': 'radio-repeater-activity-*',
    'adsb': 'radio-adsb-*',
    'ais': 'radio-ais-*',
    'ism': 'radio-ism-*',
    'alerts': 'radio-alerts-*',
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ElasticsearchService(StorageBackend):
    """Elasticsearch client wrapper for radio monitoring data"""

    name = 'elasticsearch'

    def __init__(self, hosts: Optional[List[str]] = None,
                 logstash_host: Optional[str] = None,
                 logstash_aprs_host: Optional[str] = None,
                 logstash_pocsag_host: Optional[str] = None,
                 logstash_repeater_host: Optional[str] = None,
                 logstash_auth: Optional[tuple[str, str]] = None):
        self.es_hosts = hosts or ['http://elasticsearch:9200']
        self.logstash_host = logstash_host or 'http://logstash:9600'
        self.logstash_aprs_host = logstash_aprs_host or 'http://logstash:9601'
        self.logstash_pocsag_host = logstash_pocsag_host or 'http://logstash:9602'
        self.logstash_repeater_host = logstash_repeater_host or 'http://logstash:9603'
        self.logstash_auth = logstash_auth
        self.es_client = Elasticsearch(self.es_hosts, request_timeout=30)
        self._http = requests.Session()
        logger.info("Elasticsearch storage initialized")

    # ------------------------------------------------------------------ helpers
    def _post_logstash(self, url: str, doc: Dict[str, Any], what: str) -> None:
        response = self._http.post(url, json=doc, auth=self.logstash_auth, timeout=30)
        if response.status_code not in (200, 201):
            logger.error(f"Logstash {what} indexing failed: HTTP {response.status_code}")
            raise RuntimeError(f"Failed to index {what}: HTTP {response.status_code}")

    def _count(self, index: str, hours: Optional[int] = None) -> int:
        try:
            if hours is None:
                return int(self.es_client.count(index=index, allow_no_indices=True)['count'])
            return int(self.es_client.count(
                index=index, allow_no_indices=True,
                query={'range': {'@timestamp': {'gte': f'now-{hours}h'}}})['count'])
        except NotFoundError:
            return 0

    def health_check(self) -> Dict[str, Any]:
        """Check Elasticsearch cluster health"""
        try:
            health = self.es_client.cluster.health()
            return {
                'status': health['status'],
                'number_of_nodes': health['number_of_nodes'],
                'active_shards': health['active_shards']
            }
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            return {'status': 'error', 'message': 'Elasticsearch unreachable'}

    # ------------------------------------------------------------------ captures
    def index_capture(self, capture: Dict[str, Any]) -> Optional[str]:
        """Index a capture document via Logstash"""
        capture.setdefault('uuid', str(uuid.uuid4()))
        capture.setdefault('@timestamp', capture.get('created_at') or _now())
        if 'frequency' in capture:
            capture['frequency_mhz'] = capture['frequency'] / 1_000_000.0
        self._post_logstash(self.logstash_host, capture, 'capture')
        logger.info(f"Indexed capture {capture.get('uuid')}")
        return cast(Optional[str], capture.get('uuid'))

    def search_captures(self, query: Optional[str] = None, frequency_min: Optional[int] = None,
                        frequency_max: Optional[int] = None, modulation: Optional[str] = None,
                        language: Optional[str] = None, sdr_type: Optional[str] = None,
                        hours: int = 24, limit: int = 100, offset: int = 0,
                        mode: Optional[str] = None) -> Dict[str, Any]:
        """Search captures with full-text and filters"""
        must: List[Dict[str, Any]] = [{'range': {'@timestamp': {'gte': f'now-{hours}h', 'lte': 'now'}}}]
        if query:
            must.append({'multi_match': {
                'query': query,
                'fields': ['transcription^2', 'transcription.english', 'transcription.german',
                           'transcription.french', 'transcription.spanish'],
                'type': 'best_fields'}})
        if frequency_min or frequency_max:
            rng: Dict[str, int] = {}
            if frequency_min:
                rng['gte'] = frequency_min
            if frequency_max:
                rng['lte'] = frequency_max
            must.append({'range': {'frequency': rng}})
        for field, value in (('modulation', modulation), ('detected_language', language),
                             ('sdr_type', sdr_type), ('mode', mode)):
            if value:
                must.append({'term': {field: value}})
        try:
            result = self.es_client.search(index=INDEX_PATTERNS['captures'], query={'bool': {'must': must}},
                                           sort=[{'@timestamp': 'desc'}], size=limit, from_=offset,
                                           allow_no_indices=True)
        except NotFoundError:
            return {'hits': [], 'total': 0, 'limit': limit, 'offset': offset}
        return {
            'hits': [hit['_source'] for hit in result['hits']['hits']],
            'total': result['hits']['total']['value'],
            'limit': limit,
            'offset': offset
        }

    def get_capture_by_id(self, capture_id: str) -> Optional[Dict[str, Any]]:
        """Get a single capture by UUID"""
        try:
            result = self.es_client.search(index=INDEX_PATTERNS['captures'],
                                           query={'bool': {'should': [
                                               {'term': {'uuid': capture_id}},
                                               {'term': {'uuid.keyword': capture_id}}]}},
                                           size=1, allow_no_indices=True)
            if result['hits']['total']['value'] > 0:
                return cast(Dict[str, Any], result['hits']['hits'][0]['_source'])
            return None
        except Exception as e:
            logger.error(f"Error getting capture by ID: {e}")
            return None

    def get_frequency_usage(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Most used frequencies"""
        aggs_body = {
            'by_frequency': {
                'terms': {'field': 'frequency', 'size': limit, 'order': {'_count': 'desc'}},
                'aggs': {
                    'modulations': {'terms': {'field': 'modulation'}},
                    'last_capture': {'max': {'field': '@timestamp'}}
                }
            }
        }
        try:
            result = self.es_client.search(index=INDEX_PATTERNS['captures'], size=0, aggs=aggs_body,
                                           allow_no_indices=True)
        except NotFoundError:
            return []
        frequencies = []
        for bucket in result.get('aggregations', {}).get('by_frequency', {}).get('buckets', []):
            frequencies.append({
                'frequency': bucket['key'],
                'frequency_mhz': bucket['key'] / 1_000_000.0,
                'count': bucket['doc_count'],
                'modulations': [b['key'] for b in bucket['modulations']['buckets']],
                'last_capture': bucket['last_capture'].get('value_as_string')
            })
        return frequencies

    # ------------------------------------------------------------------ APRS
    def index_aprs(self, message: Dict[str, Any]) -> Optional[str]:
        """Index APRS message via Logstash"""
        enrich_aprs(message)
        message.setdefault('uuid', str(uuid.uuid4()))
        message.setdefault('@timestamp', message.get('timestamp') or _now())
        if message.get('latitude') is not None and message.get('longitude') is not None:
            message['position'] = {'lat': message['latitude'], 'lon': message['longitude']}
        if message.get('frequency'):
            message['frequency_mhz'] = message['frequency'] / 1_000_000.0
        self._post_logstash(self.logstash_aprs_host, message, 'APRS')
        return cast(Optional[str], message.get('uuid'))

    def search_aprs(self, callsign: Optional[str] = None, packet_type: Optional[str] = None,
                    hours: int = 24, limit: int = 100) -> Dict[str, Any]:
        """Search APRS messages"""
        must: List[Dict[str, Any]] = [{'range': {'@timestamp': {'gte': f'now-{hours}h'}}}]
        if callsign:
            must.append({'term': {'source_callsign': callsign.upper()}})
        if packet_type:
            must.append({'term': {'packet_type': packet_type}})
        try:
            result = self.es_client.search(index=INDEX_PATTERNS['aprs'], query={'bool': {'must': must}},
                                           sort=[{'@timestamp': 'desc'}], size=limit, allow_no_indices=True)
        except NotFoundError:
            return {'hits': [], 'total': 0}
        return {'hits': [hit['_source'] for hit in result['hits']['hits']],
                'total': result['hits']['total']['value']}

    def get_aprs_stats(self, hours: int = 24) -> Dict[str, Any]:
        """APRS statistics"""
        aggs_body: Dict[str, Any] = {
            'unique_callsigns': {'cardinality': {'field': 'source_callsign'}},
            'top_callsigns': {'terms': {'field': 'source_callsign', 'size': 15}},
            'packet_types': {'terms': {'field': 'packet_type', 'size': 10}}
        }
        try:
            result = self.es_client.search(index=INDEX_PATTERNS['aprs'],
                                           query={'range': {'@timestamp': {'gte': f'now-{hours}h'}}},
                                           size=0, aggs=aggs_body, track_total_hits=True, allow_no_indices=True)
        except NotFoundError:
            return {'total_packets': 0, 'unique_callsigns': 0, 'top_callsigns': [], 'packet_types': []}
        aggs = result.get('aggregations', {})
        return {
            'total_packets': result['hits']['total']['value'],
            'unique_callsigns': aggs.get('unique_callsigns', {}).get('value', 0),
            'top_callsigns': [{'callsign': b['key'], 'count': b['doc_count']}
                              for b in aggs.get('top_callsigns', {}).get('buckets', [])],
            'packet_types': [{'type': b['key'], 'count': b['doc_count']}
                             for b in aggs.get('packet_types', {}).get('buckets', [])]
        }

    # ------------------------------------------------------------------ POCSAG
    def index_pocsag(self, message: Dict[str, Any]) -> Optional[str]:
        """Index POCSAG message via Logstash"""
        message.setdefault('uuid', str(uuid.uuid4()))
        message.setdefault('@timestamp', message.get('timestamp') or _now())
        if message.get('frequency'):
            message['frequency_mhz'] = message['frequency'] / 1_000_000.0
        self._post_logstash(self.logstash_pocsag_host, message, 'POCSAG')
        return cast(Optional[str], message.get('uuid'))

    def search_pocsag(self, address: Optional[int] = None, message_type: Optional[str] = None,
                      hours: int = 24, limit: int = 100) -> Dict[str, Any]:
        """Search POCSAG messages"""
        must: List[Dict[str, Any]] = [{'range': {'@timestamp': {'gte': f'now-{hours}h'}}}]
        if address:
            must.append({'term': {'address': address}})
        if message_type:
            must.append({'term': {'message_type': message_type}})
        try:
            result = self.es_client.search(index=INDEX_PATTERNS['pocsag'], query={'bool': {'must': must}},
                                           sort=[{'@timestamp': 'desc'}], size=limit, allow_no_indices=True)
        except NotFoundError:
            return {'hits': [], 'total': 0}
        return {'hits': [hit['_source'] for hit in result['hits']['hits']],
                'total': result['hits']['total']['value']}

    def get_pocsag_stats(self, hours: int = 24) -> Dict[str, Any]:
        """POCSAG statistics"""
        aggs_body: Dict[str, Any] = {
            'unique_addresses': {'cardinality': {'field': 'address'}},
            'top_addresses': {'terms': {'field': 'address', 'size': 15}},
            'message_types': {'terms': {'field': 'message_type', 'size': 10}},
            'baud_rates': {'terms': {'field': 'baud_rate'}}
        }
        try:
            result = self.es_client.search(index=INDEX_PATTERNS['pocsag'],
                                           query={'range': {'@timestamp': {'gte': f'now-{hours}h'}}},
                                           size=0, aggs=aggs_body, track_total_hits=True, allow_no_indices=True)
        except NotFoundError:
            return {'total_messages': 0, 'unique_addresses': 0, 'top_addresses': [],
                    'message_types': [], 'baud_rates': []}
        aggs = result.get('aggregations', {})
        return {
            'total_messages': result['hits']['total']['value'],
            'unique_addresses': aggs.get('unique_addresses', {}).get('value', 0),
            'top_addresses': [{'address': b['key'], 'count': b['doc_count']}
                              for b in aggs.get('top_addresses', {}).get('buckets', [])],
            'message_types': [{'type': b['key'], 'count': b['doc_count']}
                              for b in aggs.get('message_types', {}).get('buckets', [])],
            'baud_rates': [{'baud': b['key'], 'count': b['doc_count']}
                           for b in aggs.get('baud_rates', {}).get('buckets', [])]
        }

    # ------------------------------------------------------------------ repeaters
    def index_repeater_activity(self, activity: Dict[str, Any]) -> Optional[str]:
        """Index repeater activity via Logstash"""
        activity.setdefault('uuid', str(uuid.uuid4()))
        activity.setdefault('@timestamp', activity.get('created_at') or _now())
        if activity.get('frequency'):
            activity['frequency_mhz'] = activity['frequency'] / 1_000_000.0
        self._post_logstash(self.logstash_repeater_host, activity, 'repeater activity')
        return cast(Optional[str], activity.get('uuid'))

    def get_repeater_activity_summary(self, hours: int = 24, band: Optional[str] = None,
                                      canton: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Most active repeaters"""
        must: List[Dict[str, Any]] = [
            {'range': {'@timestamp': {'gte': f'now-{hours}h'}}},
            {'term': {'carrier_detected': True}}
        ]
        if band:
            must.append({'term': {'band': band}})
        if canton:
            must.append({'term': {'canton': canton.upper()}})
        aggs_body = {
            'by_repeater': {
                'terms': {'field': 'repeater_callsign', 'size': limit, 'order': {'avg_activity': 'desc'}},
                'aggs': {
                    'avg_activity': {'avg': {'field': 'activity_percentage'}},
                    'total_transmissions': {'sum': {'field': 'transmission_count'}},
                    'avg_signal': {'avg': {'field': 'average_signal_strength'}},
                    'latest': {'top_hits': {'size': 1, '_source': ['frequency_mhz', 'band', 'canton'],
                                            'sort': [{'@timestamp': 'desc'}]}}
                }
            }
        }
        try:
            result = self.es_client.search(index=INDEX_PATTERNS['repeater'], query={'bool': {'must': must}},
                                           size=0, aggs=aggs_body, allow_no_indices=True)
        except NotFoundError:
            return []
        repeaters = []
        for bucket in result.get('aggregations', {}).get('by_repeater', {}).get('buckets', []):
            latest = bucket['latest']['hits']['hits'][0]['_source']
            avg_signal = bucket['avg_signal']['value']
            repeaters.append({
                'callsign': bucket['key'],
                'avg_activity_pct': round(bucket['avg_activity']['value'] or 0, 2),
                'total_transmissions': int(bucket['total_transmissions']['value'] or 0),
                'avg_signal_db': round(avg_signal, 1) if avg_signal is not None else None,
                'frequency_mhz': latest.get('frequency_mhz'),
                'band': latest.get('band'),
                'canton': latest.get('canton')
            })
        return repeaters

    def index_repeater(self, repeater: Dict[str, Any]) -> Optional[str]:
        """Index repeater master data"""
        repeater_id = repeater.get('id') or repeater.get('uuid')
        if repeater_id is None:
            raise ValueError("Repeater must have an id or uuid")
        self.es_client.index(index='radio-repeaters', id=str(repeater_id), document=repeater)
        return str(repeater_id)

    def get_repeaters(self, band: Optional[str] = None, canton: Optional[str] = None,
                      mode: Optional[str] = None, status: Optional[str] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        """Repeaters with optional filters"""
        must: List[Dict[str, Any]] = []
        if band and band != 'all':
            must.append({'term': {'band.keyword': band}})
        if canton:
            must.append({'term': {'canton.keyword': canton.upper()}})
        if mode:
            must.append({'term': {'mode.keyword': mode}})
        if status:
            must.append({'term': {'status.keyword': status}})
        query = {'bool': {'must': must}} if must else {'match_all': {}}
        try:
            result = self.es_client.search(index='radio-repeaters', query=query,
                                           sort=[{'callsign.keyword': 'asc'}], size=limit)
        except NotFoundError:
            logger.warning("Repeaters index not found")
            return []
        return [hit['_source'] for hit in result['hits']['hits']]

    def get_repeater_by_id(self, repeater_id: Any) -> Optional[Dict[str, Any]]:
        """Single repeater by ID"""
        try:
            result = self.es_client.get(index='radio-repeaters', id=str(repeater_id))
            source = result.get('_source')
            return cast(Dict[str, Any], source) if source else None
        except NotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting repeater by ID: {e}")
            return None

    # ------------------------------------------------------------------ events
    def index_event(self, kind: str, doc: Dict[str, Any]) -> Optional[str]:
        """Index an ADS-B/AIS/ISM/alert document directly into a daily index"""
        if kind not in EVENT_KINDS:
            raise ValueError(f"Unknown event kind: {kind}")
        doc.setdefault('uuid', str(uuid.uuid4()))
        doc.setdefault('@timestamp', doc.get('timestamp') or _now())
        if doc.get('latitude') is not None and doc.get('longitude') is not None:
            doc['position'] = {'lat': doc['latitude'], 'lon': doc['longitude']}
        index = f"radio-{kind}-{datetime.now(timezone.utc):%Y.%m.%d}"
        self.es_client.index(index=index, id=doc['uuid'], document=doc)
        return cast(Optional[str], doc['uuid'])

    def search_events(self, kind: str, hours: int = 24, limit: int = 100,
                      term: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        must: List[Dict[str, Any]] = [{'range': {'@timestamp': {'gte': f'now-{hours}h'}}}]
        for field, value in (term or {}).items():
            must.append({'term': {field: value}})
        try:
            result = self.es_client.search(index=INDEX_PATTERNS[kind], query={'bool': {'must': must}},
                                           sort=[{'@timestamp': 'desc'}], size=limit, allow_no_indices=True)
        except NotFoundError:
            return {'hits': [], 'total': 0}
        return {'hits': [hit['_source'] for hit in result['hits']['hits']],
                'total': result['hits']['total']['value']}

    # ------------------------------------------------------------------ stats
    def get_overall_stats(self) -> Dict[str, Any]:
        """Totals across all indices"""
        return {
            'total_captures': self._count(INDEX_PATTERNS['captures']),
            'total_aprs_messages': self._count(INDEX_PATTERNS['aprs']),
            'total_pocsag_messages': self._count(INDEX_PATTERNS['pocsag']),
            'total_repeater_scans': self._count(INDEX_PATTERNS['repeater']),
            'total_adsb': self._count(INDEX_PATTERNS['adsb']),
            'total_ais': self._count(INDEX_PATTERNS['ais']),
            'total_ism': self._count(INDEX_PATTERNS['ism']),
            'cluster_health': self.health_check(),
        }

    def get_dashboard_stats(self, hours: int = 24) -> Dict[str, Any]:
        counts = {kind: self._count(pattern, hours) for kind, pattern in INDEX_PATTERNS.items()}
        timeline: List[Dict[str, Any]] = []
        try:
            result = self.es_client.search(
                index='radio-captures-*,radio-aprs-*,radio-pocsag-*,radio-adsb-*,radio-ais-*,radio-ism-*',
                query={'range': {'@timestamp': {'gte': f'now-{hours}h'}}}, size=0, allow_no_indices=True,
                aggs={'per_hour': {
                    'date_histogram': {'field': '@timestamp', 'fixed_interval': '1h', 'min_doc_count': 0,
                                       'extended_bounds': {'min': f'now-{hours}h', 'max': 'now'}},
                    'aggs': {'by_index': {'terms': {'field': '_index', 'size': 50}}}}})
            for bucket in result.get('aggregations', {}).get('per_hour', {}).get('buckets', []):
                per_kind: Dict[str, int] = {}
                for ib in bucket['by_index']['buckets']:
                    kind = _kind_from_index(ib['key'])
                    per_kind[kind] = per_kind.get(kind, 0) + ib['doc_count']
                timeline.append({'time': bucket['key_as_string'], **per_kind})
        except Exception as e:
            logger.warning(f"Dashboard timeline failed: {e}")
        latest_aprs = self.search_aprs(hours=hours, limit=5)['hits']
        latest_pocsag = self.search_pocsag(hours=hours, limit=5)['hits']
        latest_captures = self.search_captures(hours=hours, limit=5)['hits']
        return {'hours': hours, 'counts': counts, 'timeline': timeline,
                'latest': {'aprs': latest_aprs, 'pocsag': latest_pocsag, 'captures': latest_captures}}


def _kind_from_index(index: str) -> str:
    # radio-captures-2026.10.16 / .ds-... → captures
    name = index.lstrip('.').split('radio-', 1)[-1]
    return name.rsplit('-', 1)[0] if '-' in name else name


def create_elasticsearch_service() -> ElasticsearchService:
    """Build the backend from environment configuration"""
    import os
    hosts = [h for h in os.getenv('ELASTICSEARCH_HOSTS', 'http://elasticsearch:9200').split(',') if h]
    auth = (config.LOGSTASH_HTTP_USER, config.LOGSTASH_HTTP_PASSWORD) if config.LOGSTASH_HTTP_PASSWORD else None
    return ElasticsearchService(
        hosts=hosts,
        logstash_host=os.getenv('LOGSTASH_HOST', 'http://logstash:9600'),
        logstash_aprs_host=os.getenv('LOGSTASH_APRS_HOST', 'http://logstash:9601'),
        logstash_pocsag_host=os.getenv('LOGSTASH_POCSAG_HOST', 'http://logstash:9602'),
        logstash_repeater_host=os.getenv('LOGSTASH_REPEATER_HOST', 'http://logstash:9603'),
        logstash_auth=auth,
    )


def get_elasticsearch_service() -> StorageBackend:
    """Backwards-compatible alias for storage.get_storage()"""
    from storage import get_storage
    return get_storage()
