#!/usr/bin/env python3
"""
SDR Hardware Abstraction Layer
Supports multiple SDR hardware types with automatic detection
"""

import os
import subprocess
import tempfile
import logging
import gc
import math
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray
from scipy import signal
from scipy.io import wavfile

logger = logging.getLogger(__name__)


def apply_hackrf_iq_correction(iq: NDArray[np.complex64]) -> NDArray[np.complex64]:
    """Apply 3-step IQ correction for HackRF zero-IF (direct-conversion) hardware.

    Step 1 - DC offset removal: subtract mean of I and Q independently.
    Step 2 - Amplitude imbalance correction: scale Q to match I power.
    Step 3 - Phase imbalance correction: Gram-Schmidt orthogonalisation.
    """
    i = iq.real.copy()
    q = iq.imag.copy()

    # Step 1: DC-Offset entfernen
    i -= np.mean(i)
    q -= np.mean(q)

    # Step 2: Amplituden-Imbalance korrigieren
    i_power = float(np.mean(i * i))
    q_power = float(np.mean(q * q))
    if q_power > 0:
        q *= np.sqrt(i_power / q_power)

    # Step 3: Phasen-Imbalance korrigieren (Gram-Schmidt)
    if i_power > 0:
        q -= (float(np.mean(i * q)) / i_power) * i

    return (i + 1j * q).astype(np.complex64)


