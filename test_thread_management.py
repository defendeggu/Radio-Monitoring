#!/usr/bin/env python3
"""
Test script for thread management improvements
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Mock Flask and dependencies
class MockFlask:
    def __init__(self, *args, **kwargs):
        pass

    def route(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator

class MockRequest:
    pass

class MockResponse:
    pass

sys.modules['flask'] = type('module', (), {
    'Flask': MockFlask,
    'request': MockRequest(),
    'jsonify': lambda x: x,
    'Response': MockResponse,
})()
sys.modules['flask_cors'] = type('module', (), {'CORS': lambda *args, **kwargs: None})()

class MockSDRType:
    pass

class MockTranscriptionService:
    pass

class MockAPRSDecoder:
    pass

class MockPOCSAGDecoder:
    pass

class MockRepeaterActivityAnalyzer:
    pass

sys.modules['sdr_hardware'] = type('module', (), {
    'get_sdr_instance': lambda **kwargs: None,
    'detect_sdr': lambda: None,
    'SDRType': MockSDRType,
})()
sys.modules['transcription_service'] = type('module', (), {'TranscriptionService': MockTranscriptionService})()
sys.modules['aprs_decoder_service'] = type('module', (), {'APRSDecoder': MockAPRSDecoder})()
sys.modules['pocsag_decoder_service'] = type('module', (), {'POCSAGDecoder': MockPOCSAGDecoder})()
sys.modules['elasticsearch_service'] = type('module', (), {'get_elasticsearch_service': lambda: None})()
sys.modules['repeater_activity_analyzer'] = type('module', (), {'RepeaterActivityAnalyzer': MockRepeaterActivityAnalyzer})()
sys.modules['dotenv'] = type('module', (), {'load_dotenv': lambda *args, **kwargs: None})()

# Now import the components we want to test
from api_service import (
    scan_thread_pool,
    has_active_scan,
    scan_sessions,
    scan_sessions_lock,
    _session_id_counter
)


def test_thread_pool():
    """Test that thread pool is configured correctly"""
    print("========================================")
    print("Thread Management Tests")
    print("========================================")
    print()

    # Test 1: Thread pool exists and is configured correctly
    print("Test 1: Thread pool configuration")
    assert scan_thread_pool is not None, "Thread pool should exist"
    assert scan_thread_pool._max_workers == 1, "Thread pool should have max 1 worker"
    print(f"  ✅ Thread pool exists with max_workers=1")
    print()

    # Test 2: Session ID counter is atomic (itertools.count)
    print("Test 2: Atomic session ID counter")
    from itertools import count
    assert isinstance(_session_id_counter, type(count())), "Session ID counter should be itertools.count"

    # Get a few session IDs
    id1 = next(_session_id_counter)
    id2 = next(_session_id_counter)
    id3 = next(_session_id_counter)

    assert id2 == id1 + 1, "Session IDs should increment"
    assert id3 == id2 + 1, "Session IDs should increment"
    print(f"  Generated IDs: {id1}, {id2}, {id3}")
    print(f"  ✅ Session IDs increment atomically")
    print()

    # Test 3: has_active_scan() function
    print("Test 3: Active scan detection")

    # Clear sessions
    with scan_sessions_lock:
        scan_sessions.clear()

    # No active scans
    assert not has_active_scan(), "Should be no active scans"
    print(f"  ✅ No active scans detected (empty)")

    # Add completed session
    with scan_sessions_lock:
        scan_sessions[1] = {'status': 'completed'}

    assert not has_active_scan(), "Completed scan should not be active"
    print(f"  ✅ No active scans detected (completed only)")

    # Add in-progress session
    with scan_sessions_lock:
        scan_sessions[2] = {'status': 'in_progress'}

    assert has_active_scan(), "Should detect in-progress scan"
    print(f"  ✅ Active scan detected (in_progress)")

    # Clean up
    with scan_sessions_lock:
        scan_sessions.clear()
    print()

    print("========================================")
    print("All Tests Passed! ✅")
    print("========================================")
    print()
    print("Summary:")
    print("- Thread pool configured with max_workers=1")
    print("- Session IDs generated atomically (thread-safe)")
    print("- Active scan detection working correctly")
    print("- Only 1 scan can run at a time (enforced by thread pool)")


if __name__ == '__main__':
    test_thread_pool()
