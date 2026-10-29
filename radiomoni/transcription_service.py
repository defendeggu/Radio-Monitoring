#!/usr/bin/env python3
"""
Faster-Whisper transcription service.

Models: tiny, base, small, medium, large-v3, large-v3-turbo, distil-large-v3, ...
(any name or path faster-whisper accepts). Models are cached in HF_HOME.

Simulated (fake) transcriptions are only returned when SIMULATION_MODE=true.
Real errors are raised instead of being hidden behind fake text.
"""

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict, cast

from radiomoni import config

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = ['tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3', 'large-v3-turbo',
                    'distil-large-v3', 'distil-medium.en', 'distil-small.en']


class SegmentDict(TypedDict):
    """Type definition for transcription segment"""
    start: float
    end: float
    text: str


class TranscriptionResult(TypedDict, total=False):
    """Type definition for complete transcription result"""
    text: str
    language: str
    language_probability: float
    duration: float
    segments: list[SegmentDict]
    audio_file: str
    timestamp: str
    model: str
    simulation_mode: bool
    warning: str


class TranscriptionService:
    def __init__(self, model: str = 'small', device: str = 'cpu', compute_type: str = 'int8') -> None:
        """
        Args:
            model: Whisper model name (see SUPPORTED_MODELS) or local path
            device: cpu, cuda or auto
            compute_type: int8, int8_float16, float16, float32
        """
        self.model_name: str = model
        self.device: str = device
        self.compute_type: str = compute_type
        self.model: Any = None
        self.simulation_mode: bool = False
        logger.info(f"Initializing Whisper model: {model} on {device} ({compute_type})")
        self._load_model()

    def _load_model(self) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            if not config.SIMULATION_MODE:
                raise
            logger.warning("SIMULATION MODE: faster-whisper not installed — transcriptions are FAKE")
            self.simulation_mode = True
            return
        self.model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)
        logger.info("Whisper model loaded")

    def transcribe(self, audio_file: str, language: Optional[str] = None, task: str = 'transcribe',
                   beam_size: int = 5, vad_filter: bool = True,
                   initial_prompt: Optional[str] = None) -> TranscriptionResult:
        """
        Transcribe an audio file.

        Raises FileNotFoundError for missing files and RuntimeError when no
        model is available (outside simulation mode).
        """
        logger.info(f"Transcribing: {os.path.basename(audio_file)}")
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {os.path.basename(audio_file)}")

        if self.model is None:
            if self.simulation_mode:
                return self._simulate_transcription(audio_file)
            raise RuntimeError("Whisper model is not loaded")

        segments, info = self.model.transcribe(
            audio_file,
            language=language,
            task=task,
            beam_size=beam_size,
            vad_filter=vad_filter,
            vad_parameters=dict(min_silence_duration_ms=500),
            initial_prompt=initial_prompt or config.WHISPER_INITIAL_PROMPT,
        )

        texts: list[str] = []
        all_segments: list[SegmentDict] = []
        for segment in segments:
            texts.append(segment.text.strip())
            all_segments.append({'start': segment.start, 'end': segment.end, 'text': segment.text})

        result: TranscriptionResult = {
            'text': ' '.join(t for t in texts if t),
            'language': info.language,
            'language_probability': info.language_probability,
            'duration': info.duration,
            'segments': all_segments,
            'audio_file': os.path.basename(audio_file),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'model': self.model_name,
        }
        logger.info(f"Transcription complete: language={result['language']} "
                    f"({result['language_probability']:.0%}), duration={result['duration']:.1f}s")
        return result

    def _simulate_transcription(self, audio_file: str) -> TranscriptionResult:
        """Fake transcription for tests and demos (SIMULATION_MODE=true only)."""
        logger.warning("SIMULATION MODE: generating MOCK transcription")
        result = {
            "text": "[SIMULATED] This is a simulated transcription of a radio message. "
                    "The actual transcription will appear here when faster-whisper is available.",
            "language": "en",
            "language_probability": 0.95,
            "duration": 10.0,
            "segments": [
                {"start": 0.0, "end": 5.0,
                 "text": "[SIMULATED] This is a simulated transcription of a radio message."},
                {"start": 5.0, "end": 10.0,
                 "text": "[SIMULATED] The actual transcription will appear here when faster-whisper is available."}
            ],
            "audio_file": os.path.basename(audio_file),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": self.model_name,
            "simulation_mode": True,
            "warning": "This is a simulated transcription, not real data"
        }
        return cast(TranscriptionResult, result)

    def transcribe_and_save(self, audio_file: str, output_file: Optional[str] = None,
                            language: Optional[str] = None) -> TranscriptionResult:
        """Transcribe and optionally write the result as JSON."""
        result = self.transcribe(audio_file, language)
        if output_file:
            os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"Results saved to: {output_file}")
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Transcribe audio using faster-whisper')
    parser.add_argument('-i', '--input', type=str, required=True, help='Input audio file')
    parser.add_argument('-o', '--output', type=str, help='Output JSON file (optional)')
    parser.add_argument('-m', '--model', type=str, default='small', help='Whisper model name or path')
    parser.add_argument('-l', '--language', type=str, help='Language code (auto-detect if not specified)')
    parser.add_argument('-d', '--device', type=str, default='cpu', choices=['cpu', 'cuda', 'auto'])
    parser.add_argument('-c', '--compute-type', type=str, default='int8',
                        choices=['int8', 'int8_float16', 'int16', 'float16', 'float32'])
    args = parser.parse_args()

    service = TranscriptionService(model=args.model, device=args.device, compute_type=args.compute_type)
    result = service.transcribe_and_save(args.input, args.output, args.language)
    print(result['text'])


if __name__ == '__main__':
    main()
