"""
Gunicorn configuration for the RadioMoni API.

One worker process with many threads (gthread):
- the SDR is a single device; live decoder objects, the scheduler and the
  capture queue belong to one process,
- threads handle concurrent requests and long-lived SSE connections,
- DSP code (NumPy/SciPy) and subprocess pipes work reliably with real threads
  (gevent monkey-patching does not play well with them).

The SDR lock, sessions and control messages live in Redis, so running more
workers is possible (GUNICORN_WORKERS), but not needed for one station.
"""

import os

bind = os.getenv('GUNICORN_BIND', '0.0.0.0:5000')
backlog = 256

workers = int(os.getenv('GUNICORN_WORKERS', '1'))
worker_class = 'gthread'
threads = int(os.getenv('GUNICORN_THREADS', '32'))

# Recycling a worker would kill running streams — keep the process alive.
max_requests = 0

# Worker heartbeat timeout. Long requests (SSE) run in threads and do not block it.
timeout = int(os.getenv('GUNICORN_TIMEOUT', '120'))
graceful_timeout = 30
keepalive = 5

accesslog = '-'
errorlog = '-'
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'

proc_name = 'radio-api'
daemon = False
pidfile = None
# Recordings must not be world-writable
umask = 0o027
worker_tmp_dir = '/dev/shm' if os.path.isdir('/dev/shm') else None
# No gunicornc control socket: /app is read-only in the container and nothing uses it
control_socket_disable = True

limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190


def on_starting(server):  # type: ignore[no-untyped-def]
    server.log.info(f"RadioMoni API starting: {workers} worker(s) x {threads} threads, bind {bind}")