class SDRType(Enum):
    """Supported SDR hardware types"""
    HACKRF = "hackrf"
    RTLSDR = "rtlsdr"
    AIRSPYHF = "airspyhf"
    USRP = "usrp"
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
            audio = np.abs(iq_samples).astype(np.float64)
        elif modulation in ('USB', 'LSB'):
            # Already at audio sample rate, skip the generic decimation below
            audio = self._ssb_demodulate(iq_samples, upper=(modulation == 'USB'))
        else:
            raise ValueError(f"Unsupported modulation: {modulation}")

        if modulation not in ('USB', 'LSB'):
            # Decimate to audio sample rate
            decimation_factor = int(self.sample_rate / self.audio_sample_rate)
            if decimation_factor > 1:
                audio = signal.decimate(audio, decimation_factor, zero_phase=True)

        # Normalize
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val

        return audio

    def _ssb_demodulate(self, iq_samples: NDArray[np.complex64], upper: bool) -> NDArray[np.float64]:
        """SSB demodulation that keeps only one sideband.

        Taking iq.real alone folds negative and positive frequencies onto each other,
        so USB and LSB stations (and neighbours up to the decimation cutoff) are heard
        together. Here the complex signal is decimated first (sideband information is
        kept), then a complex low-pass selects 300-2700 Hz above (USB) or below (LSB)
        the tuned frequency before the real part is taken.
        """
        # 1. Decimate the complex IQ to audio rate; resample_poly handles large factors
        #    and complex input and needs no integer ratio
        g = math.gcd(self.audio_sample_rate, self.sample_rate)
        baseband = signal.resample_poly(iq_samples.astype(np.complex128),
                                        self.audio_sample_rate // g, self.sample_rate // g)

        # 2. Move the middle of the voice band (+/-1500 Hz) to 0 Hz, low-pass +/-1200 Hz
        #    -> only 300-2700 Hz of the wanted sideband survives
        centre = 1500.0 if upper else -1500.0
        t = np.arange(len(baseband)) / self.audio_sample_rate
        baseband = baseband * np.exp(-2j * np.pi * centre * t)
        taps = signal.firwin(255, 1200.0, fs=self.audio_sample_rate)
        baseband = signal.lfilter(taps, 1.0, baseband)

        # 3. Move back and take the real part = audio
        audio = (baseband * np.exp(2j * np.pi * centre * t)).real
        return np.asarray(audio, dtype=np.float64)

    def _fm_demodulate(self, iq_samples: NDArray[np.complex64]) -> NDArray[np.float64]:
        """FM demodulation using phase differentiation"""
        phase = np.angle(iq_samples)
        audio = np.diff(phase)
        audio = np.unwrap(audio)

        # Low-pass filter
        b, a = signal.butter(5, 0.1)
        filtered: NDArray[np.float64] = np.asarray(signal.filtfilt(b, a, audio), dtype=np.float64)

        return filtered

    def _save_wav(self, audio: NDArray[np.float64], output_file: str) -> None:
        """Save audio to WAV file"""
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

        # Convert to int16
        audio_int16 = (audio * 32767).astype(np.int16)

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
                '-n', str(num_samples)  # complex samples (I+Q pairs), not bytes
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
            iq_samples = apply_hackrf_iq_correction(iq_samples)

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
            return result.returncode == 0 or "Found" in result.stdout
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

        # rtl_sdr -n counts complex samples (it reads 2 bytes per sample itself)
        num_samples = int(duration * self.sample_rate)

        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmpfile:
            raw_file = tmpfile.name

        try:
            # RTL-SDR capture command
            cmd = [
                'rtl_sdr',
                '-f', str(int(self.frequency)),
                '-s', str(self.sample_rate),
                '-g', str(self.gain),
                '-n', str(num_samples),
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


class AirspyHFCapture(SDRCapture):
    """Airspy HF+ implementation"""

    def is_available(self) -> bool:
        """Check if Airspy HF+ is connected"""
        try:
            result = subprocess.run(
                ['airspyhf_info'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and b"S/N:" in result.stdout.encode()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_frequency_range(self) -> Tuple[int, int]:
        """
        Airspy HF+ covers 0.5 kHz to 31 MHz (HF) and 60-260 MHz (VHF)
        Note: Gap between 31-60 MHz is not supported by hardware
        """
        return (500, 260_000_000)

    def get_max_sample_rate(self) -> int:
        """Airspy HF+ max sample rate is 912 kHz (we use 768 kHz as standard)"""
        return 912_000

    def capture_iq(self, duration: int, output_file: str) -> None:
        """Capture raw IQ samples using Airspy HF+"""
        self.logger.info(f"Airspy HF+ IQ capture: {self.frequency/1e6:.3f} MHz, {duration}s")

        # airspyhf_rx -n counts complex samples (I+Q pairs)
        num_samples = int(duration * self.sample_rate)

        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmpfile:
            raw_file = tmpfile.name

        try:
            # Airspy HF+ capture command
            # Frequency in MHz, -m on enables HF AGC
            cmd = [
                'airspyhf_rx',
                '-r', raw_file,
                '-f', f"{self.frequency / 1_000_000:.6f}",  # Frequency in MHz
                '-n', str(num_samples),
                '-m', 'on'  # Enable HF AGC
            ]

            self.logger.info(f"Running: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration * 2 + 15
            )

            if result.returncode != 0:
                raise RuntimeError(f"airspyhf_rx failed: {result.stderr}")

            # Read raw IQ samples (int16 signed)
            iq_data = np.fromfile(raw_file, dtype=np.int16)

            # Convert to complex64 (Airspy HF+ normalization: divide by 32768.0)
            i_samples = iq_data[0::2].astype(np.float32) / 32768.0
            q_samples = iq_data[1::2].astype(np.float32) / 32768.0
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
        """Capture and demodulate to audio using Airspy HF+"""
        self.logger.info(f"Airspy HF+ audio capture: {self.frequency/1e6:.3f} MHz, "
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


class USRPCapture(SDRCapture):
    """Ettus Research USRP N200 implementation (Gigabit Ethernet via UHD)"""

    def __init__(self, frequency: int, sample_rate: int = 2_000_000, gain: int = 20,
                 device_address: str = ''):
        super().__init__(frequency, sample_rate, gain)
        self.device_address = device_address

    def is_available(self) -> bool:
        """Check if USRP is reachable at device_address"""
        if not self.device_address:
            return False
        try:
            result = subprocess.run(
                ['uhd_usrp_probe', f'--args=addr={self.device_address}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_frequency_range(self) -> Tuple[int, int]:
        """USRP N200 with WBX daughterboard: 50 MHz – 2.2 GHz"""
        return (50_000_000, 2_200_000_000)

    def get_max_sample_rate(self) -> int:
        """USRP N200 max: 25 MS/s (100 MS/s ADC with 4x minimum decimation)"""
        return 25_000_000

    def capture_iq(self, duration: int, output_file: str) -> None:
        """Capture raw IQ samples using uhd_rx_cfile"""
        self.logger.info(f"USRP IQ capture: {self.frequency/1e6:.3f} MHz, {duration}s, addr={self.device_address}")

        num_samples = int(duration * self.sample_rate)

        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmpfile:
            raw_file = tmpfile.name

        try:
            cmd = [
                'uhd_rx_cfile',
                f'--args=addr={self.device_address}',
                '-f', str(int(self.frequency)),
                '-r', str(self.sample_rate),
                '-g', str(self.gain),
                '-N', str(num_samples),
                '--type', 'short',
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
                raise RuntimeError(f"uhd_rx_cfile failed: {result.stderr}")

            # Read raw IQ samples (int16 signed, I/Q interleaved)
            iq_data = np.fromfile(raw_file, dtype=np.int16)

            # Convert to complex64 (USRP: int16, divide by 32768.0)
            i_samples = iq_data[0::2].astype(np.float32) / 32768.0
            q_samples = iq_data[1::2].astype(np.float32) / 32768.0
            iq_samples = (i_samples + 1j * q_samples).astype(np.complex64)

            os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
            iq_samples.tofile(output_file)

            self.logger.info(f"IQ capture complete: {len(iq_samples)} samples, "
                             f"{os.path.getsize(output_file) / 1024 / 1024:.1f} MB")

        finally:
            if os.path.exists(raw_file):
                os.unlink(raw_file)

    def capture_audio(self, duration: int, output_file: str, modulation: str = 'FM') -> None:
        """Capture and demodulate to audio using USRP"""
        self.logger.info(f"USRP audio capture: {self.frequency/1e6:.3f} MHz, {modulation}, {duration}s")

        with tempfile.NamedTemporaryFile(suffix='.iq', delete=False) as tmpfile:
            iq_file = tmpfile.name

        try:
            self.capture_iq(duration, iq_file)

            iq_samples = np.fromfile(iq_file, dtype=np.complex64)
            audio = self._demodulate(iq_samples, modulation)
            self._save_wav(audio, output_file)

            del iq_samples, audio
            gc.collect()

            self.logger.info(f"Audio capture complete: {output_file}")

        finally:
            if os.path.exists(iq_file):
                os.unlink(iq_file)


def detect_sdr(preferred_type: Optional[str] = None,
               device_address: Optional[str] = None) -> SDRType:
    """
    Detect available SDR hardware.

    Args:
        preferred_type: Explicit SDR type string ('hackrf', 'rtlsdr', 'airspyhf', 'usrp',
                        'auto', or None). When set and not 'auto', only that type is tried.
        device_address: IP address for USRP N200 (required when preferred_type='usrp').

    Priority for auto-detect: HackRF > Airspy HF+ > RTL-SDR
    """
    logger.info("Detecting SDR hardware...")

    _type_map: dict[str, SDRType] = {
        'hackrf': SDRType.HACKRF,
        'rtlsdr': SDRType.RTLSDR,
        'airspyhf': SDRType.AIRSPYHF,
        'usrp': SDRType.USRP,
    }

    # Explicit device type requested (not auto)
    if preferred_type and preferred_type.lower() not in ('auto', ''):
        pt = preferred_type.lower()
        if pt == 'usrp':
            if not device_address:
                logger.warning("USRP selected but no device_address provided")
                return SDRType.UNKNOWN
            usrp = USRPCapture(frequency=100_000_000, device_address=device_address)
            if usrp.is_available():
                logger.info(f"Detected: USRP N200 at {device_address}")
                return SDRType.USRP
            logger.warning(f"USRP N200 not reachable at {device_address}")
            return SDRType.UNKNOWN
        sdr_type = _type_map.get(pt)
        if sdr_type:
            logger.info(f"Using explicitly selected SDR type: {sdr_type.value}")
            return sdr_type
        logger.warning(f"Unknown preferred_type '{preferred_type}', falling back to auto-detect")

    # Auto-detect: HackRF > Airspy HF+ > RTL-SDR
    hackrf = HackRFCapture(frequency=100_000_000)
    if hackrf.is_available():
        logger.info("Detected: HackRF One")
        return SDRType.HACKRF

    airspyhf = AirspyHFCapture(frequency=100_000_000)
    if airspyhf.is_available():
        logger.info("Detected: Airspy HF+")
        return SDRType.AIRSPYHF

    rtlsdr = RTLSDRCapture(frequency=100_000_000)
    if rtlsdr.is_available():
        logger.info("Detected: RTL-SDR")
        return SDRType.RTLSDR

    logger.warning("No SDR hardware detected")
    return SDRType.UNKNOWN


def get_sdr_instance(frequency: int, sample_rate: int = 2_000_000, gain: int = 20,
                     sdr_type: Optional[SDRType] = None,
                     device_address: Optional[str] = None) -> SDRCapture:
    """
    Factory function to get appropriate SDR instance with validation

    Args:
        frequency: Center frequency in Hz
        sample_rate: Sample rate in Hz
        gain: RF gain in dB
        sdr_type: Force specific SDR type (optional, auto-detect if None)
        device_address: IP address for USRP N200 (required when sdr_type=USRP)

    Returns:
        SDRCapture instance

    Raises:
        RuntimeError: If no SDR hardware detected
        ValueError: If frequency or sample rate out of range, or USRP without address
    """
    # Auto-detect if not specified
    if sdr_type is None:
        sdr_type = detect_sdr()

    if sdr_type == SDRType.UNKNOWN:
        raise RuntimeError(
            "No SDR hardware detected. Please connect HackRF One, RTL-SDR, Airspy HF+, "
            "or specify a USRP N200 IP address."
        )

    # Create instance
    instance: SDRCapture
    if sdr_type == SDRType.HACKRF:
        instance = HackRFCapture(frequency, sample_rate, gain)
    elif sdr_type == SDRType.AIRSPYHF:
        clamped_rate = min(sample_rate, 912_000)
        if clamped_rate != sample_rate:
            logger.warning(
                f"Sample rate clamped from {sample_rate/1e6:.3f} MHz to "
                f"{clamped_rate/1e6:.3f} MHz (Airspy HF+ max)"
            )
        instance = AirspyHFCapture(frequency, clamped_rate, gain)
    elif sdr_type == SDRType.RTLSDR:
        instance = RTLSDRCapture(frequency, sample_rate, gain)
    elif sdr_type == SDRType.USRP:
        if not device_address:
            raise ValueError("USRP N200 requires a device_address (IP address)")
        clamped_rate = min(sample_rate, 25_000_000)
        if clamped_rate != sample_rate:
            logger.warning(
                f"Sample rate clamped from {sample_rate/1e6:.3f} MHz to "
                f"{clamped_rate/1e6:.3f} MHz (USRP N200 max)"
            )
        instance = USRPCapture(frequency, clamped_rate, gain, device_address)
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
