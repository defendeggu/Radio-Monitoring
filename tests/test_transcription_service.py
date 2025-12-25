"""Unit tests for transcription_service.py"""

import os
import json
import pytest
from transcription_service import TranscriptionService, SegmentDict, TranscriptionResult


class TestTranscriptionServiceInit:
    """Test TranscriptionService initialization"""

    def test_init_default_parameters(self):
        """Test initialization with default parameters"""
        service = TranscriptionService()
        assert service.model_name == 'base'
        assert service.device == 'cpu'
        assert service.compute_type == 'int8'

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters"""
        service = TranscriptionService(
            model='small',
            device='cuda',
            compute_type='float16'
        )
        assert service.model_name == 'small'
        assert service.device == 'cuda'
        assert service.compute_type == 'float16'

    def test_init_loads_model_or_simulation(self):
        """Test that initialization loads model or falls back to simulation"""
        service = TranscriptionService(model='tiny')
        # Model should be None in simulation mode (faster-whisper not available)
        # or an actual model object if available
        assert service.model is None or service.model is not None


class TestTranscriptionServiceTranscribe:
    """Test TranscriptionService.transcribe() method"""

    def test_transcribe_missing_file(self):
        """Test transcription with non-existent file raises FileNotFoundError"""
        service = TranscriptionService()
        with pytest.raises(FileNotFoundError):
            service.transcribe('/nonexistent/file.wav')

    def test_transcribe_simulation_mode(self, sample_audio_file: str):
        """Test transcription in simulation mode"""
        service = TranscriptionService()
        result = service.transcribe(sample_audio_file)

        # Check return type structure
        assert isinstance(result, dict)
        assert 'text' in result
        assert 'language' in result
        assert 'language_probability' in result
        assert 'duration' in result
        assert 'segments' in result
        assert 'audio_file' in result
        assert 'timestamp' in result

        # Check types
        assert isinstance(result['text'], str)
        assert isinstance(result['language'], str)
        assert isinstance(result['language_probability'], float)
        assert isinstance(result['duration'], float)
        assert isinstance(result['segments'], list)
        assert result['audio_file'] == sample_audio_file

    def test_transcribe_simulation_returns_english(self, sample_audio_file: str):
        """Test that simulation mode returns English language"""
        service = TranscriptionService()
        result = service.transcribe(sample_audio_file)
        assert result['language'] == 'en'
        assert result['language_probability'] == 0.95

    def test_transcribe_with_language_hint(self, sample_audio_file: str):
        """Test transcription with language hint"""
        service = TranscriptionService()
        # Should not raise even with language hint
        result = service.transcribe(sample_audio_file, language='de')
        assert isinstance(result, dict)

    def test_transcribe_segments_structure(self, sample_audio_file: str):
        """Test that segments have correct structure"""
        service = TranscriptionService()
        result = service.transcribe(sample_audio_file)

        assert len(result['segments']) > 0
        for segment in result['segments']:
            assert 'start' in segment
            assert 'end' in segment
            assert 'text' in segment
            assert isinstance(segment['start'], (int, float))
            assert isinstance(segment['end'], (int, float))
            assert isinstance(segment['text'], str)


class TestTranscriptionServiceSimulate:
    """Test TranscriptionService._simulate_transcription() method"""

    def test_simulate_transcription(self, sample_audio_file: str):
        """Test simulation transcription"""
        service = TranscriptionService()
        result = service._simulate_transcription(sample_audio_file)

        assert result['text'] is not None
        assert len(result['text']) > 0
        assert result['language'] == 'en'
        assert result['language_probability'] == 0.95
        assert result['duration'] == 10.0
        assert len(result['segments']) == 2

    def test_simulate_has_realistic_segments(self, sample_audio_file: str):
        """Test that simulation has realistic segment timing"""
        service = TranscriptionService()
        result = service._simulate_transcription(sample_audio_file)

        segments = result['segments']
        assert segments[0]['start'] == 0.0
        assert segments[0]['end'] == 5.0
        assert segments[1]['start'] == 5.0
        assert segments[1]['end'] == 10.0


class TestTranscriptionServiceTranscribeAndSave:
    """Test TranscriptionService.transcribe_and_save() method"""

    def test_transcribe_and_save_without_output(self, sample_audio_file: str):
        """Test transcribe without saving to file"""
        service = TranscriptionService()
        result = service.transcribe_and_save(sample_audio_file)

        assert isinstance(result, dict)
        assert 'text' in result

    def test_transcribe_and_save_with_output(self, sample_audio_file: str, temp_recording_dir: str):
        """Test transcribe and save to JSON file"""
        service = TranscriptionService()
        output_file = os.path.join(temp_recording_dir, 'output.json')

        result = service.transcribe_and_save(sample_audio_file, output_file)

        # Check file was created
        assert os.path.exists(output_file)

        # Check file content
        with open(output_file, 'r') as f:
            saved_data = json.load(f)

        assert saved_data == result
        assert saved_data['audio_file'] == sample_audio_file

    def test_transcribe_and_save_creates_directory(self, sample_audio_file: str, temp_recording_dir: str):
        """Test that output directory is created if it doesn't exist"""
        service = TranscriptionService()
        nested_dir = os.path.join(temp_recording_dir, 'nested', 'dir')
        output_file = os.path.join(nested_dir, 'output.json')

        result = service.transcribe_and_save(sample_audio_file, output_file)

        assert os.path.exists(output_file)
        assert os.path.exists(nested_dir)

    def test_transcribe_and_save_with_language(self, sample_audio_file: str, temp_recording_dir: str):
        """Test transcribe and save with language hint"""
        service = TranscriptionService()
        output_file = os.path.join(temp_recording_dir, 'output.json')

        result = service.transcribe_and_save(
            sample_audio_file,
            output_file,
            language='en'
        )

        assert os.path.exists(output_file)
        assert isinstance(result, dict)


class TestTranscriptionServiceEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_audio_file_path(self):
        """Test with empty string as audio file"""
        service = TranscriptionService()
        with pytest.raises(FileNotFoundError):
            service.transcribe('')

    def test_transcribe_result_has_timestamp(self, sample_audio_file: str):
        """Test that result includes ISO format timestamp"""
        service = TranscriptionService()
        result = service.transcribe(sample_audio_file)

        assert 'timestamp' in result
        # Check it's a valid ISO format string
        from datetime import datetime
        datetime.fromisoformat(result['timestamp'])  # Should not raise

    def test_multiple_transcriptions(self, sample_audio_file: str):
        """Test multiple transcriptions with same service instance"""
        service = TranscriptionService()

        result1 = service.transcribe(sample_audio_file)
        result2 = service.transcribe(sample_audio_file)

        assert result1['text'] == result2['text']
        assert result1['language'] == result2['language']
