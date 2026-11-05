# REST-API

🇬🇧 **[English Version](#english-version)** below

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
| GET | `/metrics/gpu` | GPU-Auslastung, Speicher, Temperatur im Prometheus-Format (für Metricbeat; auch mit `METRICS_API_KEY`) |
| GET | `/sdr/detect`, `/sdr/status` | Hardware, aktueller Belegungsstatus |
| POST | `/sdr/force-stop` | Notstopp aller SDR-Jobs |
| POST | `/capture-and-transcribe` | Aufnahme + Dekodierung (`mode`: voice/aprs/pocsag), HTTP 202 |
| POST | `/capture` | Nur Audio aufnehmen, HTTP 202 |
| GET | `/capture-status/{id}` | Fortschritt und Ergebnis eines Jobs |
| POST | `/transcribe` | Vorhandene Aufnahme transkribieren |
| POST | `/stream-decode` | APRS/POCSAG-Streaming starten |
| GET / DELETE | `/stream-decode/{id}` | Status / Stopp einer Session |
| POST | `/vox/start` | VOX-Aufnahme starten |
| POST | `/spectrum` | Wasserfall starten (`sample_rate` = Bandbreite, `fft_size`, `fps`); weicht jedem anderen Job |
| GET | `/spectrum/{id}`, `/spectrum/{id}/stream` | Zustand / binärer Live-Strom (Spektrumzeilen, mit `?audio=1` auch Ton) |
| POST | `/spectrum/{id}/tune` | Mittenfrequenz, Mithör-Kanal, Modulation, Squelch ändern |
| POST | `/cw/start` | CW-Decoder starten (`frequency`, `wpm`, `cw_bandwidth`, `tone_hz`, `record`) |
| POST | `/cw/{id}/tune` | CW-Decoder umstimmen (`channel`), z. B. auf einen RBN-Spot; innerhalb der Bandbreite ohne Neustart |
| GET | `/cw/transmissions` | Gespeicherte CW-Durchgänge (`hours`, `limit`, `call`) |
| GET | `/rbn/spots`, `/rbn/status` | CW-Spots des Reverse Beacon Network der letzten 30 min (`band`, `freq_min`/`freq_max`, `call`, `cq_only`, `max_age`) / Verbindungsstatus |
| POST | `/skimmer/start` | Contest-Skimmer auf einem Bandsegment (`band` oder `freq_low`/`freq_high`, `mode` CW oder SSB, `language` für SSB, `contest`, `max_decoders`, `record_iq`, `include_rbn`, `duration` 0 = bis Stopp) |
| GET | `/skimmer/spots` | Spots des Skimmers, eingestuft (`band`, `priority`, `source`, `max_age`) |
| GET / PUT | `/contest/contests`, `/contest/active` | Contest-Regeln / aktiven Contest wählen |
| GET | `/contest/status`, `/contest/lookup` | Referenzdaten, Log, N1MM+, Cluster / ein Rufzeichen einstufen (`call`, `frequency`, `mode`) |
| POST | `/contest/refdata/update` | cty.csv, MASTER.SCP und Most Wanted herunterladen |
| GET / POST / DELETE | `/contest/worked`, `/contest/worked/import` | Log der gearbeiteten Stationen: Übersicht / ADIF- oder Cabrillo-Import (`text`, `replace`) / löschen |
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

Ereignistypen: `aprs`, `pocsag`, `adsb`, `adsb_snapshot`, `ais`, `ism`, `vox`, `cw`, `alert`, `capture`, `session`, `scan`, `schedule`, `sdr`.

```bash
curl -N -H "X-API-Key: $API_KEY" "$API/events?types=aprs,alert"
```

## Änderungen gegenüber 3.x

- `POST /capture` arbeitet jetzt asynchron (HTTP 202 + `capture_id`), wie `/capture-and-transcribe`.
- `/stream/aprs/start` und `/stream/pocsag/start` sind entfernt. Nutze `POST /stream-decode`.
- `/sdr/detect` antwortet ohne Gerät mit HTTP 200 und `"detected": false` statt mit 404.
- `/list-recordings` ist entfernt. Nutze `/recordings`, das nur Dateinamen statt Serverpfaden liefert.
- Unbekannte Felder im Body werden mit 400 abgelehnt (`extra='forbid'`).

---

<a id="english-version"></a>

## English Version

The API runs behind nginx at **`http://<host>:8080/api`**. The complete description is available as OpenAPI 3.1 at `/api/openapi.json` and can be read in the web interface (page *API*).

### Authentication

Every request needs the `X-API-Key` header. Exceptions are `/health`, `/health/ready` and `/openapi.json`.

```bash
export API=http://localhost:8080/api
export API_KEY=$(grep ^API_KEYS= .env | cut -d= -f2 | cut -d, -f1)
curl -H "X-API-Key: $API_KEY" $API/sdr/status
```

| Code | Meaning |
|---|---|
| 400 | validation error; `details` lists the field and the reason |
| 401 / 403 | key missing / invalid |
| 404 | not found |
| 409 | SDR busy; `holder` names the job |
| 503 | no SDR detected or tool missing |
| 500 | internal error; only a generic message, details in the server log under `correlation_id` |

### Important endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health`, `/health/ready` | liveness / readiness (Redis, storage, SDR) |
| GET | `/metrics/gpu` | GPU utilization, memory, temperature in Prometheus format (for Metricbeat; also with `METRICS_API_KEY`) |
| GET | `/sdr/detect`, `/sdr/status` | hardware, current busy state |
| POST | `/sdr/force-stop` | emergency stop of all SDR jobs |
| POST | `/capture-and-transcribe` | recording + decoding (`mode`: voice/aprs/pocsag), HTTP 202 |
| POST | `/capture` | record audio only, HTTP 202 |
| GET | `/capture-status/{id}` | progress and result of a job |
| POST | `/transcribe` | transcribe an existing recording |
| POST | `/stream-decode` | start APRS/POCSAG streaming |
| GET / DELETE | `/stream-decode/{id}` | status / stop of a session |
| POST | `/vox/start` | start VOX recording |
| POST | `/spectrum` | start the waterfall (`sample_rate` = bandwidth, `fft_size`, `fps`); gives way to every other job |
| GET | `/spectrum/{id}`, `/spectrum/{id}/stream` | state / binary live stream (spectrum rows, with `?audio=1` also audio) |
| POST | `/spectrum/{id}/tune` | change centre frequency, listening channel, modulation, squelch |
| POST | `/cw/start` | start the CW decoder (`frequency`, `wpm`, `cw_bandwidth`, `tone_hz`, `record`) |
| POST | `/cw/{id}/tune` | retune the CW decoder (`channel`), e.g. to an RBN spot; no restart inside the bandwidth |
| GET | `/cw/transmissions` | stored CW transmissions (`hours`, `limit`, `call`) |
| GET | `/rbn/spots`, `/rbn/status` | Reverse Beacon Network CW spots of the last 30 min (`band`, `freq_min`/`freq_max`, `call`, `cq_only`, `max_age`) / connection state |
| POST | `/skimmer/start` | contest skimmer on a band segment (`band` or `freq_low`/`freq_high`, `mode` CW or SSB, `language` for SSB, `contest`, `max_decoders`, `record_iq`, `include_rbn`, `duration` 0 = until stopped) |
| GET | `/skimmer/spots` | skimmer spots, classified (`band`, `priority`, `source`, `max_age`) |
| GET / PUT | `/contest/contests`, `/contest/active` | contest rules / select the active contest |
| GET | `/contest/status`, `/contest/lookup` | reference data, log, N1MM+, cluster / classify one callsign (`call`, `frequency`, `mode`) |
| POST | `/contest/refdata/update` | download cty.csv, MASTER.SCP and Most Wanted |
| GET / POST / DELETE | `/contest/worked`, `/contest/worked/import` | log of worked stations: summary / ADIF or Cabrillo import (`text`, `replace`) / clear |
| POST | `/decoders/start` | start ADS-B/AIS/ISM (`decoder`: adsb/ais/ism) |
| POST | `/stream/multi/start` | multi-channel (USRP) |
| POST | `/scan-repeaters` | repeater scan (`repeater_ids` or `band`/`canton`; `total_duration` in s or `until_stopped`, otherwise one round) |
| GET / POST | `/scan-repeaters/{id}/progress`, `/scan-repeaters/{id}/stop` | progress / stop of a scan |
| GET | `/search`, `/aprs/search`, `/pocsag/search`, `/decoders/{kind}/search` | search |
| GET | `/aprs/map` | APRS stations as GeoJSON |
| GET | `/dashboard/stats`, `/stats` | statistics |
| GET | `/recordings`, `/recordings/{name}` | list / download recordings |
| GET | `/export/{kind}.csv`, `/export/{kind}.geojson`, `/export/aprs.kml`, `/export/capture/{id}.zip` | export |
| CRUD | `/bookmarks`, `/alerts/rules`, `/schedules` | bookmarks, alert rules, schedules |
| GET | `/events` | live events (server-sent events) |

### Examples

Voice recording with transcription:

```bash
ID=$(curl -s -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"frequency": 145500000, "modulation": "FM", "duration": 30, "mode": "voice", "language": "de"}' \
  $API/capture-and-transcribe | jq -r .capture_id)
curl -s -H "X-API-Key: $API_KEY" $API/capture-status/$ID | jq '.status, .result.transcription.text'
```

Stream APRS for 2 hours and stop again:

```bash
SID=$(curl -s -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"mode": "aprs", "frequency": 144800000, "duration": 7200}' $API/stream-decode | jq -r .session_id)
curl -s -X DELETE -H "X-API-Key: $API_KEY" $API/stream-decode/$SID
```

Create an alert rule:

```bash
curl -s -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"name": "Feuer", "source": "pocsag", "field": "text", "match_type": "regex", "pattern": "FEUER|BRAND", "channels": ["ntfy"]}' \
  $API/alerts/rules
```

### Live events (SSE)

`GET /events?types=aprs,pocsag,alert` returns `text/event-stream`. Every event looks like this:

```
event: aprs
data: {"type": "aprs", "time": "2026-10-16T10:00:00+00:00", "data": {"source_callsign": "HB9XYZ-7", ...}}
```

Event types: `aprs`, `pocsag`, `adsb`, `adsb_snapshot`, `ais`, `ism`, `vox`, `cw`, `alert`, `capture`, `session`, `scan`, `schedule`, `sdr`.

```bash
curl -N -H "X-API-Key: $API_KEY" "$API/events?types=aprs,alert"
```

### Changes compared to 3.x

- `POST /capture` now works asynchronously (HTTP 202 + `capture_id`), like `/capture-and-transcribe`.
- `/stream/aprs/start` and `/stream/pocsag/start` are removed. Use `POST /stream-decode`.
- Without a device, `/sdr/detect` answers with HTTP 200 and `"detected": false` instead of 404.
- `/list-recordings` is removed. Use `/recordings`, which only returns file names instead of server paths.
- Unknown fields in the body are rejected with 400 (`extra='forbid'`).
