#!/usr/bin/env python3
"""
Database Service for Radio Monitoring System
Handles all PostgreSQL database operations
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool


def read_secret(secret_name: str) -> Optional[str]:
    """
    Read a Docker secret from /run/secrets/ or return None

    Args:
        secret_name: Name of the secret file

    Returns:
        Secret value or None if not found
    """
    secret_path = Path(f'/run/secrets/{secret_name}')
    if secret_path.exists():
        return secret_path.read_text().strip()
    return None


def get_database_url() -> str:
    """
    Construct database URL from environment variables or Docker secrets

    Returns:
        PostgreSQL connection URL
    """
    # Try to read from Docker secrets first
    postgres_user = read_secret('postgres_user')
    postgres_password = read_secret('postgres_password')
    postgres_db = read_secret('postgres_db')
    postgres_host = os.getenv('POSTGRES_HOST', 'postgres')
    postgres_port = os.getenv('POSTGRES_PORT', '5432')

    # If secrets are available, construct URL from secrets
    if postgres_user and postgres_password and postgres_db:
        return f'postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}'

    # Fall back to DATABASE_URL environment variable
    return os.getenv(
        'DATABASE_URL',
        'postgresql://radio_user:radio_password_change_in_production@postgres:5432/radio_monitoring'
    )


class DatabaseService:
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database service

        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url or get_database_url()

        # Initialize connection pool
        try:
            self.pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=self.database_url
            )
            print("Database connection pool initialized")
        except Exception as e:
            print(f"WARNING: Could not connect to database: {e}")
            print("Running without database support")
            self.pool = None

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections

        Yields:
            Database connection
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized")

        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def save_capture(
        self,
        frequency: int,
        modulation: str,
        duration: int,
        gain: int,
        audio_file_path: str,
        transcription_text: Optional[str] = None,
        language: Optional[str] = None,
        language_confidence: Optional[float] = None,
        segments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        sample_rate: int = 2000000,
        file_size: Optional[int] = None,
        json_file_path: Optional[str] = None,
        transcription_duration: Optional[float] = None
    ) -> int:
        """
        Save a capture to the database

        Args:
            frequency: Frequency in Hz
            modulation: Modulation type (FM, AM, USB, LSB)
            duration: Recording duration in seconds
            gain: RF gain
            audio_file_path: Path to audio file
            transcription_text: Transcribed text
            language: Detected language
            language_confidence: Language detection confidence
            segments: Transcription segments with timestamps
            metadata: Additional metadata
            sample_rate: Sample rate in Hz
            file_size: File size in bytes
            json_file_path: Path to JSON file
            transcription_duration: Time taken for transcription

        Returns:
            int: ID of inserted record
        """
        if self.pool is None:
            print("WARNING: Database not available, skipping save")
            return -1

        query = """
            INSERT INTO captures (
                frequency, modulation, duration, gain, sample_rate,
                audio_file_path, json_file_path, file_size,
                transcription_text, language, language_confidence,
                transcription_duration, segments, metadata, status
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING id;
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (
                        frequency, modulation, duration, gain, sample_rate,
                        audio_file_path, json_file_path, file_size,
                        transcription_text, language, language_confidence,
                        transcription_duration,
                        Json(segments) if segments else None,
                        Json(metadata) if metadata else None,
                        'completed'
                    ))
                    result = cursor.fetchone()
                    capture_id = result[0]
                    print(f"Capture saved to database with ID: {capture_id}")
                    return capture_id
        except Exception as e:
            print(f"Error saving to database: {e}")
            return -1

    def search_captures(
        self,
        text_query: Optional[str] = None,
        frequency: Optional[int] = None,
        modulation: Optional[str] = None,
        language: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search captures with various filters

        Args:
            text_query: Full-text search query
            frequency: Filter by frequency
            modulation: Filter by modulation
            language: Filter by language
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of matching captures
        """
        if self.pool is None:
            return []

        conditions = []
        params = []

        if text_query:
            conditions.append("to_tsvector('english', transcription_text) @@ plainto_tsquery('english', %s)")
            params.append(text_query)

        if frequency is not None:
            conditions.append("frequency = %s")
            params.append(frequency)

        if modulation:
            conditions.append("modulation = %s")
            params.append(modulation)

        if language:
            conditions.append("language = %s")
            params.append(language)

        if start_date:
            conditions.append("created_at >= %s")
            params.append(start_date)

        if end_date:
            conditions.append("created_at <= %s")
            params.append(end_date)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT
                id, uuid, created_at, frequency, modulation, duration, gain,
                audio_file_path, transcription_text, language, language_confidence,
                segments, status
            FROM captures
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error searching captures: {e}")
            return []

    def get_capture_by_id(self, capture_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single capture by ID

        Args:
            capture_id: Capture ID

        Returns:
            Capture data or None
        """
        if self.pool is None:
            return None

        query = """
            SELECT
                id, uuid, created_at, updated_at,
                frequency, modulation, duration, gain, sample_rate,
                audio_file_path, json_file_path, file_size,
                transcription_text, language, language_confidence,
                transcription_duration, segments, metadata, status
            FROM captures
            WHERE id = %s
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (capture_id,))
                    result = cursor.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            print(f"Error getting capture: {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics

        Returns:
            Statistics dictionary
        """
        if self.pool is None:
            return {}

        query = """
            SELECT
                COUNT(*) as total_captures,
                COUNT(CASE WHEN transcription_text IS NOT NULL AND transcription_text != '' THEN 1 END) as successful_transcriptions,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_captures,
                COUNT(DISTINCT frequency) as unique_frequencies,
                COUNT(DISTINCT language) as unique_languages,
                MIN(created_at) as first_capture,
                MAX(created_at) as last_capture
            FROM captures
            WHERE frequency > 0  -- Exclude placeholder
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query)
                    result = cursor.fetchone()
                    return dict(result) if result else {}
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {}

    def get_frequency_usage(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most used frequencies

        Args:
            limit: Number of results

        Returns:
            List of frequencies with usage count
        """
        if self.pool is None:
            return []

        query = """
            SELECT
                frequency,
                COUNT(*) as capture_count,
                MAX(created_at) as last_used,
                ARRAY_AGG(DISTINCT modulation) as modulations
            FROM captures
            WHERE frequency > 0  -- Exclude placeholder
            GROUP BY frequency
            ORDER BY capture_count DESC
            LIMIT %s
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (limit,))
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting frequency usage: {e}")
            return []

    def save_aprs_capture(
        self,
        capture_id: int,
        packets: List[Dict[str, Any]]
    ) -> List[int]:
        """
        Save multiple APRS packets linked to a capture

        Args:
            capture_id: Parent capture ID
            packets: List of decoded APRS packets

        Returns:
            List of inserted packet IDs
        """
        if self.pool is None or not packets:
            return []

        query = """
            INSERT INTO aprs_messages (
                capture_id, source_callsign, destination_callsign, path,
                latitude, longitude, altitude_meters, speed_kmh, course_degrees,
                message_text, symbol_table, symbol_code, raw_packet, aprs_type,
                aprs_data, decode_confidence
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id;
        """

        packet_ids = []
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for packet in packets:
                        cursor.execute(query, (
                            capture_id,
                            packet.get('source_callsign'),
                            packet.get('destination_callsign'),
                            packet.get('path'),
                            packet.get('latitude'),
                            packet.get('longitude'),
                            packet.get('altitude'),
                            packet.get('speed'),
                            packet.get('course'),
                            packet.get('message_text'),
                            packet.get('symbol_table'),
                            packet.get('symbol_code'),
                            packet.get('raw_packet'),
                            packet.get('aprs_type'),
                            Json(packet.get('aprs_data', {})),
                            packet.get('decode_confidence')
                        ))
                        result = cursor.fetchone()
                        packet_ids.append(result[0])

            print(f"Saved {len(packet_ids)} APRS packets to database")
            return packet_ids
        except Exception as e:
            print(f"Error saving APRS packets: {e}")
            return []

    def search_aprs_messages(
        self,
        callsign: Optional[str] = None,
        message_text: Optional[str] = None,
        aprs_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search APRS messages with various filters

        Args:
            callsign: Filter by source callsign
            message_text: Full-text search in message text
            aprs_type: Filter by APRS type
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of matching APRS messages
        """
        if self.pool is None:
            return []

        conditions = []
        params = []

        if callsign:
            conditions.append("source_callsign ILIKE %s")
            params.append(f"%{callsign}%")

        if message_text:
            conditions.append("to_tsvector('english', message_text) @@ plainto_tsquery('english', %s)")
            params.append(message_text)

        if aprs_type:
            conditions.append("aprs_type = %s")
            params.append(aprs_type)

        if start_date:
            conditions.append("created_at >= %s")
            params.append(start_date)

        if end_date:
            conditions.append("created_at <= %s")
            params.append(end_date)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT
                am.id, am.uuid, am.created_at, am.capture_id,
                am.source_callsign, am.destination_callsign, am.path,
                am.latitude, am.longitude, am.altitude_meters,
                am.speed_kmh, am.course_degrees,
                am.message_text, am.symbol_table, am.symbol_code,
                am.raw_packet, am.aprs_type, am.aprs_data,
                c.frequency, c.modulation
            FROM aprs_messages am
            JOIN captures c ON am.capture_id = c.id
            {where_clause}
            ORDER BY am.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error searching APRS messages: {e}")
            return []

    def get_aprs_statistics(self) -> Dict[str, Any]:
        """
        Get APRS statistics

        Returns:
            APRS statistics dictionary
        """
        if self.pool is None:
            return {}

        query = """
            SELECT
                COUNT(*) as total_packets,
                COUNT(DISTINCT source_callsign) as unique_callsigns,
                COUNT(DISTINCT capture_id) as total_captures,
                COUNT(CASE WHEN latitude IS NOT NULL THEN 1 END) as packets_with_position,
                MIN(created_at) as first_packet,
                MAX(created_at) as last_packet
            FROM aprs_messages
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query)
                    result = cursor.fetchone()
                    return dict(result) if result else {}
        except Exception as e:
            print(f"Error getting APRS statistics: {e}")
            return {}

    def get_aprs_by_capture_id(self, capture_id: int) -> List[Dict[str, Any]]:
        """
        Get all APRS messages for a specific capture

        Args:
            capture_id: Capture ID

        Returns:
            List of APRS messages
        """
        if self.pool is None:
            return []

        query = """
            SELECT
                id, uuid, created_at, source_callsign, destination_callsign,
                path, latitude, longitude, altitude_meters, speed_kmh, course_degrees,
                message_text, symbol_table, symbol_code, raw_packet, aprs_type,
                aprs_data
            FROM aprs_messages
            WHERE capture_id = %s
            ORDER BY created_at ASC
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (capture_id,))
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting APRS messages for capture: {e}")
            return []

    def save_pocsag_capture(
        self,
        capture_id: int,
        messages: List[Dict[str, Any]]
    ) -> List[int]:
        """
        Save multiple POCSAG messages linked to a capture

        Args:
            capture_id: Parent capture ID
            messages: List of decoded POCSAG messages

        Returns:
            List of inserted message IDs
        """
        if self.pool is None or not messages:
            return []

        query = """
            INSERT INTO pocsag_messages (
                capture_id, address, function_code, message_type,
                message_text, baud_rate, raw_packet, pocsag_data,
                decode_confidence
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id;
        """

        message_ids = []
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for msg in messages:
                        cursor.execute(query, (
                            capture_id,
                            msg.get('address'),
                            msg.get('function_code'),
                            msg.get('message_type'),
                            msg.get('message_text'),
                            msg.get('baud_rate'),
                            msg.get('raw_line'),  # Note: renamed to raw_packet in DB
                            Json(msg.get('pocsag_data', {})),
                            msg.get('decode_confidence')
                        ))
                        result = cursor.fetchone()
                        message_ids.append(result[0])

            print(f"Saved {len(message_ids)} POCSAG messages to database")
            return message_ids
        except Exception as e:
            print(f"Error saving POCSAG messages: {e}")
            return []

    def search_pocsag_messages(
        self,
        address: Optional[int] = None,
        message_text: Optional[str] = None,
        message_type: Optional[str] = None,
        baud_rate: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search POCSAG messages with various filters

        Args:
            address: Filter by pager address
            message_text: Full-text search in message text
            message_type: Filter by message type (alphanumeric, numeric, tone)
            baud_rate: Filter by baud rate (512, 1200, 2400)
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of matching POCSAG messages
        """
        if self.pool is None:
            return []

        conditions = []
        params = []

        if address is not None:
            conditions.append("address = %s")
            params.append(address)

        if message_text:
            conditions.append("to_tsvector('english', message_text) @@ plainto_tsquery('english', %s)")
            params.append(message_text)

        if message_type:
            conditions.append("message_type = %s")
            params.append(message_type)

        if baud_rate is not None:
            conditions.append("baud_rate = %s")
            params.append(baud_rate)

        if start_date:
            conditions.append("created_at >= %s")
            params.append(start_date)

        if end_date:
            conditions.append("created_at <= %s")
            params.append(end_date)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT
                pm.id, pm.uuid, pm.created_at, pm.capture_id,
                pm.address, pm.function_code, pm.message_type,
                pm.message_text, pm.baud_rate, pm.raw_packet,
                pm.pocsag_data,
                c.frequency, c.modulation
            FROM pocsag_messages pm
            JOIN captures c ON pm.capture_id = c.id
            {where_clause}
            ORDER BY pm.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error searching POCSAG messages: {e}")
            return []

    def get_pocsag_statistics(self) -> Dict[str, Any]:
        """
        Get POCSAG statistics

        Returns:
            POCSAG statistics dictionary
        """
        if self.pool is None:
            return {}

        query = """
            SELECT
                COUNT(*) as total_messages,
                COUNT(DISTINCT address) as unique_addresses,
                COUNT(DISTINCT capture_id) as total_captures,
                COUNT(CASE WHEN message_type = 'alphanumeric' THEN 1 END) as alphanumeric_messages,
                COUNT(CASE WHEN message_type = 'numeric' THEN 1 END) as numeric_messages,
                COUNT(CASE WHEN message_type = 'tone' THEN 1 END) as tone_messages,
                MIN(created_at) as first_message,
                MAX(created_at) as last_message
            FROM pocsag_messages
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query)
                    result = cursor.fetchone()
                    return dict(result) if result else {}
        except Exception as e:
            print(f"Error getting POCSAG statistics: {e}")
            return {}

    def get_pocsag_by_capture_id(self, capture_id: int) -> List[Dict[str, Any]]:
        """
        Get all POCSAG messages for a specific capture

        Args:
            capture_id: Capture ID

        Returns:
            List of POCSAG messages
        """
        if self.pool is None:
            return []

        query = """
            SELECT
                id, uuid, created_at, address, function_code,
                message_type, message_text, baud_rate, raw_packet,
                pocsag_data
            FROM pocsag_messages
            WHERE capture_id = %s
            ORDER BY created_at ASC
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (capture_id,))
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting POCSAG messages for capture: {e}")
            return []

    def delete_old_captures(self, days_old: int = 30) -> int:
        """
        Delete captures older than specified days

        Args:
            days_old: Number of days

        Returns:
            Number of deleted records
        """
        if self.pool is None:
            return 0

        query = """
            DELETE FROM captures
            WHERE created_at < NOW() - INTERVAL '%s days'
            AND frequency > 0  -- Don't delete placeholder
            RETURNING id
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (days_old,))
                    deleted = cursor.rowcount
                    print(f"Deleted {deleted} old captures")
                    return deleted
        except Exception as e:
            print(f"Error deleting old captures: {e}")
            return 0

    # =========================================================================
    # Repeater Activity Methods
    # =========================================================================

    def get_repeaters(
        self,
        band: Optional[str] = None,
        canton: Optional[str] = None,
        status: str = 'active',
        mode: str = 'FM',
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get repeaters with optional filters.

        Args:
            band: Filter by band (2m, 70cm, 23cm)
            canton: Filter by Swiss canton (ZH, BE, GR, etc.)
            status: Filter by status (active, inactive, testing)
            mode: Filter by mode (FM, DMR, D-STAR, etc.)
            limit: Maximum results

        Returns:
            List of repeater dictionaries
        """
        if self.pool is None:
            return []

        conditions = []
        params = []

        if mode:
            conditions.append("mode = %s")
            params.append(mode)

        if status:
            conditions.append("status = %s")
            params.append(status)

        if band:
            conditions.append("band = %s")
            params.append(band)

        if canton:
            conditions.append("canton = %s")
            params.append(canton.upper())

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT
                id, uuid, created_at, updated_at,
                callsign, name, output_frequency, input_frequency,
                offset_mhz, ctcss_tone, modulation, mode, band,
                latitude, longitude, elevation_meters,
                canton, location_name, status, metadata
            FROM repeaters
            {where_clause}
            ORDER BY band, output_frequency
            LIMIT %s
        """
        params.append(limit)

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting repeaters: {e}")
            return []

    def get_repeater_by_id(self, repeater_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single repeater by ID.

        Args:
            repeater_id: Repeater ID

        Returns:
            Repeater data or None
        """
        if self.pool is None:
            return None

        query = """
            SELECT
                id, uuid, created_at, updated_at,
                callsign, name, output_frequency, input_frequency,
                offset_mhz, ctcss_tone, modulation, mode, band,
                latitude, longitude, elevation_meters,
                canton, location_name, status, metadata
            FROM repeaters
            WHERE id = %s
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (repeater_id,))
                    result = cursor.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            print(f"Error getting repeater: {e}")
            return None

    def save_repeater_activity(
        self,
        capture_id: int,
        repeater_id: int,
        frequency: int,
        scan_start_time: datetime,
        scan_end_time: datetime,
        metrics: Dict[str, Any]
    ) -> Optional[int]:
        """
        Save repeater activity analysis results.

        Args:
            capture_id: Parent capture ID
            repeater_id: Repeater ID
            frequency: Frequency in Hz
            scan_start_time: Scan start timestamp
            scan_end_time: Scan end timestamp
            metrics: ActivityMetrics dictionary from analyzer

        Returns:
            Activity record ID or None
        """
        if self.pool is None:
            return None

        scan_duration = int((scan_end_time - scan_start_time).total_seconds())

        query = """
            INSERT INTO repeater_activity (
                capture_id, repeater_id, frequency,
                scan_start_time, scan_end_time, scan_duration_seconds,
                carrier_detected, transmission_count,
                total_active_seconds, activity_percentage,
                average_signal_strength, peak_signal_strength, noise_floor,
                transmissions, analysis_data
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id;
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (
                        capture_id,
                        repeater_id,
                        frequency,
                        scan_start_time,
                        scan_end_time,
                        scan_duration,
                        metrics.get('carrier_detected', False),
                        metrics.get('transmission_count', 0),
                        metrics.get('total_active_seconds', 0),
                        metrics.get('activity_percentage', 0),
                        metrics.get('average_signal_strength'),
                        metrics.get('peak_signal_strength'),
                        metrics.get('noise_floor'),
                        Json(metrics.get('transmissions', [])),
                        Json(metrics)
                    ))
                    result = cursor.fetchone()
                    activity_id = result[0]
                    print(f"Saved repeater activity with ID: {activity_id}")
                    return activity_id
        except Exception as e:
            print(f"Error saving repeater activity: {e}")
            return None

    def create_scan_session(
        self,
        scan_duration_per_repeater: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Create a new repeater scan session.

        Args:
            scan_duration_per_repeater: Duration per repeater in seconds
            metadata: Optional metadata dictionary

        Returns:
            Session ID or None
        """
        if self.pool is None:
            return None

        query = """
            INSERT INTO repeater_scan_sessions (
                scan_duration_per_repeater,
                scan_start_time,
                status,
                metadata
            ) VALUES (
                %s, %s, %s, %s
            )
            RETURNING id;
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (
                        scan_duration_per_repeater,
                        datetime.now(),
                        'in_progress',
                        Json(metadata) if metadata else None
                    ))
                    result = cursor.fetchone()
                    session_id = result[0]
                    print(f"Created scan session with ID: {session_id}")
                    return session_id
        except Exception as e:
            print(f"Error creating scan session: {e}")
            return None

    def update_scan_session(
        self,
        session_id: int,
        status: Optional[str] = None,
        repeaters_scanned: Optional[int] = None,
        repeaters_with_activity: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update a scan session.

        Args:
            session_id: Session ID
            status: New status (in_progress, completed, failed, cancelled)
            repeaters_scanned: Number of repeaters scanned
            repeaters_with_activity: Number with detected activity
            metadata: Updated metadata

        Returns:
            True if successful
        """
        if self.pool is None:
            return False

        updates = []
        params = []

        if status:
            updates.append("status = %s")
            params.append(status)

            if status in ['completed', 'failed', 'cancelled']:
                updates.append("scan_end_time = %s")
                params.append(datetime.now())

        if repeaters_scanned is not None:
            updates.append("repeaters_scanned = %s")
            params.append(repeaters_scanned)

        if repeaters_with_activity is not None:
            updates.append("repeaters_with_activity = %s")
            params.append(repeaters_with_activity)

        if metadata is not None:
            updates.append("metadata = %s")
            params.append(Json(metadata))

        if not updates:
            return False

        query = f"""
            UPDATE repeater_scan_sessions
            SET {', '.join(updates)}
            WHERE id = %s
        """
        params.append(session_id)

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    success = cursor.rowcount > 0
                    if success:
                        print(f"Updated scan session {session_id}")
                    return success
        except Exception as e:
            print(f"Error updating scan session: {e}")
            return False

    def get_scan_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Get scan session details.

        Args:
            session_id: Session ID

        Returns:
            Session data or None
        """
        if self.pool is None:
            return None

        query = """
            SELECT
                id, uuid, created_at,
                scan_duration_per_repeater,
                repeaters_scanned, repeaters_with_activity,
                scan_start_time, scan_end_time,
                total_duration_seconds, status, metadata
            FROM repeater_scan_sessions
            WHERE id = %s
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (session_id,))
                    result = cursor.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            print(f"Error getting scan session: {e}")
            return None

    def get_repeater_activity_summary(
        self,
        hours: int = 24,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get summary of most active repeaters.

        Args:
            hours: Time window in hours
            limit: Maximum results

        Returns:
            List of repeater activity summaries
        """
        if self.pool is None:
            return []

        query = """
            SELECT
                r.id,
                r.callsign,
                r.output_frequency / 1000000.0 as frequency_mhz,
                r.band,
                r.location_name,
                r.canton,
                COUNT(ra.id) as scan_count,
                AVG(ra.activity_percentage) as avg_activity_percentage,
                SUM(ra.transmission_count) as total_transmissions,
                MAX(ra.created_at) as last_scan
            FROM repeaters r
            JOIN repeater_activity ra ON r.id = ra.repeater_id
            WHERE ra.created_at > NOW() - INTERVAL '%s hours'
            GROUP BY r.id
            ORDER BY avg_activity_percentage DESC
            LIMIT %s
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (hours, limit))
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting activity summary: {e}")
            return []

    def get_repeater_activity_by_capture(
        self,
        capture_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all repeater activity for a specific capture.

        Args:
            capture_id: Capture ID

        Returns:
            List of activity records
        """
        if self.pool is None:
            return []

        query = """
            SELECT
                ra.id, ra.uuid, ra.created_at,
                ra.repeater_id, ra.frequency,
                ra.scan_start_time, ra.scan_end_time, ra.scan_duration_seconds,
                ra.carrier_detected, ra.transmission_count,
                ra.total_active_seconds, ra.activity_percentage,
                ra.average_signal_strength, ra.peak_signal_strength, ra.noise_floor,
                ra.transmissions, ra.analysis_data,
                r.callsign, r.location_name, r.band
            FROM repeater_activity ra
            JOIN repeaters r ON ra.repeater_id = r.id
            WHERE ra.capture_id = %s
            ORDER BY ra.created_at ASC
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (capture_id,))
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting repeater activity for capture: {e}")
            return []

    def close(self):
        """Close all database connections"""
        if self.pool:
            self.pool.closeall()
            print("Database connections closed")


# Global database service instance
_db_service: Optional[DatabaseService] = None


def get_database_service() -> DatabaseService:
    """Get or create global database service instance"""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
