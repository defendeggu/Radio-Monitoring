#!/usr/bin/env python3
"""
POCSAG Pager Message Decoder Service

Decodes POCSAG pager messages from WAV audio files using multimon-ng.
Supports 512, 1200, and 2400 baud POCSAG signals.
"""

import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from typing import TypedDict, Optional, List

import config

logger = logging.getLogger(__name__)


class POCSAGMessage(TypedDict, total=False):
    """Type definition for decoded POCSAG message"""
    address: int                    # Numeric pager address (e.g., 1234567)
    function_code: int              # Function code 0-3
    message_type: str               # 'numeric', 'alphanumeric', or 'tone'
    message_text: Optional[str]     # Decoded message content
    baud_rate: int                  # 512, 1200, or 2400
    raw_line: str                   # Raw output from multimon-ng
    timestamp: str                  # ISO format timestamp
    frequency: Optional[int]        # Optional frequency in Hz


class POCSAGDecoder:
    """
    POCSAG pager message decoder using multimon-ng

    Decodes POCSAG pager messages from WAV audio files using multimon-ng.
    Falls back to simulation mode if multimon-ng is not available.
    """

    def __init__(self, multimon_path: str = 'multimon-ng'):
        """
        Initialize POCSAG decoder

        Args:
            multimon_path: Path to multimon-ng binary (default: 'multimon-ng')
        """
        self.multimon_path = multimon_path
        self.simulation_mode = False
        self.available = shutil.which(multimon_path) is not None
        if not self.available:
            if config.SIMULATION_MODE:
                logger.warning("SIMULATION MODE: multimon-ng not found — POCSAG messages will be FAKE")
                self.simulation_mode = True
            else:
                logger.warning(f"multimon-ng not found at {multimon_path}; POCSAG file decoding unavailable")

    def decode(self, audio_file: str) -> List[POCSAGMessage]:
        """
        Decode POCSAG messages from a WAV audio file.

        Raises FileNotFoundError for a missing file and RuntimeError when
        multimon-ng is not installed (outside simulation mode).
        """
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {os.path.basename(audio_file)}")
        if self.simulation_mode:
            return self._simulate_decode(audio_file)
        if not self.available:
            raise RuntimeError("multimon-ng is not installed")
        output = self._run_multimon(audio_file)
        messages = self._parse_multimon_output(output)
        logger.info(f"Decoded {len(messages)} POCSAG messages from {os.path.basename(audio_file)}")
        return messages

    def _run_multimon(self, audio_file: str) -> str:
        """
        Run multimon-ng subprocess on audio file

        Args:
            audio_file: Path to WAV audio file

        Returns:
            Raw stdout output from multimon-ng
        """
        cmd = [
            self.multimon_path,
            '-a', 'POCSAG512',      # Decode POCSAG 512 baud
            '-a', 'POCSAG1200',     # Decode POCSAG 1200 baud
            '-a', 'POCSAG2400',     # Decode POCSAG 2400 baud
            '-t', 'wav',            # Input format: WAV
            audio_file
        ]

        logger.debug(f"Running multimon-ng: {cmd}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )

        if result.returncode != 0:
            logger.warning(f"multimon-ng returned code {result.returncode}: {(result.stderr or '')[-500:]}")

        return result.stdout

    def _parse_multimon_output(self, output: str) -> List[POCSAGMessage]:
        """
        Parse multimon-ng output into structured messages

        multimon-ng outputs POCSAG in format:
        POCSAG<baud>: Address: <address>  Function: <func>  [Alpha: <text> | Numeric: <nums> | Tone Only]

        Args:
            output: Raw stdout from multimon-ng

        Returns:
            List of parsed POCSAG messages
        """
        messages = []

        for line in output.split('\n'):
            # Look for POCSAG lines
            if line.startswith('POCSAG'):
                message = self._parse_message_line(line)
                if message:
                    messages.append(message)

        return messages

    def _parse_message_line(self, line: str) -> Optional[POCSAGMessage]:
        """
        Parse single POCSAG message line

        Example formats:
        POCSAG512: Address: 1234567  Function: 3  Alpha:   Test message
        POCSAG1200: Address: 7654321  Function: 0  Numeric: 123456789
        POCSAG2400: Address: 9999999  Function: 1  Tone Only

        Args:
            line: Single line of multimon-ng output

        Returns:
            Parsed POCSAG message or None if parsing failed
        """
        try:
            # Extract baud rate
            baud_match = re.match(r'POCSAG(\d+):', line)
            if not baud_match:
                return None
            baud_rate = int(baud_match.group(1))

            # Validate baud rate
            if baud_rate not in [512, 1200, 2400]:
                logger.debug(f"Invalid baud rate: {baud_rate}")
                return None

            # Extract address
            addr_match = re.search(r'Address:\s+(\d+)', line)
            if not addr_match:
                logger.debug(f"No address found in line: {line}")
                return None
            address = int(addr_match.group(1))

            # Extract function code
            func_match = re.search(r'Function:\s+(\d+)', line)
            function_code = int(func_match.group(1)) if func_match else 0

            # Validate function code
            if function_code not in [0, 1, 2, 3]:
                logger.debug(f"Invalid function code: {function_code}, defaulting to 0")
                function_code = 0

            # Determine message type and extract content
            message_text = None
            message_type = 'tone'

            if 'Alpha:' in line:
                message_type = 'alphanumeric'
                alpha_match = re.search(r'Alpha:\s+(.+?)$', line)
                if alpha_match:
                    message_text = alpha_match.group(1).strip()
            elif 'Numeric:' in line:
                message_type = 'numeric'
                num_match = re.search(r'Numeric:\s+(.+?)$', line)
                if num_match:
                    message_text = num_match.group(1).strip()
            # else: Tone Only (no text)

            return POCSAGMessage(
                address=address,
                function_code=function_code,
                message_type=message_type,
                message_text=message_text,
                baud_rate=baud_rate,
                raw_line=line,
                timestamp=datetime.now(timezone.utc).isoformat()
            )

        except Exception as e:
            logger.debug(f"Error parsing POCSAG line {line!r}: {e}")
            return None

    def _simulate_decode(self, audio_file: str) -> List[POCSAGMessage]:
        """
        Fallback simulation mode for testing

        Returns mock POCSAG messages when multimon-ng is not available.

        Args:
            audio_file: Path to audio file (used for logging only)

        Returns:
            List of simulated POCSAG messages
        """
        logger.warning("POCSAG SIMULATION MODE: generating MOCK messages")

        return [
            POCSAGMessage(
                address=1234567,
                function_code=3,
                message_type='alphanumeric',
                message_text='[SIMULATED] Test POCSAG message (simulated)',
                baud_rate=1200,
                raw_line='POCSAG1200: Address: 1234567  Function: 3  Alpha:   [SIMULATED] Test POCSAG message (simulated)',
                timestamp=datetime.now(timezone.utc).isoformat()
            ),
            POCSAGMessage(
                address=7654321,
                function_code=0,
                message_type='numeric',
                message_text='[SIMULATED] 555-1234',
                baud_rate=512,
                raw_line='POCSAG512: Address: 7654321  Function: 0  Numeric: [SIMULATED] 555-1234',
                timestamp=datetime.now(timezone.utc).isoformat()
            ),
            POCSAGMessage(
                address=9999999,
                function_code=1,
                message_type='tone',
                message_text=None,
                baud_rate=2400,
                raw_line='POCSAG2400: Address: 9999999  Function: 1  Tone Only',
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        ]


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pocsag_decoder_service.py <audio_file.wav>")
        print("\nDecodes POCSAG pager messages from WAV audio files.")
        print("Supports 512, 1200, and 2400 baud POCSAG signals.")
        sys.exit(1)

    audio_file = sys.argv[1]
    print("\n=== POCSAG Decoder ===")
    print(f"Audio file: {audio_file}\n")

    decoder = POCSAGDecoder()
    messages = decoder.decode(audio_file)

    print(f"\n=== Decoded {len(messages)} POCSAG Messages ===\n")
    for i, msg in enumerate(messages, 1):
        print(f"Message {i}:")
        print(f"  Address: {msg['address']}")
        print(f"  Function: {msg['function_code']}")
        print(f"  Type: {msg['message_type']}")
        print(f"  Baud: {msg['baud_rate']}")
        if msg['message_text']:
            print(f"  Text: {msg['message_text']}")
        print(f"  Time: {msg['timestamp']}")
        print()
