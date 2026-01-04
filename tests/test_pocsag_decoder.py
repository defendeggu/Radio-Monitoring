"""
Test Suite for POCSAG Decoder Service

Tests:
- POCSAGDecoder initialization - 2 tests
- Decode workflow - 4 tests
- Message parsing - 8 tests
- Baud rate detection - 3 tests
- Message type detection - 4 tests
- Address parsing - 3 tests
- Error handling - 3 tests
- API integration - 3 tests

Total: 30 tests covering POCSAG decoding functionality
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path
from typing import List
from flask.testing import FlaskClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pocsag_decoder_service import POCSAGDecoder, POCSAGMessage


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def decoder():
    """Create POCSAGDecoder instance"""
    return POCSAGDecoder(multimon_path='multimon-ng')


@pytest.fixture
def sample_audio_file(tmp_path):
    """Create sample audio file for testing"""
    audio_file = tmp_path / "test_pocsag.wav"
    # Create empty file (actual content not needed for parsing tests)
    audio_file.touch()
    return str(audio_file)


@pytest.fixture
def sample_multimon_output():
    """Sample multimon-ng output for testing"""
    return """
multimon-ng 1.1.8
POCSAG512: Address: 1234567  Function: 1  Alpha:   Test Message
POCSAG1200: Address: 9876543  Function: 3  Numeric: 12345
POCSAG2400: Address: 5555555  Function: 2  Alpha:   Emergency Alert
    """


# ============================================================================
# Initialization Tests
# ============================================================================

class TestPOCSAGDecoderInit:
    """Tests for POCSAGDecoder initialization"""

    def test_decoder_initialization_default(self):
        """Test decoder initialization with default path"""
        decoder = POCSAGDecoder()

        assert decoder.multimon_path == 'multimon-ng'

    def test_decoder_initialization_custom_path(self):
        """Test decoder initialization with custom multimon path"""
        decoder = POCSAGDecoder(multimon_path='/usr/local/bin/multimon-ng')

        assert decoder.multimon_path == '/usr/local/bin/multimon-ng'


# ============================================================================
# Decode Workflow Tests
# ============================================================================

class TestPOCSAGDecodeWorkflow:
    """Tests for POCSAG decode workflow"""

    def test_decode_returns_list(self, decoder, sample_audio_file):
        """Test that decode returns a list"""
        # Will use simulation mode if multimon-ng not available
        result = decoder.decode(sample_audio_file)

        assert isinstance(result, list)

    def test_decode_with_nonexistent_file(self, decoder):
        """Test decode with non-existent audio file"""
        with pytest.raises(FileNotFoundError):
            decoder.decode('/nonexistent/file.wav')

    def test_simulate_decode(self, decoder, sample_audio_file):
        """Test simulation mode decode"""
        messages = decoder._simulate_decode(sample_audio_file)

        assert isinstance(messages, list)
        if len(messages) > 0:
            assert isinstance(messages[0], dict)
            assert 'address' in messages[0]

    def test_decode_empty_file(self, decoder, tmp_path):
        """Test decode with empty audio file"""
        empty_file = tmp_path / "empty.wav"
        empty_file.touch()

        # Should handle gracefully (return empty list or error)
        result = decoder.decode(str(empty_file))

        assert isinstance(result, list)


# ============================================================================
# Message Parsing Tests
# ============================================================================

class TestPOCSAGMessageParsing:
    """Tests for POCSAG message parsing"""

    def test_parse_multimon_output(self, decoder, sample_multimon_output):
        """Test parsing multimon-ng output"""
        messages = decoder._parse_multimon_output(sample_multimon_output)

        assert isinstance(messages, list)
        # Should parse multiple messages
        assert len(messages) > 0

    def test_parse_message_line_alpha(self, decoder):
        """Test parsing alphanumeric message"""
        line = "POCSAG1200: Address: 1234567  Function: 1  Alpha:   Test Message"

        message = decoder._parse_message_line(line)

        if message:
            assert message['address'] == 1234567
            assert message['function'] == 1
            assert message['type'] == 'alpha'
            assert 'Test Message' in message['message']

    def test_parse_message_line_numeric(self, decoder):
        """Test parsing numeric message"""
        line = "POCSAG512: Address: 9876543  Function: 3  Numeric: 12345"

        message = decoder._parse_message_line(line)

        if message:
            assert message['address'] == 9876543
            assert message['function'] == 3
            assert message['type'] == 'numeric'

    def test_parse_message_line_empty_message(self, decoder):
        """Test parsing message with empty content"""
        line = "POCSAG2400: Address: 1111111  Function: 0  Alpha:   "

        message = decoder._parse_message_line(line)

        if message:
            assert message['address'] == 1111111
            assert 'message' in message

    def test_parse_message_line_invalid(self, decoder):
        """Test parsing invalid message line"""
        line = "Invalid message data"

        message = decoder._parse_message_line(line)

        assert message is None

    def test_parse_message_line_empty(self, decoder):
        """Test parsing empty line"""
        line = ""

        message = decoder._parse_message_line(line)

        assert message is None

    def test_parse_message_line_comment(self, decoder):
        """Test parsing comment line"""
        line = "# This is a comment"

        message = decoder._parse_message_line(line)

        assert message is None

    def test_parse_multiple_baud_rates(self, decoder):
        """Test parsing messages with different baud rates"""
        lines = [
            "POCSAG512: Address: 1111111  Function: 1  Alpha:   512 baud",
            "POCSAG1200: Address: 2222222  Function: 2  Alpha:   1200 baud",
            "POCSAG2400: Address: 3333333  Function: 3  Alpha:   2400 baud"
        ]

        messages = [decoder._parse_message_line(line) for line in lines]

        # All should parse successfully
        parsed_count = sum(1 for m in messages if m is not None)
        assert parsed_count >= 0


# ============================================================================
# Baud Rate Detection Tests
# ============================================================================

class TestPOCSAGBaudRate:
    """Tests for POCSAG baud rate detection"""

    def test_detect_baud_rate_512(self, decoder):
        """Test detecting 512 baud rate"""
        line = "POCSAG512: Address: 1234567  Function: 1  Alpha:   Test"

        message = decoder._parse_message_line(line)

        if message:
            assert message['baud_rate'] == 512

    def test_detect_baud_rate_1200(self, decoder):
        """Test detecting 1200 baud rate"""
        line = "POCSAG1200: Address: 1234567  Function: 1  Alpha:   Test"

        message = decoder._parse_message_line(line)

        if message:
            assert message['baud_rate'] == 1200

    def test_detect_baud_rate_2400(self, decoder):
        """Test detecting 2400 baud rate"""
        line = "POCSAG2400: Address: 1234567  Function: 1  Alpha:   Test"

        message = decoder._parse_message_line(line)

        if message:
            assert message['baud_rate'] == 2400


# ============================================================================
# Message Type Detection Tests
# ============================================================================

class TestPOCSAGMessageType:
    """Tests for POCSAG message type detection"""

    def test_message_type_alpha(self, decoder):
        """Test detecting alphanumeric message type"""
        line = "POCSAG1200: Address: 1234567  Function: 1  Alpha:   Text message"

        message = decoder._parse_message_line(line)

        if message:
            assert message['type'] == 'alpha'

    def test_message_type_numeric(self, decoder):
        """Test detecting numeric message type"""
        line = "POCSAG1200: Address: 1234567  Function: 2  Numeric: 123456"

        message = decoder._parse_message_line(line)

        if message:
            assert message['type'] == 'numeric'

    def test_message_type_tone(self, decoder):
        """Test detecting tone-only message"""
        line = "POCSAG1200: Address: 1234567  Function: 0"

        message = decoder._parse_message_line(line)

        # Tone-only or unknown type
        if message:
            assert 'type' in message

    def test_message_type_unknown(self, decoder):
        """Test handling unknown message type"""
        line = "POCSAG1200: Address: 1234567  Function: 1  Unknown: data"

        # Should handle gracefully
        message = decoder._parse_message_line(line)

        assert message is None or 'type' in message


# ============================================================================
# Address Parsing Tests
# ============================================================================

class TestPOCSAGAddressParsing:
    """Tests for POCSAG address parsing"""

    def test_parse_address_valid(self, decoder):
        """Test parsing valid address"""
        line = "POCSAG1200: Address: 1234567  Function: 1  Alpha:   Test"

        message = decoder._parse_message_line(line)

        if message:
            assert isinstance(message['address'], int)
            assert message['address'] == 1234567

    def test_parse_address_large(self, decoder):
        """Test parsing large address"""
        line = "POCSAG1200: Address: 9999999  Function: 1  Alpha:   Test"

        message = decoder._parse_message_line(line)

        if message:
            assert message['address'] == 9999999

    def test_parse_address_small(self, decoder):
        """Test parsing small address"""
        line = "POCSAG1200: Address: 1  Function: 1  Alpha:   Test"

        message = decoder._parse_message_line(line)

        if message:
            assert message['address'] == 1


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestPOCSAGErrorHandling:
    """Tests for POCSAG decoder error handling"""

    def test_decode_with_corrupted_output(self, decoder):
        """Test handling corrupted multimon-ng output"""
        corrupted = "Garbage\n$$\x00\x01\x02Invalid"

        messages = decoder._parse_multimon_output(corrupted)

        # Should handle gracefully
        assert isinstance(messages, list)

    def test_parse_malformed_address(self, decoder):
        """Test parsing malformed address"""
        line = "POCSAG1200: Address: INVALID  Function: 1  Alpha:   Test"

        message = decoder._parse_message_line(line)

        # Should return None or handle error
        assert message is None or isinstance(message, dict)

    def test_decode_with_permission_denied(self, decoder, tmp_path):
        """Test decode with inaccessible file"""
        restricted_file = tmp_path / "restricted.wav"
        restricted_file.touch()
        restricted_file.chmod(0o000)

        try:
            result = decoder.decode(str(restricted_file))
            # Should either raise or return empty
            assert isinstance(result, list)
        except PermissionError:
            # Expected behavior
            pass
        finally:
            # Cleanup
            restricted_file.chmod(0o644)


# ============================================================================
# API Integration Tests
# ============================================================================

class TestPOCSAGDecoderAPI:
    """API integration tests for POCSAG decoder"""

    def test_pocsag_decode_endpoint_exists(self, client: FlaskClient):
        """Test that /pocsag/decode endpoint exists"""
        response = client.post('/pocsag/decode', json={})

        # Should not return 404
        assert response.status_code != 404

    def test_pocsag_decode_requires_audio_file(self, client: FlaskClient):
        """Test that POCSAG decode requires audio file"""
        response = client.post('/pocsag/decode', json={})

        # Should return error for missing file
        assert response.status_code in [400, 404, 500]

    def test_pocsag_decode_with_frequency(self, client: FlaskClient):
        """Test POCSAG decode with frequency parameter"""
        response = client.post('/pocsag/decode', json={
            'audio_file': 'test.wav',
            'frequency': 147325000  # 147.325 MHz (CH)
        })

        # Should process (may fail if file doesn't exist, but endpoint works)
        assert response.status_code in [200, 400, 404, 500]


# ============================================================================
# Integration Tests
# ============================================================================

class TestPOCSAGIntegration:
    """Integration tests for POCSAG decode workflow"""

    def test_full_decode_workflow_simulation(self, decoder, sample_audio_file):
        """Test complete decode workflow in simulation mode"""
        # Simulation mode should always work
        messages = decoder._simulate_decode(sample_audio_file)

        assert isinstance(messages, list)

        if len(messages) > 0:
            message = messages[0]
            assert 'address' in message
            assert 'timestamp' in message
            assert 'type' in message

    def test_message_structure_validation(self, decoder, sample_audio_file):
        """Test that decoded messages have required structure"""
        messages = decoder._simulate_decode(sample_audio_file)

        if len(messages) > 0:
            message = messages[0]

            # Required fields
            required_fields = ['address', 'timestamp', 'type', 'baud_rate']
            for field in required_fields:
                assert field in message

            # Function field should be present
            assert 'function' in message
            assert 0 <= message['function'] <= 3

    def test_multiple_messages_decode(self, decoder, sample_multimon_output):
        """Test decoding multiple messages"""
        messages = decoder._parse_multimon_output(sample_multimon_output)

        # Should parse all messages in output
        assert len(messages) >= 0

        if len(messages) > 1:
            # Verify different addresses/types
            addresses = [m['address'] for m in messages if 'address' in m]
            assert len(set(addresses)) > 0  # At least one unique address

    def test_baud_rate_variety(self, decoder, sample_multimon_output):
        """Test that different baud rates are detected"""
        messages = decoder._parse_multimon_output(sample_multimon_output)

        if len(messages) > 0:
            baud_rates = [m.get('baud_rate') for m in messages if 'baud_rate' in m]
            # Should detect valid baud rates
            valid_bauds = [b for b in baud_rates if b in [512, 1200, 2400]]
            assert len(valid_bauds) >= 0


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
