"""
APRS Decoder Service

Decodes APRS (Automatic Packet Reporting System) packets from audio files
using direwolf software TNC.

APRS is a digital packet radio protocol used for real-time tactical communications
of position, weather, messages, and telemetry.

Usage:
    decoder = APRSDecoder()
    packets = decoder.decode('path/to/audio.wav')
"""

from typing import List, Optional, Dict, Any, TypedDict
import subprocess
import re
from datetime import datetime
import os


class APRSPacket(TypedDict, total=False):
    """Type definition for decoded APRS packet"""
    source_callsign: str
    destination_callsign: str
    path: str
    latitude: Optional[float]
    longitude: Optional[float]
    altitude: Optional[int]
    speed: Optional[float]
    course: Optional[int]
    message_text: Optional[str]
    symbol_table: Optional[str]
    symbol_code: Optional[str]
    raw_packet: str
    aprs_type: str
    aprs_data: Dict[str, Any]
    timestamp: str
    frequency: Optional[int]  # Optional frequency in Hz


class APRSDecoder:
    """
    APRS packet decoder using direwolf

    Decodes APRS packets from WAV audio files using the direwolf software TNC.
    Falls back to simulation mode if direwolf is not available.
    """

    def __init__(self, direwolf_path: str = 'direwolf',
                 config_path: str = '/app/direwolf.conf'):
        """
        Initialize APRS decoder

        Args:
            direwolf_path: Path to direwolf binary (default: 'direwolf')
            config_path: Path to direwolf configuration file
        """
        self.direwolf_path = direwolf_path
        self.config_path = config_path
        self.simulation_mode = False

        # Check if direwolf is available
        try:
            subprocess.run([self.direwolf_path, '-h'],
                         capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print("="*80)
            print("⚠️  WARNING: APRS DECODER SIMULATION MODE ACTIVE ⚠️")
            print(f"direwolf not found at {direwolf_path} - using MOCK APRS packets")
            print("All APRS decodes will be simulated and NOT REAL!")
            print("Install direwolf to enable real APRS decoding:")
            print("  apt-get install direwolf")
            print("="*80)
            self.simulation_mode = True

    def decode(self, audio_file: str) -> List[APRSPacket]:
        """
        Decode APRS packets from WAV audio file

        Args:
            audio_file: Path to WAV audio file (16kHz, mono)

        Returns:
            List of decoded APRS packets
        """
        if not os.path.exists(audio_file):
            print(f"Error: Audio file not found: {audio_file}")
            return []

        if self.simulation_mode:
            return self._simulate_decode(audio_file)

        try:
            raw_output = self._run_direwolf(audio_file)
            packets = self._parse_direwolf_output(raw_output)
            print(f"Decoded {len(packets)} APRS packets from {audio_file}")
            return packets
        except FileNotFoundError:
            print("="*80)
            print("⚠️  WARNING: direwolf not found")
            print("⚠️  Falling back to SIMULATION MODE")
            print("="*80)
            self.simulation_mode = True
            return self._simulate_decode(audio_file)
        except Exception as e:
            print("="*80)
            print(f"⚠️  APRS DECODING ERROR: {e}")
            print("⚠️  Falling back to SIMULATION MODE")
            print("⚠️  The returned packets will be SIMULATED, not real!")
            print("="*80)
            return self._simulate_decode(audio_file)

    def _run_direwolf(self, audio_file: str) -> str:
        """
        Run direwolf subprocess on audio file

        Args:
            audio_file: Path to WAV audio file

        Returns:
            Raw stdout output from direwolf
        """
        cmd = [
            self.direwolf_path,
            '-r', '16000',          # Sample rate (16kHz from radio_capture.py)
            '-n', '1',              # Mono channel
            '-t', '0',              # Text output only (no colors)
            '-c', self.config_path,  # Configuration file
            audio_file
        ]

        print(f"Running direwolf: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            print(f"Direwolf returned code {result.returncode}")
            print(f"Stderr: {result.stderr}")

        return result.stdout

    def _parse_direwolf_output(self, output: str) -> List[APRSPacket]:
        """
        Parse direwolf output into structured packets

        Direwolf outputs packets in format:
        [channel] CALLSIGN>DESTINATION,PATH:payload

        Args:
            output: Raw stdout from direwolf

        Returns:
            List of parsed APRS packets
        """
        packets = []

        for line in output.split('\n'):
            # Look for packet lines (start with [channel])
            if line.startswith('[') and '>' in line and ':' in line:
                packet = self._parse_packet_line(line)
                if packet:
                    packets.append(packet)

        return packets

    def _parse_packet_line(self, line: str) -> Optional[APRSPacket]:
        """
        Parse single APRS packet line from direwolf

        Example formats:
        [0] W1ABC>APRS,WIDE1-1:=4903.50N/07201.75W-Test message
        [0] N0CALL>APRS:!4903.50N/07201.75W#PHG5360

        Args:
            line: Single line of direwolf output

        Returns:
            Parsed APRS packet or None if parsing failed
        """
        try:
            # Match: [channel] SOURCE>DEST,PATH:payload
            match = re.match(r'\[(\d+)\]\s+(.+?)>(.+?):(.*)', line)
            if not match:
                return None

            channel, source, dest_path, payload = match.groups()

            # Split destination and path
            dest_parts = dest_path.split(',')
            destination = dest_parts[0]
            path = ','.join(dest_parts[1:]) if len(dest_parts) > 1 else ''

            # Parse payload for position, message, etc.
            lat, lon, altitude, speed, course, msg = self._parse_payload(payload)
            aprs_type = self._determine_type(payload)

            return APRSPacket(
                source_callsign=source.strip(),
                destination_callsign=destination.strip(),
                path=path.strip(),
                latitude=lat,
                longitude=lon,
                altitude=altitude,
                speed=speed,
                course=course,
                message_text=msg,
                symbol_table=self._extract_symbol_table(payload),
                symbol_code=self._extract_symbol_code(payload),
                raw_packet=line,
                aprs_type=aprs_type,
                aprs_data={
                    'payload': payload,
                    'channel': channel
                },
                timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            print(f"Error parsing packet line: {e}")
            print(f"Line: {line}")
            return None

    def _parse_payload(self, payload: str) -> tuple[Optional[float], Optional[float], Optional[int], Optional[float], Optional[int], Optional[str]]:
        """
        Parse APRS payload for position and data

        APRS formats:
        - Position with timestamp: /DDHHMM (compressed or uncompressed)
        - Position without timestamp: ! or = (uncompressed or compressed)
        - Message: :ADDRESSEE :message
        - Weather: _
        - Telemetry: T#

        Args:
            payload: APRS payload string

        Returns:
            Tuple: (lat, lon, altitude, speed, course, message)
        """
        lat, lon, alt, speed, course, msg = None, None, None, None, None, None

        # Position report (uncompressed format)
        # Format: =DDMM.MMN/DDDMM.MME-comment
        if payload.startswith('=') or payload.startswith('!') or payload.startswith('/'):
            # Extract position
            pos_match = re.match(
                r'[=/!@](\d{4}\.\d{2}[NS])[/\\](\d{5}\.\d{2}[EW])',
                payload
            )
            if pos_match:
                lat_str, lon_str = pos_match.groups()
                lat = self._parse_latitude(lat_str)
                lon = self._parse_longitude(lon_str)

                # Extract message after position (after symbol)
                remainder = payload[pos_match.end():]
                if len(remainder) > 1:
                    msg = remainder[1:].strip()  # Skip symbol character

        # Message format: :ADDRESSEE :message
        elif payload.startswith(':'):
            msg_match = re.match(r':(.{9}):(.+)', payload)
            if msg_match:
                addressee, message = msg_match.groups()
                msg = f"To {addressee.strip()}: {message.strip()}"

        # Weather report
        elif payload.startswith('_'):
            msg = "Weather report"
            # Could parse weather data here

        # Telemetry
        elif payload.startswith('T#'):
            msg = "Telemetry data"

        # Other/unknown format
        else:
            msg = payload.strip()

        return lat, lon, alt, speed, course, msg

    def _parse_latitude(self, lat_str: str) -> Optional[float]:
        """
        Parse APRS latitude DDMM.MMN to decimal degrees

        Format: DDMM.MM + N/S
        Example: 4903.50N -> 49 degrees + 3.50 minutes = 49.0583°N

        Args:
            lat_str: Latitude string (DDMM.MMN)

        Returns:
            Latitude in decimal degrees or None
        """
        match = re.match(r'(\d{2})(\d{2}\.\d{2})([NS])', lat_str)
        if not match:
            return None

        deg, min_val, direction = match.groups()
        decimal = float(deg) + float(min_val) / 60.0

        # South is negative
        return decimal if direction == 'N' else -decimal

    def _parse_longitude(self, lon_str: str) -> Optional[float]:
        """
        Parse APRS longitude DDDMM.MME to decimal degrees

        Format: DDDMM.MM + E/W
        Example: 07201.75W -> 072 degrees + 01.75 minutes = 72.0292°W = -72.0292°

        Args:
            lon_str: Longitude string (DDDMM.MME)

        Returns:
            Longitude in decimal degrees or None
        """
        match = re.match(r'(\d{3})(\d{2}\.\d{2})([EW])', lon_str)
        if not match:
            return None

        deg, min_val, direction = match.groups()
        decimal = float(deg) + float(min_val) / 60.0

        # West is negative
        return decimal if direction == 'E' else -decimal

    def _determine_type(self, payload: str) -> str:
        """
        Determine APRS packet type from payload

        Args:
            payload: APRS payload string

        Returns:
            Packet type: 'position', 'message', 'weather', 'telemetry', or 'unknown'
        """
        if not payload:
            return 'unknown'

        first_char = payload[0]

        if first_char in '=!/!@':
            return 'position'
        elif first_char == ':':
            return 'message'
        elif first_char == '_':
            return 'weather'
        elif first_char == 'T' and payload.startswith('T#'):
            return 'telemetry'
        elif first_char == '>':
            return 'status'
        else:
            return 'unknown'

    def _extract_symbol_table(self, payload: str) -> Optional[str]:
        """
        Extract APRS symbol table character

        In uncompressed position: character before symbol code
        Format: ...lat/lon[TABLE][CODE]...

        Args:
            payload: APRS payload string

        Returns:
            Symbol table character or None
        """
        # Simplified: In position reports, symbol table is typically '/' or '\'
        if payload.startswith('=') or payload.startswith('!'):
            # Look for pattern after lat/lon
            if '/' in payload:
                return '/'
        return None

    def _extract_symbol_code(self, payload: str) -> Optional[str]:
        """
        Extract APRS symbol code character

        Args:
            payload: APRS payload string

        Returns:
            Symbol code character or None
        """
        # Simplified: Symbol code follows symbol table
        # Full implementation would extract from position report format
        return None

    def _simulate_decode(self, audio_file: str) -> List[APRSPacket]:
        """
        Fallback simulation mode for testing

        Returns mock APRS packets when direwolf is not available.

        Args:
            audio_file: Path to audio file (used for logging only)

        Returns:
            List of simulated APRS packets
        """
        print("="*80)
        print("⚠️  APRS SIMULATION MODE: Generating MOCK packets ⚠️")
        print("⚠️  These are NOT real APRS packets! ⚠️")
        print("="*80)

        return [
            APRSPacket(
                source_callsign='N0CALL',
                destination_callsign='APRS',
                path='WIDE1-1,WIDE2-2',
                latitude=47.6062,
                longitude=-122.3321,
                altitude=100,
                speed=None,
                course=None,
                message_text='[SIMULATED] Test APRS packet (simulated)',
                symbol_table='/',
                symbol_code='-',
                raw_packet='[0] N0CALL>APRS,WIDE1-1:=4736.37N/12219.93W-Test',
                aprs_type='position',
                aprs_data={'simulation': True, 'warning': 'Simulated data, not real'},
                timestamp=datetime.now().isoformat()
            ),
            APRSPacket(
                source_callsign='TEST123',
                destination_callsign='APRS',
                path='WIDE2-1',
                latitude=47.6101,
                longitude=-122.3420,
                altitude=None,
                speed=None,
                course=None,
                message_text='[SIMULATED] Simulated mobile station',
                symbol_table='/',
                symbol_code='>',
                raw_packet='[0] TEST123>APRS,WIDE2-1:=4736.61N/12220.52W>Simulated',
                aprs_type='position',
                aprs_data={'simulation': True, 'warning': 'Simulated data, not real'},
                timestamp=datetime.now().isoformat()
            )
        ]


# Simple CLI test interface
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python aprs_decoder_service.py <audio_file.wav>")
        sys.exit(1)

    audio_file = sys.argv[1]
    decoder = APRSDecoder()
    packets = decoder.decode(audio_file)

    print(f"\n=== Decoded {len(packets)} APRS Packets ===\n")
    for i, packet in enumerate(packets, 1):
        print(f"Packet {i}:")
        print(f"  From: {packet['source_callsign']}")
        print(f"  To: {packet['destination_callsign']}")
        print(f"  Type: {packet['aprs_type']}")
        if packet['latitude'] and packet['longitude']:
            print(f"  Position: {packet['latitude']:.4f}, {packet['longitude']:.4f}")
        if packet['message_text']:
            print(f"  Message: {packet['message_text']}")
        print()
