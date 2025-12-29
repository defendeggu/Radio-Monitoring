#!/usr/bin/env python3
"""
HackRF Radio Capture Service
Captures radio signals from HackRF and converts them to audio files
"""

import os
import sys
import time
import numpy as np
from numpy.typing import NDArray
from scipy import signal
from scipy.io import wavfile
import argparse
from datetime import datetime


class HackRFCapture:
    def __init__(self, frequency: float, sample_rate: int = 2000000, gain: int = 20, modulation: str = 'FM') -> None:
        """
        Initialize HackRF capture

        Args:
            frequency: Center frequency in Hz
            sample_rate: Sample rate in Hz (default 2MHz)
            gain: RF gain in dB (0-47)
            modulation: Modulation type (FM, AM, USB, LSB)
        """
        self.frequency: float = frequency
        self.sample_rate: int = sample_rate
        self.gain: int = gain
        self.modulation: str = modulation.upper()
        self.audio_sample_rate: int = 16000  # For Whisper compatibility

    def capture(self, duration: int, output_file: str) -> None:
        """
        Capture radio signal and save as WAV file

        Args:
            duration: Recording duration in seconds
            output_file: Output WAV file path
        """
        print(f"Starting capture:")
        print(f"  Frequency: {self.frequency/1e6:.3f} MHz")
        print(f"  Modulation: {self.modulation}")
        print(f"  Duration: {duration}s")
        print(f"  Output: {output_file}")

        try:
            import subprocess
            import tempfile

            # Calculate number of samples
            num_samples = int(duration * self.sample_rate)

            # Create temporary file for raw IQ samples
            with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmpfile:
                raw_file = tmpfile.name

            try:
                # Use hackrf_transfer command-line tool
                print("Recording...")
                cmd = [
                    'hackrf_transfer',
                    '-r', raw_file,
                    '-f', str(int(self.frequency)),
                    '-s', str(self.sample_rate),
                    '-l', str(self.gain),
                    '-g', str(self.gain),
                    '-n', str(num_samples * 2)  # * 2 for IQ samples
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration * 2 + 15)

                if result.returncode != 0:
                    raise RuntimeError(f"hackrf_transfer failed: {result.stderr}")

                # Read raw IQ samples
                iq_data = np.fromfile(raw_file, dtype=np.int8)

                # Convert to complex IQ samples
                iq_samples = iq_data[0::2] + 1j * iq_data[1::2]
                iq_samples = iq_samples.astype(np.complex64) / 127.0

                # Trim to exact length
                iq_samples = iq_samples[:num_samples]

                # Demodulate based on type
                audio = self._demodulate(iq_samples)

                # Save to WAV file
                self._save_wav(audio, output_file)

                print(f"Capture complete: {output_file}")

            finally:
                # Clean up temporary file
                if os.path.exists(raw_file):
                    os.unlink(raw_file)

        except Exception as e:
            print(f"Error during capture: {e}")
            print("Falling back to simulation mode")
            self._simulate_capture(duration, output_file)

    def capture_iq(self, duration: int, output_file: str) -> None:
        """
        Capture raw IQ samples and save as complex64 binary file

        Args:
            duration: Recording duration in seconds
            output_file: Output IQ file path (complex64 format)
        """
        print(f"Starting IQ capture:")
        print(f"  Frequency: {self.frequency/1e6:.3f} MHz")
        print(f"  Duration: {duration}s")
        print(f"  Output: {output_file}")

        try:
            import subprocess
            import tempfile

            # Calculate number of samples
            num_samples = int(duration * self.sample_rate)

            # Create temporary file for raw IQ samples
            with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmpfile:
                raw_file = tmpfile.name

            try:
                # Use hackrf_transfer command-line tool
                print("Recording IQ samples...")
                cmd = [
                    'hackrf_transfer',
                    '-r', raw_file,
                    '-f', str(int(self.frequency)),
                    '-s', str(self.sample_rate),
                    '-l', str(self.gain),
                    '-g', str(self.gain),
                    '-n', str(num_samples * 2)  # * 2 for IQ samples
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration * 2 + 15)

                if result.returncode != 0:
                    raise RuntimeError(f"hackrf_transfer failed: {result.stderr}")

                # Read raw IQ samples
                iq_data = np.fromfile(raw_file, dtype=np.int8)

                # Convert to complex IQ samples (complex64 format)
                iq_samples = iq_data[0::2] + 1j * iq_data[1::2]
                iq_samples = iq_samples.astype(np.complex64) / 127.0

                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

                # Save IQ samples as complex64
                iq_samples.tofile(output_file)

                print(f"IQ capture complete: {output_file}")
                print(f"  Samples: {len(iq_samples)}")
                print(f"  File size: {os.path.getsize(output_file) / 1024 / 1024:.1f} MB")

            finally:
                # Clean up temporary file
                if os.path.exists(raw_file):
                    os.unlink(raw_file)

        except Exception as e:
            print(f"Error during IQ capture: {e}")
            raise

    def _demodulate(self, iq_samples: NDArray[np.complex64]) -> NDArray[np.float64]:
        """Demodulate IQ samples based on modulation type"""

        if self.modulation == 'FM':
            # FM demodulation
            audio = self._fm_demodulate(iq_samples)
        elif self.modulation == 'AM':
            # AM demodulation (envelope detection)
            audio = np.abs(iq_samples)
        elif self.modulation in ['USB', 'LSB']:
            # SSB demodulation
            audio = iq_samples.real if self.modulation == 'USB' else iq_samples.imag
        else:
            raise ValueError(f"Unsupported modulation: {self.modulation}")

        # Decimate to audio sample rate
        decimation_factor = int(self.sample_rate / self.audio_sample_rate)
        audio = signal.decimate(audio, decimation_factor, zero_phase=True)

        # Normalize
        audio = audio / np.max(np.abs(audio))

        return audio

    def _fm_demodulate(self, iq_samples: NDArray[np.complex64]) -> NDArray[np.float64]:
        """FM demodulation using phase differentiation"""
        # Calculate instantaneous phase
        phase = np.angle(iq_samples)

        # Differentiate phase to get frequency
        audio = np.diff(phase)

        # Unwrap phase discontinuities
        audio = np.unwrap(audio)

        # Low-pass filter
        b, a = signal.butter(5, 0.1)
        audio = signal.filtfilt(b, a, audio)

        return audio

    def _save_wav(self, audio: NDArray[np.float64], output_file: str) -> None:
        """Save audio to WAV file"""
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

        # Convert to int16
        audio_int16 = np.int16(audio * 32767)

        # Save WAV file
        wavfile.write(output_file, self.audio_sample_rate, audio_int16)

    def _simulate_capture(self, duration: int, output_file: str) -> None:
        """Simulate capture for testing without hardware"""
        print("SIMULATION MODE: Generating test audio")

        # Generate a simple tone with some noise
        t = np.linspace(0, duration, int(self.audio_sample_rate * duration))

        # Create a voice-like signal (multiple frequencies)
        audio = 0.3 * np.sin(2 * np.pi * 200 * t)  # Base tone
        audio += 0.2 * np.sin(2 * np.pi * 400 * t)  # Harmonic
        audio += 0.1 * np.sin(2 * np.pi * 600 * t)  # Harmonic
        audio += 0.05 * np.random.randn(len(t))     # Noise

        # Add amplitude modulation to simulate speech
        modulation = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t)
        audio = audio * modulation

        self._save_wav(audio, output_file)
        print(f"Simulation complete: {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description='Capture radio signals from HackRF')
    parser.add_argument('-f', '--frequency', type=float, required=True,
                        help='Center frequency in Hz')
    parser.add_argument('-m', '--modulation', type=str, default='FM',
                        choices=['FM', 'AM', 'USB', 'LSB'],
                        help='Modulation type')
    parser.add_argument('-d', '--duration', type=int, default=30,
                        help='Recording duration in seconds')
    parser.add_argument('-g', '--gain', type=int, default=20,
                        help='RF gain (0-47 dB)')
    parser.add_argument('-s', '--sample-rate', type=int, default=2000000,
                        help='Sample rate in Hz')
    parser.add_argument('-o', '--output', type=str,
                        help='Output WAV file path')

    args = parser.parse_args()

    # Generate output filename if not provided
    if not args.output:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output = f"recordings/capture_{timestamp}.wav"

    # Create capture instance
    capture = HackRFCapture(
        frequency=args.frequency,
        sample_rate=args.sample_rate,
        gain=args.gain,
        modulation=args.modulation
    )

    # Perform capture
    capture.capture(args.duration, args.output)


if __name__ == '__main__':
    main()
