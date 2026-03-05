#!/usr/bin/env python3
"""
Faster-Whisper Transcription Service
Transcribes audio files using faster-whisper
"""

import os
import sys
import argparse
import json
from datetime import datetime
from typing import TypedDict, cast, Any, Dict, Optional

import logging

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class SegmentDict(TypedDict):
    """Type definition for transcription segment"""
    start: float
    end: float
    text: str


class TranscriptionResult(TypedDict):
    """Type definition for complete transcription result"""
    text: str
    language: str
    language_probability: float
    duration: float
    segments: list[SegmentDict]
    audio_file: str
    timestamp: str


class TranscriptionService:
    def __init__(self, model: str = 'base', device: str = 'cpu', compute_type: str = 'int8') -> None:
        """
        Initialize Whisper transcription service

        Args:
            model: Whisper model size (tiny, base, small, medium, large)
            device: Device to use (cpu, cuda)
            compute_type: Compute type (int8, int16, float16, float32)
        """
        self.model_name: str = model
        self.device: str = device
        self.compute_type: str = compute_type
        self.model: WhisperModel | None = None
        self.simulation_mode: bool = False  # Track if simulation mode is active

        logger.info(f"Initializing Whisper model: {model}")
        self._load_model()

    def _load_model(self) -> None:
        """Load the Whisper model"""
        try:
            from faster_whisper import WhisperModel

            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type
            )
            logger.info("Model loaded successfully")

        except ImportError:
            logger.warning("SIMULATION MODE ACTIVE: faster-whisper not available - using MOCK transcriptions")
            logger.warning("Install faster-whisper to enable real transcriptions: pip install faster-whisper")
            self.model = None
            self.simulation_mode = True

    def transcribe(self, audio_file: str, language: str | None = None) -> TranscriptionResult:
        """
        Transcribe an audio file

        Args:
            audio_file: Path to audio file
            language: Language code (optional, auto-detect if None)

        Returns:
            dict: Transcription result with text and metadata
        """
        logger.info(f"Transcribing: {audio_file}")

        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        if self.model is None:
            return self._simulate_transcription(audio_file)

        try:
            # Transcribe
            segments, info = self.model.transcribe(
                audio_file,
                language=language,
                beam_size=5,
                vad_filter=True,  # Voice Activity Detection
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            # Collect results
            transcription_text = ""
            all_segments = []

            for segment in segments:
                transcription_text += segment.text + " "
                all_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                })

            result = {
                "text": transcription_text.strip(),
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "segments": all_segments,
                "audio_file": audio_file,
                "timestamp": datetime.now().isoformat()
            }

            logger.info(f"Transcription complete: language={result['language']} ({result['language_probability']:.2%}), duration={result['duration']:.2f}s")
            logger.info(f"Text preview: {result['text'][:100]}...")

            return cast(TranscriptionResult, result)

        except Exception as e:
            logger.error(f"Transcription error: {e} - Falling back to SIMULATION MODE")
            return self._simulate_transcription(audio_file)

    def _simulate_transcription(self, audio_file: str) -> TranscriptionResult:
        """Simulate transcription for testing"""
        logger.warning("SIMULATION MODE: Generating MOCK transcription - NOT a real transcription!")

        result = {
            "text": "[SIMULATED] This is a simulated transcription of a radio message. "
                    "The actual transcription will appear here when faster-whisper is available.",
            "language": "en",
            "language_probability": 0.95,
            "duration": 10.0,
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "[SIMULATED] This is a simulated transcription of a radio message."
                },
                {
                    "start": 5.0,
                    "end": 10.0,
                    "text": "[SIMULATED] The actual transcription will appear here when faster-whisper is available."
                }
            ],
            "audio_file": audio_file,
            "timestamp": datetime.now().isoformat(),
            "simulation_mode": True,  # Flag to indicate simulated data
            "warning": "This is a simulated transcription, not real data"
        }

        return cast(TranscriptionResult, result)

    def transcribe_and_save(self, audio_file: str, output_file: str | None = None,
                           language: str | None = None) -> TranscriptionResult:
        """
        Transcribe an audio file and optionally save to JSON

        Args:
            audio_file: Path to audio file
            output_file: Optional path to save JSON results
            language: Optional language code

        Returns:
            TranscriptionResult: Transcription result dictionary
        """
        # Transcribe
        result = self.transcribe(audio_file, language)

        # Save to file if requested
        if output_file:
            os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"Results saved to: {output_file}")

        return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Transcribe audio using faster-whisper')
    parser.add_argument('-i', '--input', type=str, required=True,
                        help='Input audio file')
    parser.add_argument('-o', '--output', type=str,
                        help='Output JSON file (optional)')
    parser.add_argument('-m', '--model', type=str, default='base',
                        choices=['tiny', 'base', 'small', 'medium', 'large'],
                        help='Whisper model size')
    parser.add_argument('-l', '--language', type=str,
                        help='Language code (auto-detect if not specified)')
    parser.add_argument('-d', '--device', type=str, default='cpu',
                        choices=['cpu', 'cuda'],
                        help='Device to use')
    parser.add_argument('-c', '--compute-type', type=str, default='int8',
                        choices=['int8', 'int16', 'float16', 'float32'],
                        help='Compute type')

    args = parser.parse_args()

    # Create transcription service
    service = TranscriptionService(
        model=args.model,
        device=args.device,
        compute_type=args.compute_type
    )

    # Transcribe
    result = service.transcribe(
        audio_file=args.input,
        language=args.language
    )

    if args.output:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Results saved to: {args.output}")

    # Print transcription
    print("\n" + "="*50)
    print("TRANSCRIPTION:")
    print("="*50)
    print(result['text'])
    print("="*50)


if __name__ == '__main__':
    main()
