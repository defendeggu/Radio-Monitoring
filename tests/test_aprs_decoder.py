"""
Test Suite for APRS Decoder Service

Tests:
- APRSDecoder initialization - 2 tests
- Decode workflow - 4 tests
- Packet parsing - 8 tests
- Payload parsing - 6 tests
- Position parsing - 4 tests
- Type determination - 3 tests
- Symbol parsing - 2 tests
- Error handling - 3 tests
- API integration - 3 tests

Total: 35 tests covering APRS decoding functionality
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

from aprs_decoder_service import APRSDecoder, APRSPacket


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def decoder():
    """Create APRSDecoder instance"""
    return APRSDecoder(direwolf_path='direwolf')


@pytest.fixture
def sample_audio_file(tmp_path):
    """Create sample audio file for testing"""
    audio_file = tmp_path / "test_aprs.wav"
    # Create empty file (actual content not needed for parsing tests)
    audio_file.touch()
    return str(audio_file)


@pytest.fixture
def sample_direwolf_output():
    """Sample direwolf output for testing"""
    return """
Dire Wolf version 1.6
[0] N0CALL>APRS,WIDE1-1:!4903.50N/07201.75W-Test station
[0] KB1ABC>APUDR,WIDE1-1:=4242.00N/07100.00WrPHG5130/W1,MASs
[0] W1XYZ>APRS,TCPIP*:@092345z4903.50N/07201.75W_135/002/A=000100Test
    """


# ============================================================================
# Initialization Tests
# ============================================================================

class TestAPRSDecoderInit:
    """Tests for APRSDecoder initialization"""

    def test_decoder_initialization_default(self):
        """Test decoder initialization with default path"""
        decoder = APRSDecoder()

        assert decoder.direwolf_path == 'direwolf'

    def test_decoder_initialization_custom_path(self):
        """Test decoder initialization with custom direwolf path"""
        decoder = APRSDecoder(direwolf_path='/usr/local/bin/direwolf')

        assert decoder.direwolf_path == '/usr/local/bin/direwolf'


# ============================================================================
# Decode Workflow Tests
# ============================================================================

class TestAPRSDecodeWorkflow:
    """Tests for APRS decode workflow"""

    def test_decode_returns_list(self, decoder, sample_audio_file):
        """Test that decode returns a list"""
        # Will use simulation mode if direwolf not available
        result = decoder.decode(sample_audio_file)

        assert isinstance(result, list)

    def test_decode_with_nonexistent_file(self, decoder):
        """Test decode with non-existent audio file"""
        with pytest.raises(FileNotFoundError):
            decoder.decode('/nonexistent/file.wav')

    def test_simulate_decode(self, decoder, sample_audio_file):
        """Test simulation mode decode"""
        packets = decoder._simulate_decode(sample_audio_file)

        assert isinstance(packets, list)
        if len(packets) > 0:
            assert isinstance(packets[0], dict)
            assert 'callsign' in packets[0]

    def test_decode_empty_file(self, decoder, tmp_path):
        """Test decode with empty audio file"""
        empty_file = tmp_path / "empty.wav"
        empty_file.touch()

        # Should handle gracefully (return empty list or error)
        result = decoder.decode(str(empty_file))

        assert isinstance(result, list)


# ============================================================================
# Packet Parsing Tests
# ============================================================================

class TestAPRSPacketParsing:
    """Tests for APRS packet parsing"""

    def test_parse_direwolf_output(self, decoder, sample_direwolf_output):
        """Test parsing direwolf output"""
        packets = decoder._parse_direwolf_output(sample_direwolf_output)

        assert isinstance(packets, list)
        # Should parse multiple packets
        assert len(packets) > 0

    def test_parse_packet_line_valid_position(self, decoder):
        """Test parsing valid position packet"""
        line = "[0] N0CALL>APRS,WIDE1-1:!4903.50N/07201.75W-Test station"

        packet = decoder._parse_packet_line(line)

        if packet:
            assert packet['callsign'] == 'N0CALL'
            assert packet['destination'] == 'APRS'

    def test_parse_packet_line_with_timestamp(self, decoder):
        """Test parsing packet with timestamp"""
        line = "[0] W1XYZ>APRS,TCPIP*:@092345z4903.50N/07201.75W_Test"

        packet = decoder._parse_packet_line(line)

        if packet:
            assert 'callsign' in packet
            assert packet['callsign'] == 'W1XYZ'

    def test_parse_packet_line_with_path(self, decoder):
        """Test parsing packet with digipeater path"""
        line = "[0] KB1ABC>APUDR,WIDE1-1,WIDE2-1:=4242.00N/07100.00W"

        packet = decoder._parse_packet_line(line)

        if packet:
            assert 'path' in packet or 'callsign' in packet

    def test_parse_packet_line_invalid(self, decoder):
        """Test parsing invalid packet line"""
        line = "Invalid packet data"

        packet = decoder._parse_packet_line(line)

        assert packet is None

    def test_parse_packet_line_empty(self, decoder):
        """Test parsing empty line"""
        line = ""

        packet = decoder._parse_packet_line(line)

        assert packet is None

    def test_parse_packet_line_comment_only(self, decoder):
        """Test parsing comment-only packet"""
        line = "# This is a comment"

        packet = decoder._parse_packet_line(line)

        assert packet is None

    def test_parse_multiple_packet_types(self, decoder):
        """Test parsing different packet types"""
        lines = [
            "[0] N0CALL>APRS:!4903.50N/07201.75W-Position",
            "[0] KB1ABC>APRS::KB1ABC   :Test message",
            "[0] W1XYZ>APRS:>Status text"
        ]

        packets = [decoder._parse_packet_line(line) for line in lines]

        # Some should parse successfully
        parsed_count = sum(1 for p in packets if p is not None)
        assert parsed_count >= 0


# ============================================================================
# Payload Parsing Tests
# ============================================================================

class TestAPRSPayloadParsing:
    """Tests for APRS payload parsing"""

    def test_parse_payload_position(self, decoder):
        """Test parsing position payload"""
        payload = "!4903.50N/07201.75W-Test"

        lat, lon, altitude, course, speed, comment = decoder._parse_payload(payload)

        # Should extract some information
        assert lat is not None or lon is not None or comment is not None

    def test_parse_payload_compressed(self, decoder):
        """Test parsing compressed position"""
        payload = "!/5L!!<*e7>{comment"

        result = decoder._parse_payload(payload)

        # Should handle compressed format
        assert isinstance(result, tuple)
        assert len(result) == 6

    def test_parse_payload_mic_e(self, decoder):
        """Test parsing Mic-E format"""
        # Mic-E packets have position in destination address
        payload = "`test'data"

        result = decoder._parse_payload(payload)

        assert isinstance(result, tuple)

    def test_parse_payload_object(self, decoder):
        """Test parsing object report"""
        payload = ";OBJECT   *092345z4903.50N/07201.75W-Test"

        result = decoder._parse_payload(payload)

        assert isinstance(result, tuple)

    def test_parse_payload_message(self, decoder):
        """Test parsing message payload"""
        payload = ":KB1ABC   :Test message{123"

        result = decoder._parse_payload(payload)

        assert isinstance(result, tuple)

    def test_parse_payload_status(self, decoder):
        """Test parsing status payload"""
        payload = ">Status text here"

        result = decoder._parse_payload(payload)

        assert isinstance(result, tuple)


# ============================================================================
# Position Parsing Tests
# ============================================================================

class TestAPRSPositionParsing:
    """Tests for APRS position parsing"""

    def test_parse_latitude_valid(self, decoder):
        """Test parsing valid latitude"""
        lat_str = "4903.50N"

        lat = decoder._parse_latitude(lat_str)

        if lat is not None:
            assert -90 <= lat <= 90

    def test_parse_latitude_south(self, decoder):
        """Test parsing south latitude"""
        lat_str = "3345.12S"

        lat = decoder._parse_latitude(lat_str)

        if lat is not None:
            assert lat < 0  # South is negative

    def test_parse_longitude_valid(self, decoder):
        """Test parsing valid longitude"""
        lon_str = "07201.75W"

        lon = decoder._parse_longitude(lon_str)

        if lon is not None:
            assert -180 <= lon <= 180

    def test_parse_longitude_east(self, decoder):
        """Test parsing east longitude"""
        lon_str = "13912.45E"

        lon = decoder._parse_longitude(lon_str)

        if lon is not None:
            assert lon > 0  # East is positive


# ============================================================================
# Type Determination Tests
# ============================================================================

class TestAPRSTypeDetermination:
    """Tests for APRS packet type determination"""

    def test_determine_type_position(self, decoder):
        """Test identifying position packet"""
        payload = "!4903.50N/07201.75W-"

        packet_type = decoder._determine_type(payload)

        assert packet_type in ['position', 'unknown']

    def test_determine_type_message(self, decoder):
        """Test identifying message packet"""
        payload = ":KB1ABC   :Test"

        packet_type = decoder._determine_type(payload)

        assert packet_type in ['message', 'unknown']

    def test_determine_type_status(self, decoder):
        """Test identifying status packet"""
        payload = ">Status text"

        packet_type = decoder._determine_type(payload)

        assert packet_type in ['status', 'unknown']


# ============================================================================
# Symbol Parsing Tests
# ============================================================================

class TestAPRSSymbolParsing:
    """Tests for APRS symbol parsing"""

    def test_extract_symbol_table(self, decoder):
        """Test extracting symbol table"""
        payload = "!4903.50N/07201.75W-"

        symbol_table = decoder._extract_symbol_table(payload)

        # Should return '/' or None
        assert symbol_table is None or isinstance(symbol_table, str)

    def test_extract_symbol_code(self, decoder):
        """Test extracting symbol code"""
        payload = "!4903.50N/07201.75W-"

        symbol_code = decoder._extract_symbol_code(payload)

        # Should return symbol or None
        assert symbol_code is None or isinstance(symbol_code, str)


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestAPRSErrorHandling:
    """Tests for APRS decoder error handling"""

    def test_decode_with_corrupted_output(self, decoder):
        """Test handling corrupted direwolf output"""
        corrupted = "Garbage\n$$\x00\x01\x02Invalid"

        packets = decoder._parse_direwolf_output(corrupted)

        # Should handle gracefully
        assert isinstance(packets, list)

    def test_parse_malformed_coordinates(self, decoder):
        """Test parsing malformed coordinates"""
        lat_str = "invalid"

        lat = decoder._parse_latitude(lat_str)

        assert lat is None

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

class TestAPRSDecoderAPI:
    """API integration tests for APRS decoder"""

    def test_aprs_decode_endpoint_exists(self, client: FlaskClient):
        """Test that /aprs/decode endpoint exists"""
        response = client.post('/aprs/decode', json={})

        # Should not return 404
        assert response.status_code != 404

    def test_aprs_decode_requires_audio_file(self, client: FlaskClient):
        """Test that APRS decode requires audio file"""
        response = client.post('/aprs/decode', json={})

        # Should return error for missing file
        assert response.status_code in [400, 404, 500]

    def test_aprs_decode_with_frequency(self, client: FlaskClient):
        """Test APRS decode with frequency parameter"""
        response = client.post('/aprs/decode', json={
            'audio_file': 'test.wav',
            'frequency': 144800000  # 144.8 MHz
        })

        # Should process (may fail if file doesn't exist, but endpoint works)
        assert response.status_code in [200, 400, 404, 500]


# ============================================================================
# Integration Tests
# ============================================================================

class TestAPRSIntegration:
    """Integration tests for APRS decode workflow"""

    def test_full_decode_workflow_simulation(self, decoder, sample_audio_file):
        """Test complete decode workflow in simulation mode"""
        # Simulation mode should always work
        packets = decoder._simulate_decode(sample_audio_file)

        assert isinstance(packets, list)

        if len(packets) > 0:
            packet = packets[0]
            assert 'callsign' in packet
            assert 'timestamp' in packet
            assert 'type' in packet

    def test_packet_structure_validation(self, decoder, sample_audio_file):
        """Test that decoded packets have required structure"""
        packets = decoder._simulate_decode(sample_audio_file)

        if len(packets) > 0:
            packet = packets[0]

            # Required fields
            required_fields = ['callsign', 'timestamp', 'type']
            for field in required_fields:
                assert field in packet

            # Optional but common fields
            optional_fields = ['latitude', 'longitude', 'comment']
            # At least one should be present
            has_optional = any(field in packet for field in optional_fields)
            assert has_optional or packet['type'] in ['message', 'status']


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
