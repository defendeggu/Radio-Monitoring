#!/usr/bin/env python3
"""
Keep the version number the same everywhere. Source of truth: radiomoni/version.py.

    python3 scripts/version.py check        # exit 1 if README badge or frontend differ (runs in CI)
    python3 scripts/version.py set 4.1.0    # write the version to all places

Places: radiomoni/version.py, the version badge in README.md, frontend/package.json
and frontend/package-lock.json (pyproject.toml reads radiomoni/version.py itself).
Standard library only, so it runs on the CI runner without the Docker image.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_PY = ROOT / 'radiomoni' / 'version.py'
README = ROOT / 'README.md'
PACKAGE = ROOT / 'frontend' / 'package.json'
LOCK = ROOT / 'frontend' / 'package-lock.json'

VERSION_RE = re.compile(r'__version__ = "([^"]+)"')
# shields.io writes a literal "-" in the badge text as "--"
BADGE_RE = re.compile(r'(img\.shields\.io/badge/version-)((?:[0-9A-Za-z.+]|--)+?)(-[0-9a-f]{6})')
SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.]+)?$')


def source_version() -> str:
    match = VERSION_RE.search(VERSION_PY.read_text(encoding='utf-8'))
    if not match:
        raise SystemExit(f'No __version__ in {VERSION_PY}')
    return match.group(1)


def found_versions() -> dict[str, str | None]:
    badge = BADGE_RE.search(README.read_text(encoding='utf-8'))
    lock = json.loads(LOCK.read_text(encoding='utf-8'))
    return {
        'README.md (badge)': badge.group(2).replace('--', '-') if badge else None,
        'frontend/package.json': json.loads(PACKAGE.read_text(encoding='utf-8')).get('version'),
        'frontend/package-lock.json': lock.get('version'),
        'frontend/package-lock.json (packages[""])': lock.get('packages', {}).get('', {}).get('version'),
    }


def check() -> int:
    expected = source_version()
    wrong = {place: v for place, v in found_versions().items() if v != expected}
    for place, v in wrong.items():
        print(f'{place}: {v or "missing"} (expected {expected} from radiomoni/version.py)')
    if wrong:
        print(f'Fix with: python3 scripts/version.py set {expected}')
        return 1
    print(f'Version {expected} is consistent.')
    return 0


def set_version(version: str) -> int:
    if not SEMVER_RE.match(version):
        raise SystemExit(f'Not a semantic version: {version}')
    VERSION_PY.write_text(VERSION_RE.sub(f'__version__ = "{version}"', VERSION_PY.read_text(encoding='utf-8')),
                          encoding='utf-8')
    readme = README.read_text(encoding='utf-8')
    if not BADGE_RE.search(readme):
        raise SystemExit('No version badge in README.md')
    README.write_text(BADGE_RE.sub(lambda m: m.group(1) + version.replace('-', '--') + m.group(3), readme, count=1),
                      encoding='utf-8')
    for path, keys in ((PACKAGE, [()]), (LOCK, [(), ('packages', '')])):
        data = json.loads(path.read_text(encoding='utf-8'))
        for key in keys:
            target = data
            for part in key:
                target = target[part]
            target['version'] = version
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Version set to {version}. Add a "## [{version}]" section to CHANGELOG.md.')
    return check()


def main() -> int:
    match sys.argv[1:]:
        case ['check']:
            return check()
        case ['set', version]:
            return set_version(version)
        case _:
            print(__doc__.strip())
            return 2


if __name__ == '__main__':
    sys.exit(main())
