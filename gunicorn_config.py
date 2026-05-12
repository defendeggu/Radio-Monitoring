"""
Gunicorn configuration for Radio Transcription System API

Production WSGI server configuration optimized for:
- Long-running streaming sessions (1-24 hours)
- Asynchronous I/O with gevent workers
- Multiple concurrent users
- Graceful restarts without session loss
"""

import multiprocessing
import os

# =============================================================================
# Server Socket
# =============================================================================

bind = "0.0.0.0:5000"
backlog = 2048  # Maximum number of pending connections

# =============================================================================
# Worker Processes
# =============================================================================

# Worker count formula: (2 x CPU cores) + 1
# Override with GUNICORN_WORKERS environment variable
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))

# Worker class: gevent for async I/O (perfect for streaming sessions)
worker_class = 'gevent'

# Maximum simultaneous clients per worker
worker_connections = 1000

# Restart workers after N requests (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 50  # Randomize restart to avoid all workers restarting at once

# Worker timeout: voice captures run up to 600s + ~60s transcription overhead
# 660s ensures the worker is not killed before the longest allowed capture completes.
# When the async capture refactor lands this can be reduced back to 120s.
timeout = 660

# Keep-alive connections
keepalive = 5

# =============================================================================
# Logging
# =============================================================================

# Log to stdout/stderr (Docker best practice)
accesslog = '-'
errorlog = '-'

# Log level
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')

# Access log format (includes response time in microseconds)
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s µs'

# =============================================================================
# Process Naming
# =============================================================================

proc_name = 'radio-api'

# =============================================================================
# Server Mechanics
# =============================================================================

daemon = False  # Run in foreground (Docker requirement)
pidfile = None
umask = 0
user = None  # Set by Docker/Dockerfile
group = None
tmp_upload_dir = None

# =============================================================================
# Security
# =============================================================================

# Limit request sizes to prevent DoS attacks
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# =============================================================================
# Graceful Shutdown
# =============================================================================

# Grace period for workers to finish serving requests during shutdown
# Important: Streaming sessions need time to clean up properly
graceful_timeout = 30

# =============================================================================
# Server Hooks
# =============================================================================

def on_starting(server):
    """Called before the master process starts."""
    server.log.info("=" * 60)
    server.log.info("Radio Transcription System API - Starting")
    server.log.info("=" * 60)
    server.log.info(f"Workers: {workers} ({worker_class})")
    server.log.info(f"Bind: {bind}")
    server.log.info(f"Timeout: {timeout}s")
    server.log.info(f"Worker Connections: {worker_connections}")
    server.log.info("=" * 60)


def on_reload(server):
    """Called when configuration is reloaded."""
    server.log.info("Configuration reloaded - gracefully restarting workers")


def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal."""
    worker.log.info(f"Worker {worker.pid} received INT/QUIT - graceful shutdown")


def worker_abort(worker):
    """Called when a worker receives the ABRT signal."""
    worker.log.warning(f"Worker {worker.pid} received ABRT - forced shutdown!")


def pre_fork(server, worker):
    """Called before a worker is forked."""
    pass


def post_fork(server, worker):
    """Called after a worker is forked."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")


def pre_exec(server):
    """Called before a new master process is forked."""
    server.log.info("Forking new master process")


def when_ready(server):
    """Called when the server is ready to accept requests."""
    server.log.info("=" * 60)
    server.log.info("Server is ready - accepting connections")
    server.log.info("=" * 60)


def worker_exit(server, worker):
    """Called when a worker exits."""
    server.log.info(f"Worker exited (pid: {worker.pid})")


def nworkers_changed(server, new_value, old_value):
    """Called when the number of workers changes."""
    server.log.info(f"Worker count changed: {old_value} → {new_value}")
