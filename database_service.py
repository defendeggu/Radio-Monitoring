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

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool


class DatabaseService:
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database service

        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url or os.getenv(
            'DATABASE_URL',
            'postgresql://radio_user:radio_password_change_in_production@postgres:5432/radio_monitoring'
        )

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
