#!/bin/bash
export PYTHONPATH=/app
python /app/scripts/elasticsearch/import_repeaters_to_es.py /app/scripts/example_repeaters.csv --es-hosts "$ELASTICSEARCH_HOSTS"