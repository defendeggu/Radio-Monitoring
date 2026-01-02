#!/usr/bin/env python3
"""
SDR Hardware Abstraction Layer
Supports multiple SDR hardware types with automatic detection
"""

import os
import sys
import subprocess
import tempfile
import logging
import gc
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray
from scipy import signal
from scipy.io import wavfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SDRType(Enum):
    """Supported SDR hardware types"""
    HACKRF = "hackrf"
    RTLSDR = "rtlsdr"
    UNKNOWN = "unknown"


class SDRCapture(ABC):
    """Abstract base class for SDR hardware implementations"""

    def __init__(self, frequency: int, sample_rate: int = 2_000_000, gain: int = 20):
        """
        Initialize SDR capture

        Args:
            frequency: Center frequency in Hz
            sample_rate: Sample rate in Hz (default 2MHz)
            gain: RF gain in dB
        """
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.gain = gain
        self.audio_sample_rate = 16000  # For Whisper compatibility
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this SDR hardware is connected and ready"""
        pass

    @abstractmethod
    def capture_iq(self, duration: int, output_file: str) -> None:
        """
        Capture raw IQ samples to file as complex64

        Args:
            duration: Recording duration in seconds
            output_file: Output IQ file path
        """
        pass

    @abstractmethod
    def capture_audio(self, duration: int, output_file: str, modulation: str = 'FM') -> None:
        """
        Capture and demodulate to audio file

        Args:
            duration: Recording duration in seconds
            output_file: Output WAV file path
            modulation: Modulation type (FM, AM, USB, LSB)
        """
        pass

    @abstractmethod
    def get_frequency_range(self) -> Tuple[int, int]:
        """Return (min_freq, max_freq) in Hz"""
        pass

    @abstractmethod
    def get_max_sample_rate(self) -> int:
        """Return maximum supported sample rate in Hz"""
        pass

    def _demodulate(self, iq_samples: NDArray[np.complex64], modulation: str) -> NDArray[np.float64]:
        """Demodulate IQ samples based on modulation type"""
        modulation = modulation.upper()

        if modulation == 'FM':
            audio = self._fm_demodulate(iq_samples)
        elif modulation == 'AM':
            audio = np.abs(iq_samples)
        elif modulation == 'USB':
            audio = iq_samples.real
        elif modulation == 'LSB':
            audio = -iq_samples.real
        else:
            raise ValueError(f"Unsupported modulation: {modulation}")

        # Decimate to audio sample rate
        decimation_factor = int(self.sample_rate / self.audio_sample_rate)
        if decimation_factor > 1:
            audio = signal.decimate(audio, decimation_factor, zero_phase=True)

        # Normalize
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val

        return audio

    def _fm_demodulate(self, iq_samples: NDArray[np.complex64]) -> NDArray[np.float64]:
        """FM demodulation using phase differentiation"""
        phase = np.angle(iq_samples)
        audio = np.diff(phase)
        audio = np.unwrap(audio)

        # Low-pass filter
        b, a = signal.butter(5, 0.1)
        audio = signal.filtfilt(b, a, audio)

        return audio

    def _save_wav(self, audio: NDArray[np.float64], output_file: str) -> None:
        """Save audio to WAV file"""
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

        # Convert to int16
        audio_int16 = np.int16(audio * 32767)

        # Save WAV file
        wavfile.write(output_file, self.audio_sample_rate, audio_int16)


class HackRFCapture(SDRCapture):
    """HackRF One implementation"""

    def is_available(self) -> bool:
        """Check if HackRF is connected"""
        try:
            result = subprocess.run(
                ['hackrf_info'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and b"Serial number" in result.stdout.encode()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_frequency_range(self) -> Tuple[int, int]:
        """HackRF covers 1 MHz to 6 GHz"""
        return (1_000_000, 6_000_000_000)

    def get_max_sample_rate(self) -> int:
        """HackRF max sample rate is 20 MHz"""
        return 20_000_000

    def capture_iq(self, duration: int, output_file: str) -> None:
        """Capture raw IQ samples using HackRF"""
        self.logger.info(f"HackRF IQ capture: {self.frequency/1e6:.3f} MHz, {duration}s")

        num_samples = int(duration * self.sample_rate)

        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmpfile:
            raw_file = tmpfile.name

        try:
            # HackRF capture command
            cmd = [
                'hackrf_transfer',
                '-r', raw_file,
                '-f', str(int(self.frequency)),
                '-s', str(self.sample_rate),
                '-l', str(self.gain),
                '-g', str(self.gain),
                '-n', str(num_samples * 2)  # * 2 for I and Q
            ]

            self.logger.info(f"Running: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration * 2 + 15
            )

            if result.returncode != 0:
                raise RuntimeError(f"hackrf_transfer failed: {result.stderr}")

            # Read raw IQ samples (int8 signed)
            iq_data = np.fromfile(raw_file, dtype=np.int8)

            # Convert to complex64 (HackRF normalization: divide by 127.0)
            i_samples = iq_data[0::2].astype(np.float32) / 127.0
            q_samples = iq_data[1::2].astype(np.float32) / 127.0
            iq_samples = (i_samples + 1j * q_samples).astype(np.complex64)

            # Save IQ samples
            os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
            iq_samples.tofile(output_file)

            self.logger.info(f"IQ capture complete: {len(iq_samples)} samples, "
                           f"{os.path.getsize(output_file) / 1024 / 1024:.1f} MB")

        finally:
            if os.path.exists(raw_file):
                os.unlink(raw_file)

    def capture_audio(self, duration: int, output_file: str, modulation: str = 'FM') -> None:
        """Capture and demodulate to audio using HackRF"""
        self.logger.info(f"HackRF audio capture: {self.frequency/1e6:.3f} MHz, "
                        f"{modulation}, {duration}s")

        # Capture IQ samples to temp file
        with tempfile.NamedTemporaryFile(suffix='.iq', delete=False) as tmpfile:
            iq_file = tmpfile.name

        try:
            self.capture_iq(duration, iq_file)

            # Load and demodulate
            iq_samples = np.fromfile(iq_file, dtype=np.complex64)
            audio = self._demodulate(iq_samples, modulation)
            self._save_wav(audio, output_file)

            # Force garbage collection to free memory from large arrays
            del iq_samples, audio
            gc.collect()

            self.logger.info(f"Audio capture complete: {output_file}")

        finally:
            if os.path.exists(iq_file):
                os.unlink(iq_file)


class RTLSDRCapture(SDRCapture):
    """RTL-SDR implementation"""

    def is_available(self) -> bool:
        """Check if RTL-SDR is connected"""
        try:
            result = subprocess.run(
                ['rtl_test', '-t'],
                capture_output=True,
                text=True,
                timeout=3
            )
            # rtl_test returns 0 on success or if device found
            return result.returncode == 0 or b"Found" in result.stdout.encode()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_frequency_range(self) -> Tuple[int, int]:
        """RTL-SDR covers 24 MHz to 1766 MHz"""
        return (24_000_000, 1_766_000_000)

    def get_max_sample_rate(self) -> int:
        """RTL-SDR max sample rate is 3.2 MHz"""
        return 3_200_000

    def capture_iq(self, duration: int, output_file: str) -> None:
        """Capture raw IQ samples using RTL-SDR"""
        self.logger.info(f"RTL-SDR IQ capture: {self.frequency/1e6:.3f} MHz, {duration}s")

        num_samples = int(duration * self.sample_rate)
        num_bytes = num_samples * 2  # I and Q samples

        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmpfile:
            raw_file = tmpfile.name

        try:
            # RTL-SDR capture command
            cmd = [
                'rtl_sdr',
                '-f', str(int(self.frequency)),
                '-s', str(self.sample_rate),
                '-g', str(self.gain),
                '-n', str(num_bytes),
                raw_file
            ]

            self.logger.info(f"Running: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration * 2 + 15
            )

            if result.returncode != 0:
                raise RuntimeError(f"rtl_sdr failed: {result.stderr}")

            # Read raw IQ samples (uint8 unsigned)
            iq_data = np.fromfile(raw_file, dtype=np.uint8)

            # Convert to complex64 (RTL-SDR normalization: center then divide)
            # RTL-SDR outputs 0-255, center around 127.5, then normalize
            i_samples = (iq_data[0::2].astype(np.float32) - 127.5) / 127.5
            q_samples = (iq_data[1::2].astype(np.float32) - 127.5) / 127.5
            iq_samples = (i_samples + 1j * q_samples).astype(np.complex64)

            # Save IQ samples
            os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
            iq_samples.tofile(output_file)

            self.logger.info(f"IQ capture complete: {len(iq_samples)} samples, "
                           f"{os.path.getsize(output_file) / 1024 / 1024:.1f} MB")

        finally:
            if os.path.exists(raw_file):
                os.unlink(raw_file)

    def capture_audio(self, duration: int, output_file: str, modulation: str = 'FM') -> None:
        """Capture and demodulate to audio using RTL-SDR"""
        self.logger.info(f"RTL-SDR audio capture: {self.frequency/1e6:.3f} MHz, "
                        f"{modulation}, {duration}s")

        modulation = modulation.upper()

        if modulation == 'FM':
            # Use rtl_fm for direct FM demodulation (more efficient)
            self._capture_fm_direct(duration, output_file)
        else:
            # For AM/SSB, capture IQ then demodulate manually
            with tempfile.NamedTemporaryFile(suffix='.iq', delete=False) as tmpfile:
                iq_file = tmpfile.name

            try:
                self.capture_iq(duration, iq_file)

                # Load and demodulate
                iq_samples = np.fromfile(iq_file, dtype=np.complex64)
                audio = self._demodulate(iq_samples, modulation)
                self._save_wav(audio, output_file)

                # Force garbage collection to free memory from large arrays
                del iq_samples, audio
                gc.collect()

                self.logger.info(f"Audio capture complete: {output_file}")

            finally:
                if os.path.exists(iq_file):
                    os.unlink(iq_file)

    def _capture_fm_direct(self, duration: int, output_file: str) -> None:
        """Use rtl_fm for direct FM demodulation"""
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmpfile:
            raw_audio_file = tmpfile.name

        try:
            # rtl_fm outputs 16kHz audio by default
            cmd = [
                'timeout', str(duration + 5),  # Add timeout wrapper
                'rtl_fm',
                '-f', str(int(self.frequency)),
                '-s', str(200000),  # 200kHz for FM broadcast
                '-g', str(self.gain),
                '-M', 'fm',
                '-r', str(self.audio_sample_rate),
                raw_audio_file
            ]

            self.logger.info(f"Running: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration + 10
            )

            # rtl_fm with timeout returns 124 when killed by timeout (expected)
            if result.returncode not in [0, 124]:
                raise RuntimeError(f"rtl_fm failed: {result.stderr}")

            # Read raw audio (16-bit signed PCM)
            audio = np.fromfile(raw_audio_file, dtype=np.int16)

            # Normalize to float
            audio_float = audio.astype(np.float64) / 32767.0

            # Save as WAV
            self._save_wav(audio_float, output_file)

            self.logger.info(f"FM capture complete: {output_file}")

        finally:
            if os.path.exists(raw_audio_file):
                os.unlink(raw_audio_file)


def detect_sdr() -> SDRType:
    """
    Auto-detect available SDR hardware
    Prefer HackRF if both are connected (better specs)
    """
    logger.info("Detecting SDR hardware...")

    # Check HackRF first (preferred)
    hackrf = HackRFCapture(frequency=100_000_000)
    if hackrf.is_available():
        logger.info("Detected: HackRF One")
        return SDRType.HACKRF

    # Check RTL-SDR
    rtlsdr = RTLSDRCapture(frequency=100_000_000)
    if rtlsdr.is_available():
        logger.info("Detected: RTL-SDR")
        return SDRType.RTLSDR

    logger.warning("No SDR hardware detected")
    return SDRType.UNKNOWN


def get_sdr_instance(frequency: int, sample_rate: int = 2_000_000, gain: int = 20,
                     sdr_type: Optional[SDRType] = None) -> SDRCapture:
    """
    Factory function to get appropriate SDR instance with validation

    Args:
        frequency: Center frequency in Hz
        sample_rate: Sample rate in Hz
        gain: RF gain in dB
        sdr_type: Force specific SDR type (optional, auto-detect if None)

    Returns:
        SDRCapture instance

    Raises:
        RuntimeError: If no SDR hardware detected
        ValueError: If frequency or sample rate out of range for detected SDR
    """
    # Auto-detect if not specified
    if sdr_type is None:
        sdr_type = detect_sdr()

    if sdr_type == SDRType.UNKNOWN:
        raise RuntimeError(
            "No SDR hardware detected. Please connect HackRF One or RTL-SDR."
        )

    # Create instance
    if sdr_type == SDRType.HACKRF:
        instance = HackRFCapture(frequency, sample_rate, gain)
    elif sdr_type == SDRType.RTLSDR:
        instance = RTLSDRCapture(frequency, sample_rate, gain)
    else:
        raise ValueError(f"Unsupported SDR type: {sdr_type}")

    # Validate frequency range
    min_freq, max_freq = instance.get_frequency_range()
    if not (min_freq <= frequency <= max_freq):
        raise ValueError(
            f"{sdr_type.value.upper()} does not support {frequency/1e6:.3f} MHz. "
            f"Valid range: {min_freq/1e6:.3f} - {max_freq/1e6:.3f} MHz"
        )

    # Validate and clamp sample rate
    max_rate = instance.get_max_sample_rate()
    if sample_rate > max_rate:
        logger.warning(
            f"Requested sample rate {sample_rate/1e6:.1f} MHz exceeds "
            f"maximum {max_rate/1e6:.1f} MHz. Clamping to maximum."
        )
        instance.sample_rate = max_rate

    return instance


# Compatibility alias for existing code
HackRFCapture_Legacy = HackRFCapture
