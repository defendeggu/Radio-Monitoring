#!/usr/bin/env python3
"""
Data Migration Script: PostgreSQL → Elasticsearch
Migrates all existing data from PostgreSQL to Elasticsearch indices
"""

import sys
import os
import uuid as uuid_lib
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from elasticsearch import Elasticsearch, helpers
    from elasticsearch.exceptions import ConnectionError as ESConnectionError
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    print("Install with: pip install elasticsearch psycopg2-binary")
    sys.exit(1)


class DataMigrator:
    """Migrates data from PostgreSQL to Elasticsearch"""

    def __init__(self, pg_config: Dict[str, str], es_hosts: List[str]):
        """
        Initialize migrator

        Args:
            pg_config: PostgreSQL connection parameters
            es_hosts: List of Elasticsearch hosts
        """
        self.pg_config = pg_config
        self.es_client = Elasticsearch(es_hosts)
        self.pg_conn = None

        # Verify Elasticsearch connection
        try:
            if not self.es_client.ping():
                raise RuntimeError("Cannot connect to Elasticsearch")
            print(f"✓ Connected to Elasticsearch: {es_hosts}")
        except ESConnectionError as e:
            raise RuntimeError(f"Elasticsearch connection failed: {e}")

    def connect_postgres(self):
        """Connect to PostgreSQL database"""
        try:
            self.pg_conn = psycopg2.connect(**self.pg_config)
            print(f"✓ Connected to PostgreSQL: {self.pg_config['host']}:{self.pg_config['port']}")
        except psycopg2.Error as e:
            raise RuntimeError(f"PostgreSQL connection failed: {e}")

    def close(self):
        """Close database connections"""
        if self.pg_conn:
            self.pg_conn.close()

    def migrate_captures(self) -> int:
        """Migrate voice captures from PostgreSQL to Elasticsearch"""
        print("\n" + "="*70)
        print("Migrating Voice Captures...")
        print("="*70)

        cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT
                id, uuid, created_at, frequency, duration,
                modulation, sample_rate, gain,
                audio_file_path, transcription_text, language,
                language_confidence, segments, status, metadata
            FROM captures
            ORDER BY created_at
        """)

        docs = []
        batch_size = 500

        for row in cursor.fetchall():
            # Determine daily index
            created_at = row['created_at']
            index = f"radio-captures-{created_at:%Y.%m.%d}"

            doc = {
                '_index': index,
                '_id': row['uuid'] or str(uuid_lib.uuid4()),
                '@timestamp': created_at.isoformat(),
                'uuid': row['uuid'] or str(uuid_lib.uuid4()),
                'frequency': row['frequency'],
                'frequency_mhz': row['frequency'] / 1_000_000.0 if row['frequency'] else None,
                'duration_seconds': row['duration'],
                'modulation': row['modulation'],
                'sample_rate': row['sample_rate'],
                'rf_gain': row['gain'],
                'sdr_type': 'hackrf',  # Default for old data
                'audio_file': row['audio_file_path'],
                'transcription': row['transcription_text'],
                'detected_language': row['language'],
                'confidence_score': row['language_confidence'],
                'segments': row['segments'],
                'status': row['status'] or 'completed',
                'metadata': row['metadata']
            }

            # Remove None values
            doc = {k: v for k, v in doc.items() if v is not None}

            docs.append(doc)

            if len(docs) >= batch_size:
                success, failed = helpers.bulk(self.es_client, docs, raise_on_error=False)
                print(f"  Indexed {success} captures, {failed} failed")
                docs = []

        # Index remaining documents
        if docs:
            success, failed = helpers.bulk(self.es_client, docs, raise_on_error=False)
            print(f"  Indexed {success} captures, {failed} failed")

        cursor.close()

        # Get total count
        cursor = self.pg_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM captures")
        total = cursor.fetchone()[0]
        cursor.close()

        print(f"✓ Migration complete: {total} voice captures")
        return total

    def migrate_aprs(self) -> int:
        """Migrate APRS messages from PostgreSQL to Elasticsearch"""
        print("\n" + "="*70)
        print("Migrating APRS Messages...")
        print("="*70)

        cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT
                id, uuid, created_at, capture_id, source_callsign,
                destination_callsign, aprs_type as packet_type, latitude, longitude,
                message_text, raw_packet
            FROM aprs_messages
            ORDER BY created_at
        """)

        docs = []
        batch_size = 500

        for row in cursor.fetchall():
            created_at = row['created_at']
            index = f"radio-aprs-{created_at:%Y.%m.%d}"

            doc = {
                '_index': index,
                '_id': row['uuid'] or str(uuid_lib.uuid4()),
                '@timestamp': created_at.isoformat(),
                'uuid': row['uuid'] or str(uuid_lib.uuid4()),
                'capture_id': str(row['capture_id']) if row['capture_id'] else None,
                'source_callsign': row['source_callsign'],
                'destination_callsign': row['destination_callsign'],
                'packet_type': row['packet_type'],
                'latitude': row['latitude'],
                'longitude': row['longitude'],
                'message_text': row['message_text'],
                'raw_packet': row['raw_packet']
            }

            # Build geo_point if lat/lon present
            if row['latitude'] and row['longitude']:
                doc['position'] = {
                    'lat': float(row['latitude']),
                    'lon': float(row['longitude'])
                }

            doc = {k: v for k, v in doc.items() if v is not None}
            docs.append(doc)

            if len(docs) >= batch_size:
                success, failed = helpers.bulk(self.es_client, docs, raise_on_error=False)
                print(f"  Indexed {success} APRS messages, {failed} failed")
                docs = []

        if docs:
            success, failed = helpers.bulk(self.es_client, docs, raise_on_error=False)
            print(f"  Indexed {success} APRS messages, {failed} failed")

        cursor.close()

        cursor = self.pg_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM aprs_messages")
        total = cursor.fetchone()[0]
        cursor.close()

        print(f"✓ Migration complete: {total} APRS messages")
        return total

    def migrate_pocsag(self) -> int:
        """Migrate POCSAG messages from PostgreSQL to Elasticsearch"""
        print("\n" + "="*70)
        print("Migrating POCSAG Messages...")
        print("="*70)

        cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT
                id, uuid, created_at, capture_id, address, message_type,
                function_code, baud_rate, message_text
            FROM pocsag_messages
            ORDER BY created_at
        """)

        docs = []
        batch_size = 500

        for row in cursor.fetchall():
            created_at = row['created_at']
            index = f"radio-pocsag-{created_at:%Y.%m.%d}"

            doc = {
                '_index': index,
                '_id': row['uuid'] or str(uuid_lib.uuid4()),
                '@timestamp': created_at.isoformat(),
                'uuid': row['uuid'] or str(uuid_lib.uuid4()),
                'capture_id': str(row['capture_id']) if row['capture_id'] else None,
                'address': row['address'],
                'message_type': row['message_type'],
                'function_code': row['function_code'],
                'baud_rate': row['baud_rate'],
                'message_text': row['message_text']
            }

            doc = {k: v for k, v in doc.items() if v is not None}
            docs.append(doc)

            if len(docs) >= batch_size:
                success, failed = helpers.bulk(self.es_client, docs, raise_on_error=False)
                print(f"  Indexed {success} POCSAG messages, {failed} failed")
                docs = []

        if docs:
            success, failed = helpers.bulk(self.es_client, docs, raise_on_error=False)
            print(f"  Indexed {success} POCSAG messages, {failed} failed")

        cursor.close()

        cursor = self.pg_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pocsag_messages")
        total = cursor.fetchone()[0]
        cursor.close()

        print(f"✓ Migration complete: {total} POCSAG messages")
        return total

    def migrate_repeater_activity(self) -> int:
        """Migrate repeater activity data from PostgreSQL to Elasticsearch"""
        print("\n" + "="*70)
        print("Migrating Repeater Activity...")
        print("="*70)

        cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT
                ra.id, ra.uuid, ra.created_at, ra.capture_id, ra.repeater_id,
                r.callsign, r.output_frequency, r.band, r.canton, r.location_name,
                ra.carrier_detected, ra.transmission_count, ra.activity_percentage,
                ra.average_signal_strength, ra.noise_floor, ra.scan_duration_seconds,
                ra.transmissions
            FROM repeater_activity ra
            LEFT JOIN repeaters r ON ra.repeater_id = r.id
            ORDER BY ra.created_at
        """)

        docs = []
        batch_size = 500

        for row in cursor.fetchall():
            created_at = row['created_at']
            index = f"radio-repeater-activity-{created_at:%Y.%m.%d}"

            doc = {
                '_index': index,
                '_id': row['uuid'] or str(uuid_lib.uuid4()),
                '@timestamp': created_at.isoformat(),
                'uuid': row['uuid'] or str(uuid_lib.uuid4()),
                'capture_id': str(row['capture_id']) if row['capture_id'] else None,
                'repeater_id': str(row['repeater_id']) if row['repeater_id'] else None,
                'repeater_callsign': row['callsign'],
                'frequency': row['output_frequency'],
                'frequency_mhz': row['output_frequency'] / 1_000_000.0 if row['output_frequency'] else None,
                'band': row['band'],
                'canton': row['canton'],
                'location_name': row['location_name'],
                'carrier_detected': row['carrier_detected'],
                'transmission_count': row['transmission_count'],
                'activity_percentage': float(row['activity_percentage']) if row['activity_percentage'] else None,
                'average_signal_strength': float(row['average_signal_strength']) if row['average_signal_strength'] else None,
                'noise_floor': float(row['noise_floor']) if row['noise_floor'] else None,
                'scan_duration_seconds': row['scan_duration_seconds'],
                'transmissions': row['transmissions']
            }

            doc = {k: v for k, v in doc.items() if v is not None}
            docs.append(doc)

            if len(docs) >= batch_size:
                success, failed = helpers.bulk(self.es_client, docs, raise_on_error=False)
                print(f"  Indexed {success} repeater activity records, {failed} failed")
                docs = []

        if docs:
            success, failed = helpers.bulk(self.es_client, docs, raise_on_error=False)
            print(f"  Indexed {success} repeater activity records, {failed} failed")

        cursor.close()

        cursor = self.pg_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM repeater_activity")
        total = cursor.fetchone()[0]
        cursor.close()

        print(f"✓ Migration complete: {total} repeater activity records")
        return total

    def verify_migration(self):
        """Verify migrated data counts"""
        print("\n" + "="*70)
        print("Verifying Migration...")
        print("="*70)

        # Check Elasticsearch indices
        try:
            for index_pattern in ['radio-captures-*', 'radio-aprs-*', 'radio-pocsag-*', 'radio-repeater-activity-*']:
                try:
                    result = self.es_client.count(index=index_pattern)
                    count = result['count']
                    print(f"  {index_pattern}: {count} documents")
                except:
                    print(f"  {index_pattern}: 0 documents (index not found)")
        except Exception as e:
            print(f"  Error checking Elasticsearch: {e}")


