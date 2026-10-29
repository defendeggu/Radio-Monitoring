"""
Streaming endpoints: long-running APRS/POCSAG sessions, multi-channel DDC
(USRP N200), VOX recording and external decoders (ADS-B/AIS/ISM).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, Response, jsonify

from radiomoni import actions
from radiomoni import events
from radiomoni.api_docs import api, parse_body
from radiomoni.errors import ApiError, call_action
from radiomoni.jobs import start_stream_session
from radiomoni.schemas import (ExternalDecoderRequest, LegacyStreamRequest, MultiChannelRequest, StreamRequest,
                     VoxRequest)
from radiomoni.session_store import session_manager
from radiomoni.streaming_decoder_service import ChannelConfig, MultiChannelStreamingDecoder

logger = logging.getLogger(__name__)
streaming_bp = Blueprint('streaming', __name__)

LEGACY_DEFAULT_FREQ = {'aprs': 144_800_000, 'pocsag': 147_325_000}


@streaming_bp.post('/stream-decode')
@api('Start an APRS or POCSAG streaming session', tags=['Streaming'], body=StreamRequest,
     responses={409: 'SDR busy', 503: 'No SDR detected'})
def start_streaming_decode() -> Response:
    req = parse_body(StreamRequest)
    result = call_action(actions.start_stream, req)
    return jsonify({'status': 'success', 'message': f'{req.mode.upper()} streaming started', **result})


def _legacy_start(mode: str) -> Response:
    raw = parse_body(LegacyStreamRequest)
    data = raw.model_dump()
    data['frequency'] = data['frequency'] or LEGACY_DEFAULT_FREQ[mode]
    req = StreamRequest.model_validate({**data, 'mode': mode})
    result = call_action(actions.start_stream, req)
    response = jsonify({'status': 'success', 'message': f'{mode.upper()} streaming started', **result})
    response.headers['Deprecation'] = 'true'
    response.headers['Link'] = '</stream-decode>; rel="successor-version"'
    return response


@streaming_bp.post('/stream/aprs/start')
@api('Start APRS streaming (deprecated, use POST /stream-decode)', tags=['Streaming'],
     body=LegacyStreamRequest, deprecated=True)
def start_aprs_streaming() -> Response:
    return _legacy_start('aprs')


@streaming_bp.post('/stream/pocsag/start')
@api('Start POCSAG streaming (deprecated, use POST /stream-decode)', tags=['Streaming'],
     body=LegacyStreamRequest, deprecated=True)
def start_pocsag_streaming() -> Response:
    return _legacy_start('pocsag')


@streaming_bp.post('/vox/start')
@api('Start squelch-controlled (VOX) voice recording', tags=['Streaming'], body=VoxRequest,
     responses={409: 'SDR busy'})
def start_vox() -> Response:
    req = parse_body(VoxRequest)
    return jsonify({'status': 'success', 'message': 'VOX recording started',
                    **call_action(actions.start_vox, req)})


@streaming_bp.post('/decoders/start')
@api('Start an ADS-B, AIS or ISM (rtl_433) decoder session', tags=['Decoders'], body=ExternalDecoderRequest,
     responses={409: 'SDR busy', 503: 'Tool not installed'})
def start_external_decoder() -> Response:
    req = parse_body(ExternalDecoderRequest)
    return jsonify({'status': 'success', 'message': f'{req.decoder.upper()} decoder started',
                    **call_action(actions.start_external_decoder, req)})


@streaming_bp.post('/stream/multi/start')
@api('Start a multi-channel DDC session (USRP N200)', tags=['Streaming'], body=MultiChannelRequest,
     responses={409: 'SDR busy'})
def start_multi_channel_streaming() -> Response:
    req = parse_body(MultiChannelRequest)
    half_bw = req.wideband_rate / 2.0
    channels: list[ChannelConfig] = []
    seen: list[int] = []
    for i, ch in enumerate(req.channels):
        label = ch.label or f'ch{i}'
        bw = 16000 if ch.mode == 'aprs' else 25000
        if abs(ch.frequency - req.center_freq) + bw / 2 > half_bw:
            raise ApiError(f'Channel "{label}" ({ch.frequency} Hz) is outside the wideband range', 400)
        if any(abs(ch.frequency - f) < 50_000 for f in seen):
            raise ApiError(f'Channel "{label}": minimum 50 kHz separation required', 400)
        seen.append(ch.frequency)
        channels.append(ChannelConfig(mode=ch.mode, frequency=ch.frequency, label=label, channel_bw_hz=bw))

    def build() -> tuple[MultiChannelStreamingDecoder, str]:
        decoder = MultiChannelStreamingDecoder(center_freq=req.center_freq, wideband_rate=req.wideband_rate,
                                               gain=req.gain, duration=req.duration, channels=channels,
                                               device_address=str(req.device_address))

        def configure(session: Any) -> None:
            if session:
                session.channel_configs = [{'mode': c.mode, 'frequency': c.frequency, 'label': c.label}
                                           for c in channels]
                session_manager.save_session(session)

        sid = start_stream_session(decoder, 'multi', req.center_freq, req.wideband_rate, req.gain, configure)
        return decoder, sid

    decoder, session_id = call_action(build)
    return jsonify({
        'status': 'success', 'session_id': session_id, 'message': 'Multi-channel streaming started',
        'center_freq': req.center_freq, 'wideband_rate': req.wideband_rate,
        'decimation_factor': decoder.decimation_factor, 'intermediate_rate': decoder.intermediate_rate,
        'channels': [{'mode': c.mode, 'frequency': c.frequency, 'label': c.label} for c in channels],
    })


@streaming_bp.get('/stream-decode/<session_id>')
@api('Status of a streaming session', tags=['Streaming'], responses={404: 'Unknown session'})
def get_streaming_session(session_id: str) -> Response:
    session_manager.reap_orphaned_sessions()
    session = session_manager.get_session(session_id)
    if not session:
        raise ApiError('Session not found', 404)
    end = session.end_time or datetime.now(timezone.utc)
    return jsonify({
        'status': session.status,
        'session': session.to_dict(),
        'stats': {
            'packet_count': session.packet_count,
            'elapsed_seconds': (end - session.start_time).total_seconds(),
            'last_packet_time': session.last_packet_time.isoformat() if session.last_packet_time else None,
            'error': session.error,
        },
    })


@streaming_bp.delete('/stream-decode/<session_id>')
@api('Stop a streaming session', tags=['Streaming'], responses={404: 'Unknown session'})
def stop_streaming_session(session_id: str) -> Response:
    session = session_manager.get_session(session_id)
    if not session:
        raise ApiError('Session not found', 404)
    if not stop_session(session_id) and not session_manager.reap_orphaned_sessions():
        # owned by another API process: ask it to stop via the control channel
        events.send_control('stop', session_id=session_id)
    return jsonify({'status': 'success', 'message': 'Streaming session stopped'})


@streaming_bp.get('/stream-decode')
@api('List streaming sessions', tags=['Streaming'])
def list_streaming_sessions() -> Response:
    session_manager.reap_orphaned_sessions()
    sessions = sorted(session_manager.list_sessions(), key=lambda s: s.start_time, reverse=True)
    return jsonify({'status': 'success', 'count': len(sessions), 'sessions': [s.to_dict() for s in sessions]})


def stop_session(session_id: str) -> bool:
    """Stop a decoder owned by this process. Returns False if it is not local."""
    decoder = session_manager.get_decoder(session_id)
    if not decoder:
        return False
    logger.info(f"Stopping decoder for session {session_id}")
    decoder.stop_stream()
    session_manager.unregister_decoder(session_id)
    return True
