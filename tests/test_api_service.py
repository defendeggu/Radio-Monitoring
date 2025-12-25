"""Integration tests for api_service.py"""

import os
import json
import pytest
from flask.testing import FlaskClient


class TestHealthEndpoint:
    """Test /health endpoint"""

    def test_health_returns_200(self, client: FlaskClient):
        """Test that health endpoint returns 200 OK"""
        response = client.get('/health')
        assert response.status_code == 200

    def test_health_returns_json(self, client: FlaskClient):
        """Test that health endpoint returns JSON"""
        response = client.get('/health')
        assert response.content_type == 'application/json'

    def test_health_response_structure(self, client: FlaskClient):
        """Test health response has correct structure"""
        response = client.get('/health')
        data = response.get_json()

        assert 'status' in data
        assert 'service' in data
        assert 'timestamp' in data
        assert data['status'] == 'healthy'
        assert data['service'] == 'radio-transcription-api'


class TestCaptureEndpoint:
    """Test /capture endpoint"""

    def test_capture_requires_frequency(self, client: FlaskClient):
        """Test that capture requires frequency parameter"""
        response = client.post('/capture', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'frequency' in data['error'].lower()

    def test_capture_with_minimal_params(self, client: FlaskClient, set_recording_dir):
        """Test capture with only required parameters"""
        response = client.post('/capture', json={
            'frequency': 100000000
        })
        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'success'
        assert 'audio_file' in data
        assert data['frequency'] == 100000000

    def test_capture_with_all_params(self, client: FlaskClient, set_recording_dir):
        """Test capture with all parameters"""
        response = client.post('/capture', json={
            'frequency': 144390000,
            'modulation': 'FM',
            'duration': 5,
            'gain': 30,
            'sample_rate': 2000000
        })
        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'success'
        assert data['frequency'] == 144390000
        assert data['modulation'] == 'FM'
        assert data['duration'] == 5

    def test_capture_creates_wav_file(self, client: FlaskClient, set_recording_dir, temp_recording_dir: str):
        """Test that capture creates actual WAV file"""
        response = client.post('/capture', json={
            'frequency': 100000000,
            'duration': 1
        })
        assert response.status_code == 200
        data = response.get_json()

        audio_file = data['audio_file']
        # File should exist (in temp dir due to fixture)
        assert os.path.exists(audio_file)
        assert audio_file.endswith('.wav')

    def test_capture_different_modulations(self, client: FlaskClient, set_recording_dir):
        """Test capture with different modulation types"""
        modulations = ['FM', 'AM', 'USB', 'LSB']

        for mod in modulations:
            response = client.post('/capture', json={
                'frequency': 100000000,
                'modulation': mod
            })
            assert response.status_code == 200
            data = response.get_json()
            assert data['modulation'] == mod


class TestTranscribeEndpoint:
    """Test /transcribe endpoint"""

    def test_transcribe_requires_audio_file(self, client: FlaskClient):
        """Test that transcribe requires audio_file parameter"""
        response = client.post('/transcribe', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'audio_file' in data['error'].lower()

    def test_transcribe_missing_file(self, client: FlaskClient):
        """Test transcribe with non-existent file returns 404"""
        response = client.post('/transcribe', json={
            'audio_file': '/nonexistent/file.wav'
        })
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_transcribe_with_valid_file(self, client: FlaskClient, sample_audio_file: str):
        """Test transcribe with valid audio file"""
        response = client.post('/transcribe', json={
            'audio_file': sample_audio_file
        })
        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'success'
        assert 'result' in data
        result = data['result']
        assert 'text' in result
        assert 'language' in result
        assert 'duration' in result

    def test_transcribe_with_language_hint(self, client: FlaskClient, sample_audio_file: str):
        """Test transcribe with language parameter"""
        response = client.post('/transcribe', json={
            'audio_file': sample_audio_file,
            'language': 'en'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'


class TestCaptureAndTranscribeEndpoint:
    """Test /capture-and-transcribe endpoint"""

    def test_capture_and_transcribe_requires_frequency(self, client: FlaskClient):
        """Test that endpoint requires frequency"""
        response = client.post('/capture-and-transcribe', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'frequency' in data['error'].lower()

    def test_capture_and_transcribe_minimal_params(self, client: FlaskClient, set_recording_dir):
        """Test with minimal parameters"""
        response = client.post('/capture-and-transcribe', json={
            'frequency': 100000000
        })
        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'success'
        assert 'capture' in data
        assert 'transcription' in data
        assert 'timestamp' in data

    def test_capture_and_transcribe_full_workflow(self, client: FlaskClient, set_recording_dir, temp_recording_dir: str):
        """Test complete capture and transcribe workflow"""
        response = client.post('/capture-and-transcribe', json={
            'frequency': 144390000,
            'modulation': 'FM',
            'duration': 1,
            'gain': 20,
            'language': 'en'
        })
        assert response.status_code == 200
        data = response.get_json()

        # Check capture data
        assert 'capture' in data
        capture = data['capture']
        assert capture['frequency'] == 144390000
        assert capture['modulation'] == 'FM'
        assert capture['duration'] == 1
        assert os.path.exists(capture['audio_file'])

        # Check transcription data
        assert 'transcription' in data
        transcription = data['transcription']
        assert 'text' in transcription
        assert 'language' in transcription
        assert 'segments' in transcription

    def test_capture_and_transcribe_creates_files(self, client: FlaskClient, set_recording_dir, temp_recording_dir: str):
        """Test that both WAV and JSON files are created"""
        response = client.post('/capture-and-transcribe', json={
            'frequency': 100000000,
            'duration': 1
        })
        assert response.status_code == 200
        data = response.get_json()

        audio_file = data['capture']['audio_file']
        assert os.path.exists(audio_file)
        assert audio_file.endswith('.wav')

        # JSON file should also exist
        json_file = audio_file.replace('.wav', '.json')
        assert os.path.exists(json_file)

        # Verify JSON content
        with open(json_file, 'r') as f:
            json_data = json.load(f)
        assert 'text' in json_data
        assert 'language' in json_data


class TestListRecordingsEndpoint:
    """Test /list-recordings endpoint"""

    def test_list_recordings_empty_directory(self, client: FlaskClient, set_recording_dir):
        """Test listing when no recordings exist"""
        response = client.get('/list-recordings')
        assert response.status_code == 200
        data = response.get_json()

        assert 'recordings' in data
        assert isinstance(data['recordings'], list)

    def test_list_recordings_with_files(self, client: FlaskClient, set_recording_dir, temp_recording_dir: str):
        """Test listing after creating recordings"""
        # First create a recording
        client.post('/capture', json={
            'frequency': 100000000,
            'duration': 1
        })

        # Then list recordings
        response = client.get('/list-recordings')
        assert response.status_code == 200
        data = response.get_json()

        assert len(data['recordings']) > 0
        recording = data['recordings'][0]

        assert 'filename' in recording
        assert 'path' in recording
        assert 'size' in recording
        assert 'created' in recording
        assert recording['filename'].endswith('.wav')

    def test_list_recordings_sorted_by_date(self, client: FlaskClient, set_recording_dir):
        """Test that recordings are sorted by creation time (newest first)"""
        # Create multiple recordings
        client.post('/capture', json={'frequency': 100000000, 'duration': 1})
        client.post('/capture', json={'frequency': 200000000, 'duration': 1})

        response = client.get('/list-recordings')
        data = response.get_json()

        if len(data['recordings']) >= 2:
            # Should be sorted newest first
            created_times = [r['created'] for r in data['recordings']]
            assert created_times == sorted(created_times, reverse=True)


class TestAPIErrorHandling:
    """Test API error handling"""

    def test_invalid_json_request(self, client: FlaskClient):
        """Test API handles invalid JSON"""
        response = client.post(
            '/capture',
            data='invalid json',
            content_type='application/json'
        )
        # Should return 400 or 500 depending on implementation
        assert response.status_code in [400, 500]

    def test_missing_content_type(self, client: FlaskClient):
        """Test request without JSON content type"""
        response = client.post('/capture')
        # Flask might return 400 or process as empty JSON
        assert response.status_code in [400, 500]

    def test_capture_with_invalid_frequency(self, client: FlaskClient, set_recording_dir):
        """Test capture with invalid frequency value"""
        response = client.post('/capture', json={
            'frequency': 'invalid'
        })
        # Should handle gracefully
        assert response.status_code in [400, 500]


class TestAPIIntegration:
    """Test end-to-end API workflows"""

    def test_complete_workflow(self, client: FlaskClient, set_recording_dir):
        """Test complete workflow: health -> capture -> transcribe -> list"""
        # 1. Check health
        health_response = client.get('/health')
        assert health_response.status_code == 200

        # 2. Capture
        capture_response = client.post('/capture', json={
            'frequency': 100000000,
            'duration': 1
        })
        assert capture_response.status_code == 200
        audio_file = capture_response.get_json()['audio_file']

        # 3. Transcribe
        transcribe_response = client.post('/transcribe', json={
            'audio_file': audio_file
        })
        assert transcribe_response.status_code == 200

        # 4. List recordings
        list_response = client.get('/list-recordings')
        assert list_response.status_code == 200
        assert len(list_response.get_json()['recordings']) > 0

    def test_capture_and_transcribe_combined(self, client: FlaskClient, set_recording_dir):
        """Test combined endpoint vs separate calls"""
        # Combined approach
        combined_response = client.post('/capture-and-transcribe', json={
            'frequency': 100000000,
            'duration': 1
        })
        assert combined_response.status_code == 200
        combined_data = combined_response.get_json()

        # Verify structure
        assert 'capture' in combined_data
        assert 'transcription' in combined_data
        assert combined_data['transcription']['text'] is not None


class TestAPIConfiguration:
    """Test API configuration and environment variables"""

    def test_recording_directory_configuration(self, client: FlaskClient, temp_recording_dir: str, monkeypatch):
        """Test that RECORDING_DIR configuration is respected"""
        import api_service
        monkeypatch.setattr(api_service, 'RECORDING_DIR', temp_recording_dir)

        response = client.post('/capture', json={'frequency': 100000000, 'duration': 1})
        assert response.status_code == 200

        audio_file = response.get_json()['audio_file']
        assert audio_file.startswith(temp_recording_dir)
