"""
Central configuration for the RadioMoni API.

All settings are read from environment variables once at import time.
Modules should import values from here instead of calling os.getenv directly.
"""

import os


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == '':
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == '':
        return default
    return int(value)


def _list(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, '').split(',') if item.strip()]


# --- Security ---------------------------------------------------------------
API_KEYS: list[str] = _list('API_KEYS')
TRUSTED_IPS: list[str] = _list('TRUSTED_IPS')
CORS_ORIGINS: list[str] = _list('CORS_ORIGINS')
# Without API keys the API refuses to start unless this is explicitly set.
ALLOW_INSECURE: bool = _bool('ALLOW_INSECURE')
# Number of reverse proxies in front of the API (nginx = 1). Used for X-Forwarded-For.
PROXY_COUNT: int = _int('PROXY_COUNT', 1)

# --- Storage ----------------------------------------------------------------
# "elasticsearch" (full stack) or "sqlite" (light profile, no ELK)
STORAGE_BACKEND: str = os.getenv('STORAGE_BACKEND', 'elasticsearch').strip().lower()
SQLITE_PATH: str = os.getenv('SQLITE_PATH', './data/radiomoni.sqlite3')

# --- Redis ------------------------------------------------------------------
REDIS_HOST: str = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT: int = _int('REDIS_PORT', 6379)
REDIS_DB: int = _int('REDIS_DB', 0)
REDIS_PASSWORD: str | None = os.getenv('REDIS_PASSWORD') or None
# Tests use an in-process fake Redis (requires the "fakeredis" dev dependency).
REDIS_FAKE: bool = _bool('SKIP_REDIS_CHECK') or _bool('REDIS_FAKE')

# --- Recordings -------------------------------------------------------------
RECORDING_DIR: str = os.getenv('AUDIO_OUTPUT_DIR', './recordings')
RECORDING_RETENTION_DAYS: int = _int('RECORDING_RETENTION_DAYS', 30)
MIN_FREE_DISK_MB: int = _int('MIN_FREE_DISK_MB', 500)
# Secret for signed recording links (audio player in Kibana). Empty = no links.
RECORDING_LINK_SECRET: str = os.getenv('RECORDING_LINK_SECRET', '')

# --- Whisper ----------------------------------------------------------------
WHISPER_MODEL: str = os.getenv('WHISPER_MODEL', 'small')
WHISPER_DEVICE: str = os.getenv('WHISPER_DEVICE', 'cpu')
WHISPER_COMPUTE_TYPE: str = os.getenv('WHISPER_COMPUTE_TYPE', 'int8')
WHISPER_BEAM_SIZE: int = _int('WHISPER_BEAM_SIZE', 5)
WHISPER_INITIAL_PROMPT: str | None = os.getenv('WHISPER_INITIAL_PROMPT') or None

# Decoders/transcription fall back to fake data only when this is enabled.
SIMULATION_MODE: bool = _bool('SIMULATION_MODE')

# --- Limits -----------------------------------------------------------------
MAX_CAPTURE_SECONDS: dict[str, int] = {'voice': 600, 'aprs': 300, 'pocsag': 120, 'raw': 600}
MAX_STREAM_DURATION: int = _int('MAX_STREAM_DURATION', 86400)
MAX_REPEATER_SCAN_SECONDS: int = _int('MAX_REPEATER_SCAN_SECONDS', 600)
SCAN_SESSION_MAX_AGE_HOURS: int = _int('REPEATER_SESSION_MAX_AGE_HOURS', 24)

# --- Scheduler --------------------------------------------------------------
SCHEDULER_ENABLED: bool = _bool('SCHEDULER_ENABLED', True)
TIMEZONE: str = os.getenv('TZ', 'Europe/Zurich')

# --- Notifications (alerts) -------------------------------------------------
NTFY_URL: str | None = os.getenv('NTFY_URL') or None          # e.g. https://ntfy.sh/my-topic
NTFY_TOKEN: str | None = os.getenv('NTFY_TOKEN') or None
TELEGRAM_BOT_TOKEN: str | None = os.getenv('TELEGRAM_BOT_TOKEN') or None
TELEGRAM_CHAT_ID: str | None = os.getenv('TELEGRAM_CHAT_ID') or None
ALERT_WEBHOOK_URL: str | None = os.getenv('ALERT_WEBHOOK_URL') or None
SMTP_HOST: str | None = os.getenv('SMTP_HOST') or None
SMTP_PORT: int = _int('SMTP_PORT', 587)
SMTP_USER: str | None = os.getenv('SMTP_USER') or None
SMTP_PASSWORD: str | None = os.getenv('SMTP_PASSWORD') or None
SMTP_FROM: str | None = os.getenv('SMTP_FROM') or None
ALERT_EMAIL_TO: str | None = os.getenv('ALERT_EMAIL_TO') or None

# --- Logstash ingestion -----------------------------------------------------
LOGSTASH_HTTP_USER: str = os.getenv('LOGSTASH_HTTP_USER', 'radio')
LOGSTASH_HTTP_PASSWORD: str | None = os.getenv('LOGSTASH_HTTP_PASSWORD') or None
