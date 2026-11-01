"""
Health endpoints.

/health        liveness (process is up) — used by the container healthcheck
/health/ready  readiness: Redis, storage backend and SDR lock state
/metrics/gpu   NVIDIA GPU usage in Prometheus text format (Metricbeat, GPU setup)
"""

import shutil
import subprocess
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify

from radiomoni.errors import ApiError

from radiomoni import config
from radiomoni import redis_client
from radiomoni import sdr_lock
from radiomoni.api_docs import api
from radiomoni.version import __version__

health_bp = Blueprint('health', __name__)


@health_bp.get('/health')
@api('Liveness check', tags=['System'])
def health() -> Response:
    return jsonify({
        'status': 'healthy',
        'service': 'radio-transcription-api',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': __version__,
    })


@health_bp.get('/health/ready')
@api('Readiness check (Redis, storage, SDR)', tags=['System'], responses={503: 'A dependency is down'})
def ready() -> tuple[Response, int]:
    from radiomoni.storage.base import get_storage

    redis_ok = redis_client.ping()
    try:
        storage = get_storage().health_check()
    except Exception:
        storage = {'status': 'error'}
    storage_ok = storage.get('status') in ('green', 'yellow')
    holder = sdr_lock.current_holder() if redis_ok else None
    ok = redis_ok and storage_ok
    return jsonify({
        'status': 'ready' if ok else 'degraded',
        'version': __version__,
        'checks': {
            'redis': 'ok' if redis_ok else 'down',
            'storage': {'backend': config.STORAGE_BACKEND, **storage},
            'sdr': {'busy': holder is not None, 'holder': holder},
        },
    }), 200 if ok else 503


# nvidia-smi query field -> (metric name, help text)
GPU_METRICS = {
    'utilization.gpu': ('radiomoni_gpu_utilization_percent', 'GPU utilization'),
    'utilization.memory': ('radiomoni_gpu_memory_utilization_percent', 'GPU memory bandwidth utilization'),
    'memory.used': ('radiomoni_gpu_memory_used_mib', 'GPU memory used (MiB)'),
    'memory.total': ('radiomoni_gpu_memory_total_mib', 'GPU memory total (MiB)'),
    'temperature.gpu': ('radiomoni_gpu_temperature_celsius', 'GPU temperature'),
    'power.draw': ('radiomoni_gpu_power_draw_watts', 'GPU power draw'),
}


def gpu_metrics_text(csv: str) -> str:
    """Prometheus text from nvidia-smi CSV (index, GPU_METRICS, name). Skips [N/A] values."""
    samples: dict[str, list[str]] = {name: [] for name, _ in GPU_METRICS.values()}
    for line in csv.strip().splitlines():
        # name last: it is the only free-text column and may contain commas
        index, *values, name = [v.strip() for v in line.split(',', len(GPU_METRICS) + 1)]
        clean = name.replace('\\', '').replace('"', '')
        labels = f'{{gpu="{index}",name="{clean}"}}'
        for (metric, _), value in zip(GPU_METRICS.values(), values, strict=True):
            try:
                samples[metric].append(f'{metric}{labels} {float(value)}')
            except ValueError:
                continue
    out = []
    for metric, help_text in GPU_METRICS.values():
        if samples[metric]:
            out += [f'# HELP {metric} {help_text}', f'# TYPE {metric} gauge', *samples[metric]]
    return '\n'.join(out) + '\n'


@health_bp.get('/metrics/gpu')
@api('GPU usage (Prometheus text format)', tags=['System'], responses={503: 'No NVIDIA GPU available'})
def gpu_metrics() -> Response:
    """Utilization, memory, temperature and power of the NVIDIA GPUs, read with nvidia-smi."""
    if not shutil.which('nvidia-smi'):
        raise ApiError('No NVIDIA GPU available (nvidia-smi not found)', 503)
    query = ','.join(['index', *GPU_METRICS, 'name'])
    try:
        result = subprocess.run(['nvidia-smi', f'--query-gpu={query}', '--format=csv,noheader,nounits'],
                                capture_output=True, text=True, timeout=10, check=True)
    except (subprocess.SubprocessError, OSError) as e:
        raise ApiError(f'nvidia-smi failed: {e}', 503)
    return Response(gpu_metrics_text(result.stdout), mimetype='text/plain', headers={'Cache-Control': 'no-store'})
