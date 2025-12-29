#!/usr/bin/env python3
"""
Repeater Activity Analyzer

Analyzes IQ samples from radio captures to detect carrier activity and measure
repeater usage statistics.

Algorithm:
1. Calibration: Use first 2 seconds to establish noise floor baseline
2. RMS Power Calculation: Sliding window (100ms) RMS power from I/Q samples
3. Carrier Detection: RMS power exceeds noise_floor × threshold_multiplier
4. Transmission Segmentation: Group carrier events with minimum gap/duration
5. Activity Metrics: Calculate transmission count, duration, and percentage

Author: Radio Monitoring System
License: MIT
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransmissionEvent:
    """
    Represents a single transmission detected in the recording.

    Attributes:
        start_offset: Start time in seconds from beginning of recording
        duration: Duration of transmission in seconds
        avg_strength: Average signal strength in dB
        peak_strength: Peak signal strength in dB
    """
    start_offset: float
    duration: float
    avg_strength: float
    peak_strength: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'start_offset': round(self.start_offset, 3),
            'duration': round(self.duration, 3),
            'avg_strength': round(self.avg_strength, 2),
            'peak_strength': round(self.peak_strength, 2)
        }


@dataclass
class ActivityMetrics:
    """
    Container for repeater activity analysis results.

    Attributes:
        carrier_detected: Whether any carrier activity was detected
        transmission_count: Number of distinct transmissions
        total_active_seconds: Total time with carrier present
        activity_percentage: Percentage of time with carrier (0-100)
        average_signal_strength: Average signal strength across all activity (dB)
        peak_signal_strength: Maximum signal strength detected (dB)
        noise_floor: Calculated noise floor baseline (dB)
        transmissions: List of individual transmission events
    """
    carrier_detected: bool
    transmission_count: int
    total_active_seconds: float
    activity_percentage: float
    average_signal_strength: Optional[float]
    peak_signal_strength: Optional[float]
    noise_floor: float
    transmissions: List[TransmissionEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'carrier_detected': self.carrier_detected,
            'transmission_count': self.transmission_count,
            'total_active_seconds': round(self.total_active_seconds, 2),
            'activity_percentage': round(self.activity_percentage, 2),
            'average_signal_strength': round(self.average_signal_strength, 2) if self.average_signal_strength else None,
            'peak_signal_strength': round(self.peak_signal_strength, 2) if self.peak_signal_strength else None,
            'noise_floor': round(self.noise_floor, 2),
            'transmissions': [t.to_dict() for t in self.transmissions]
        }


class RepeaterActivityAnalyzer:
    """
    Analyzes radio captures to detect and measure repeater activity.

    Uses RMS power analysis with adaptive noise floor calibration to detect
    carrier presence and segment individual transmissions.
    """

    def __init__(
        self,
        sample_rate: int = 2_000_000,
        audio_rate: int = 48000,
        threshold_multiplier: float = 1.5,
        min_transmission_seconds: float = 1.0,
        min_gap_seconds: float = 0.5,
        calibration_seconds: float = 2.0,
        window_seconds: float = 0.1
    ):
        """
        Initialize the activity analyzer.

        Args:
            sample_rate: IQ sample rate in Hz (default: 2 MHz)
            audio_rate: Audio sample rate in Hz (default: 48 kHz)
            threshold_multiplier: Multiplier above noise floor for carrier detection (default: 1.5)
            min_transmission_seconds: Minimum transmission duration to count (default: 1.0s)
            min_gap_seconds: Minimum gap between transmissions (default: 0.5s)
            calibration_seconds: Duration for noise floor calibration (default: 2.0s)
            window_seconds: RMS calculation window size (default: 0.1s)
        """
        self.sample_rate = sample_rate
        self.audio_rate = audio_rate
        self.threshold_multiplier = threshold_multiplier
        self.min_transmission_seconds = min_transmission_seconds
        self.min_gap_seconds = min_gap_seconds
        self.calibration_seconds = calibration_seconds
        self.window_seconds = window_seconds

        # Calculate sample counts
        self.window_samples = int(window_seconds * sample_rate)
        self.calibration_samples = int(calibration_seconds * sample_rate)
        self.min_transmission_samples = int(min_transmission_seconds * sample_rate)
        self.min_gap_samples = int(min_gap_seconds * sample_rate)

        logger.info(f"RepeaterActivityAnalyzer initialized:")
        logger.info(f"  Sample rate: {sample_rate/1e6:.1f} MHz")
        logger.info(f"  Threshold: {threshold_multiplier}x noise floor")
        logger.info(f"  Min transmission: {min_transmission_seconds}s ({self.min_transmission_samples} samples)")
        logger.info(f"  Min gap: {min_gap_seconds}s ({self.min_gap_samples} samples)")

    def analyze_iq_file(self, iq_file_path: str) -> ActivityMetrics:
        """
        Analyze an IQ file to detect repeater activity.

        Args:
            iq_file_path: Path to IQ file (complex64 format)

        Returns:
            ActivityMetrics with analysis results

        Raises:
            FileNotFoundError: If IQ file doesn't exist
            ValueError: If file is too short for analysis
        """
        iq_path = Path(iq_file_path)
        if not iq_path.exists():
            raise FileNotFoundError(f"IQ file not found: {iq_file_path}")

        # Load IQ samples (complex64 format)
        iq_samples = np.fromfile(iq_file_path, dtype=np.complex64)

        if len(iq_samples) < self.calibration_samples:
            raise ValueError(
                f"IQ file too short for analysis: {len(iq_samples)} samples "
                f"(need at least {self.calibration_samples} for calibration)"
            )

        logger.info(f"Loaded {len(iq_samples)} IQ samples from {iq_file_path}")
        logger.info(f"Duration: {len(iq_samples) / self.sample_rate:.1f} seconds")

        return self.analyze_iq_samples(iq_samples)

    def analyze_iq_samples(self, iq_samples: np.ndarray) -> ActivityMetrics:
        """
        Analyze IQ samples to detect repeater activity.

        Args:
            iq_samples: Complex IQ samples (numpy array)

        Returns:
            ActivityMetrics with analysis results
        """
        total_samples = len(iq_samples)
        total_duration = total_samples / self.sample_rate

        logger.info(f"Analyzing {total_samples} samples ({total_duration:.1f}s)")

        # Step 1: Calculate RMS power
        rms_power = self._calculate_rms_power(iq_samples)

        # Step 2: Calibrate noise floor using first calibration_seconds
        noise_floor = self._calibrate_noise_floor(rms_power)

        # Step 3: Detect carrier activity
        carrier_threshold = noise_floor * self.threshold_multiplier
        carrier_active = rms_power > carrier_threshold

        # Step 4: Find transmission events
        transmissions = self._find_transmissions(carrier_active, rms_power)

        # Step 5: Calculate activity metrics
        total_active_windows = np.sum(carrier_active)
        total_active_seconds = total_active_windows * self.window_seconds
        total_windows = len(rms_power)
        activity_percentage = (total_active_windows / total_windows) * 100

        # Calculate signal strengths (only where carrier is active)
        if total_active_windows > 0:
            active_power = rms_power[carrier_active]
            # Convert to dB (using arbitrary reference)
            avg_strength = float(10 * np.log10(np.mean(active_power)))
            peak_strength = float(10 * np.log10(np.max(active_power)))
        else:
            avg_strength = None
            peak_strength = None

        noise_floor_db = float(10 * np.log10(noise_floor))

        logger.info(f"Analysis complete:")
        logger.info(f"  Noise floor: {noise_floor_db:.1f} dB")
        logger.info(f"  Carrier threshold: {10*np.log10(carrier_threshold):.1f} dB")
        logger.info(f"  Transmissions: {len(transmissions)}")
        logger.info(f"  Active time: {total_active_seconds:.1f}s ({activity_percentage:.1f}%)")

        return ActivityMetrics(
            carrier_detected=len(transmissions) > 0,
            transmission_count=len(transmissions),
            total_active_seconds=total_active_seconds,
            activity_percentage=activity_percentage,
            average_signal_strength=avg_strength,
            peak_signal_strength=peak_strength,
            noise_floor=noise_floor_db,
            transmissions=transmissions
        )

    def _calculate_rms_power(self, iq_samples: np.ndarray) -> np.ndarray:
        """
        Calculate RMS power using sliding window.

        Args:
            iq_samples: Complex IQ samples

        Returns:
            RMS power array (one value per window)
        """
        # Calculate instantaneous power: I^2 + Q^2
        power = np.abs(iq_samples) ** 2

        # Calculate number of windows
        num_windows = len(power) // self.window_samples

        # Reshape to windows and calculate RMS (sqrt of mean power)
        power_windows = power[:num_windows * self.window_samples].reshape(num_windows, self.window_samples)
        rms_power = np.sqrt(np.mean(power_windows, axis=1))

        logger.debug(f"Calculated RMS power: {num_windows} windows of {self.window_samples} samples")

        return rms_power

    def _calibrate_noise_floor(self, rms_power: np.ndarray) -> float:
        """
        Calibrate noise floor using initial samples.

        Uses mean + 2×std to establish baseline above thermal noise.

        Args:
            rms_power: RMS power array

        Returns:
            Noise floor threshold
        """
        # Use first calibration period for baseline
        calibration_windows = int(self.calibration_seconds / self.window_seconds)
        calibration_windows = min(calibration_windows, len(rms_power))

        calibration_power = rms_power[:calibration_windows]

        mean_power = np.mean(calibration_power)
        std_power = np.std(calibration_power)

        # Noise floor = mean + 2×std (covers ~95% of noise variations)
        noise_floor = mean_power + (2 * std_power)

        logger.debug(f"Noise floor calibration: mean={mean_power:.2e}, std={std_power:.2e}, floor={noise_floor:.2e}")

        return float(noise_floor)

    def _find_transmissions(
        self,
        carrier_active: np.ndarray,
        rms_power: np.ndarray
    ) -> List[TransmissionEvent]:
        """
        Segment carrier activity into individual transmission events.

        Groups consecutive active windows with minimum gap/duration requirements.

        Args:
            carrier_active: Boolean array of carrier detection per window
            rms_power: RMS power per window

        Returns:
            List of TransmissionEvent objects
        """
        transmissions = []

        # Find transitions (inactive->active and active->inactive)
        active_padded = np.pad(carrier_active.astype(int), (1, 1), mode='constant', constant_values=0)
        transitions = np.diff(active_padded)

        starts = np.where(transitions == 1)[0]  # Inactive to active
        ends = np.where(transitions == -1)[0]   # Active to inactive

        if len(starts) == 0:
            logger.debug("No carrier activity detected")
            return transmissions

        logger.debug(f"Found {len(starts)} potential transmission starts")

        # Process each transmission candidate
        for start_idx, end_idx in zip(starts, ends):
            duration_windows = end_idx - start_idx
            duration_seconds = duration_windows * self.window_seconds

            # Filter: minimum duration
            if duration_seconds < self.min_transmission_seconds:
                logger.debug(f"Skipping short transmission: {duration_seconds:.2f}s < {self.min_transmission_seconds}s")
                continue

            # Calculate start offset in seconds
            start_offset = start_idx * self.window_seconds

            # Extract power for this transmission
            transmission_power = rms_power[start_idx:end_idx]

            # Convert to dB
            avg_power_db = float(10 * np.log10(np.mean(transmission_power)))
            peak_power_db = float(10 * np.log10(np.max(transmission_power)))

            transmission = TransmissionEvent(
                start_offset=start_offset,
                duration=duration_seconds,
                avg_strength=avg_power_db,
                peak_strength=peak_power_db
            )

            transmissions.append(transmission)
            logger.debug(f"Transmission: {start_offset:.1f}s, duration {duration_seconds:.1f}s, avg {avg_power_db:.1f}dB")

        # Apply minimum gap filtering
        if len(transmissions) > 1:
            transmissions = self._merge_close_transmissions(transmissions)

        return transmissions

    def _merge_close_transmissions(
        self,
        transmissions: List[TransmissionEvent]
    ) -> List[TransmissionEvent]:
        """
        Merge transmissions that are separated by less than minimum gap.

        Args:
            transmissions: List of transmission events

        Returns:
            Filtered list with merged transmissions
        """
        if not transmissions:
            return transmissions

        merged = []
        current = transmissions[0]

        for next_tx in transmissions[1:]:
            gap = next_tx.start_offset - (current.start_offset + current.duration)

            if gap < self.min_gap_seconds:
                # Merge: extend current transmission
                new_duration = (next_tx.start_offset + next_tx.duration) - current.start_offset

                # Recalculate average strength (weighted by duration)
                total_duration = current.duration + next_tx.duration
                weighted_avg = (
                    (current.avg_strength * current.duration +
                     next_tx.avg_strength * next_tx.duration) / total_duration
                )

                current = TransmissionEvent(
                    start_offset=current.start_offset,
                    duration=new_duration,
                    avg_strength=weighted_avg,
                    peak_strength=max(current.peak_strength, next_tx.peak_strength)
                )

                logger.debug(f"Merged transmissions: gap {gap:.2f}s < {self.min_gap_seconds}s")
            else:
                # Gap is sufficient, keep separate
                merged.append(current)
                current = next_tx

        # Don't forget the last one
        merged.append(current)

        logger.debug(f"Merged {len(transmissions)} → {len(merged)} transmissions")

        return merged


if __name__ == '__main__':
    """
    Test the analyzer with synthetic data.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("RepeaterActivityAnalyzer Test")
    print("=" * 60)
    print()

    # Create synthetic test data
    sample_rate = 2_000_000
    duration = 10  # seconds
    num_samples = sample_rate * duration

    # Generate noise
    noise = (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * 0.1

    # Add synthetic transmissions
    # Transmission 1: 2.0s - 3.5s (1.5s duration)
    t1_start = int(2.0 * sample_rate)
    t1_end = int(3.5 * sample_rate)
    noise[t1_start:t1_end] += (np.random.randn(t1_end - t1_start) +
                                1j * np.random.randn(t1_end - t1_start)) * 0.5

    # Transmission 2: 5.0s - 7.0s (2.0s duration)
    t2_start = int(5.0 * sample_rate)
    t2_end = int(7.0 * sample_rate)
    noise[t2_start:t2_end] += (np.random.randn(t2_end - t2_start) +
                                1j * np.random.randn(t2_end - t2_start)) * 0.7

    print(f"Generated synthetic data: {duration}s, {num_samples} samples")
    print(f"  Transmission 1: 2.0-3.5s (1.5s)")
    print(f"  Transmission 2: 5.0-7.0s (2.0s)")
    print()

    # Analyze
    analyzer = RepeaterActivityAnalyzer(
        sample_rate=sample_rate,
        threshold_multiplier=2.0,  # Higher threshold for synthetic data
        min_transmission_seconds=1.0,
        min_gap_seconds=0.5
    )

    metrics = analyzer.analyze_iq_samples(noise)

    print()
    print("=" * 60)
    print("Analysis Results")
    print("=" * 60)
    print(f"Carrier detected: {metrics.carrier_detected}")
    print(f"Transmission count: {metrics.transmission_count}")
    print(f"Total active time: {metrics.total_active_seconds:.2f}s")
    print(f"Activity percentage: {metrics.activity_percentage:.1f}%")
    print(f"Noise floor: {metrics.noise_floor:.1f} dB")

    if metrics.average_signal_strength:
        print(f"Average signal strength: {metrics.average_signal_strength:.1f} dB")
        print(f"Peak signal strength: {metrics.peak_signal_strength:.1f} dB")

    print()
    print("Transmissions:")
    for i, tx in enumerate(metrics.transmissions, 1):
        print(f"  {i}. Start: {tx.start_offset:.1f}s, Duration: {tx.duration:.1f}s, "
              f"Avg: {tx.avg_strength:.1f}dB, Peak: {tx.peak_strength:.1f}dB")

    print()
    print("=" * 60)
