#!/usr/bin/env python3
"""
Elasticsearch Service for Radio Monitoring System
Replaces PostgreSQL database with Elasticsearch for scalable storage and analytics
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import NotFoundError, RequestError
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ElasticsearchService:
    """Elasticsearch client wrapper for radio monitoring data"""

    def __init__(self, hosts: List[str] = None, logstash_host: str = None):
        """
        Initialize Elasticsearch service

        Args:
            hosts: List of Elasticsearch hosts (default: http://elasticsearch:9200)
            logstash_host: Logstash HTTP input endpoint (default: http://logstash:9600)
        """
        self.es_hosts = hosts or ['http://elasticsearch:9200']
        self.logstash_host = logstash_host or 'http://logstash:9600'
        self.es_client = Elasticsearch(self.es_hosts)
        logger.info(f"Elasticsearch service initialized: {self.es_hosts}")

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
            return {'status': 'error', 'message': str(e)}

    # =========================================================================
    # Voice Capture Operations
    # =========================================================================

    def index_capture(self, capture: Dict[str, Any]) -> str:
        """
        Index voice capture document via Logstash

        Args:
            capture: Capture data dictionary

        Returns:
            UUID of indexed document
        """
        try:
            # Add timestamp if not present
            if '@timestamp' not in capture:
                capture['@timestamp'] = capture.get('created_at') or datetime.utcnow().isoformat()

            # Calculate frequency_mhz
            if 'frequency' in capture:
                capture['frequency_mhz'] = capture['frequency'] / 1_000_000.0

            # Send to Logstash for processing
            response = requests.post(
                self.logstash_host,
                json=capture,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code not in [200, 201]:
                logger.error(f"Logstash indexing failed: {response.text}")
                raise RuntimeError(f"Failed to index capture: {response.status_code}")

            logger.info(f"Indexed capture {capture.get('uuid')}")
            return capture.get('uuid')

        except Exception as e:
            logger.error(f"Error indexing capture: {e}")
            raise

    def search_captures(self,
                       query: str = None,
                       frequency_min: int = None,
                       frequency_max: int = None,
                       modulation: str = None,
                       language: str = None,
                       sdr_type: str = None,
                       hours: int = 24,
                       limit: int = 100,
                       offset: int = 0) -> Dict[str, Any]:
        """
        Search voice captures with full-text and filters

        Args:
            query: Full-text search query
            frequency_min: Minimum frequency in Hz
            frequency_max: Maximum frequency in Hz
            modulation: Modulation type filter
            language: Language code filter
            sdr_type: SDR type filter (hackrf, rtlsdr)
            hours: Time range in hours
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Search results with hits and total count
        """
        try:
            must_clauses = [
                {'range': {'@timestamp': {'gte': f'now-{hours}h', 'lte': 'now'}}}
            ]

            # Full-text search in transcription with language-specific analyzers
            if query:
                must_clauses.append({
                    'multi_match': {
                        'query': query,
                        'fields': [
                            'transcription^2',
                            'transcription.english',
                            'transcription.german',
                            'transcription.french',
                            'transcription.spanish'
                        ],
                        'type': 'best_fields'
                    }
                })

            # Frequency range filter
            if frequency_min or frequency_max:
                range_clause = {}
                if frequency_min:
                    range_clause['gte'] = frequency_min
                if frequency_max:
                    range_clause['lte'] = frequency_max
                must_clauses.append({'range': {'frequency': range_clause}})

            # Exact match filters
            if modulation:
                must_clauses.append({'term': {'modulation': modulation}})
            if language:
                must_clauses.append({'term': {'detected_language': language}})
            if sdr_type:
                must_clauses.append({'term': {'sdr_type': sdr_type}})

            body = {
                'query': {'bool': {'must': must_clauses}},
                'sort': [{'@timestamp': 'desc'}],
                'size': limit,
                'from': offset
            }

            result = self.es_client.search(index='radio-captures-*', body=body)

            return {
                'hits': [hit['_source'] for hit in result['hits']['hits']],
                'total': result['hits']['total']['value'],
                'limit': limit,
                'offset': offset
            }

        except Exception as e:
            logger.error(f"Error searching captures: {e}")
            raise

    # =========================================================================
    # APRS Operations
    # =========================================================================

    def index_aprs(self, message: Dict[str, Any]) -> str:
        """Index APRS message via Logstash"""
        try:
            if '@timestamp' not in message:
                message['@timestamp'] = message.get('timestamp') or datetime.utcnow().isoformat()

            # Build geo_point if lat/lon present
            if message.get('latitude') and message.get('longitude'):
                message['position'] = {
                    'lat': message['latitude'],
                    'lon': message['longitude']
                }

            if 'frequency' in message:
                message['frequency_mhz'] = message['frequency'] / 1_000_000.0

            response = requests.post(
                f"{self.logstash_host.replace(':9600', ':9601')}",  # APRS pipeline port
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code not in [200, 201]:
                logger.error(f"Logstash APRS indexing failed: {response.text}")
                raise RuntimeError(f"Failed to index APRS: {response.status_code}")

            logger.info(f"Indexed APRS message from {message.get('source_callsign')}")
            return message.get('uuid')

        except Exception as e:
            logger.error(f"Error indexing APRS: {e}")
            raise

    def search_aprs(self,
                    callsign: str = None,
                    packet_type: str = None,
                    hours: int = 24,
                    limit: int = 100) -> Dict[str, Any]:
        """Search APRS messages"""
        try:
            must_clauses = [
                {'range': {'@timestamp': {'gte': f'now-{hours}h'}}}
            ]

            if callsign:
                must_clauses.append({
                    'term': {'source_callsign': callsign.upper()}
                })
            if packet_type:
                must_clauses.append({'term': {'packet_type': packet_type}})

            body = {
                'query': {'bool': {'must': must_clauses}},
                'sort': [{'@timestamp': 'desc'}],
                'size': limit
            }

            result = self.es_client.search(index='radio-aprs-*', body=body)

            return {
                'hits': [hit['_source'] for hit in result['hits']['hits']],
                'total': result['hits']['total']['value']
            }

        except Exception as e:
            logger.error(f"Error searching APRS: {e}")
            raise

    def get_aprs_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get APRS statistics with aggregations"""
        try:
            body = {
                'query': {
                    'range': {'@timestamp': {'gte': f'now-{hours}h'}}
                },
                'size': 0,
                'aggs': {
                    'total_packets': {
                        'value_count': {'field': 'uuid.keyword'}
                    },
                    'unique_callsigns': {
                        'cardinality': {'field': 'source_callsign'}
                    },
                    'top_callsigns': {
                        'terms': {
                            'field': 'source_callsign',
                            'size': 15
                        }
                    },
                    'packet_types': {
                        'terms': {
                            'field': 'packet_type',
                            'size': 10
                        }
                    }
                }
            }

            result = self.es_client.search(index='radio-aprs-*', body=body)
            aggs = result['aggregations']

            return {
                'total_packets': aggs['total_packets']['value'],
                'unique_callsigns': aggs['unique_callsigns']['value'],
                'top_callsigns': [
                    {'callsign': b['key'], 'count': b['doc_count']}
                    for b in aggs['top_callsigns']['buckets']
                ],
                'packet_types': [
                    {'type': b['key'], 'count': b['doc_count']}
                    for b in aggs['packet_types']['buckets']
                ]
            }

        except Exception as e:
            logger.error(f"Error getting APRS stats: {e}")
            raise

    # =========================================================================
    # POCSAG Operations
    # =========================================================================

    def index_pocsag(self, message: Dict[str, Any]) -> str:
        """Index POCSAG message via Logstash"""
        try:
            if '@timestamp' not in message:
                message['@timestamp'] = message.get('timestamp') or datetime.utcnow().isoformat()

            if 'frequency' in message:
                message['frequency_mhz'] = message['frequency'] / 1_000_000.0

            response = requests.post(
                f"{self.logstash_host.replace(':9600', ':9602')}",  # POCSAG pipeline port
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code not in [200, 201]:
                logger.error(f"Logstash POCSAG indexing failed: {response.text}")
                raise RuntimeError(f"Failed to index POCSAG: {response.status_code}")

            logger.info(f"Indexed POCSAG message to address {message.get('address')}")
            return message.get('uuid')

        except Exception as e:
            logger.error(f"Error indexing POCSAG: {e}")
            raise

    def search_pocsag(self,
                      address: int = None,
                      message_type: str = None,
                      hours: int = 24,
                      limit: int = 100) -> Dict[str, Any]:
        """Search POCSAG messages"""
        try:
            must_clauses = [
                {'range': {'@timestamp': {'gte': f'now-{hours}h'}}}
            ]

            if address:
                must_clauses.append({'term': {'address': address}})
            if message_type:
                must_clauses.append({'term': {'message_type': message_type}})

            body = {
                'query': {'bool': {'must': must_clauses}},
                'sort': [{'@timestamp': 'desc'}],
                'size': limit
            }

            result = self.es_client.search(index='radio-pocsag-*', body=body)

            return {
                'hits': [hit['_source'] for hit in result['hits']['hits']],
                'total': result['hits']['total']['value']
            }

        except Exception as e:
            logger.error(f"Error searching POCSAG: {e}")
            raise

    def get_pocsag_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get POCSAG statistics"""
        try:
            body = {
                'query': {
                    'range': {'@timestamp': {'gte': f'now-{hours}h'}}
                },
                'size': 0,
                'aggs': {
                    'total_messages': {
                        'value_count': {'field': 'uuid.keyword'}
                    },
                    'unique_addresses': {
                        'cardinality': {'field': 'address'}
                    },
                    'top_addresses': {
                        'terms': {
                            'field': 'address',
                            'size': 15
                        }
                    },
                    'message_types': {
                        'terms': {
                            'field': 'message_type',
                            'size': 10
                        }
                    },
                    'baud_rates': {
                        'terms': {
                            'field': 'baud_rate'
                        }
                    }
                }
            }

            result = self.es_client.search(index='radio-pocsag-*', body=body)
            aggs = result['aggregations']

            return {
                'total_messages': aggs['total_messages']['value'],
                'unique_addresses': aggs['unique_addresses']['value'],
                'top_addresses': [
                    {'address': b['key'], 'count': b['doc_count']}
                    for b in aggs['top_addresses']['buckets']
                ],
                'message_types': [
                    {'type': b['key'], 'count': b['doc_count']}
                    for b in aggs['message_types']['buckets']
                ],
                'baud_rates': [
                    {'baud': b['key'], 'count': b['doc_count']}
                    for b in aggs['baud_rates']['buckets']
                ]
            }

        except Exception as e:
            logger.error(f"Error getting POCSAG stats: {e}")
            raise

    # =========================================================================
    # Repeater Activity Operations
    # =========================================================================

    def index_repeater_activity(self, activity: Dict[str, Any]) -> str:
        """Index repeater activity data via Logstash"""
        try:
            if '@timestamp' not in activity:
                activity['@timestamp'] = activity.get('created_at') or datetime.utcnow().isoformat()

            if 'frequency' in activity:
                activity['frequency_mhz'] = activity['frequency'] / 1_000_000.0

            response = requests.post(
                f"{self.logstash_host.replace(':9600', ':9603')}",  # Repeater pipeline port
                json=activity,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code not in [200, 201]:
                logger.error(f"Logstash repeater indexing failed: {response.text}")
                raise RuntimeError(f"Failed to index repeater activity: {response.status_code}")

            logger.info(f"Indexed repeater activity for {activity.get('repeater_callsign')}")
            return activity.get('uuid')

        except Exception as e:
            logger.error(f"Error indexing repeater activity: {e}")
            raise

    def get_repeater_activity_summary(self,
                                     hours: int = 24,
                                     band: str = None,
                                     canton: str = None,
                                     limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get most active repeaters via aggregation

        Args:
            hours: Time range in hours
            band: Filter by band (2m, 70cm, etc.)
            canton: Filter by Swiss canton
            limit: Maximum repeaters to return

        Returns:
            List of repeaters with activity statistics
        """
        try:
            must_clauses = [
                {'range': {'@timestamp': {'gte': f'now-{hours}h'}}},
                {'term': {'carrier_detected': True}}
            ]

            if band:
                must_clauses.append({'term': {'band': band}})
            if canton:
                must_clauses.append({'term': {'canton': canton.upper()}})

            body = {
                'query': {'bool': {'must': must_clauses}},
                'size': 0,
                'aggs': {
                    'by_repeater': {
                        'terms': {
                            'field': 'repeater_callsign',
                            'size': limit,
                            'order': {'avg_activity': 'desc'}
                        },
                        'aggs': {
                            'avg_activity': {
                                'avg': {'field': 'activity_percentage'}
                            },
                            'total_transmissions': {
                                'sum': {'field': 'transmission_count'}
                            },
                            'avg_signal': {
                                'avg': {'field': 'average_signal_strength'}
                            },
                            'latest_frequency': {
                                'top_hits': {
                                    'size': 1,
                                    '_source': ['frequency_mhz', 'band', 'canton'],
                                    'sort': [{'@timestamp': 'desc'}]
                                }
                            }
                        }
                    }
                }
            }

            result = self.es_client.search(index='radio-repeater-activity-*', body=body)

            repeaters = []
            for bucket in result['aggregations']['by_repeater']['buckets']:
                latest = bucket['latest_frequency']['hits']['hits'][0]['_source']
                repeaters.append({
                    'callsign': bucket['key'],
                    'avg_activity_pct': round(bucket['avg_activity']['value'], 2),
                    'total_transmissions': int(bucket['total_transmissions']['value']),
                    'avg_signal_db': round(bucket['avg_signal']['value'], 1) if bucket['avg_signal']['value'] else None,
                    'frequency_mhz': latest.get('frequency_mhz'),
                    'band': latest.get('band'),
                    'canton': latest.get('canton')
                })

            return repeaters

        except Exception as e:
            logger.error(f"Error getting repeater activity summary: {e}")
            raise

    # =========================================================================
    # System Statistics
    # =========================================================================

    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall system statistics across all indices"""
        try:
            stats = {}

            # Voice captures count
            try:
                captures_result = self.es_client.count(index='radio-captures-*')
                stats['total_captures'] = captures_result['count']
            except NotFoundError:
                stats['total_captures'] = 0

            # APRS messages count
            try:
                aprs_result = self.es_client.count(index='radio-aprs-*')
                stats['total_aprs_messages'] = aprs_result['count']
            except NotFoundError:
                stats['total_aprs_messages'] = 0

            # POCSAG messages count
            try:
                pocsag_result = self.es_client.count(index='radio-pocsag-*')
                stats['total_pocsag_messages'] = pocsag_result['count']
            except NotFoundError:
                stats['total_pocsag_messages'] = 0

            # Repeater activity scans count
            try:
                repeater_result = self.es_client.count(index='radio-repeater-activity-*')
                stats['total_repeater_scans'] = repeater_result['count']
            except NotFoundError:
                stats['total_repeater_scans'] = 0

            # Cluster health
            stats['cluster_health'] = self.health_check()

            return stats

        except Exception as e:
            logger.error(f"Error getting overall stats: {e}")
            raise


# Initialize global instance (singleton pattern)
_es_service_instance = None


def get_elasticsearch_service() -> ElasticsearchService:
    """Get or create Elasticsearch service singleton"""
    global _es_service_instance
    if _es_service_instance is None:
        _es_service_instance = ElasticsearchService()
    return _es_service_instance
