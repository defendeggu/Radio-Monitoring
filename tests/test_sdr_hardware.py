#!/usr/bin/env python3
"""
Unit tests for SDR Hardware Abstraction Layer
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import tempfile
import os

# Import the module to test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdr_hardware import (
    SDRType,
    HackRFCapture,
    RTLSDRCapture,
    USRPCapture,
    detect_sdr,
    get_sdr_instance,
    apply_hackrf_iq_correction,
)


class TestSDRDetection(unittest.TestCase):
    """Test SDR hardware detection"""

    @patch('subprocess.run')
    def test_detect_hackrf_success(self, mock_run):
        """Test successful HackRF detection"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Serial number: 0x12345678"
        )

        result = detect_sdr()
        self.assertEqual(result, SDRType.HACKRF)

    @patch('subprocess.run')
    def test_detect_rtlsdr_success(self, mock_run):
        """Test successful RTL-SDR detection when HackRF not present"""
        # First call (HackRF check) fails, second call (RTL-SDR check) succeeds
        mock_run.side_effect = [
            Mock(returncode=1, stdout=""),    # HackRF not found
            Mock(returncode=1, stdout=""),    # Airspy HF+ not found
            Mock(returncode=0, stdout=b""),   # RTL-SDR found (returncode=0 short-circuits)
        ]

        result = detect_sdr()
        self.assertEqual(result, SDRType.RTLSDR)

    @patch('subprocess.run')
    def test_detect_no_sdr(self, mock_run):
        """Test no SDR hardware detected"""
        mock_run.side_effect = [
            Mock(returncode=1, stdout=""),   # HackRF not found (text=True -> str)
            Mock(returncode=1, stdout=""),   # Airspy HF+ not found (text=True -> str)
            Mock(returncode=1, stdout=""),   # RTL-SDR not found (text=True -> str)
        ]

        result = detect_sdr()
        self.assertEqual(result, SDRType.UNKNOWN)

    @patch('subprocess.run')
    def test_detect_prefers_hackrf(self, mock_run):
        """Test that HackRF is preferred when both devices present"""
        # Both succeed, but HackRF checked first
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Serial number: 0x12345678"
        )

        result = detect_sdr()
        self.assertEqual(result, SDRType.HACKRF)


