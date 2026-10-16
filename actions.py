"""
High-level SDR actions shared by the REST API and the scheduler.

Each function validates nothing itself — callers pass already validated
pydantic models — and returns a small dict describing what was started.
"""

from typing import Any

from schemas import CaptureRequest, ExternalDecoderRequest, StreamRequest, VoxRequest


def start_stream(req: StreamRequest) -> dict[str, Any]:
    from jobs import start_stream_session
    from streaming_decoder_service import StreamingAPRSDecoder, StreamingPOCSAGDecoder

    cls = StreamingAPRSDecoder if req.mode == 'aprs' else StreamingPOCSAGDecoder
    decoder = cls(frequency=req.frequency, duration=req.duration, sample_rate=req.sample_rate, gain=req.gain,
                  device_type=req.device_type, device_address=req.device_address_str)
    session_id = start_stream_session(decoder, req.mode, req.frequency, req.sample_rate, req.gain)
    return {'session_id': session_id, 'mode': req.mode, 'frequency': req.frequency}


def start_capture(req: CaptureRequest) -> dict[str, Any]:
    from jobs import submit_capture
    return {'capture_id': submit_capture(req), 'status': 'queued'}


def start_vox(req: VoxRequest) -> dict[str, Any]:
    from jobs import start_stream_session
    from services import ensure_disk_space, recording_dir
    from vox_recorder import VoxRecorder

    ensure_disk_space()
    recorder = VoxRecorder(
        frequency=req.frequency, duration=req.duration, gain=req.gain, sample_rate=req.sample_rate,
        modulation=req.modulation, squelch_db=req.squelch_db, hang_time_ms=req.hang_time_ms,
        min_segment_ms=req.min_segment_ms, max_segment_s=req.max_segment_s, transcribe=req.transcribe,
        language=req.language, device_type=req.device_type, device_address=req.device_address_str,
        output_dir=recording_dir())
    session_id = start_stream_session(recorder, 'vox', req.frequency, recorder.sample_rate, req.gain)
    return {'session_id': session_id, 'mode': 'vox', 'frequency': req.frequency}


def start_external_decoder(req: ExternalDecoderRequest) -> dict[str, Any]:
    from external_decoders import ExternalDecoderSession
    from jobs import start_stream_session

    session = ExternalDecoderSession(decoder=req.decoder, duration=req.duration, gain=req.gain,
                                     frequency=req.frequency, ppm=req.ppm)
    session_id = start_stream_session(session, req.decoder, int(session.frequency), session.sample_rate,
                                      req.gain if req.gain is not None else -1)
    return {'session_id': session_id, 'mode': req.decoder, 'frequency': int(session.frequency)}


def run_action(action: str, params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch by action name (used by the scheduler)."""
    if action == 'stream':
        return start_stream(StreamRequest.model_validate(params))
    if action == 'capture':
        return start_capture(CaptureRequest.model_validate(params))
    if action == 'vox':
        return start_vox(VoxRequest.model_validate(params))
    if action == 'decoder':
        return start_external_decoder(ExternalDecoderRequest.model_validate(params))
    raise ValueError(f"Unknown action: {action}")

