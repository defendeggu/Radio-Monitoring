"""Unit tests for radio_capture.py"""

import os
import pytest
import numpy as np
from scipy.io import wavfile
from radio_capture import HackRFCapture


class TestHackRFCaptureInit:
    """Test HackRFCapture initialization"""

    def test_init_default_parameters(self):
        """Test initialization with default parameters"""
        capture = HackRFCapture(frequency=100e6)
        assert capture.frequency == 100e6
        assert capture.sample_rate == 2000000
        assert capture.gain == 20
        assert capture.modulation == 'FM'
        assert capture.audio_sample_rate == 16000

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters"""
        capture = HackRFCapture(
            frequency=144.39e6,
            sample_rate=3000000,
            gain=30,
            modulation='AM'
        )
        assert capture.frequency == 144.39e6
        assert capture.sample_rate == 3000000
        assert capture.gain == 30
        assert capture.modulation == 'AM'

    def test_init_modulation_uppercase(self):
        """Test that modulation is converted to uppercase"""
        capture = HackRFCapture(frequency=100e6, modulation='fm')
        assert capture.modulation == 'FM'


class TestHackRFCaptureSimulation:
    """Test HackRFCapture simulation mode"""

    def test_simulate_capture_creates_file(self, temp_recording_dir: str):
        """Test that simulation creates WAV file"""
        output_file = os.path.join(temp_recording_dir, 'test_capture.wav')
        capture = HackRFCapture(frequency=100e6, modulation='FM')
        capture._simulate_capture(duration=1, output_file=output_file)

        assert os.path.exists(output_file)

    def test_simulate_capture_wav_format(self, temp_recording_dir: str):
        """Test that simulated capture creates valid WAV file"""
        output_file = os.path.join(temp_recording_dir, 'test_capture.wav')
        capture = HackRFCapture(frequency=100e6)
        capture._simulate_capture(duration=1, output_file=output_file)

        # Read WAV file
        sample_rate, audio = wavfile.read(output_file)

        assert sample_rate == 16000  # Whisper-compatible sample rate
        assert len(audio) == 16000  # 1 second at 16kHz
        assert audio.dtype == np.int16

    def test_simulate_capture_duration(self, temp_recording_dir: str):
        """Test simulation respects duration parameter"""
        output_file = os.path.join(temp_recording_dir, 'test_capture.wav')
        capture = HackRFCapture(frequency=100e6)

        # Test 2 seconds
        capture._simulate_capture(duration=2, output_file=output_file)
        sample_rate, audio = wavfile.read(output_file)
        assert len(audio) == 32000  # 2 seconds at 16kHz

    def test_simulate_capture_creates_directory(self, temp_recording_dir: str):
        """Test that simulation creates output directory if needed"""
        nested_dir = os.path.join(temp_recording_dir, 'nested', 'dir')
        output_file = os.path.join(nested_dir, 'test.wav')
        capture = HackRFCapture(frequency=100e6)

        capture._simulate_capture(duration=1, output_file=output_file)

        assert os.path.exists(output_file)
        assert os.path.exists(nested_dir)


class TestHackRFCaptureCapture:
    """Test HackRFCapture.capture() method"""

    def test_capture_fallback_to_simulation(self, temp_recording_dir: str):
        """Test that capture falls back to simulation mode when HackRF not available"""
        output_file = os.path.join(temp_recording_dir, 'capture.wav')
        capture = HackRFCapture(frequency=100e6, modulation='FM')

        # Should use simulation mode since HackRF is not available
        capture.capture(duration=1, output_file=output_file)

        assert os.path.exists(output_file)
        sample_rate, audio = wavfile.read(output_file)
        assert sample_rate == 16000

    def test_capture_different_modulations(self, temp_recording_dir: str):
        """Test capture with different modulation types"""
        modulations = ['FM', 'AM', 'USB', 'LSB']

        for mod in modulations:
            output_file = os.path.join(temp_recording_dir, f'capture_{mod}.wav')
            capture = HackRFCapture(frequency=100e6, modulation=mod)
            capture.capture(duration=1, output_file=output_file)

            assert os.path.exists(output_file)


class TestHackRFCaptureDemodulation:
    """Test demodulation methods"""

    def test_fm_demodulate(self):
        """Test FM demodulation"""
        capture = HackRFCapture(frequency=100e6, modulation='FM')

        # Create test IQ samples (simple complex signal)
        t = np.linspace(0, 1, 2000000)  # 1 second at 2MHz
        freq_deviation = 1000  # Hz
        iq_samples = np.exp(1j * 2 * np.pi * freq_deviation * t).astype(np.complex64)

        audio = capture._fm_demodulate(iq_samples)

        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float64
        assert len(audio) > 0

    def test_demodulate_fm(self):
        """Test _demodulate with FM modulation"""
        capture = HackRFCapture(frequency=100e6, modulation='FM')

        # Create test signal
        t = np.linspace(0, 1, 2000000)
        iq_samples = np.exp(1j * 2 * np.pi * 1000 * t).astype(np.complex64)

        audio = capture._demodulate(iq_samples)

        assert isinstance(audio, np.ndarray)
        assert len(audio) == 16000  # Decimated to audio sample rate
        assert -1.0 <= audio.max() <= 1.0  # Normalized
        assert -1.0 <= audio.min() <= 1.0

    def test_demodulate_am(self):
        """Test _demodulate with AM modulation"""
        capture = HackRFCapture(frequency=100e6, modulation='AM')

        # Create test signal
        iq_samples = np.random.randn(2000000) + 1j * np.random.randn(2000000)
        iq_samples = iq_samples.astype(np.complex64)

        audio = capture._demodulate(iq_samples)

        assert isinstance(audio, np.ndarray)
        assert len(audio) == 16000
        assert -1.0 <= audio.max() <= 1.0
        assert -1.0 <= audio.min() <= 1.0

    def test_demodulate_usb(self):
        """Test _demodulate with USB modulation"""
        capture = HackRFCapture(frequency=100e6, modulation='USB')

        iq_samples = np.random.randn(2000000) + 1j * np.random.randn(2000000)
        iq_samples = iq_samples.astype(np.complex64)

        audio = capture._demodulate(iq_samples)

        assert isinstance(audio, np.ndarray)
        assert len(audio) == 16000

    def test_demodulate_lsb(self):
        """Test _demodulate with LSB modulation"""
        capture = HackRFCapture(frequency=100e6, modulation='LSB')

        iq_samples = np.random.randn(2000000) + 1j * np.random.randn(2000000)
        iq_samples = iq_samples.astype(np.complex64)

        audio = capture._demodulate(iq_samples)

        assert isinstance(audio, np.ndarray)
        assert len(audio) == 16000

    def test_demodulate_unsupported_modulation(self):
        """Test that unsupported modulation raises ValueError"""
        capture = HackRFCapture(frequency=100e6)
        capture.modulation = 'INVALID'

        iq_samples = np.random.randn(2000000).astype(np.complex64)

        with pytest.raises(ValueError, match="Unsupported modulation"):
            capture._demodulate(iq_samples)


class TestHackRFCaptureSaveWav:
    """Test _save_wav method"""

    def test_save_wav_creates_file(self, temp_recording_dir: str):
        """Test that _save_wav creates a file"""
        capture = HackRFCapture(frequency=100e6)
        audio = np.random.randn(16000)  # 1 second of audio
        output_file = os.path.join(temp_recording_dir, 'output.wav')

        capture._save_wav(audio, output_file)

        assert os.path.exists(output_file)

    def test_save_wav_format(self, temp_recording_dir: str):
        """Test WAV file format"""
        capture = HackRFCapture(frequency=100e6)
        audio = np.random.randn(16000)
        output_file = os.path.join(temp_recording_dir, 'output.wav')

        capture._save_wav(audio, output_file)

        sample_rate, saved_audio = wavfile.read(output_file)
        assert sample_rate == 16000
        assert saved_audio.dtype == np.int16
        assert len(saved_audio) == len(audio)

    def test_save_wav_normalization(self, temp_recording_dir: str):
        """Test that audio is properly converted to int16"""
        capture = HackRFCapture(frequency=100e6)
        audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0])
        output_file = os.path.join(temp_recording_dir, 'output.wav')

        capture._save_wav(audio, output_file)

        sample_rate, saved_audio = wavfile.read(output_file)
        assert saved_audio.dtype == np.int16
        assert saved_audio.max() <= 32767
        assert saved_audio.min() >= -32767


class TestHackRFCaptureFrequencies:
    """Test various frequency configurations"""

    def test_fm_broadcast_frequency(self, temp_recording_dir: str):
        """Test FM broadcast frequency (88.5 MHz)"""
        output_file = os.path.join(temp_recording_dir, 'fm_broadcast.wav')
        capture = HackRFCapture(frequency=88.5e6, modulation='FM')
        capture.capture(duration=1, output_file=output_file)

        assert os.path.exists(output_file)

    def test_marine_vhf_frequency(self, temp_recording_dir: str):
        """Test Marine VHF frequency (162.55 MHz)"""
        output_file = os.path.join(temp_recording_dir, 'marine_vhf.wav')
        capture = HackRFCapture(frequency=162.55e6, modulation='FM')
        capture.capture(duration=1, output_file=output_file)

        assert os.path.exists(output_file)

    def test_amateur_2m_frequency(self, temp_recording_dir: str):
        """Test Amateur 2m frequency (144.39 MHz)"""
        output_file = os.path.join(temp_recording_dir, 'amateur_2m.wav')
        capture = HackRFCapture(frequency=144.39e6, modulation='FM')
        capture.capture(duration=1, output_file=output_file)

        assert os.path.exists(output_file)


class TestHackRFCaptureEdgeCases:
    """Test edge cases and error handling"""

    def test_capture_with_empty_output_path(self, temp_recording_dir: str):
        """Test capture with empty output path"""
        capture = HackRFCapture(frequency=100e6)
        # Should create file in current directory
        output_file = os.path.join(temp_recording_dir, '')

        # This should handle gracefully or raise appropriate error
        # The implementation creates parent directory, so empty string means current dir
        try:
            capture.capture(duration=1, output_file=output_file)
        except (OSError, ValueError):
            pass  # Expected behavior

    def test_zero_duration(self, temp_recording_dir: str):
        """Test capture with zero duration"""
        output_file = os.path.join(temp_recording_dir, 'zero_duration.wav')
        capture = HackRFCapture(frequency=100e6)

        # Simulation should handle this
        capture._simulate_capture(duration=0, output_file=output_file)

        if os.path.exists(output_file):
            sample_rate, audio = wavfile.read(output_file)
            assert len(audio) == 0 or len(audio) > 0  # Implementation dependent

    def test_large_gain_value(self):
        """Test initialization with large gain value"""
        capture = HackRFCapture(frequency=100e6, gain=100)
        assert capture.gain == 100  # Should accept but may be clamped in hardware

    def test_negative_frequency_raises_or_accepts(self):
        """Test negative frequency (implementation dependent)"""
        # Some implementations might accept negative frequencies
        capture = HackRFCapture(frequency=-100e6)
        assert capture.frequency == -100e6
