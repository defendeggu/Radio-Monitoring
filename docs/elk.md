# Elasticsearch, Kibana und Logstash

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

`http://127.0.0.1:5601`, Benutzer `elastic`, Passwort `ELASTIC_PASSWORD` aus `.env`. Die Dashboards (Captures, APRS mit Karte, POCSAG, Repeater, Logs, Systemzustand) importiert `./scripts/import-kibana-dashboards.sh`.

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