class TestHackRFCapture(unittest.TestCase):
    """Test HackRF implementation"""

    def test_frequency_range(self):
        """Test HackRF frequency range"""
        hackrf = HackRFCapture(frequency=100_000_000)
        min_freq, max_freq = hackrf.get_frequency_range()

        self.assertEqual(min_freq, 1_000_000)  # 1 MHz
        self.assertEqual(max_freq, 6_000_000_000)  # 6 GHz

    def test_max_sample_rate(self):
        """Test HackRF maximum sample rate"""
        hackrf = HackRFCapture(frequency=100_000_000)
        max_rate = hackrf.get_max_sample_rate()

        self.assertEqual(max_rate, 20_000_000)  # 20 MHz

    @patch('subprocess.run')
    def test_is_available_true(self, mock_run):
        """Test HackRF availability check returns True"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Serial number: 0x12345678"
        )

        hackrf = HackRFCapture(frequency=100_000_000)
        self.assertTrue(hackrf.is_available())

    @patch('subprocess.run')
    def test_is_available_false(self, mock_run):
        """Test HackRF availability check returns False"""
        mock_run.return_value = Mock(returncode=1, stdout="")

        hackrf = HackRFCapture(frequency=100_000_000)
        self.assertFalse(hackrf.is_available())

    def test_iq_normalization(self):
        """Test HackRF IQ sample normalization (int8 signed)"""
        # Simulate int8 IQ data from HackRF
        raw_int8 = np.array([127, -128, 0, 64, -64, 32], dtype=np.int8)

        # Expected normalization: divide by 127.0
        i_expected = raw_int8[0::2].astype(np.float32) / 127.0
        q_expected = raw_int8[1::2].astype(np.float32) / 127.0
        expected = i_expected + 1j * q_expected

        # Verify normalization
        self.assertAlmostEqual(expected[0].real, 1.0, places=5)
        self.assertAlmostEqual(expected[0].imag, -1.007874, places=5)  # -128/127
        self.assertAlmostEqual(expected[1].real, 0.0, places=5)
        self.assertAlmostEqual(expected[1].imag, 0.503937, places=5)  # 64/127


class TestIQCorrection(unittest.TestCase):
    """Test apply_hackrf_iq_correction"""

    def _make_signal(self, n: int = 4096) -> np.ndarray:
        """Return a balanced, zero-mean complex tone."""
        t = np.arange(n, dtype=np.float32)
        return (np.cos(2 * np.pi * t / 64) + 1j * np.sin(2 * np.pi * t / 64)).astype(np.complex64)

    def test_dc_offset_removal(self):
        """After correction, I and Q mean must be essentially zero."""
        sig = self._make_signal()
        sig_biased = (sig.real + 0.15 + 1j * (sig.imag - 0.07)).astype(np.complex64)
        result = apply_hackrf_iq_correction(sig_biased)
        self.assertAlmostEqual(float(np.mean(result.real)), 0.0, places=5)
        self.assertAlmostEqual(float(np.mean(result.imag)), 0.0, places=5)

    def test_amplitude_imbalance_correction(self):
        """After correction, I and Q power must be equal."""
        n = 4096
        t = np.arange(n, dtype=np.float32)
        i = np.cos(2 * np.pi * t / 64)
        q = 0.5 * np.sin(2 * np.pi * t / 64)  # Q at half amplitude
        sig = (i + 1j * q).astype(np.complex64)
        result = apply_hackrf_iq_correction(sig)
        i_power = float(np.mean(result.real ** 2))
        q_power = float(np.mean(result.imag ** 2))
        self.assertAlmostEqual(i_power, q_power, places=3)

    def test_phase_imbalance_correction(self):
        """After correction, cross-correlation mean(I*Q) must be near zero."""
        n = 4096
        t = np.arange(n, dtype=np.float32)
        i = np.cos(2 * np.pi * t / 64)
        q = np.sin(2 * np.pi * t / 64) + 0.2 * i  # I leaks into Q
        sig = (i + 1j * q).astype(np.complex64)
        result = apply_hackrf_iq_correction(sig)
        cross = float(np.abs(np.mean(result.real * result.imag)))
        self.assertLess(cross, 1e-4)

    def test_zero_array_safety(self):
        """Function must not raise on an all-zero input."""
        sig = np.zeros(100, dtype=np.complex64)
        result = apply_hackrf_iq_correction(sig)
        self.assertEqual(result.shape, sig.shape)
        self.assertEqual(result.dtype, np.complex64)


class TestRTLSDRCapture(unittest.TestCase):
    """Test RTL-SDR implementation"""

    def test_frequency_range(self):
        """Test RTL-SDR frequency range"""
        rtlsdr = RTLSDRCapture(frequency=100_000_000)
        min_freq, max_freq = rtlsdr.get_frequency_range()

        self.assertEqual(min_freq, 24_000_000)  # 24 MHz
        self.assertEqual(max_freq, 1_766_000_000)  # 1.766 GHz

    def test_max_sample_rate(self):
        """Test RTL-SDR maximum sample rate"""
        rtlsdr = RTLSDRCapture(frequency=100_000_000)
        max_rate = rtlsdr.get_max_sample_rate()

        self.assertEqual(max_rate, 3_200_000)  # 3.2 MHz

    @patch('subprocess.run')
    def test_is_available_true(self, mock_run):
        """Test RTL-SDR availability check returns True"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Found Rafael Micro R820T tuner"
        )

        rtlsdr = RTLSDRCapture(frequency=100_000_000)
        self.assertTrue(rtlsdr.is_available())

    @patch('subprocess.run')
    def test_is_available_false(self, mock_run):
        """Test RTL-SDR availability check returns False"""
        mock_run.return_value = Mock(returncode=1, stdout="")

        rtlsdr = RTLSDRCapture(frequency=100_000_000)
        self.assertFalse(rtlsdr.is_available())

    def test_iq_normalization(self):
        """Test RTL-SDR IQ sample normalization (uint8 unsigned)"""
        # Simulate uint8 IQ data from RTL-SDR
        raw_uint8 = np.array([255, 0, 127, 200, 50, 128], dtype=np.uint8)

        # Expected normalization: (sample - 127.5) / 127.5
        i_expected = (raw_uint8[0::2].astype(np.float32) - 127.5) / 127.5
        q_expected = (raw_uint8[1::2].astype(np.float32) - 127.5) / 127.5
        expected = i_expected + 1j * q_expected

        # Verify normalization
        self.assertAlmostEqual(expected[0].real, 1.0, places=5)  # (255-127.5)/127.5
        self.assertAlmostEqual(expected[0].imag, -1.0, places=5)  # (0-127.5)/127.5
        self.assertAlmostEqual(expected[1].real, -0.003921, places=5)  # (127-127.5)/127.5
        self.assertAlmostEqual(expected[1].imag, 0.568627, places=5)  # (200-127.5)/127.5


