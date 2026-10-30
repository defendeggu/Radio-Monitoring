#!/usr/bin/env python3
"""
Check .env before starting the stack (standard library only).

    python3 scripts/validate_env.py           # errors → exit code 1
    python3 scripts/validate_env.py --strict  # warnings count as errors
"""

import ipaddress
import sys
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / '.env'

SECRETS = ['REDIS_PASSWORD', 'ELASTIC_PASSWORD', 'KIBANA_SYSTEM_PASSWORD', 'LOGSTASH_WRITER_PASSWORD',
           'LOGSTASH_HTTP_PASSWORD', 'BEATS_WRITER_PASSWORD', 'RADIO_API_PASSWORD', 'KIBANA_ENCRYPTION_KEY']


def load(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    strict = '--strict' in sys.argv
    if not ENV_FILE.exists():
        print("No .env found. Create it with: ./scripts/setup-env.sh")
        return 1
    env = load(ENV_FILE)
    errors: list[str] = []
    warnings: list[str] = []

    keys = [k for k in env.get('API_KEYS', '').split(',') if k]
    if not keys:
        errors.append('API_KEYS is empty — the API refuses to start without keys')
    elif any(len(k) < 32 for k in keys):
        warnings.append('API_KEYS: keys shorter than 32 characters')

    elk = 'elk' in env.get('COMPOSE_PROFILES', '').split(',')
    required = SECRETS if elk else ['REDIS_PASSWORD']
    for name in required:
        value = env.get(name, '')
        if not value or value.lower().startswith('changeme'):
            errors.append(f'{name} is missing or a placeholder')
        elif len(value) < 16:
            warnings.append(f'{name} is short ({len(value)} characters)')

    backend = env.get('STORAGE_BACKEND', 'elasticsearch')
    if backend not in ('elasticsearch', 'sqlite'):
        errors.append(f'STORAGE_BACKEND must be elasticsearch or sqlite, not {backend!r}')
    if backend == 'elasticsearch' and not elk:
        errors.append('STORAGE_BACKEND=elasticsearch needs COMPOSE_PROFILES=elk')

    for entry in [e for e in env.get('TRUSTED_IPS', '').split(',') if e.strip()]:
        try:
            net = ipaddress.ip_network(entry.strip(), strict=False)
            if net.num_addresses > 2 ** 16:
                warnings.append(f'TRUSTED_IPS entry {entry} is very large ({net.num_addresses} addresses)')
        except ValueError:
            errors.append(f'TRUSTED_IPS entry {entry!r} is not an IP address or network')

    if env.get('ALLOW_INSECURE', '').lower() == 'true':
        warnings.append('ALLOW_INSECURE=true disables the startup check — development only')
    if env.get('KIBANA_BIND', '127.0.0.1') not in ('127.0.0.1', 'localhost', '::1'):
        warnings.append('Kibana is published on all interfaces (KIBANA_BIND)')

    for e in errors:
        print(f'ERROR   {e}')
    for w in warnings:
        print(f'WARNING {w}')
    if not errors and not warnings:
        print('.env looks good.')
    return 1 if errors or (strict and warnings) else 0


if __name__ == '__main__':
    sys.exit(main())
