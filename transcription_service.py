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
from typing import TypedDict


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
        self.model: object | None = None

        print(f"Initializing Whisper model: {model}")
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
            print("Model loaded successfully")

        except ImportError:
            print("WARNING: faster-whisper not available, using simulation mode")
            self.model = None

    def transcribe(self, audio_file: str, language: str | None = None) -> TranscriptionResult:
        """
        Transcribe an audio file

        Args:
            audio_file: Path to audio file
            language: Language code (optional, auto-detect if None)

        Returns:
            dict: Transcription result with text and metadata
        """
        print(f"Transcribing: {audio_file}")

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

            print(f"Transcription complete:")
            print(f"  Language: {result['language']} ({result['language_probability']:.2%})")
            print(f"  Duration: {result['duration']:.2f}s")
            print(f"  Text: {result['text'][:100]}...")

            return result

        except Exception as e:
            print(f"Error during transcription: {e}")
            return self._simulate_transcription(audio_file)

    def _simulate_transcription(self, audio_file: str) -> TranscriptionResult:
        """Simulate transcription for testing"""
        print("SIMULATION MODE: Generating mock transcription")

        result = {
            "text": "This is a simulated transcription of a radio message. "
                    "The actual transcription will appear here when faster-whisper is available.",
            "language": "en",
            "language_probability": 0.95,
            "duration": 10.0,
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "This is a simulated transcription of a radio message."
                },
                {
                    "start": 5.0,
                    "end": 10.0,
                    "text": "The actual transcription will appear here when faster-whisper is available."
                }
            ],
            "audio_file": audio_file,
            "timestamp": datetime.now().isoformat()
        }

        return result

    def transcribe_and_save(self, audio_file: str, output_file: str | None = None, language: str | None = None) -> TranscriptionResult:
        """
        Transcribe and save results to JSON file

        Args:
            audio_file: Path to audio file
            output_file: Path to output JSON file (optional)
            language: Language code (optional)

        Returns:
            dict: Transcription result
        """
        result = self.transcribe(audio_file, language)

        if output_file:
            os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Results saved to: {output_file}")

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
    result = service.transcribe_and_save(
        args.input,
        args.output,
        args.language
    )

    # Print transcription
    print("\n" + "="*50)
    print("TRANSCRIPTION:")
    print("="*50)
    print(result['text'])
    print("="*50)


if __name__ == '__main__':
    main()
