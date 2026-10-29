#!/usr/bin/env python3
"""
Scan Session Manager for Radio Monitoring System
Provides Redis-based session management for repeater scanning operations

Similar to streaming_decoder_service.py SessionManager but for repeater scans.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from radiomoni.redis_client import get_redis

logger = logging.getLogger(__name__)


class RepeaterScanSession:
    """Represents a repeater scanning session"""

    def __init__(
        self,
        session_id: int,
        repeaters_total: int,
        duration_per_repeater: int,
        sample_rate: int,
        gain: int,
        total_duration: Optional[int] = None,
        until_stopped: bool = False
    ):
        self.session_id = session_id
        self.repeaters_total = repeaters_total
        self.duration_per_repeater = duration_per_repeater
        self.sample_rate = sample_rate
        self.gain = gain
        # End condition: one round (both unset), total_duration seconds, or until stopped
        self.total_duration = total_duration
        self.until_stopped = until_stopped

        # Status tracking
        self.status = 'in_progress'  # in_progress, completed, stopped, failed
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None

        # Progress tracking
        self.repeaters_scanned = 0
        self.repeaters_with_activity = 0
        self.current_index = 0
        self.current_repeater: Optional[str] = None
        self.elapsed_time = 0.0
        self.current_round = 1
        self.rounds_completed = 0

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
            'total_duration': self.total_duration,
            'until_stopped': self.until_stopped,
            'status': self.status,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'repeaters_scanned': self.repeaters_scanned,
            'repeaters_with_activity': self.repeaters_with_activity,
            'current_index': self.current_index,
            'current_repeater': self.current_repeater,
            'elapsed_time': self.elapsed_time,
            'current_round': self.current_round,
            'rounds_completed': self.rounds_completed,
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
            gain=data['gain'],
            total_duration=data.get('total_duration'),
            until_stopped=data.get('until_stopped', False)
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
        session.current_round = data.get('current_round', 1)
        session.rounds_completed = data.get('rounds_completed', 0)

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

    def stop(self) -> None:
        """Mark session as stopped by the user"""
        self.status = 'stopped'
        self.end_time = datetime.now(timezone.utc)

    def fail(self, error: str) -> None:
        """Mark session as failed"""
        self.status = 'failed'
        self.end_time = datetime.now(timezone.utc)
        self.error = error


class ScanSessionManager:
    """Manages repeater scan sessions in Redis"""

    def __init__(self, redis_client: Any = None) -> None:
        """Use the shared Redis connection (or an explicit client in tests)."""
        self.redis: Any = redis_client if redis_client is not None else get_redis()

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

    def request_stop(self, session_id: int) -> None:
        """Ask the scan worker to stop (separate key: the worker rewrites the session itself)."""
        self.redis.set(f"scan_stop:{session_id}", '1', ex=86400)

    def stop_requested(self, session_id: int) -> bool:
        return bool(self.redis.exists(f"scan_stop:{session_id}"))

    def get_next_session_id(self) -> int:
        """
        Get next available session ID using Redis atomic counter

        Returns:
            Next session ID
        """
        counter_value = self.redis.incr('scan_session_counter')
        return int(counter_value)


# ============================================================================
# Singleton Instance
# ============================================================================

_scan_session_manager: Optional[ScanSessionManager] = None


def get_scan_session_manager() -> ScanSessionManager:
    """Get or create the singleton ScanSessionManager"""
    global _scan_session_manager
    if _scan_session_manager is None:
        _scan_session_manager = ScanSessionManager()
    return _scan_session_manager