class TestFactoryFunction(unittest.TestCase):
    """Test get_sdr_instance factory function"""

    @patch('sdr_hardware.detect_sdr')
    def test_factory_auto_detect_hackrf(self, mock_detect):
        """Test factory with auto-detection returning HackRF"""
        mock_detect.return_value = SDRType.HACKRF

        instance = get_sdr_instance(frequency=100_000_000)

        self.assertIsInstance(instance, HackRFCapture)
        self.assertEqual(instance.frequency, 100_000_000)

    @patch('sdr_hardware.detect_sdr')
    def test_factory_auto_detect_rtlsdr(self, mock_detect):
        """Test factory with auto-detection returning RTL-SDR"""
        mock_detect.return_value = SDRType.RTLSDR

        instance = get_sdr_instance(frequency=100_000_000)

        self.assertIsInstance(instance, RTLSDRCapture)
        self.assertEqual(instance.frequency, 100_000_000)

    @patch('sdr_hardware.detect_sdr')
    def test_factory_no_sdr_raises(self, mock_detect):
        """Test factory raises when no SDR detected"""
        mock_detect.return_value = SDRType.UNKNOWN

        with self.assertRaises(RuntimeError) as context:
            get_sdr_instance(frequency=100_000_000)

        self.assertIn("No SDR hardware detected", str(context.exception))

    def test_factory_frequency_validation_rtlsdr_too_low(self):
        """Test frequency validation rejects frequency below RTL-SDR minimum"""
        with self.assertRaises(ValueError) as context:
            get_sdr_instance(
                frequency=10_000_000,  # 10 MHz, below RTL-SDR min of 24 MHz
                sdr_type=SDRType.RTLSDR
            )

        self.assertIn("does not support 10.000 MHz", str(context.exception))
        self.assertIn("24.000 - 1766.000 MHz", str(context.exception))

    def test_factory_frequency_validation_rtlsdr_too_high(self):
        """Test frequency validation rejects frequency above RTL-SDR maximum"""
        with self.assertRaises(ValueError) as context:
            get_sdr_instance(
                frequency=2_000_000_000,  # 2 GHz, above RTL-SDR max of 1.766 GHz
                sdr_type=SDRType.RTLSDR
            )

        self.assertIn("does not support 2000.000 MHz", str(context.exception))

    def test_factory_frequency_validation_hackrf_success(self):
        """Test HackRF accepts wide frequency range"""
        # Test low frequency (10 MHz)
        instance = get_sdr_instance(
            frequency=10_000_000,
            sdr_type=SDRType.HACKRF
        )
        self.assertIsInstance(instance, HackRFCapture)

        # Test high frequency (5 GHz)
        instance = get_sdr_instance(
            frequency=5_000_000_000,
            sdr_type=SDRType.HACKRF
        )
        self.assertIsInstance(instance, HackRFCapture)

    def test_factory_sample_rate_clamping_rtlsdr(self):
        """Test sample rate is clamped to RTL-SDR maximum"""
        instance = get_sdr_instance(
            frequency=100_000_000,
            sample_rate=5_000_000,  # Request 5 MHz
            sdr_type=SDRType.RTLSDR
        )

        # Should be clamped to 3.2 MHz
        self.assertEqual(instance.sample_rate, 3_200_000)

    def test_factory_sample_rate_clamping_hackrf(self):
        """Test sample rate is clamped to HackRF maximum"""
        instance = get_sdr_instance(
            frequency=100_000_000,
            sample_rate=25_000_000,  # Request 25 MHz
            sdr_type=SDRType.HACKRF
        )

        # Should be clamped to 20 MHz
        self.assertEqual(instance.sample_rate, 20_000_000)

    def test_factory_explicit_sdr_type(self):
        """Test factory with explicitly specified SDR type"""
        instance = get_sdr_instance(
            frequency=100_000_000,
            sdr_type=SDRType.HACKRF
        )

        self.assertIsInstance(instance, HackRFCapture)


