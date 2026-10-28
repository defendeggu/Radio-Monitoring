# REST-API

Die API läuft hinter nginx unter **`http://<host>:8080/api`**. Die vollständige Beschreibung steht als OpenAPI 3.1 unter `/api/openapi.json` und ist in der Weboberfläche lesbar (Seite *API*).

## Authentifizierung

Jede Anfrage braucht den Header `X-API-Key`. Ausgenommen sind `/health`, `/health/ready` und `/openapi.json`.

```bash
export API=http://localhost:8080/api
export API_KEY=$(grep ^API_KEYS= .env | cut -d= -f2 | cut -d, -f1)
curl -H "X-API-Key: $API_KEY" $API/sdr/status
```

| Code | Bedeutung |
|---|---|
| 400 | Validierungsfehler; `details` listet Feld und Grund auf |
| 401 / 403 | Key fehlt / ist ungültig |
| 404 | nicht gefunden |
| 409 | SDR belegt; `holder` nennt den Job |
| 503 | kein SDR erkannt oder Werkzeug fehlt |
| 500 | interner Fehler; nur generische Meldung, Details im Server-Log unter `correlation_id` |

## Wichtige Endpunkte

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/health`, `/health/ready` | Liveness / Readiness (Redis, Storage, SDR) |
| GET | `/sdr/detect`, `/sdr/status` | Hardware, aktueller Belegungsstatus |
| POST | `/sdr/force-stop` | Notstopp aller SDR-Jobs |
| POST | `/capture-and-transcribe` | Aufnahme + Dekodierung (`mode`: voice/aprs/pocsag), HTTP 202 |
| POST | `/capture` | Nur Audio aufnehmen, HTTP 202 |
| GET | `/capture-status/{id}` | Fortschritt und Ergebnis eines Jobs |
| POST | `/transcribe` | Vorhandene Aufnahme transkribieren |
| POST | `/stream-decode` | APRS/POCSAG-Streaming starten |
| GET / DELETE | `/stream-decode/{id}` | Status / Stopp einer Session |
| POST | `/vox/start` | VOX-Aufnahme starten |
| POST | `/decoders/start` | ADS-B/AIS/ISM starten (`decoder`: adsb/ais/ism) |
| POST | `/stream/multi/start` | Multi-Channel (USRP) |
| POST | `/scan-repeaters` | Repeater-Scan (`repeater_ids` oder `band`/`canton`; `total_duration` in s oder `until_stopped`, sonst ein Durchgang) |
| GET / POST | `/scan-repeaters/{id}/progress`, `/scan-repeaters/{id}/stop` | Fortschritt / Stopp eines Scans |
| GET | `/search`, `/aprs/search`, `/pocsag/search`, `/decoders/{kind}/search` | Suchen |
| GET | `/aprs/map` | APRS-Stationen als GeoJSON |
| GET | `/dashboard/stats`, `/stats` | Statistiken |
| GET | `/recordings`, `/recordings/{name}` | Aufnahmen auflisten / herunterladen |
| GET | `/export/{kind}.csv`, `/export/{kind}.geojson`, `/export/aprs.kml`, `/export/capture/{id}.zip` | Export |
| CRUD | `/bookmarks`, `/alerts/rules`, `/schedules` | Lesezeichen, Alarmregeln, Zeitpläne |
| GET | `/events` | Live-Ereignisse (Server-Sent Events) |

## Beispiele

Sprachaufnahme mit Transkription:

```bash
ID=$(curl -s -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"frequency": 145500000, "modulation": "FM", "duration": 30, "mode": "voice", "language": "de"}' \
  $API/capture-and-transcribe | jq -r .capture_id)
curl -s -H "X-API-Key: $API_KEY" $API/capture-status/$ID | jq '.status, .result.transcription.text'
```

APRS 2 Stunden streamen und wieder stoppen:

```bash
SID=$(curl -s -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"mode": "aprs", "frequency": 144800000, "duration": 7200}' $API/stream-decode | jq -r .session_id)
curl -s -X DELETE -H "X-API-Key: $API_KEY" $API/stream-decode/$SID
```

Alarmregel anlegen:

```bash
curl -s -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"name": "Feuer", "source": "pocsag", "field": "text", "match_type": "regex", "pattern": "FEUER|BRAND", "channels": ["ntfy"]}' \
  $API/alerts/rules
```

## Live-Ereignisse (SSE)

`GET /events?types=aprs,pocsag,alert` liefert `text/event-stream`. Jedes Ereignis sieht so aus:

```
event: aprs
data: {"type": "aprs", "time": "2026-10-16T10:00:00+00:00", "data": {"source_callsign": "HB9XYZ-7", ...}}
```

Ereignistypen: `aprs`, `pocsag`, `adsb`, `adsb_snapshot`, `ais`, `ism`, `vox`, `alert`, `capture`, `session`, `scan`, `schedule`, `sdr`.

```bash
curl -N -H "X-API-Key: $API_KEY" "$API/events?types=aprs,alert"
```

## Änderungen gegenüber 3.x

- `POST /capture` arbeitet jetzt asynchron (HTTP 202 + `capture_id`), wie `/capture-and-transcribe`.
- `/stream/aprs/start` und `/stream/pocsag/start` sind veraltet (Header `Deprecation: true`). Nutze `POST /stream-decode`.
- `/sdr/detect` antwortet ohne Gerät mit HTTP 200 und `"detected": false` statt mit 404.
- `/list-recordings` ist ein Alias von `/recordings` und liefert nur noch Dateinamen statt Serverpfaden.
- Unbekannte Felder im Body werden mit 400 abgelehnt (`extra='forbid'`).
