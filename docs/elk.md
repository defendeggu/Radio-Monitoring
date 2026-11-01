# Elasticsearch, Kibana und Logstash

🇬🇧 **[English Version](#english-version)** below

## Datenfluss

```
radio-api ──HTTP (Basic-Auth)──► Logstash :9600–9603 ──► radio-captures-*, radio-aprs-*, radio-pocsag-*, radio-repeater-activity-*
radio-api ──direkt (radio_api)──────────────────────────► radio-adsb-*, radio-ais-*, radio-ism-*, radio-alerts-*
Filebeat (Container-Logs) ──────────────────────────────► radio-logs-*
Metricbeat (Host/Container/ES) ─────────────────────────► metricbeat-*
```

Alle Indizes sind Tagesindizes (`…-YYYY.MM.dd`) mit 1 Shard und 0 Replikas (Single-Node).

## Templates und Aufbewahrung

`./scripts/setup-elk-users.sh` (Teil von `post-docker-setup.sh`) installiert:

- Index-Templates aus `monitoring/elasticsearch/index-templates/`. Unbekannte Text-Felder werden `keyword` (exakte Suche, Aggregationen), Positionen `geo_point`.
- ILM-Policy `radio-retention-policy`: nach 7 Tagen warm (read-only, forcemerge), nach 90 Tagen löschen. `logs-ilm-policy` löscht Logs und Metriken nach 7 Tagen.
- Rollen und Benutzer `radio_api`, `logstash_writer`, `beats_writer`.

Das Skript ist idempotent und gehört nach jedem Update ausgeführt.

## Kibana

`http://127.0.0.1:5601`, Benutzer `elastic`, Passwort `ELASTIC_PASSWORD` aus `.env`. Die Dashboards heissen wie die Module der Weboberfläche (`RadioMoni · Übersicht`, `Sprache`, `VOX-Aufnahme`, `APRS`, `POCSAG`, `ADS-B`, `AIS`, `ISM-Sensoren`, `Repeater-Scan`, `Alarme`, dazu `System – Logs` und `System – Zustand`). APRS, ADS-B und AIS haben eine Karte. Importiert werden sie mit `./scripts/import-kibana-dashboards.sh`, erzeugt von `monitoring/kibana/build_dashboards.py` (siehe [monitoring/kibana/dashboards/README.md](../monitoring/kibana/dashboards/README.md)).

**Aufnahmen abspielen:** In den Listen der Dashboards *Sprache* und *VOX-Aufnahme* (und in Discover auf `radio-captures-*`) zeigt die Spalte `audio_url` einen Play-Button. Er lädt die WAV-Datei über einen signierten Link von der Weboberfläche (`WEB_PUBLIC_URL`, Standard `http://localhost:${WEB_PORT}`), ohne API-Key. Öffnest du Kibana von einem anderen Rechner, setze `WEB_PUBLIC_URL` auf die Adresse, unter der dieser Rechner die Weboberfläche erreicht, und führe `./scripts/import-kibana-dashboards.sh` erneut aus. Aufnahmen von vor diesem Feature bekommen den Link mit `docker compose exec radio-api python -m radiomoni.recording_links backfill`. Ist die WAV-Datei schon gelöscht (`RECORDING_RETENTION_DAYS`), bleibt der Player stumm.

Von einem anderen Rechner aus erreichst du Kibana per SSH-Tunnel: `ssh -L 5601:127.0.0.1:5601 user@host`. Alternativ setzt du `KIBANA_BIND=0.0.0.0`, dann ist Kibana im ganzen LAN sichtbar.

Beispiele für die Konsole (Dev Tools):

```
GET _cat/indices/radio-*?v&s=index
GET radio-aprs-*/_search
{ "query": { "term": { "source_callsign": "HB9XYZ-7" } }, "sort": [{ "@timestamp": "desc" }] }
GET radio-captures-*/_search
{ "query": { "multi_match": { "query": "notfall", "fields": ["transcription", "transcription.german"] } } }
```

## Backup

Volume-Backup (Stack gestoppt, konsistent):

```bash
docker compose stop elasticsearch
docker run --rm -v radio-monitoring_elasticsearch-data:/data -v "$PWD/backups":/backup alpine \
  tar czf /backup/es-data-$(date +%Y%m%d).tgz -C /data .
docker compose start elasticsearch
```

Zurückspielen: Volume leeren und das Archiv mit `tar xzf` hineinentpacken, bei gestopptem Elasticsearch und **mit derselben oder einer neueren Version**.

## Upgrade

Elasticsearch erlaubt Major-Upgrades nur von der letzten Minor-Version aus. Ein Downgrade ist nach dem Start mit der neuen Version **nicht** mehr möglich. Vorgehen:

1. Backup wie oben.
2. `ELK_VERSION` auf die letzte 8.x setzen (`8.19.23`), `docker compose up -d`, dann `GET _migration/deprecations` prüfen. Warten, bis Kibana unter `/api/status` den Level `available` meldet: Erst dann sind seine gespeicherten Objekte migriert. Kibana 9 startet nicht mit Objekten aus einer älteren 8.x.
3. `ELK_VERSION` auf die Ziel-Version (`9.5.5`) setzen, `docker compose up -d`.
4. `./scripts/post-docker-setup.sh`.

Die Python-Bibliothek `elasticsearch` muss zur Major-Version des Servers passen (9.x für Server 9.x).

## Ohne ELK

Mit `COMPOSE_PROFILES=` und `STORAGE_BACKEND=sqlite` speichert die API alles in `/app/data/radiomoni.sqlite3` (Volume `api-data`). Kibana gibt es dann nicht, Dashboard und Suche der Weboberfläche funktionieren weiterhin.

---

<a id="english-version"></a>

## English Version

### Data flow

```
radio-api ──HTTP (basic auth)──► Logstash :9600–9603 ──► radio-captures-*, radio-aprs-*, radio-pocsag-*, radio-repeater-activity-*
radio-api ──direct (radio_api)──────────────────────────► radio-adsb-*, radio-ais-*, radio-ism-*, radio-alerts-*
Filebeat (container logs) ──────────────────────────────► radio-logs-*
Metricbeat (host/container/ES) ─────────────────────────► metricbeat-*
```

All indices are daily indices (`…-YYYY.MM.dd`) with 1 shard and 0 replicas (single node).

### Templates and retention

`./scripts/setup-elk-users.sh` (part of `post-docker-setup.sh`) installs:

- Index templates from `monitoring/elasticsearch/index-templates/`. Unknown text fields become `keyword` (exact search, aggregations), positions `geo_point`.
- ILM policy `radio-retention-policy`: warm after 7 days (read-only, forcemerge), deleted after 90 days. `logs-ilm-policy` deletes logs and metrics after 7 days.
- Roles and users `radio_api`, `logstash_writer`, `beats_writer`.

The script is idempotent and should be run after every update.

### Kibana

`http://127.0.0.1:5601`, user `elastic`, password `ELASTIC_PASSWORD` from `.env`. The dashboards are named after the modules of the web interface (`RadioMoni · Übersicht` (overview), `Sprache` (voice), `VOX-Aufnahme` (VOX recording), `APRS`, `POCSAG`, `ADS-B`, `AIS`, `ISM-Sensoren` (ISM sensors), `Repeater-Scan`, `Alarme` (alerts), plus `System – Logs` and `System – Zustand` (health)). APRS, ADS-B and AIS have a map. They are imported with `./scripts/import-kibana-dashboards.sh` and generated by `monitoring/kibana/build_dashboards.py` (see [monitoring/kibana/dashboards/README.md](../monitoring/kibana/dashboards/README.md)).

**Playing recordings:** in the lists of the *Sprache* (voice) and *VOX-Aufnahme* dashboards (and in Discover on `radio-captures-*`) the column `audio_url` shows a play button. It loads the WAV file through a signed link from the web interface (`WEB_PUBLIC_URL`, default `http://localhost:${WEB_PORT}`), without an API key. If you open Kibana from another computer, set `WEB_PUBLIC_URL` to the address under which that computer reaches the web interface and run `./scripts/import-kibana-dashboards.sh` again. Recordings from before this feature get the link with `docker compose exec radio-api python -m radiomoni.recording_links backfill`. If the WAV file has already been deleted (`RECORDING_RETENTION_DAYS`), the player stays silent.

From another computer you can reach Kibana through an SSH tunnel: `ssh -L 5601:127.0.0.1:5601 user@host`. Alternatively set `KIBANA_BIND=0.0.0.0`; Kibana is then visible on the whole LAN.

Examples for the console (Dev Tools):

```
GET _cat/indices/radio-*?v&s=index
GET radio-aprs-*/_search
{ "query": { "term": { "source_callsign": "HB9XYZ-7" } }, "sort": [{ "@timestamp": "desc" }] }
GET radio-captures-*/_search
{ "query": { "multi_match": { "query": "notfall", "fields": ["transcription", "transcription.german"] } } }
```

### Backup

Volume backup (stack stopped, consistent):

```bash
docker compose stop elasticsearch
docker run --rm -v radio-monitoring_elasticsearch-data:/data -v "$PWD/backups":/backup alpine \
  tar czf /backup/es-data-$(date +%Y%m%d).tgz -C /data .
docker compose start elasticsearch
```

Restoring: empty the volume and extract the archive into it with `tar xzf`, with Elasticsearch stopped and **with the same or a newer version**.

### Upgrade

Elasticsearch only allows major upgrades from the last minor version. A downgrade is **no longer** possible once the new version has started. Procedure:

1. Backup as above.
2. Set `ELK_VERSION` to the last 8.x (`8.19.23`), `docker compose up -d`, then check `GET _migration/deprecations`. Wait until Kibana reports the level `available` at `/api/status`: only then are its saved objects migrated. Kibana 9 does not start with objects from an older 8.x.
3. Set `ELK_VERSION` to the target version (`9.5.5`), `docker compose up -d`.
4. `./scripts/post-docker-setup.sh`.

The Python library `elasticsearch` must match the server's major version (9.x for server 9.x).

### Without ELK

With `COMPOSE_PROFILES=` and `STORAGE_BACKEND=sqlite`, the API stores everything in `/app/data/radiomoni.sqlite3` (volume `api-data`). There is no Kibana then; dashboard and search of the web interface keep working.
