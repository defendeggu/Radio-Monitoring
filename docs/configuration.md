# Konfiguration (`.env`)

🇬🇧 **[English Version](#english-version)** below

`./scripts/setup-env.sh` legt die Datei an. Die vollständige, kommentierte Liste aller Variablen steht in [`.env.example`](../.env.example). Hier die wichtigsten:

## Betrieb

| Variable | Standard | Bedeutung |
|---|---|---|
| `COMPOSE_PROFILES` | `elk` | `elk` = Vollausbau, leer = Light-Profil |
| `STORAGE_BACKEND` | `elasticsearch` | `elasticsearch` oder `sqlite` |
| `WEB_PORT` / `WEB_BIND` | `8080` / `0.0.0.0` | Port und Interface der Weboberfläche |
| `WEB_PUBLIC_URL` | `http://localhost:${WEB_PORT}` | Adresse der Weboberfläche aus Sicht des Browsers; Ziel der Play-Buttons in Kibana |
| `KIBANA_BIND` / `KIBANA_PORT` | `127.0.0.1` / `5601` | Kibana nur lokal; `0.0.0.0` macht es im LAN sichtbar |
| `TZ` | `Europe/Zurich` | Zeitzone der Zeitpläne |
| `ELK_VERSION` | `9.5.5` | Version des Elastic-Stacks |
| `ES_HEAP` | `2g` | Java-Heap von Elasticsearch |
| `WITH_USRP` | `0` | `1` = UHD/GNU Radio ins API-Image (USRP N200) |

## Sicherheit

| Variable | Bedeutung |
|---|---|
| `API_KEYS` | Kommagetrennte Keys (32 Zeichen oder mehr). **Pflicht**: Ohne Key startet die API nicht. |
| `TRUSTED_IPS` | Netze ohne Key-Pflicht, z. B. `192.168.1.0/24`. Standard: keine (nur `localhost` im Container). |
| `ALLOW_INSECURE` | Nur für Entwicklung ausserhalb von Docker: API ohne Keys starten. |
| `METRICS_API_KEY` | Key nur für `GET /metrics/*`. Damit liest Metricbeat im GPU-Setup die GPU-Auslastung. Generiert von `setup-env.sh`. |

Generierte Secrets: `REDIS_PASSWORD`, `ELASTIC_PASSWORD`, `KIBANA_SYSTEM_PASSWORD`, `LOGSTASH_SYSTEM_PASSWORD`, `LOGSTASH_WRITER_PASSWORD`, `LOGSTASH_HTTP_PASSWORD`, `BEATS_SYSTEM_PASSWORD`, `BEATS_WRITER_PASSWORD`, `RADIO_API_PASSWORD`, `KIBANA_ENCRYPTION_KEY`, `RECORDING_LINK_SECRET`, `METRICS_API_KEY`.

## Whisper

| Variable | Standard | Bedeutung |
|---|---|---|
| `WHISPER_MODEL` | `small` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`, `distil-large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cpu` oder `cuda`. Kann die Karte das Modell nicht rechnen, weicht die API mit einer Warnung auf die CPU aus (siehe [installation.md](installation.md#whisper-auf-der-gpu)). |
| `WHISPER_COMPUTE_TYPE` | `int8` | CPU: `int8`; GPU: `float16` |
| `WHISPER_INITIAL_PROMPT` | – | Vokabular-Hinweis für alle Transkriptionen (Rufzeichen, Ortsnamen) |

Pro Aufnahme lassen sich Sprache, `beam_size`, `initial_prompt` und `task` (`transcribe`/`translate`) zusätzlich in der API bzw. der Weboberfläche setzen.

## Aufnahmen

| Variable | Standard | Bedeutung |
|---|---|---|
| `RECORDING_RETENTION_DAYS` | `30` | Ältere Dateien in `recordings/` werden täglich um 03:30 gelöscht (`0` = nie) |
| `MIN_FREE_DISK_MB` | `500` | Unter diesem freien Speicher werden neue Aufnahmen abgelehnt |
| `RECORDING_LINK_SECRET` | generiert | Schlüssel für die signierten Links auf WAV-Dateien (Play-Button in Kibana). Leer = keine Links. Ein neuer Wert macht alle bisherigen Links ungültig. |

Elasticsearch-Daten werden nach 90 Tagen gelöscht (ILM-Policy `radio-retention-policy`), Container-Logs und Metriken nach 7 Tagen.

## Alarm-Benachrichtigungen

Alle Ziele sind optional. In den Alarmregeln wählst du nur den Kanal, die Ziele selbst stehen ausschliesslich hier. So kann eine Regel den Server nicht zu beliebigen URLs schicken.

| Kanal | Variablen |
|---|---|
| ntfy | `NTFY_URL` (vollständige Topic-URL), optional `NTFY_TOKEN` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Webhook | `ALERT_WEBHOOK_URL` (JSON-POST mit `title`, `message`, `alert`) |
| E-Mail | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `ALERT_EMAIL_TO` |

Testen kannst du die Kanäle in der Weboberfläche unter *Alarme → Test senden*.

## Prüfen

```bash
python3 scripts/validate_env.py          # Fehler → Exit-Code 1
python3 scripts/validate_env.py --strict # Warnungen zählen als Fehler
```

---

<a id="english-version"></a>

## English Version

`./scripts/setup-env.sh` creates the file. The complete, commented list of all variables is in [`.env.example`](../.env.example). The most important ones:

### Operation

| Variable | Default | Meaning |
|---|---|---|
| `COMPOSE_PROFILES` | `elk` | `elk` = full stack, empty = light profile |
| `STORAGE_BACKEND` | `elasticsearch` | `elasticsearch` or `sqlite` |
| `WEB_PORT` / `WEB_BIND` | `8080` / `0.0.0.0` | port and interface of the web interface |
| `WEB_PUBLIC_URL` | `http://localhost:${WEB_PORT}` | address of the web interface as seen by the browser; target of the play buttons in Kibana |
| `KIBANA_BIND` / `KIBANA_PORT` | `127.0.0.1` / `5601` | Kibana only locally; `0.0.0.0` makes it visible on the LAN |
| `TZ` | `Europe/Zurich` | time zone of the schedules |
| `ELK_VERSION` | `9.5.5` | version of the Elastic stack |
| `ES_HEAP` | `2g` | Java heap of Elasticsearch |
| `WITH_USRP` | `0` | `1` = UHD/GNU Radio in the API image (USRP N200) |

### Security

| Variable | Meaning |
|---|---|
| `API_KEYS` | Comma-separated keys (32 characters or more). **Required**: the API does not start without a key. |
| `TRUSTED_IPS` | Networks that need no key, e.g. `192.168.1.0/24`. Default: none (only `localhost` inside the container). |
| `ALLOW_INSECURE` | Only for development outside Docker: start the API without keys. |
| `METRICS_API_KEY` | key for `GET /metrics/*` only. Metricbeat uses it to read the GPU usage in the GPU setup. Generated by `setup-env.sh`. |

Generated secrets: `REDIS_PASSWORD`, `ELASTIC_PASSWORD`, `KIBANA_SYSTEM_PASSWORD`, `LOGSTASH_SYSTEM_PASSWORD`, `LOGSTASH_WRITER_PASSWORD`, `LOGSTASH_HTTP_PASSWORD`, `BEATS_SYSTEM_PASSWORD`, `BEATS_WRITER_PASSWORD`, `RADIO_API_PASSWORD`, `KIBANA_ENCRYPTION_KEY`, `RECORDING_LINK_SECRET`, `METRICS_API_KEY`.

### Whisper

| Variable | Default | Meaning |
|---|---|---|
| `WHISPER_MODEL` | `small` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`, `distil-large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cpu` or `cuda`. If the card cannot run the model, the API falls back to the CPU with a warning (see [installation.md](installation.md#whisper-on-the-gpu)). |
| `WHISPER_COMPUTE_TYPE` | `int8` | CPU: `int8`; GPU: `float16` |
| `WHISPER_INITIAL_PROMPT` | – | vocabulary hint for all transcriptions (callsigns, place names) |

Language, `beam_size`, `initial_prompt` and `task` (`transcribe`/`translate`) can also be set per recording in the API or the web interface.

### Recordings

| Variable | Default | Meaning |
|---|---|---|
| `RECORDING_RETENTION_DAYS` | `30` | older files in `recordings/` are deleted daily at 03:30 (`0` = never) |
| `MIN_FREE_DISK_MB` | `500` | below this free space, new recordings are rejected |
| `RECORDING_LINK_SECRET` | generated | key for the signed links to WAV files (play button in Kibana). Empty = no links. A new value invalidates all existing links. |

Elasticsearch data is deleted after 90 days (ILM policy `radio-retention-policy`), container logs and metrics after 7 days.

### Alert notifications

All targets are optional. In the alert rules you only choose the channel; the targets themselves are defined only here. This way a rule cannot make the server send requests to arbitrary URLs.

| Channel | Variables |
|---|---|
| ntfy | `NTFY_URL` (full topic URL), optional `NTFY_TOKEN` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Webhook | `ALERT_WEBHOOK_URL` (JSON POST with `title`, `message`, `alert`) |
| E-mail | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `ALERT_EMAIL_TO` |

You can test the channels in the web interface under *Alerts → Send test*.

### Checking

```bash
python3 scripts/validate_env.py          # errors → exit code 1
python3 scripts/validate_env.py --strict # warnings count as errors
```
