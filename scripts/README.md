# Skripte

| Skript | Zweck |
|---|---|
| `setup-env.sh [--light]` | `.env` mit zufälligen Secrets anlegen oder ergänzen |
| `validate_env.py [--strict]` | `.env` prüfen |
| `post-docker-setup.sh` | nach `docker compose up`: ES-Benutzer, Templates, Dashboards |
| `setup-elk-users.sh` | nur den Elasticsearch-Teil (idempotent) |
| `import-kibana-dashboards.sh` | Kibana-Objekte aus `monitoring/kibana/dashboards/` importieren |
| `run_import.sh [csv]` | Repeater-Liste importieren (Standard: `repeaters_ch.csv`, nicht mehr gelistete Relais werden inaktiv) |
| `update_repeaters_from_uska.py` | `repeaters_ch.csv` aus der aktuellen USKA-Liste neu erzeugen |
| `generate_api_keys.py` | zusätzliche API-Keys erzeugen |
| `run_mypy.sh` | Typprüfung (strict) |

## Repeater-CSV

```csv
callsign,frequency_mhz,offset_mhz,tone,mode,band,location,canton,status
HB9AB,145.625,-0.6,123.0,FM,2m,Zürich,ZH,active
```

Pflichtfelder sind `callsign`, `frequency_mhz`, `mode` und `band`. Die IDs werden aus Rufzeichen und Frequenz gebildet (bei mehreren Standorten mit gleichem Rufzeichen und gleicher Frequenz zusätzlich aus dem Standort), ein erneuter Import aktualisiert also statt zu duplizieren.

## Schweizer Repeater-Liste

`repeaters_ch.csv` stammt aus der [HB Voice Repeater List der USKA](https://uska.ch/de/funkamateure/repeater-liste-und-bandplaene/hb-voice-repeater-list/). Aktualisieren:

```bash
python3 scripts/update_repeaters_from_uska.py   # lädt die Liste und schreibt repeaters_ch.csv
docker compose build radio-api && docker compose up -d radio-api
./scripts/run_import.sh
```

Analoge und gemischte Relais werden als `FM` eingetragen, reine Digital-Relais als `DMR`, `D-STAR` oder `C4FM`. Der Repeater-Scan misst nur FM-Relais mit Status `active` (USKA `qrv`); `qrx`, `qrt` und `planned` werden `inactive`. Der CTCSS-Ton kommt aus der Spalte TX Tone oder, wenn diese leer ist, aus den Bemerkungen.