def main():
    """Main migration function"""
    print("="*70)
    print("PostgreSQL → Elasticsearch Data Migration")
    print("="*70)

    # PostgreSQL configuration
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'radio_monitoring'),
        'user': os.getenv('POSTGRES_USER', 'radio_user'),
        'password': os.getenv('POSTGRES_PASSWORD', 'radio_password')
    }

    # Elasticsearch configuration
    es_hosts = [os.getenv('ELASTICSEARCH_HOSTS', 'http://localhost:9200')]

    print(f"\nConfiguration:")
    print(f"  PostgreSQL: {pg_config['host']}:{pg_config['port']}/{pg_config['database']}")
    print(f"  Elasticsearch: {es_hosts[0]}")

    try:
        # Initialize migrator
        migrator = DataMigrator(pg_config, es_hosts)
        migrator.connect_postgres()

        # Run migrations
        captures_count = migrator.migrate_captures()
        aprs_count = migrator.migrate_aprs()
        pocsag_count = migrator.migrate_pocsag()
        repeater_count = migrator.migrate_repeater_activity()

        # Verify
        migrator.verify_migration()

        # Summary
        print("\n" + "="*70)
        print("Migration Summary")
        print("="*70)
        print(f"  Voice Captures:        {captures_count}")
        print(f"  APRS Messages:         {aprs_count}")
        print(f"  POCSAG Messages:       {pocsag_count}")
        print(f"  Repeater Activity:     {repeater_count}")
        print(f"  Total Documents:       {captures_count + aprs_count + pocsag_count + repeater_count}")
        print("\n✓ Migration completed successfully!")

        migrator.close()

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
