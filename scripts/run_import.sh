#!/usr/bin/env bash
# Import the Swiss repeater list (or another CSV) into the running stack.
#   ./scripts/run_import.sh [scripts/repeaterbook_ch_fm.csv]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
CSV="${1:-scripts/repeaterbook_ch_fm.csv}"
docker compose exec -T radio-api python scripts/elasticsearch/import_repeaters_to_es.py "$CSV"
