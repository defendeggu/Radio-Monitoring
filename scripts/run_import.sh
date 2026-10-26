#!/usr/bin/env bash
# Import the Swiss repeater list (or another CSV) into the running stack.
#   ./scripts/run_import.sh          # scripts/repeaters_ch.csv (USKA list); repeaters no longer
#                                    # listed there are marked inactive
#   ./scripts/run_import.sh my.csv   # add/update the repeaters of another CSV only
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ $# -eq 0 ]]; then
  docker compose exec -T radio-api python scripts/elasticsearch/import_repeaters_to_es.py \
    scripts/repeaters_ch.csv --deactivate-missing
else
  docker compose exec -T radio-api python scripts/elasticsearch/import_repeaters_to_es.py "$1"
fi
