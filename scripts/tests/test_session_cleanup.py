#!/usr/bin/env python3
"""
Test script for scan_sessions cleanup functionality
"""
import time
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Mock Flask and dependencies to avoid import errors
class MockFlask:
    def __init__(self, *args, **kwargs):
        pass

    def route(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator

sys.modules['flask'] = type('module', (), {
    'Flask': MockFlask,
    'request': object(),
    'jsonify': lambda x: x,
    'Response': object(),
})()
sys.modules['flask_cors'] = type('module', (), {'CORS': lambda *args, **kwargs: None})()
sys.modules['sdr_hardware'] = type('module', (), {
    'get_sdr_instance': lambda **kwargs: None,
    'detect_sdr': lambda: None,
    'SDRType': object(),
})()
sys.modules['transcription_service'] = type('module', (), {'TranscriptionService': object()})()
sys.modules['aprs_decoder_service'] = type('module', (), {'APRSDecoder': object()})()
sys.modules['pocsag_decoder_service'] = type('module', (), {'POCSAGDecoder': object()})()
sys.modules['elasticsearch_service'] = type('module', (), {'get_elasticsearch_service': lambda: None})()
sys.modules['repeater_activity_analyzer'] = type('module', (), {'RepeaterActivityAnalyzer': object()})()
sys.modules['dotenv'] = type('module', (), {'load_dotenv': lambda *args, **kwargs: None})()

# Now import the functions we want to test
from api_service import cleanup_old_sessions, scan_sessions, scan_sessions_lock, MAX_SESSIONS, SESSION_MAX_AGE_HOURS


def test_session_cleanup():
    """Test the session cleanup functionality"""
    print("========================================")
    print("Session Cleanup Tests")
    print("========================================")
    print()

    # Test 1: Empty cleanup (no sessions)
    print("Test 1: Cleanup with no sessions")
    removed = cleanup_old_sessions()
    print(f"  Removed: {removed} (expected: 0)")
    assert removed == 0, "Should not remove anything when no sessions exist"
    print("  ✅ PASS")
    print()

    # Test 2: Add some fresh sessions (should not be removed)
    print("Test 2: Fresh sessions not removed")
    with scan_sessions_lock:
        for i in range(5):
            scan_sessions[i] = {
                'status': 'completed',
                'start_time': time.time(),
            }

    removed = cleanup_old_sessions()
    print(f"  Sessions before: 5")
    print(f"  Removed: {removed} (expected: 0)")
    with scan_sessions_lock:
        remaining = len(scan_sessions)
    print(f"  Sessions after: {remaining} (expected: 5)")
    assert removed == 0, "Should not remove fresh sessions"
    assert remaining == 5, "All sessions should remain"
    print("  ✅ PASS")
    print()

    # Test 3: Add old sessions (should be removed)
    print("Test 3: Old sessions removed")
    old_time = time.time() - (SESSION_MAX_AGE_HOURS * 3600 + 1)
    with scan_sessions_lock:
        for i in range(5, 8):
            scan_sessions[i] = {
                'status': 'completed',
                'start_time': old_time,
            }

    removed = cleanup_old_sessions()
    print(f"  Sessions before: 8")
    print(f"  Removed: {removed} (expected: 3)")
    with scan_sessions_lock:
        remaining = len(scan_sessions)
    print(f"  Sessions after: {remaining} (expected: 5)")
    assert removed == 3, "Should remove 3 old sessions"
    assert remaining == 5, "Should have 5 fresh sessions remaining"
    print("  ✅ PASS")
    print()

    # Test 4: Exceed MAX_SESSIONS (should remove oldest completed)
    print(f"Test 4: Enforce MAX_SESSIONS limit ({MAX_SESSIONS})")

    # Clear existing sessions
    with scan_sessions_lock:
        scan_sessions.clear()

    # Add MAX_SESSIONS + 20 fresh completed sessions
    excess_sessions = 20
    current_time = time.time()
    with scan_sessions_lock:
        for i in range(MAX_SESSIONS + excess_sessions):
            scan_sessions[i] = {
                'status': 'completed',
                'start_time': current_time - (1000 - i),  # Older sessions have lower IDs
            }

    print(f"  Sessions before: {MAX_SESSIONS + excess_sessions}")
    removed = cleanup_old_sessions()
    print(f"  Removed: {removed} (expected: {excess_sessions})")
    with scan_sessions_lock:
        remaining = len(scan_sessions)
    print(f"  Sessions after: {remaining} (expected: {MAX_SESSIONS})")
    assert removed == excess_sessions, f"Should remove {excess_sessions} excess sessions"
    assert remaining == MAX_SESSIONS, f"Should have {MAX_SESSIONS} sessions remaining"
    print("  ✅ PASS")
    print()

    # Test 5: In-progress sessions protected from excess removal
    print("Test 5: In-progress sessions protected")

    # Clear and add mix of in-progress and completed
    with scan_sessions_lock:
        scan_sessions.clear()
        current_time = time.time()

        # Add 10 in-progress sessions
        for i in range(10):
            scan_sessions[i] = {
                'status': 'in_progress',
                'start_time': current_time - 100,
            }

        # Add MAX_SESSIONS completed sessions (will exceed limit)
        for i in range(10, 10 + MAX_SESSIONS):
            scan_sessions[i] = {
                'status': 'completed',
                'start_time': current_time - (1000 - i),
            }

    total_before = 10 + MAX_SESSIONS
    print(f"  Sessions before: {total_before} (10 in-progress + {MAX_SESSIONS} completed)")
    removed = cleanup_old_sessions()
    print(f"  Removed: {removed}")

    with scan_sessions_lock:
        remaining = len(scan_sessions)
        in_progress = sum(1 for s in scan_sessions.values() if s.get('status') == 'in_progress')

    print(f"  Sessions after: {remaining}")
    print(f"  In-progress sessions: {in_progress} (expected: 10)")
    assert in_progress == 10, "All in-progress sessions should remain"
    assert remaining <= MAX_SESSIONS, f"Total should be <= {MAX_SESSIONS}"
    print("  ✅ PASS")
    print()

    # Clean up for next run
    with scan_sessions_lock:
        scan_sessions.clear()

    print("========================================")
    print("All Tests Passed! ✅")
    print("========================================")
    print()
    print("Summary:")
    print("- Old sessions (>24h) are automatically removed")
    print(f"- Session count limited to {MAX_SESSIONS}")
    print("- In-progress sessions are protected from excess removal")
    print("- Background thread runs cleanup every hour")


if __name__ == '__main__':
    test_session_cleanup()
