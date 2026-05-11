"""
Streaming Decoder Blueprint

Provides endpoints for real-time streaming decoding:
- Start APRS streaming
- Start POCSAG streaming
- Start generic streaming decode
- Get stream status
- Stop stream
- List active streams
"""

from flask import Blueprint, request, jsonify, Response
from typing import Union
import os
import signal
from streaming_decoder_service import (
    StreamingAPRSDecoder,
    StreamingPOCSAGDecoder,
    MultiChannelStreamingDecoder,
    ChannelConfig
)
from session_store import session_manager
import logging

logger = logging.getLogger(__name__)

# Create blueprint
streaming_bp = Blueprint('streaming', __name__)


@streaming_bp.route('/stream/aprs/start', methods=['POST'])
def start_aprs_streaming() -> Response | tuple[Response, int]:
    """
    Start APRS streaming decoder session

    Request body:
    {
        "frequency": 144800000,  // APRS frequency in Hz
        "sample_rate": 2000000,  // optional
        "gain": 20              // optional
    }
    """
    try:

        data = request.get_json() or {}

        frequency = data.get('frequency', 144800000)
        sample_rate = data.get('sample_rate', 2000000)
        gain = data.get('gain', 20)
        duration = data.get('duration', 3600)
        device_type = data.get('device_type', 'auto')
        device_address = data.get('device_address') or None

        if device_type == 'usrp' and not device_address:
            return jsonify({'error': 'USRP N200 requires device_address (IP address)'}), 400

        # Create streaming decoder
        decoder = StreamingAPRSDecoder(
            frequency=frequency,
            duration=duration,
            sample_rate=sample_rate,
            gain=gain,
            device_type=device_type,
            device_address=device_address
        )

        # Create session
        session_id = session_manager.create_session(
            decoder_type='aprs',
            decoder=decoder,
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain
        )

        # Start streaming
        decoder.start(session_manager)

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': 'APRS streaming started',
            'frequency': frequency
        })

    except Exception as e:
        logger.error(f"Failed to start APRS streaming: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/stream/pocsag/start', methods=['POST'])
def start_pocsag_streaming() -> Response | tuple[Response, int]:
    """
    Start POCSAG streaming decoder session

    Request body:
    {
        "frequency": 147325000,  // POCSAG frequency in Hz
        "sample_rate": 2000000,  // optional
        "gain": 20              // optional
    }
    """
    try:

        data = request.get_json() or {}

        frequency = data.get('frequency', 147325000)
        sample_rate = data.get('sample_rate', 2000000)
        gain = data.get('gain', 20)
        duration = data.get('duration', 3600)
        device_type = data.get('device_type', 'auto')
        device_address = data.get('device_address') or None

        if device_type == 'usrp' and not device_address:
            return jsonify({'error': 'USRP N200 requires device_address (IP address)'}), 400

        # Create streaming decoder
        decoder = StreamingPOCSAGDecoder(
            frequency=frequency,
            duration=duration,
            sample_rate=sample_rate,
            gain=gain,
            device_type=device_type,
            device_address=device_address
        )

        # Create session
        session_id = session_manager.create_session(
            decoder_type='pocsag',
            decoder=decoder,
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain
        )

        # Start streaming
        decoder.start(session_manager)

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': 'POCSAG streaming started',
            'frequency': frequency
        })

    except Exception as e:
        logger.error(f"Failed to start POCSAG streaming: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/stream-decode', methods=['POST'])
def start_streaming_decode() -> Response | tuple[Response, int]:
    """
    Start a streaming decode session (generic)

    Request body:
    {
        "mode": "aprs",          // "aprs" or "pocsag"
        "frequency": 144800000,
        "sample_rate": 2000000,  // optional
        "gain": 20               // optional
    }
    """
    try:

        data = request.get_json() or {}

        mode = data.get('mode', 'aprs')
        frequency = data.get('frequency')
        sample_rate = data.get('sample_rate', 2000000)
        gain = data.get('gain', 20)
        duration = data.get('duration', 3600)
        device_type = data.get('device_type', 'auto')
        device_address = data.get('device_address') or None

        if not frequency:
            return jsonify({'error': 'frequency is required'}), 400

        if mode not in ['aprs', 'pocsag']:
            return jsonify({'error': 'mode must be "aprs" or "pocsag"'}), 400

        if device_type == 'usrp' and not device_address:
            return jsonify({'error': 'USRP N200 requires device_address (IP address)'}), 400

        # Create appropriate decoder
        decoder: Union[StreamingAPRSDecoder, StreamingPOCSAGDecoder]
        if mode == 'aprs':
            decoder = StreamingAPRSDecoder(
                frequency=frequency,
                duration=duration,
                sample_rate=sample_rate,
                gain=gain,
                device_type=device_type,
                device_address=device_address
            )
        else:  # pocsag
            decoder = StreamingPOCSAGDecoder(
                frequency=frequency,
                duration=duration,
                sample_rate=sample_rate,
                gain=gain,
                device_type=device_type,
                device_address=device_address
            )

        # Create session
        session_id = session_manager.create_session(
            decoder_type=mode,
            decoder=decoder,
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain
        )

        # Start streaming
        decoder.start(session_manager)

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': f'{mode.upper()} streaming started',
            'mode': mode,
            'frequency': frequency
        })

    except Exception as e:
        logger.error(f"Failed to start streaming decode: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/stream-decode/<session_id>', methods=['GET'])
def get_streaming_session(session_id: str) -> Response | tuple[Response, int]:
    """Get status and results of a streaming decode session"""
    try:

        session = session_manager.get_session(session_id)

        if not session:
            return jsonify({
                'status': 'error',
                'message': 'Session not found'
            }), 404

        return jsonify({
            'status': 'success',
            'session': session.to_dict()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/stream-decode/<session_id>', methods=['DELETE'])
def stop_streaming_session(session_id: str) -> Response | tuple[Response, int]:
    """Stop a streaming decode session and release the HackRF."""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({'status': 'error', 'message': 'Session not found'}), 404

        # Use the live decoder instance if available (preferred: clean shutdown)
        decoder = session_manager.get_decoder(session_id)
        if decoder:
            logger.info(f"Stopping decoder for session {session_id} via registry")
            decoder.stop_stream()  # Sets stop_event, joins thread, kills subprocesses
            session_manager.unregister_decoder(session_id)
        else:
            # Fallback for sessions whose decoder is no longer in memory
            logger.warning(f"No live decoder for {session_id} — using pkill fallback")
            _kill_sdr_processes()

        session_manager.delete_session(session_id)
        return jsonify({'status': 'success', 'message': 'Streaming session stopped'})

    except Exception as e:
        logger.error(f"Failed to stop streaming session: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/sdr/force-stop', methods=['POST'])
def sdr_force_stop() -> Response | tuple[Response, int]:
    """Emergency stop: kill all active decoders and SDR processes.
    Used by the Voice module and whenever the HackRF is stuck."""
    try:
        # Stop all registered decoder instances cleanly
        decoders = session_manager.get_all_active_decoders()
        for sid, decoder in decoders.items():
            try:
                logger.info(f"Force-stopping decoder for session {sid}")
                decoder.stop_stream()
            except Exception as e:
                logger.warning(f"Error stopping decoder {sid}: {e}")
            session_manager.unregister_decoder(sid)

        # Force-kill any remaining SDR processes (catches Voice capture too)
        killed = _kill_sdr_processes()

        return jsonify({
            'status': 'success',
            'message': 'All SDR processes stopped',
            'sessions_stopped': len(decoders),
            'processes_killed': killed
        })

    except Exception as e:
        logger.error(f"Force-stop failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def _kill_sdr_processes() -> list[str]:
    """SIGKILL all SDR-related processes by scanning /proc. Returns list of PIDs killed."""
    targets = {'hackrf_transfer', 'rtl_sdr', 'airspyhf_rx', 'uhd_rx_cfile', 'multimon-ng', 'direwolf'}
    killed = []
    try:
        for pid_str in os.listdir('/proc'):
            if not pid_str.isdigit():
                continue
            try:
                with open(f'/proc/{pid_str}/cmdline', 'rb') as f:
                    cmdline = f.read().split(b'\x00')
                if not cmdline:
                    continue
                exe = os.path.basename(cmdline[0].decode('utf-8', errors='ignore'))
                if exe in targets:
                    os.kill(int(pid_str), signal.SIGKILL)
                    killed.append(exe)
                    logger.info(f"Killed SDR process {exe} (PID {pid_str})")
            except (ProcessLookupError, PermissionError, FileNotFoundError):
                pass
    except Exception as e:
        logger.warning(f"Error scanning /proc for SDR processes: {e}")
    return killed


@streaming_bp.route('/stream/multi/start', methods=['POST'])
def start_multi_channel_streaming() -> Response | tuple[Response, int]:
    """
    Start a multi-channel DDC streaming session (USRP N200 only).

    Request body:
    {
        "device_address": "192.168.10.2",
        "center_freq": 146000000,
        "wideband_rate": 5000000,
        "gain": 30,
        "duration": 3600,
        "channels": [
            {"mode": "aprs",   "frequency": 144800000, "label": "APRS-EU"},
            {"mode": "pocsag", "frequency": 147325000, "label": "POCSAG-1"}
        ]
    }
    """
    try:
        data = request.get_json() or {}

        device_address = data.get('device_address') or None
        if not device_address:
            return jsonify({'error': 'device_address (USRP N200 IP) is required'}), 400

        center_freq = data.get('center_freq')
        if not center_freq:
            return jsonify({'error': 'center_freq is required'}), 400
        if not (50_000_000 <= int(center_freq) <= 2_200_000_000):
            return jsonify({'error': 'center_freq must be in WBX range: 50 MHz – 2.2 GHz'}), 400

        wideband_rate = int(data.get('wideband_rate', 5_000_000))
        if not (1_000_000 <= wideband_rate <= 25_000_000):
            return jsonify({'error': 'wideband_rate must be 1–25 MS/s'}), 400

        gain = int(data.get('gain', 30))
        duration = int(data.get('duration', 3600))

        raw_channels = data.get('channels')
        if not raw_channels or not isinstance(raw_channels, list):
            return jsonify({'error': 'channels must be a non-empty list'}), 400
        if not (2 <= len(raw_channels) <= MultiChannelStreamingDecoder.MAX_CHANNELS):
            return jsonify({
                'error': f'2–{MultiChannelStreamingDecoder.MAX_CHANNELS} channels required'
            }), 400

        channels = []
        half_bw = wideband_rate / 2.0
        seen_freqs: list[int] = []
        for i, ch_data in enumerate(raw_channels):
            mode = ch_data.get('mode', '')
            if mode not in ('aprs', 'pocsag'):
                return jsonify({'error': f'Channel {i}: mode must be "aprs" or "pocsag"'}), 400
            freq = ch_data.get('frequency')
            if freq is None:
                return jsonify({'error': f'Channel {i}: frequency is required'}), 400
            freq = int(freq)
            label = str(ch_data.get('label', f'ch{i}'))
            bw = 16000 if mode == 'aprs' else 25000
            if abs(freq - int(center_freq)) + bw / 2 > half_bw:
                return jsonify({
                    'error': f'Channel "{label}" ({freq} Hz) is outside wideband range'
                }), 400
            for prev_freq in seen_freqs:
                if abs(freq - prev_freq) < 50_000:
                    return jsonify({'error': f'Channel "{label}": minimum 50 kHz separation required'}), 400
            seen_freqs.append(freq)
            channels.append(ChannelConfig(mode=mode, frequency=freq, label=label, channel_bw_hz=bw))

        decoder = MultiChannelStreamingDecoder(
            center_freq=int(center_freq),
            wideband_rate=wideband_rate,
            gain=gain,
            duration=duration,
            channels=channels,
            device_address=device_address
        )

        session_id = session_manager.create_session(
            decoder_type='multi',
            decoder=decoder,
            frequency=int(center_freq),
            sample_rate=wideband_rate,
            gain=gain
        )

        # Store channel config in session for status endpoint
        session = session_manager.get_session(session_id)
        if session:
            session.channel_configs = [
                {'mode': ch.mode, 'frequency': ch.frequency, 'label': ch.label}
                for ch in channels
            ]
            session_manager.save_session(session)

        decoder.start(session_manager)

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': 'Multi-channel streaming started',
            'center_freq': int(center_freq),
            'wideband_rate': wideband_rate,
            'decimation_factor': decoder.decimation_factor,
            'intermediate_rate': decoder.intermediate_rate,
            'channels': [{'mode': ch.mode, 'frequency': ch.frequency, 'label': ch.label}
                         for ch in channels]
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to start multi-channel streaming: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/stream-decode', methods=['GET'])
def list_streaming_sessions() -> Response | tuple[Response, int]:
    """List all active streaming decode sessions"""
    try:

        sessions = session_manager.list_sessions()

        return jsonify({
            'status': 'success',
            'count': len(sessions),
            'sessions': [s.to_dict() for s in sessions]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
