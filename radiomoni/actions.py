"""
High-level SDR actions shared by the REST API and the scheduler.

Each function validates nothing itself — callers pass already validated
pydantic models — and returns a small dict describing what was started.
"""

from typing import Any

from radiomoni.schemas import (CaptureRequest, CwRequest, ExternalDecoderRequest, SkimmerRequest, SpectrumRequest,
                               StreamRequest, VoxRequest)


def start_stream(req: StreamRequest) -> dict[str, Any]:
    from radiomoni.jobs import start_stream_session
    from radiomoni.decoders.streaming import StreamingAPRSDecoder, StreamingPOCSAGDecoder

    cls = StreamingAPRSDecoder if req.mode == 'aprs' else StreamingPOCSAGDecoder
    decoder = cls(frequency=req.frequency, duration=req.duration, sample_rate=req.sample_rate, gain=req.gain,
                  device_type=req.device_type, device_address=req.device_address_str)
    session_id = start_stream_session(decoder, req.mode, req.frequency, req.sample_rate, req.gain)
    return {'session_id': session_id, 'mode': req.mode, 'frequency': req.frequency}


def start_capture(req: CaptureRequest) -> dict[str, Any]:
    from radiomoni.jobs import submit_capture
    return {'capture_id': submit_capture(req), 'status': 'queued'}


def start_vox(req: VoxRequest) -> dict[str, Any]:
    from radiomoni.jobs import start_stream_session
    from radiomoni.services import ensure_disk_space, recording_dir
    from radiomoni.decoders.vox import VoxRecorder

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
    from radiomoni.decoders.external import ExternalDecoderSession
    from radiomoni.jobs import start_stream_session

    session = ExternalDecoderSession(decoder=req.decoder, duration=req.duration, gain=req.gain,
                                     frequency=req.frequency, ppm=req.ppm)
    session_id = start_stream_session(session, req.decoder, int(session.frequency), session.sample_rate,
                                      req.gain if req.gain is not None else -1)
    return {'session_id': session_id, 'mode': req.decoder, 'frequency': int(session.frequency)}


def start_spectrum(req: SpectrumRequest) -> dict[str, Any]:
    from radiomoni.decoders.spectrum import SpectrumSession
    from radiomoni.jobs import start_stream_session

    session = SpectrumSession(frequency=req.frequency, sample_rate=req.sample_rate, gain=req.gain,
                              duration=req.duration, fft_size=req.fft_size, fps=req.fps,
                              device_type=req.device_type, device_address=req.device_address_str)
    session_id = start_stream_session(session, 'spectrum', req.frequency, session.sample_rate, req.gain)
    return {'session_id': session_id, 'mode': 'spectrum', 'frequency': req.frequency, **session.state()}


def start_cw(req: CwRequest) -> dict[str, Any]:
    from radiomoni.decoders.cw import CwSession
    from radiomoni.jobs import start_stream_session
    from radiomoni.services import ensure_disk_space, recording_dir

    if req.record:
        ensure_disk_space()
    session = CwSession(frequency=req.frequency, gain=req.gain, duration=req.duration, sample_rate=req.sample_rate,
                        wpm=req.wpm, cw_bandwidth=req.cw_bandwidth, tone_hz=req.tone_hz, record=req.record,
                        device_type=req.device_type,
                        device_address=str(req.device_address) if req.device_address else None,
                        output_dir=recording_dir())
    session_id = start_stream_session(session, 'cw', req.frequency, session.sample_rate, req.gain)
    return {'session_id': session_id, 'mode': 'cw', 'frequency': req.frequency, **session.state()}


def start_skimmer(req: SkimmerRequest) -> dict[str, Any]:
    from radiomoni.jobs import start_stream_session
    from radiomoni.services import ensure_disk_space, recording_dir
    from radiomoni.skimmer.session import CW_SEGMENTS, SkimmerSession

    if req.record_iq:
        ensure_disk_space()
    low, high = (req.freq_low, req.freq_high) if req.freq_low and req.freq_high else CW_SEGMENTS[req.band or '20m']
    session = SkimmerSession(freq_low=low, freq_high=high, gain=req.gain, duration=req.duration, mode=req.mode,
                             contest=req.contest, max_decoders=req.max_decoders, sample_rate=req.sample_rate,
                             record_iq=req.record_iq, include_rbn=req.include_rbn, device_type=req.device_type,
                             device_address=str(req.device_address) if req.device_address else None,
                             output_dir=recording_dir())
    session_id = start_stream_session(session, 'skimmer', session.seg_centre, session.sample_rate, req.gain)
    return {'session_id': session_id, 'mode': 'skimmer', 'frequency': session.seg_centre, **session.state()}


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
    if action == 'cw':
        return start_cw(CwRequest.model_validate(params))
    if action == 'skimmer':
        return start_skimmer(SkimmerRequest.model_validate(params))
    raise ValueError(f"Unknown action: {action}")

