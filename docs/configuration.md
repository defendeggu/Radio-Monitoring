# Konfiguration (`.env`)

`./scripts/setup-env.sh` legt die Datei an. Die vollständige, kommentierte Liste aller Variablen steht in [`.env.example`](../.env.example). Hier die wichtigsten:

## Betrieb

| Variable | Standard | Bedeutung |
|---|---|---|
| `COMPOSE_PROFILES` | `elk` | `elk` = Vollausbau, leer = Light-Profil |
| `STORAGE_BACKEND` | `elasticsearch` | `elasticsearch` oder `sqlite` |
| `WEB_PORT` / `WEB_BIND` | `8080` / `0.0.0.0` | Port und Interface der Weboberfläche |
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

Generierte Secrets: `REDIS_PASSWORD`, `ELASTIC_PASSWORD`, `KIBANA_SYSTEM_PASSWORD`, `LOGSTASH_SYSTEM_PASSWORD`, `LOGSTASH_WRITER_PASSWORD`, `LOGSTASH_HTTP_PASSWORD`, `BEATS_SYSTEM_PASSWORD`, `BEATS_WRITER_PASSWORD`, `RADIO_API_PASSWORD`, `KIBANA_ENCRYPTION_KEY`.

## Whisper

| Variable | Standard | Bedeutung |
|---|---|---|
| `WHISPER_MODEL` | `small` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`, `distil-large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cpu` oder `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` | CPU: `int8`; GPU: `float16` |
| `WHISPER_INITIAL_PROMPT` | – | Vokabular-Hinweis für alle Transkriptionen (Rufzeichen, Ortsnamen) |

Pro Aufnahme lassen sich Sprache, `beam_size`, `initial_prompt` und `task` (`transcribe`/`translate`) zusätzlich in der API bzw. der Weboberfläche setzen.

## Aufnahmen

| Variable | Standard | Bedeutung |
|---|---|---|
| `RECORDING_RETENTION_DAYS` | `30` | Ältere Dateien in `recordings/` werden täglich um 03:30 gelöscht (`0` = nie) |
| `MIN_FREE_DISK_MB` | `500` | Unter diesem freien Speicher werden neue Aufnahmen abgelehnt |

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
