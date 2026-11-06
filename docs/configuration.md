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

## Reverse Beacon Network (CW-Spots)

Das Fenster *RBN-Spots* auf der CW-Seite und die Spot-Marken im Wasserfall zeigen, wer gerade auf Kurzwelle in CW aktiv ist ([reversebeacon.net](https://www.reversebeacon.net/)). Die API hält dafür eine einzige Telnet-Verbindung, bei mehreren Gunicorn-Workern nur einer davon.

| Variable | Standard | Bedeutung |
|---|---|---|
| `RBN_ENABLED` | `false` | Verbindung zu RBN aufbauen |
| `RBN_CALLSIGN` | – | Rufzeichen für den Login (Pflicht, sonst bleibt RBN aus) |
| `RBN_HOST`, `RBN_PORT` | `telnet.reversebeacon.net`, `7000` | Server. RBN wünscht, dass Endnutzer einen DX-Cluster nutzen, der die RBN-Spots weitergibt; dessen Adresse hier eintragen, z. B. `gb7dxg.lebs.org.uk`, `7373` (CC Cluster). |
| `RBN_LOGIN_COMMANDS` | – | Befehle nach dem Login, mit `;` getrennt. CC Cluster und DX Spider schicken RBN-Spots erst nach `SET/SKIMMER`. |
| `RBN_SPOTTER_PREFIXES` | europäische Präfixe | Nur Spots von Skimmern mit diesen Rufzeichen-Präfixen (Komma-getrennt), `*` = alle |

Gespeichert werden nur CW-Spots auf Kurzwelle der letzten 30 Minuten, in Redis, nicht in Elasticsearch.

## SDRplay RSP

Nur mit einem Image, das mit `WITH_SDRPLAY=1` gebaut ist (siehe [installation.md](installation.md#sdrplay-rsp)).

| Variable | Standard | Bedeutung |
|---|---|---|
| `WITH_SDRPLAY` | `0` | Build-Schalter: SDRplay-API (von sdrplay.com, Lizenz von SDRplay), SoapySDR, `sdrplay_rx` |
| `SDRPLAY_HIZ` | `true` | RSPduo Tuner A: Hi-Z-Eingang unter 30 MHz |
| `SDRPLAY_NOTCH` | `auto` | `auto`: MW/UKW-Notch unter 30 MHz; `on`: dazu DAB-Notch; `off`: keiner |
| `SDRPLAY_BIAS_T` | `false` | Bias-T (RSPduo nur Tuner B), z. B. für eine aktive Antenne |
| `SDRPLAY_AGC` | `true` | ZF-Verstärkung per AGC; die LNA-Stufe folgt der eingestellten Verstärkung |

## Contest-Skimmer

Bedienung, N1MM+ und Reglement: [contest.md](contest.md). Die Ports des Clusters und des N1MM+-Empfängers sind im Compose-File immer veröffentlicht, aber es hört nur etwas zu, wenn der Dienst eingeschaltet ist.

| Variable | Standard | Bedeutung |
|---|---|---|
| `SKIMMER_CALLSIGN` | `RBN_CALLSIGN` | Spotter-Rufzeichen in den Cluster-Zeilen (`HB9XYZ-#`) |
| `SKIMMER_RARE_RANK` | `100` | DXCC-Gebiete bis zu diesem Platz der Club-Log-Most-Wanted-Liste gelten als selten |
| `CLUSTER_ENABLED` | `false` | DX-Cluster-Server (Telnet) für die Bandmap von N1MM+ und anderen Logprogrammen; nur lesend, ohne Login-Prüfung |
| `CLUSTER_PORT` | `7300` | Port auf dem Host |
| `N1MM_ENABLED` | `false` | UDP-Broadcasts von N1MM+ empfangen (gearbeitete QSOs, Ausblenden beim Senden) |
| `N1MM_PORT` | `12060` | Port auf dem Host |
| `N1MM_ALLOWED` | – | Absender, die QSOs melden dürfen (IP oder Netz, Komma-getrennt); leer = alle |
| `CONTEST_BIND` | `127.0.0.1` | Interface für beide Ports; `0.0.0.0` für ein Logprogramm im LAN (dann `N1MM_ALLOWED` setzen) |

Die Referenzdaten (`cty.csv`, `MASTER.SCP`, Most Wanted) liegen in `/app/data/contest` im Volume `api-data`.

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

### Reverse Beacon Network (CW spots)

The *RBN spots* window on the CW page and the spot markers in the waterfall show who is active in CW on shortwave right now ([reversebeacon.net](https://www.reversebeacon.net/)). The API keeps a single telnet connection for this, only one of several Gunicorn workers.

| Variable | Default | Meaning |
|---|---|---|
| `RBN_ENABLED` | `false` | connect to RBN |
| `RBN_CALLSIGN` | – | callsign for the login (required, otherwise RBN stays off) |
| `RBN_HOST`, `RBN_PORT` | `telnet.reversebeacon.net`, `7000` | server. RBN asks end users to use a DX cluster that relays the RBN spots; enter its address here, e.g. `gb7dxg.lebs.org.uk`, `7373` (CC Cluster). |
| `RBN_LOGIN_COMMANDS` | – | commands after the login, separated by `;`. CC Cluster and DX Spider send RBN spots only after `SET/SKIMMER`. |
| `RBN_SPOTTER_PREFIXES` | European prefixes | only spots from skimmers with these callsign prefixes (comma-separated), `*` = all |

Only CW spots on shortwave of the last 30 minutes are kept, in Redis, not in Elasticsearch.

### SDRplay RSP

Only with an image built with `WITH_SDRPLAY=1` (see [installation.md](installation.md#sdrplay-rsp-1)).

| Variable | Default | Meaning |
|---|---|---|
| `WITH_SDRPLAY` | `0` | build switch: SDRplay API (from sdrplay.com, SDRplay licence), SoapySDR, `sdrplay_rx` |
| `SDRPLAY_HIZ` | `true` | RSPduo tuner A: Hi-Z input below 30 MHz |
| `SDRPLAY_NOTCH` | `auto` | `auto`: MW/FM notch below 30 MHz; `on`: plus DAB notch; `off`: none |
| `SDRPLAY_BIAS_T` | `false` | bias-T (RSPduo tuner B only), e.g. for an active antenna |
| `SDRPLAY_AGC` | `true` | IF gain by AGC; the LNA state follows the configured gain |

### Contest skimmer

Operation, N1MM+ and contest rules: [contest.md](contest.md#english-version). The ports of the cluster and of the N1MM+ receiver are always published in the compose file, but something listens only when the service is enabled.

| Variable | Default | Meaning |
|---|---|---|
| `SKIMMER_CALLSIGN` | `RBN_CALLSIGN` | spotter callsign in the cluster lines (`HB9XYZ-#`) |
| `SKIMMER_RARE_RANK` | `100` | DXCC entities up to this rank of the Club Log Most Wanted list count as rare |
| `CLUSTER_ENABLED` | `false` | DX cluster server (telnet) for the bandmap of N1MM+ and other loggers; read-only, no login check |
| `CLUSTER_PORT` | `7300` | port on the host |
| `N1MM_ENABLED` | `false` | receive the N1MM+ UDP broadcasts (worked QSOs, blanking while transmitting) |
| `N1MM_PORT` | `12060` | port on the host |
| `N1MM_ALLOWED` | – | senders allowed to report QSOs (IP or network, comma-separated); empty = any |
| `CONTEST_BIND` | `127.0.0.1` | interface for both ports; `0.0.0.0` for a logger in the LAN (then set `N1MM_ALLOWED`) |

The reference data (`cty.csv`, `MASTER.SCP`, Most Wanted) is kept in `/app/data/contest` in the `api-data` volume.

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
