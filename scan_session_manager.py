#!/usr/bin/env python3
"""
Scan Session Manager for Radio Monitoring System
Provides Redis-based session management for repeater scanning operations

Similar to streaming_decoder_service.py SessionManager but for repeater scans.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RepeaterScanSession:
    """Represents a repeater scanning session"""

    def __init__(
        self,
        session_id: int,
        repeaters_total: int,
        duration_per_repeater: int,
        sample_rate: int,
        gain: int
    ):
        self.session_id = session_id
        self.repeaters_total = repeaters_total
        self.duration_per_repeater = duration_per_repeater
        self.sample_rate = sample_rate
        self.gain = gain

        # Status tracking
        self.status = 'in_progress'  # in_progress, completed, failed
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None

        # Progress tracking
        self.repeaters_scanned = 0
        self.repeaters_with_activity = 0
        self.current_index = 0
        self.current_repeater: Optional[str] = None
        self.elapsed_time = 0.0

        # Results
        self.results: List[Dict[str, Any]] = []
        self.error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dict for Redis storage"""
        return {
            'session_id': self.session_id,
            'repeaters_total': self.repeaters_total,
            'duration_per_repeater': self.duration_per_repeater,
            'sample_rate': self.sample_rate,
            'gain': self.gain,
            'status': self.status,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'repeaters_scanned': self.repeaters_scanned,
            'repeaters_with_activity': self.repeaters_with_activity,
            'current_index': self.current_index,
            'current_repeater': self.current_repeater,
            'elapsed_time': self.elapsed_time,
            'results': self.results,
            'error': self.error
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RepeaterScanSession':
        """Deserialize session from dict"""
        session = cls(
            session_id=data['session_id'],
            repeaters_total=data['repeaters_total'],
            duration_per_repeater=data['duration_per_repeater'],
            sample_rate=data['sample_rate'],
            gain=data['gain']
        )

        # Restore status
        session.status = data['status']
        session.start_time = datetime.fromisoformat(data['start_time'])
        session.end_time = datetime.fromisoformat(data['end_time']) if data.get('end_time') else None

        # Restore progress
        session.repeaters_scanned = data['repeaters_scanned']
        session.repeaters_with_activity = data['repeaters_with_activity']
        session.current_index = data['current_index']
        session.current_repeater = data.get('current_repeater')
        session.elapsed_time = data['elapsed_time']

        # Restore results
        session.results = data.get('results', [])
        session.error = data.get('error')

        return session

    def update_progress(
        self,
        current_index: int,
        current_repeater: str,
        elapsed_time: float
    ) -> None:
        """Update scan progress"""
        self.current_index = current_index
        self.current_repeater = current_repeater
        self.elapsed_time = elapsed_time

    def add_result(self, result: Dict[str, Any]) -> None:
        """Add a scan result"""
        self.results.append(result)
        self.repeaters_scanned += 1
        if result.get('activity_detected'):
            self.repeaters_with_activity += 1

    def complete(self, results: List[Dict[str, Any]]) -> None:
        """Mark session as completed"""
        self.status = 'completed'
        self.end_time = datetime.now(timezone.utc)
        self.results = results
        self.repeaters_scanned = len(results)
        self.repeaters_with_activity = sum(
            1 for r in results if r.get('activity_detected')
        )

    def fail(self, error: str) -> None:
        """Mark session as failed"""
        self.status = 'failed'
        self.end_time = datetime.now(timezone.utc)
        self.error = error


class ScanSessionManager:
    """Manages repeater scan sessions in Redis"""

    def __init__(
        self,
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None
    ) -> None:
        """
        Initialize Redis connection for scan session management

        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            redis_db: Redis database number
            redis_password: Redis password (optional)
        """
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password if redis_password else None,
            decode_responses=True
        )

        # Test connection (skip in test mode)
        test_mode = os.getenv('PYTEST_CURRENT_TEST') is not None
        try:
            if not test_mode:
                self.redis.ping()
                logger.info(f"Connected to Redis at {redis_host}:{redis_port} (db={redis_db})")
            else:
                logger.info("Running in test mode - skipping Redis connection check")
        except redis.ConnectionError as e:
            if not test_mode:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
            else:
                logger.warning(f"Redis not available in test mode: {e}")

    def save_session(self, session: RepeaterScanSession) -> None:
        """
        Save session to Redis

        Args:
            session: RepeaterScanSession instance
        """
        key = f"scan_session:{session.session_id}"
        data = json.dumps(session.to_dict())
        self.redis.set(key, data)

        # Set TTL: 24 hours (86400 seconds)
        self.redis.expire(key, 86400)

        logger.debug(f"Saved scan session {session.session_id} to Redis")

    def get_session(self, session_id: int) -> Optional[RepeaterScanSession]:
        """
        Retrieve session from Redis

        Args:
            session_id: Session ID

        Returns:
            RepeaterScanSession instance or None if not found
        """
        key = f"scan_session:{session_id}"
        data_str = self.redis.get(key)

        if not data_str:
            logger.debug(f"Scan session {session_id} not found in Redis")
            return None

        data = json.loads(str(data_str))
        session = RepeaterScanSession.from_dict(data)

        logger.debug(f"Retrieved scan session {session_id} from Redis")
        return session

    def delete_session(self, session_id: int) -> None:
        """
        Delete session from Redis

        Args:
            session_id: Session ID
        """
        key = f"scan_session:{session_id}"
        self.redis.delete(key)
        logger.info(f"Deleted scan session {session_id} from Redis")

    def list_sessions(self) -> List[RepeaterScanSession]:
        """
        List all scan sessions

        Returns:
            List of RepeaterScanSession instances
        """
        sessions = []

        for key in self.redis.scan_iter("scan_session:*"):
            data_str = self.redis.get(key)
            if data_str:
                try:
                    data = json.loads(str(data_str))
                    sessions.append(RepeaterScanSession.from_dict(data))
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse session data for {key}: {e}")
                    continue

        return sessions

    def get_active_sessions(self) -> List[RepeaterScanSession]:
        """
        Get all active (in_progress) scan sessions

        Returns:
            List of active RepeaterScanSession instances
        """
        return [
            session for session in self.list_sessions()
            if session.status == 'in_progress'
        ]

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Cleanup old completed/failed sessions

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of sessions cleaned up
        """
        from datetime import timedelta

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        cleaned = 0

        for session in self.list_sessions():
            # Skip active sessions
            if session.status == 'in_progress':
                continue

            # Delete if older than cutoff
            if session.end_time and session.end_time < cutoff_time:
                self.delete_session(session.session_id)
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old scan sessions")

        return cleaned

    def get_next_session_id(self) -> int:
        """
        Get next available session ID using Redis atomic counter

        Returns:
            Next session ID
        """
        counter_value = self.redis.incr('scan_session_counter')
        return int(counter_value)  # type: ignore[arg-type]


# ============================================================================
# Singleton Instance
# ============================================================================

_scan_session_manager: Optional[ScanSessionManager] = None


def get_scan_session_manager() -> ScanSessionManager:
    """
    Get or create singleton ScanSessionManager instance

    Reads configuration from environment variables:
    - REDIS_HOST (default: localhost)
    - REDIS_PORT (default: 6379)
    - REDIS_DB (default: 0)
    - REDIS_PASSWORD (optional)

    Returns:
        ScanSessionManager instance
    """
    global _scan_session_manager

    if _scan_session_manager is None:
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_db = int(os.getenv('REDIS_DB', 0))
        redis_password = os.getenv('REDIS_PASSWORD')

        _scan_session_manager = ScanSessionManager(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            redis_password=redis_password if redis_password else None
        )

    return _scan_session_manager


# ============================================================================
# CLI Testing
# ============================================================================

if __name__ == '__main__':
    """Test scan session manager"""
    print("Testing ScanSessionManager...")
    print()

    # Create manager
    manager = get_scan_session_manager()
    print(f"✅ Connected to Redis")
    print()

    # Create test session
    session_id = manager.get_next_session_id()
    session = RepeaterScanSession(
        session_id=session_id,
        repeaters_total=10,
        duration_per_repeater=120,
        sample_rate=2000000,
        gain=20
    )

    print(f"Created session {session_id}")
    print()

    # Save session
    manager.save_session(session)
    print(f"✅ Saved session to Redis")
    print()

    # Retrieve session
    retrieved = manager.get_session(session_id)
    assert retrieved is not None
    assert retrieved.session_id == session_id
    print(f"✅ Retrieved session from Redis")
    print(f"   Status: {retrieved.status}")
    print(f"   Repeaters: {retrieved.repeaters_total}")
    print()

    # Update progress
    session.update_progress(
        current_index=3,
        current_repeater='HB9TEST',
        elapsed_time=360.0
    )
    manager.save_session(session)
    print(f"✅ Updated session progress")
    print()

    # Complete session
    session.complete([
        {'callsign': 'HB9A', 'activity_detected': True},
        {'callsign': 'HB9B', 'activity_detected': False},
    ])
    manager.save_session(session)
    print(f"✅ Completed session")
    print(f"   Scanned: {session.repeaters_scanned}")
    print(f"   With activity: {session.repeaters_with_activity}")
    print()

    # List sessions
    all_sessions = manager.list_sessions()
    print(f"✅ Total sessions: {len(all_sessions)}")
    print()

    # Cleanup
    manager.delete_session(session_id)
    print(f"✅ Cleaned up test session")
    print()

    print("All tests passed! ✅")
