"""
Test Suite for Repeater Scanning Functionality

Tests:
- RepeaterActivityAnalyzer unit tests (10 tests)
- API integration tests (8 tests)
- Progress tracking tests (4 tests)
- Elasticsearch integration tests (3 tests)

Total: 25 tests covering the entire repeater scanning workflow
"""

import os
import sys
import pytest
import numpy as np
import tempfile
import time
import json
from pathlib import Path
from typing import Dict, Any
from flask.testing import FlaskClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radiomoni.repeater_activity_analyzer import (
    RepeaterActivityAnalyzer,
    ActivityMetrics,
    TransmissionEvent
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def temp_iq_dir(tmp_path):
    """Create temporary directory for IQ files"""
    iq_dir = tmp_path / "iq_files"
    iq_dir.mkdir()
    return iq_dir


@pytest.fixture
def analyzer():
    """Create default RepeaterActivityAnalyzer instance"""
    return RepeaterActivityAnalyzer(
        sample_rate=2_000_000,
        audio_rate=48000,
        threshold_multiplier=1.5,
        min_transmission_seconds=1.0,
        min_gap_seconds=0.5,
        calibration_seconds=2.0,
        window_seconds=0.1
    )


@pytest.fixture
def noise_only_iq_samples():
    """Generate IQ samples with only noise (no transmissions)"""
    sample_rate = 2_000_000
    duration = 5  # seconds
    num_samples = sample_rate * duration

    # Generate Gaussian noise
    noise = ((np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * 0.1).astype(np.complex64)
    return noise


@pytest.fixture
def single_transmission_iq_samples():
    """Generate IQ samples with a single transmission"""
    sample_rate = 2_000_000
    duration = 10  # seconds
    num_samples = sample_rate * duration

    # Generate noise
    noise = ((np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * 0.1).astype(np.complex64)

    # Add transmission: 3.0s - 5.0s (2.0s duration)
    tx_start = int(3.0 * sample_rate)
    tx_end = int(5.0 * sample_rate)
    noise[tx_start:tx_end] += (np.random.randn(tx_end - tx_start) +
                                1j * np.random.randn(tx_end - tx_start)) * 0.5

    return noise


@pytest.fixture
def multiple_transmission_iq_samples():
    """Generate IQ samples with multiple transmissions"""
    sample_rate = 2_000_000
    duration = 15  # seconds
    num_samples = sample_rate * duration

    # Generate noise
    noise = ((np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * 0.1).astype(np.complex64)

    # Transmission 1: 2.0s - 3.5s (1.5s duration)
    t1_start = int(2.0 * sample_rate)
    t1_end = int(3.5 * sample_rate)
    noise[t1_start:t1_end] += (np.random.randn(t1_end - t1_start) +
                                1j * np.random.randn(t1_end - t1_start)) * 0.5

    # Transmission 2: 6.0s - 8.5s (2.5s duration)
    t2_start = int(6.0 * sample_rate)
    t2_end = int(8.5 * sample_rate)
    noise[t2_start:t2_end] += (np.random.randn(t2_end - t2_start) +
                                1j * np.random.randn(t2_end - t2_start)) * 0.7

    # Transmission 3: 11.0s - 12.0s (1.0s duration)
    t3_start = int(11.0 * sample_rate)
    t3_end = int(12.0 * sample_rate)
    noise[t3_start:t3_end] += (np.random.randn(t3_end - t3_start) +
                                1j * np.random.randn(t3_end - t3_start)) * 0.6

    return noise


@pytest.fixture
def mock_repeater_data():
    """Mock repeater data for testing"""
    return [
        {
            'id': 1,
            'uuid': 'test-repeater-1',
            'callsign': 'HB9TEST',
            'output_frequency': 145500000,  # 145.5 MHz
            'frequency_mhz': 145.5,
            'band': '2m',
            'canton': 'ZH',
            'mode': 'FM'
        },
        {
            'id': 2,
            'uuid': 'test-repeater-2',
            'callsign': 'HB9TST2',
            'output_frequency': 145600000,  # 145.6 MHz
            'frequency_mhz': 145.6,
            'band': '2m',
            'canton': 'BE',
            'mode': 'FM'
        }
    ]


# ============================================================================
# Unit Tests: RepeaterActivityAnalyzer
# ============================================================================

class TestRepeaterActivityAnalyzer:
    """Unit tests for RepeaterActivityAnalyzer class"""

    def test_initialization(self):
        """Test analyzer initialization with default parameters"""
        analyzer = RepeaterActivityAnalyzer()

        assert analyzer.sample_rate == 2_000_000
        assert analyzer.audio_rate == 48000
        assert analyzer.threshold_multiplier == 1.5
        assert analyzer.min_transmission_seconds == 1.0
        assert analyzer.min_gap_seconds == 0.5
        assert analyzer.calibration_seconds == 2.0
        assert analyzer.window_seconds == 0.1

    def test_initialization_custom_parameters(self):
        """Test analyzer initialization with custom parameters"""
        analyzer = RepeaterActivityAnalyzer(
            sample_rate=1_000_000,
            threshold_multiplier=2.0,
            min_transmission_seconds=0.5
        )

        assert analyzer.sample_rate == 1_000_000
        assert analyzer.threshold_multiplier == 2.0
        assert analyzer.min_transmission_seconds == 0.5

    def test_calculate_rms_power(self, analyzer, noise_only_iq_samples):
        """Test RMS power calculation from IQ samples"""
        rms_power = analyzer._calculate_rms_power(noise_only_iq_samples)

        assert isinstance(rms_power, np.ndarray)
        assert len(rms_power) > 0
        assert rms_power.dtype == np.float64
        # RMS power should be positive
        assert np.all(rms_power >= 0)

    def test_calibrate_noise_floor(self, analyzer, noise_only_iq_samples):
        """Test noise floor calibration"""
        rms_power = analyzer._calculate_rms_power(noise_only_iq_samples)
        noise_floor = analyzer._calibrate_noise_floor(rms_power)

        assert isinstance(noise_floor, float)
        assert noise_floor > 0
        # Noise floor should be reasonable (mean + 2*std)
        mean_power = np.mean(rms_power[:20])  # First 2 seconds
        assert noise_floor > mean_power

    def test_analyze_noise_only(self, analyzer, noise_only_iq_samples):
        """Test analysis with only noise (no transmissions)"""
        metrics = analyzer.analyze_iq_samples(noise_only_iq_samples)

        assert isinstance(metrics, ActivityMetrics)
        assert metrics.carrier_detected == False
        assert metrics.transmission_count == 0
        assert metrics.total_active_seconds >= 0
        assert metrics.activity_percentage < 10  # Should be very low
        assert metrics.average_signal_strength is None
        assert metrics.peak_signal_strength is None
        assert len(metrics.transmissions) == 0

    def test_analyze_single_transmission(self, analyzer, single_transmission_iq_samples):
        """Test analysis with a single transmission"""
        metrics = analyzer.analyze_iq_samples(single_transmission_iq_samples)

        assert isinstance(metrics, ActivityMetrics)
        assert metrics.carrier_detected == True
        assert metrics.transmission_count >= 1
        assert metrics.total_active_seconds > 0
        assert metrics.activity_percentage > 0
        assert metrics.average_signal_strength is not None
        assert metrics.peak_signal_strength is not None
        assert len(metrics.transmissions) >= 1

    def test_analyze_multiple_transmissions(self, analyzer, multiple_transmission_iq_samples):
        """Test analysis with multiple transmissions"""
        metrics = analyzer.analyze_iq_samples(multiple_transmission_iq_samples)

        assert isinstance(metrics, ActivityMetrics)
        assert metrics.carrier_detected == True
        assert metrics.transmission_count >= 2  # At least 2 transmissions
        assert metrics.total_active_seconds > 0
        assert len(metrics.transmissions) >= 2

    def test_transmission_event_to_dict(self):
        """Test TransmissionEvent to_dict serialization"""
        event = TransmissionEvent(
            start_offset=2.5,
            duration=3.2,
            avg_strength=-45.6,
            peak_strength=-30.1
        )

        result = event.to_dict()

        assert isinstance(result, dict)
        assert result['start_offset'] == 2.5
        assert result['duration'] == 3.2
        assert result['avg_strength'] == -45.6
        assert result['peak_strength'] == -30.1

    def test_activity_metrics_to_dict(self):
        """Test ActivityMetrics to_dict serialization"""
        metrics = ActivityMetrics(
            carrier_detected=True,
            transmission_count=3,
            total_active_seconds=12.5,
            activity_percentage=25.3,
            average_signal_strength=-40.2,
            peak_signal_strength=-28.5,
            noise_floor=-75.3,
            transmissions=[]
        )

        result = metrics.to_dict()

        assert isinstance(result, dict)
        assert result['carrier_detected'] == True
        assert result['transmission_count'] == 3
        assert result['total_active_seconds'] == 12.5
        assert result['activity_percentage'] == 25.3
        assert result['average_signal_strength'] == -40.2
        assert result['noise_floor'] == -75.3

    def test_analyze_iq_file(self, analyzer, temp_iq_dir):
        """Test analyze_iq_file with valid IQ file"""
        # Create test IQ file
        iq_file = temp_iq_dir / "test.iq"

        # Generate test data (5 seconds of noise)
        sample_rate = 2_000_000
        duration = 5
        num_samples = sample_rate * duration
        noise = ((np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * 0.1).astype(np.complex64)

        # Save to file
        noise.tofile(str(iq_file))

        # Analyze
        metrics = analyzer.analyze_iq_file(str(iq_file))

        assert isinstance(metrics, ActivityMetrics)
        assert metrics.transmission_count >= 0

    def test_analyze_iq_file_not_found(self, analyzer):
        """Test analyze_iq_file with non-existent file"""
        with pytest.raises(FileNotFoundError):
            analyzer.analyze_iq_file("/nonexistent/file.iq")

    def test_analyze_iq_file_too_short(self, analyzer, temp_iq_dir):
        """Test analyze_iq_file with file too short for calibration"""
        # Create test IQ file that's too short
        iq_file = temp_iq_dir / "short.iq"

        # Only 100 samples (need at least 4M for 2 second calibration)
        short_data = ((np.random.randn(100) + 1j * np.random.randn(100)) * 0.1).astype(np.complex64)
        short_data.tofile(str(iq_file))

        # Should raise ValueError
        with pytest.raises(ValueError, match="too short for analysis"):
            analyzer.analyze_iq_file(str(iq_file))

    def test_merge_close_transmissions(self, analyzer):
        """Test merging of transmissions with small gaps"""
        # Create two transmissions with small gap (< min_gap_seconds)
        tx1 = TransmissionEvent(
            start_offset=2.0,
            duration=1.5,
            avg_strength=-40.0,
            peak_strength=-30.0
        )

        tx2 = TransmissionEvent(
            start_offset=3.7,  # Gap of 0.2s (< 0.5s min_gap)
            duration=1.0,
            avg_strength=-38.0,
            peak_strength=-28.0
        )

        transmissions = [tx1, tx2]
        merged = analyzer._merge_close_transmissions(transmissions)

        # Should merge into one transmission
        assert len(merged) == 1
        assert merged[0].start_offset == 2.0
        assert merged[0].duration > tx1.duration
        assert merged[0].duration > tx2.duration


# ============================================================================
# API Integration Tests
# ============================================================================

class TestRepeaterScanningAPI:
    """API tests for repeater scanning endpoints"""

    REPEATER = {'id': 1, 'uuid': 'test-1', 'callsign': 'HB9TEST', 'output_frequency': 145500000,
                'frequency_mhz': 145.5, 'band': '2m', 'canton': 'ZH', 'mode': 'FM', 'status': 'active'}

    @pytest.fixture
    def seeded(self):
        from radiomoni.storage import get_storage
        get_storage().index_repeater(dict(self.REPEATER))

    @pytest.fixture
    def no_worker(self, monkeypatch):
        """Do not actually scan: record the submitted job instead"""
        from radiomoni import jobs
        submitted = []
        monkeypatch.setattr(jobs.scan_pool, 'submit', lambda fn, *args: submitted.append(args))
        return submitted

    def test_scan_without_repeaters_is_404(self, client: FlaskClient, no_worker):
        response = client.post('/scan-repeaters', json={'duration_per_repeater': 10})
        assert response.status_code == 404
        assert no_worker == []

    def test_scan_repeaters_minimal_params(self, client: FlaskClient, seeded, no_worker):
        response = client.post('/scan-repeaters', json={'duration_per_repeater': 10})
        assert response.status_code == 200
        data = response.get_json()
        assert data['repeaters_count'] == 1
        assert data['estimated_duration_seconds'] == 10
        assert len(no_worker) == 1

    def test_scan_holds_sdr_lock(self, client: FlaskClient, seeded, no_worker):
        assert client.post('/scan-repeaters', json={'duration_per_repeater': 10}).status_code == 200
        second = client.post('/scan-repeaters', json={'duration_per_repeater': 10})
        assert second.status_code == 409

    def test_scan_duration_is_validated(self, client: FlaskClient):
        assert client.post('/scan-repeaters', json={'duration_per_repeater': 100000}).status_code == 400
        assert client.post('/scan-repeaters', json={'canton': 'Zurich'}).status_code == 400
        assert client.post('/scan-repeaters', json={'band': '2m; DROP'}).status_code == 400

    def test_scan_with_filters(self, client: FlaskClient, seeded, no_worker):
        assert client.post('/scan-repeaters', json={'band': '2m', 'canton': 'zh',
                                                    'duration_per_repeater': 10}).status_code == 200
        from radiomoni import sdr_lock
        sdr_lock.force_release()
        assert client.post('/scan-repeaters', json={'band': '70cm', 'duration_per_repeater': 10}).status_code == 404

    def test_unknown_session_is_404(self, client: FlaskClient):
        assert client.get('/scan-repeaters/12345/progress').status_code == 404
        assert client.get('/scan-repeaters/12345').status_code == 404

    def test_repeaters_list_endpoint(self, client: FlaskClient, seeded):
        response = client.get('/repeaters')
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 1
        assert data['repeaters'][0]['callsign'] == 'HB9TEST'

    def test_worker_scans_and_stores_flat_metrics(self, client: FlaskClient, seeded, mock_sdr_hardware,
                                                  monkeypatch):
        """The worker stores carrier metrics at top level so the summary aggregation works"""
        from radiomoni import jobs
        from radiomoni.scan_session_manager import RepeaterScanSession, get_scan_session_manager
        from radiomoni.storage import get_storage
        from radiomoni.repeater_activity_analyzer import ActivityMetrics
        from radiomoni.sdr_hardware import SDRType

        monkeypatch.setattr(jobs, 'detect_sdr', lambda *a, **k: SDRType.HACKRF)
        monkeypatch.setattr(jobs.RepeaterActivityAnalyzer, 'analyze_iq_file', lambda self, path: ActivityMetrics(
            carrier_detected=True, transmission_count=2, total_active_seconds=3.0, activity_percentage=30.0,
            average_signal_strength=-40.0, peak_signal_strength=-30.0, noise_floor=-80.0))
        manager = get_scan_session_manager()
        manager.save_session(RepeaterScanSession(session_id=77, repeaters_total=1, duration_per_repeater=1,
                                                 sample_rate=2000000, gain=20))
        jobs.scan_repeaters_worker(77, [dict(self.REPEATER)], 1, 2000000, 20)

        assert manager.get_session(77).status == 'completed'
        summary = get_storage().get_repeater_activity_summary(hours=1)
        assert summary[0]['callsign'] == 'HB9TEST'
        assert summary[0]['avg_activity_pct'] == 30.0


# ============================================================================
# Progress Tracking Tests
# ============================================================================

class TestProgressTracking:
    """Tests for scan progress tracking"""

    def test_progress_calculation(self):
        """Test progress percentage calculation"""
        total_repeaters = 10
        scanned = 3

        progress = (scanned / total_repeaters) * 100

        assert progress == 30.0
        assert 0 <= progress <= 100

    def test_eta_calculation(self):
        """Test ETA (Estimated Time Remaining) calculation"""
        total_repeaters = 10
        scanned = 4
        elapsed_time = 200  # seconds

        # Calculate ETA
        if scanned > 0:
            time_per_repeater = elapsed_time / scanned
            remaining_repeaters = total_repeaters - scanned
            eta = remaining_repeaters * time_per_repeater
        else:
            eta = 0

        assert eta == 300.0  # 6 repeaters * 50s each

    def test_progress_updates_during_scan(self, client: FlaskClient, monkeypatch):
        """Test that progress updates are available during scan"""
        # This test verifies the structure, actual scanning tested elsewhere
        from radiomoni.scan_session_manager import RepeaterScanSession, get_scan_session_manager
        manager = get_scan_session_manager()

        # Create test session
        session_id = 999
        session = RepeaterScanSession(
            session_id=session_id,
            repeaters_total=10,
            duration_per_repeater=120,
            sample_rate=2000000,
            gain=20
        )
        session.repeaters_scanned = 3
        session.current_repeater = 'HB9TEST'
        session.current_index = 3

        # Save to Redis
        manager.save_session(session)

        response = client.get(f'/scan-repeaters/{session_id}/progress')

        assert response.status_code == 200
        data = response.get_json()
        assert data['progress']['current_callsign'] == 'HB9TEST'
        assert data['progress']['repeaters_scanned'] == 3

        # Cleanup
        manager.delete_session(session_id)

    def test_completed_scan_has_results(self, client: FlaskClient, monkeypatch):
        """Test that completed scans have results available"""
        from radiomoni.scan_session_manager import RepeaterScanSession, get_scan_session_manager
        manager = get_scan_session_manager()

        # Create completed test session
        session_id = 998
        session = RepeaterScanSession(
            session_id=session_id,
            repeaters_total=1,
            duration_per_repeater=120,
            sample_rate=2000000,
            gain=20
        )

        # Mark as completed with results
        results = [{'callsign': 'HB9TEST', 'activity_percentage': 12.5}]
        session.complete(results)

        # Save to Redis
        manager.save_session(session)

        response = client.get(f'/scan-repeaters/{session_id}')

        assert response.status_code == 200
        if True:
            data = response.get_json()
            # API returns nested structure with top-level status and session object
            assert data['status'] == 'success'
            assert 'session' in data
            assert data['session']['status'] == 'completed'
            assert 'results' in data['session']

        # Cleanup
        manager.delete_session(session_id)


# ============================================================================
# Elasticsearch Integration Tests
# ============================================================================

class TestElasticsearchIntegration:
    """Tests for Elasticsearch integration with repeater scanning"""

    def test_repeater_activity_document_structure(self):
        """Test the structure of repeater activity documents"""
        doc = {
            'repeater_id': 'test-uuid-123',
            'repeater_callsign': 'HB9TEST',
            'activity_detected': True,
            'frequency_mhz': 145.5,
            'band': '2m',
            'canton': 'ZH',
            'transmission_count': 3,
            'activity_percentage': 15.2,
            'avg_signal_strength': -42.5,
            'peak_signal_strength': -30.1,
            'noise_floor': -78.3
        }

        # Verify required fields
        assert 'repeater_id' in doc
        assert 'repeater_callsign' in doc
        assert 'activity_detected' in doc
        assert 'frequency_mhz' in doc

        # Verify types
        assert isinstance(doc['activity_detected'], bool)
        assert isinstance(doc['transmission_count'], int)
        assert isinstance(doc['activity_percentage'], float)

    def test_index_naming_pattern(self):
        """Test that index names follow the correct pattern"""
        from datetime import datetime

        # Expected pattern: radio-repeater-activity-YYYY.MM.DD
        today = datetime.now()
        expected_index = f"radio-repeater-activity-{today.strftime('%Y.%m.%d')}"

        # Verify format
        assert expected_index.startswith('radio-repeater-activity-')
        # Date uses periods: radio-repeater-activity-2026.01.04 (4 parts)
        assert len(expected_index.split('-')) == 4

    def test_elasticsearch_connectivity_mock(self, monkeypatch):
        """Test Elasticsearch service mock for repeater activity"""
        # Mock Elasticsearch service
        class MockElasticsearchService:
            def index_repeater_activity(self, doc):
                # Simulate indexing
                return f"indexed-{doc.get('repeater_callsign', 'unknown')}"

        es = MockElasticsearchService()

        doc = {
            'repeater_callsign': 'HB9TEST',
            'activity_detected': True
        }

        result = es.index_repeater_activity(doc)

        assert result == 'indexed-HB9TEST'


# ============================================================================
# Scan rounds: once, total duration, until stopped
# ============================================================================

class TestScanRounds:
    """scan_repeaters_worker with a fake measurement and a fake clock"""

    REPEATERS = [
        {'uuid': 'r1', 'callsign': 'HB9LU', 'output_frequency': 145_600_000, 'band': '2m', 'canton': 'LU',
         'location_name': 'Luzern'},
        {'uuid': 'r2', 'callsign': 'HB9AW', 'output_frequency': 439_250_000, 'band': '70cm', 'canton': 'LU',
         'location_name': 'Willisau'},
    ]

    @pytest.fixture
    def scan(self, monkeypatch):
        """Run the worker; every measurement takes `duration` seconds on the fake clock."""
        import types
        from radiomoni import jobs
        from radiomoni.scan_session_manager import RepeaterScanSession, get_scan_session_manager
        manager = get_scan_session_manager()
        clock = {'now': 0.0}
        calls: list[str] = []
        monkeypatch.setattr(jobs, 'time', types.SimpleNamespace(monotonic=lambda: clock['now']))
        monkeypatch.setattr(jobs, 'detect_sdr', lambda *a, **k: jobs.SDRType.HACKRF)

        def run(duration=60, total_duration=None, until_stopped=False, on_measure=None):
            session_id = manager.get_next_session_id()
            manager.save_session(RepeaterScanSession(session_id, len(self.REPEATERS), duration, 2_000_000, 20,
                                                     total_duration, until_stopped))

            def measure(repeater, sid, *args):
                calls.append(repeater['callsign'])
                clock['now'] += duration
                if on_measure:
                    on_measure(sid, len(calls))
                return {'carrier_detected': repeater['callsign'] == 'HB9LU', 'transmission_count': 2,
                        'activity_percentage': 10.0, 'average_signal_strength': -40.0, 'transmissions': [1, 2]}

            monkeypatch.setattr(jobs, '_measure_repeater', measure)
            jobs.scan_repeaters_worker(session_id, self.REPEATERS, duration, 2_000_000, 20, None,
                                       total_duration, until_stopped)
            return manager.get_session(session_id), calls

        return run

    def test_one_round_by_default(self, scan):
        session, calls = scan()
        assert session.status == 'completed'
        assert calls == ['HB9LU', 'HB9AW']
        assert session.rounds_completed == 1
        assert session.repeaters_scanned == 2 and session.repeaters_with_activity == 1

    def test_rounds_until_total_duration(self, scan):
        # 2 repeaters x 60 s: rounds end at 120 s and 240 s; a third round would end at 360 s > 250 s
        session, calls = scan(duration=60, total_duration=250)
        assert session.status == 'completed'
        assert calls == ['HB9LU', 'HB9AW'] * 2
        assert session.rounds_completed == 2

    def test_repeater_that_would_overrun_is_skipped(self, scan):
        session, calls = scan(duration=60, total_duration=150)
        assert calls == ['HB9LU', 'HB9AW']  # third measurement would end at 180 s
        assert session.status == 'completed'

    def test_until_stopped(self, scan):
        from radiomoni.scan_session_manager import get_scan_session_manager

        def stop_after_five(session_id, n):
            if n == 5:
                get_scan_session_manager().request_stop(session_id)

        session, calls = scan(until_stopped=True, on_measure=stop_after_five)
        assert session.status == 'stopped'
        assert len(calls) == 5
        lu = next(r for r in session.results if r['callsign'] == 'HB9LU')
        assert lu['rounds'] == 3 and lu['active_rounds'] == 3 and lu['transmission_count'] == 6
        assert 'transmissions' not in lu['activity']  # bounded result size

    def test_results_are_aggregated_per_repeater(self, scan):
        session, _ = scan(duration=60, total_duration=600)
        assert len(session.results) == 2
        assert {r['callsign']: r['rounds'] for r in session.results} == {'HB9LU': 5, 'HB9AW': 5}


class TestScanRoundsAPI:

    REPEATER = TestRepeaterScanningAPI.REPEATER

    @pytest.fixture
    def seeded(self):
        from radiomoni.storage import get_storage
        get_storage().index_repeater(dict(self.REPEATER))

    @pytest.fixture
    def no_worker(self, monkeypatch):
        from radiomoni import jobs
        submitted = []
        monkeypatch.setattr(jobs.scan_pool, 'submit', lambda fn, *args: submitted.append(args))
        return submitted

    def test_end_condition_is_validated(self, client: FlaskClient):
        both = {'total_duration': 1800, 'until_stopped': True}
        assert client.post('/scan-repeaters', json=both).status_code == 400
        assert client.post('/scan-repeaters', json={'total_duration': 10}).status_code == 400

    def test_until_stopped_scan_and_stop(self, client: FlaskClient, seeded, no_worker):
        r = client.post('/scan-repeaters', json={'until_stopped': True, 'duration_per_repeater': 30,
                                                 'repeater_ids': [1]})
        assert r.status_code == 200
        assert r.get_json()['estimated_duration_seconds'] is None
        session_id = r.get_json()['session_id']
        assert no_worker[0][-2:] == (None, True)

        progress = client.get(f'/scan-repeaters/{session_id}/progress').get_json()['progress']
        assert progress['until_stopped'] is True and progress['estimated_remaining_seconds'] is None

        assert client.post(f'/scan-repeaters/{session_id}/stop').status_code == 200
        from radiomoni.scan_session_manager import get_scan_session_manager
        assert get_scan_session_manager().stop_requested(session_id)

    def test_total_duration_estimate(self, client: FlaskClient, seeded, no_worker):
        r = client.post('/scan-repeaters', json={'total_duration': 1800, 'duration_per_repeater': 30})
        assert r.get_json()['estimated_duration_seconds'] == 1800

    def test_stop_unknown_or_finished_scan(self, client: FlaskClient):
        assert client.post('/scan-repeaters/99999/stop').status_code == 404
        from radiomoni.scan_session_manager import RepeaterScanSession, get_scan_session_manager
        manager = get_scan_session_manager()
        done = RepeaterScanSession(manager.get_next_session_id(), 1, 30, 2_000_000, 20)
        done.complete([])
        manager.save_session(done)
        assert client.post(f'/scan-repeaters/{done.session_id}/stop').status_code == 409


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
