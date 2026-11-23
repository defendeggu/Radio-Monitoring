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

from typing import List, Optional, Dict, Any, TypedDict, cast
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone

from radiomoni import config
from radiomoni.aprs_parse import parse_line

logger = logging.getLogger(__name__)


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
    packet_type: str
    aprs_data: Dict[str, Any]
    timestamp: str
    frequency: Optional[int]  # Optional frequency in Hz
    # radiomoni.aprs_parse: readable fields (message_text is the summary line)
    comment: str
    symbol: Optional[str]
    symbol_id: Optional[str]
    format: str
    object_name: str
    addressee: str
    message_id: str
    weather: Dict[str, Any]
    device: str


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
        self.available = shutil.which(direwolf_path) is not None
        if not self.available:
            if config.SIMULATION_MODE:
                logger.warning("SIMULATION MODE: direwolf not found — APRS packets will be FAKE")
                self.simulation_mode = True
            else:
                logger.warning(f"direwolf not found at {direwolf_path}; APRS file decoding unavailable")

    def decode(self, audio_file: str) -> List[APRSPacket]:
        """
        Decode APRS packets from a WAV audio file (16 kHz mono).

        Raises FileNotFoundError for a missing file and RuntimeError when
        direwolf is not installed (outside simulation mode).
        """
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {os.path.basename(audio_file)}")
        if self.simulation_mode:
            return self._simulate_decode(audio_file)
        if not self.available:
            raise RuntimeError("direwolf is not installed")
        raw_output = self._run_direwolf(audio_file)
        packets = self._parse_direwolf_output(raw_output)
        logger.info(f"Decoded {len(packets)} APRS packets from {os.path.basename(audio_file)}")
        return packets

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

        logger.debug(f"Running direwolf: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning(f"direwolf returned code {result.returncode}: {result.stderr[-500:]}")

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
        """One direwolf line ("[0] SOURCE>DEST,PATH:info") to a packet (radiomoni.aprs_parse)."""
        packet = parse_line(line)
        if packet is None:
            return None
        packet['timestamp'] = datetime.now(timezone.utc).isoformat()
        return cast(APRSPacket, packet)

    def _simulate_decode(self, audio_file: str) -> List[APRSPacket]:
        """
        Fallback simulation mode for testing

        Returns mock APRS packets when direwolf is not available.

        Args:
            audio_file: Path to audio file (used for logging only)

        Returns:
            List of simulated APRS packets
        """
        logger.warning("APRS SIMULATION MODE: generating MOCK packets")

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
                timestamp=datetime.now(timezone.utc).isoformat()
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
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        ]


# Simple CLI test interface
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m radiomoni.decoders.aprs <audio_file.wav>")
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
        if packet.get('latitude') is not None and packet.get('longitude') is not None:
            print(f"  Position: {packet['latitude']:.4f}, {packet['longitude']:.4f}")
        if packet.get('message_text'):
            print(f"  Message: {packet['message_text']}")
        print()
