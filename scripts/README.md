# Skripte

| Skript | Zweck |
|---|---|
| `setup-env.sh [--light]` | `.env` mit zufälligen Secrets anlegen oder ergänzen |
| `validate_env.py [--strict]` | `.env` prüfen |
| `post-docker-setup.sh` | nach `docker compose up`: ES-Benutzer, Templates, Dashboards |
| `setup-elk-users.sh` | nur den Elasticsearch-Teil (idempotent) |
| `import-kibana-dashboards.sh` | Kibana-Objekte aus `monitoring/kibana/dashboards/` importieren |
| `run_import.sh [csv]` | Repeater-Liste importieren (Standard: `repeaterbook_ch_fm.csv`) |
| `generate_api_keys.py` | zusätzliche API-Keys erzeugen |
| `run_mypy.sh` | Typprüfung (strict) |
| `tests/manual-tests/` | Tests mit echter Hardware (`API_URL`, `API_KEY` aus `.env`) |

## Repeater-CSV

```csv
callsign,frequency_mhz,offset_mhz,tone,mode,band,location,canton,status
HB9AB,145.625,-0.6,123.0,FM,2m,Zürich,ZH,active
```

Pflichtfelder sind `callsign`, `frequency_mhz`, `mode` und `band`. Die IDs werden aus Rufzeichen und Frequenz gebildet, ein erneuter Import aktualisiert also statt zu duplizieren.