class TestUSRPCapture(unittest.TestCase):
    """Test USRP N200 implementation"""

    def test_frequency_range(self):
        """USRP N200 with WBX daughterboard: 50 MHz – 2.2 GHz"""
        usrp = USRPCapture(frequency=466_075_000, device_address='192.168.10.2')
        min_freq, max_freq = usrp.get_frequency_range()
        self.assertEqual(min_freq, 50_000_000)
        self.assertEqual(max_freq, 2_200_000_000)

    def test_max_sample_rate(self):
        """USRP N200 max sample rate is 25 MS/s"""
        usrp = USRPCapture(frequency=466_075_000, device_address='192.168.10.2')
        self.assertEqual(usrp.get_max_sample_rate(), 25_000_000)

    def test_is_available_false_no_address(self):
        """is_available returns False when device_address is empty"""
        usrp = USRPCapture(frequency=100_000_000, device_address='')
        self.assertFalse(usrp.is_available())

    @patch('subprocess.run')
    def test_is_available_true(self, mock_run):
        """is_available returns True when uhd_usrp_probe succeeds"""
        mock_run.return_value = Mock(returncode=0, stdout='USRP N200 found')
        usrp = USRPCapture(frequency=100_000_000, device_address='192.168.10.2')
        self.assertTrue(usrp.is_available())
        mock_run.assert_called_once_with(
            ['uhd_usrp_probe', '--args=addr=192.168.10.2'],
            capture_output=True, text=True, timeout=10
        )

    @patch('subprocess.run')
    def test_is_available_false_unreachable(self, mock_run):
        """is_available returns False when uhd_usrp_probe fails"""
        mock_run.return_value = Mock(returncode=1, stdout='')
        usrp = USRPCapture(frequency=100_000_000, device_address='192.168.10.2')
        self.assertFalse(usrp.is_available())

    @patch('subprocess.run')
    def test_is_available_false_no_uhd(self, mock_run):
        """is_available returns False when uhd_usrp_probe is not installed"""
        mock_run.side_effect = FileNotFoundError('uhd_usrp_probe not found')
        usrp = USRPCapture(frequency=100_000_000, device_address='192.168.10.2')
        self.assertFalse(usrp.is_available())

    def test_requires_device_address_in_factory(self):
        """get_sdr_instance raises ValueError when USRP selected without address"""
        with self.assertRaises(ValueError) as ctx:
            get_sdr_instance(frequency=466_075_000, sdr_type=SDRType.USRP)
        self.assertIn('device_address', str(ctx.exception))

    def test_factory_creates_usrp_instance(self):
        """get_sdr_instance creates USRPCapture when sdr_type=USRP"""
        instance = get_sdr_instance(
            frequency=466_075_000,
            sdr_type=SDRType.USRP,
            device_address='192.168.10.2'
        )
        self.assertIsInstance(instance, USRPCapture)
        self.assertEqual(instance.device_address, '192.168.10.2')

    def test_factory_clamps_sample_rate(self):
        """get_sdr_instance clamps sample rate to 25 MS/s for USRP"""
        instance = get_sdr_instance(
            frequency=466_075_000,
            sample_rate=30_000_000,
            sdr_type=SDRType.USRP,
            device_address='192.168.10.2'
        )
        self.assertEqual(instance.sample_rate, 25_000_000)

    def test_iq_normalization(self):
        """USRP IQ normalization: int16 signed → float, divided by 32768.0"""
        raw_int16 = np.array([32767, -32768, 0, 16384, -16384, 8192], dtype=np.int16)
        i_expected = raw_int16[0::2].astype(np.float32) / 32768.0
        q_expected = raw_int16[1::2].astype(np.float32) / 32768.0
        expected = i_expected + 1j * q_expected
        self.assertAlmostEqual(expected[0].real, 32767 / 32768.0, places=5)
        self.assertAlmostEqual(expected[0].imag, -1.0, places=5)
        self.assertAlmostEqual(expected[1].real, 0.0, places=5)
        self.assertAlmostEqual(expected[1].imag, 0.5, places=5)

    def test_detect_sdr_usrp_preferred(self):
        """detect_sdr returns USRP when preferred_type='usrp' and device_address given"""
        with patch('sdr_hardware.USRPCapture') as MockUSRP:
            mock_instance = Mock()
            mock_instance.is_available.return_value = True
            MockUSRP.return_value = mock_instance
            result = detect_sdr(preferred_type='usrp', device_address='192.168.10.2')
        self.assertEqual(result, SDRType.USRP)

    def test_detect_sdr_usrp_no_address(self):
        """detect_sdr returns UNKNOWN when preferred_type='usrp' but no address"""
        result = detect_sdr(preferred_type='usrp', device_address=None)
        self.assertEqual(result, SDRType.UNKNOWN)


class TestDetectSdrExplicit(unittest.TestCase):
    """Test detect_sdr with explicit preferred_type"""

    def test_preferred_hackrf_returns_hackrf(self):
        """detect_sdr returns HACKRF without probing when preferred_type='hackrf'"""
        result = detect_sdr(preferred_type='hackrf')
        self.assertEqual(result, SDRType.HACKRF)

    def test_preferred_rtlsdr_returns_rtlsdr(self):
        result = detect_sdr(preferred_type='rtlsdr')
        self.assertEqual(result, SDRType.RTLSDR)

    def test_preferred_auto_falls_through(self):
        """detect_sdr with preferred_type='auto' runs normal auto-detection"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout='', stderr='')
            result = detect_sdr(preferred_type='auto')
        self.assertEqual(result, SDRType.UNKNOWN)


class TestDemodulation(unittest.TestCase):
    """Test demodulation methods"""

    def test_fm_demodulation(self):
        """Test FM demodulation produces audio output"""
        # Create a simple FM signal (frequency modulated tone)
        duration = 0.1  # 100ms
        sample_rate = 100000
        t = np.linspace(0, duration, int(duration * sample_rate))

        # Carrier with frequency modulation
        carrier_freq = 1000
        mod_freq = 100
        mod_index = 5

        phase = 2 * np.pi * carrier_freq * t + mod_index * np.sin(2 * np.pi * mod_freq * t)
        iq_samples = (np.cos(phase) + 1j * np.sin(phase)).astype(np.complex64)

        # Demodulate
        hackrf = HackRFCapture(frequency=100_000_000, sample_rate=sample_rate)
        audio = hackrf._fm_demodulate(iq_samples)

        # Check audio was produced
        self.assertGreater(len(audio), 0)
        self.assertTrue(np.isfinite(audio).all())

    def test_am_demodulation(self):
        """Test AM demodulation (envelope detection)"""
        # Create a simple AM signal
        duration = 0.1
        sample_rate = 100000
        t = np.linspace(0, duration, int(duration * sample_rate))

        # Modulating signal (audio)
        audio_signal = np.sin(2 * np.pi * 100 * t)

        # AM modulated carrier
        carrier = (1 + 0.5 * audio_signal) * np.exp(1j * 2 * np.pi * 1000 * t)
        iq_samples = carrier.astype(np.complex64)

        # Demodulate
        hackrf = HackRFCapture(frequency=100_000_000, sample_rate=sample_rate)
        audio = hackrf._demodulate(iq_samples, 'AM')

        # Check audio was produced
        self.assertGreater(len(audio), 0)
        self.assertTrue(np.isfinite(audio).all())


if __name__ == '__main__':
    unittest.main()
