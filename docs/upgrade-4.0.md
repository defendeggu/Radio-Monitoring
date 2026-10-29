# Upgrade von 3.x auf 4.0

🇬🇧 **[English Version](#english-version)** below

Version 4.0 baut Sicherheit, Datenhaltung und Oberfläche um. Ein bestehender Stack lässt sich so übernehmen:

1. **Konfiguration:** `./scripts/setup-env.sh` ergänzt die neuen Variablen (`LOGSTASH_HTTP_PASSWORD`, `BEATS_WRITER_PASSWORD`, `COMPOSE_PROFILES` …). `.env.elk` und `.secrets/` werden nicht mehr benutzt und können gelöscht werden.
2. **Projektname beibehalten:** 3.x lief als Compose-Projekt `radiomoni` (Name des Verzeichnisses), 4.0 heisst `radio-monitoring`. Damit die bestehenden Volumes (`radiomoni_elasticsearch-data`, `radiomoni_redis-data`) weiter benutzt werden, den alten Namen in `.env` festhalten. Dockge erkennt den Stack ebenfalls nur, wenn Projekt- und Verzeichnisname übereinstimmen.
   ```bash
   echo "COMPOSE_PROJECT_NAME=radiomoni" >> .env
   ```
   Die gestoppten 3.x-Container tragen dieselben Namen wie die neuen und müssen weg (die Daten liegen in den Volumes):
   ```bash
   docker rm radio-elasticsearch radio-logstash radio-kibana radio-metricbeat radio-filebeat \
     radio-redis radio-transcription-api radio-web-interface
   ```
3. **Backup** des Elasticsearch-Volumes (siehe [elk.md](elk.md#backup), Volume `radiomoni_elasticsearch-data`). Das ELK-Upgrade auf 9.x ist nicht umkehrbar.
4. **Elasticsearch und Kibana 8.11 → 8.19 → 9.5:** Ein direkter Sprung ist nicht möglich. Auch Kibana muss einmal mit 8.19 laufen, damit es seine gespeicherten Objekte migriert. Sonst bricht Kibana 9 mit `Kibana 8.11.3 deployment detected` ab.
   ```bash
   ELK_VERSION=8.19.23 docker compose up -d elasticsearch && ./scripts/setup-elk-users.sh
   ELK_VERSION=8.19.23 docker compose up -d kibana
   # warten, bis Kibana die Migration abgeschlossen hat:
   until curl -fs http://127.0.0.1:5601/api/status | grep -q '"level":"available"'; do sleep 5; done
   docker compose up -d --build          # 9.5.5 (Standard)
   ./scripts/post-docker-setup.sh
   ```
5. **Weboberfläche:** neue Adresse für die API ist `http://<host>:8080/api` (Port 5000 ist zu). Den API-Key einmal in den Einstellungen eintragen.

### Kibana-Schritt vergessen?

Läuft Elasticsearch schon mit 9.x, ist kein Zurück auf 8.19 mehr möglich. Entweder das Backup zurückspielen und Schritt 4 wiederholen, oder die alten Kibana-Objekte verwerfen (eigene Dashboards, Data Views und Einstellungen gehen verloren, die Radio-Daten bleiben). Die Kibana-Indizes sind geschützte Systemindizes, deshalb braucht es dafür kurzzeitig eine eigene Rolle:

```bash
source .env; docker compose stop kibana
es() { docker exec radio-elasticsearch curl -s -u "$1" -H 'Content-Type: application/json' -X "$2" "localhost:9200$3" ${4:+-d "$4"}; echo; }
T=$(openssl rand -hex 16)
es "elastic:$ELASTIC_PASSWORD" PUT /_security/role/tmp_kibana_reset \
  '{"indices":[{"names":[".kibana*"],"privileges":["delete_index"],"allow_restricted_indices":true}]}'
es "elastic:$ELASTIC_PASSWORD" PUT /_security/user/tmp_kibana_reset "{\"password\":\"$T\",\"roles\":[\"tmp_kibana_reset\"]}"
# Indexnamen ohne Wildcard angeben (Version anpassen, siehe GET /_cat/indices/.kibana*?expand_wildcards=all)
es "tmp_kibana_reset:$T" DELETE /.kibana_8.11.3_001,.kibana_alerting_cases_8.11.3_001,.kibana_analytics_8.11.3_001,.kibana_ingest_8.11.3_001,.kibana_security_solution_8.11.3_001,.kibana_task_manager_8.11.3_001,.kibana_security_session_1
es "elastic:$ELASTIC_PASSWORD" DELETE /_security/user/tmp_kibana_reset
es "elastic:$ELASTIC_PASSWORD" DELETE /_security/role/tmp_kibana_reset
docker compose start kibana && ./scripts/import-kibana-dashboards.sh
```

## Was sich ändert

| Bereich | 3.x | 4.0 |
|---|---|---|
| Ports | 5000, 5601, 6379, 9200, 9600–9604 offen | nur `WEB_PORT`; Kibana auf localhost |
| Auth | Docker-Netz ohne Key, ohne `API_KEYS` offen | Key-Pflicht, fail-closed, nur `TRUSTED_IPS` |
| Gunicorn | 5 gevent-Worker mit Zustand pro Prozess | 1 gthread-Worker; SDR-Sperre und Events in Redis |
| Fehler beim Dekodieren | stille Simulation (Fake-Daten) | echte Fehlermeldung; Simulation nur mit `SIMULATION_MODE=true` |
| Index-Templates | nie installiert (Callsigns als `text`) | `keyword`-Mappings, Retention 90 Tage |
| `/capture` | synchron, ohne Limit | asynchron, validiert, SDR-Sperre |
| Frontend | Vanilla JS, `localhost:5000` fest | Svelte 5, gleicher Origin, Live-Events |
| Python / ELK / Redis | 3.11 / 8.11.3 / 7 | 3.13 / 9.5.5 / 8.10 |

Bestehende Daten in `radio-logs-*` und `metricbeat-*` bleiben erhalten. Neue Radio-Indizes bekommen die korrigierten Mappings ab dem nächsten Tagesindex.

---

<a id="english-version"></a>

## English Version

Version 4.0 rebuilds security, data storage and the interface. An existing stack can be taken over like this:

1. **Configuration:** `./scripts/setup-env.sh` adds the new variables (`LOGSTASH_HTTP_PASSWORD`, `BEATS_WRITER_PASSWORD`, `COMPOSE_PROFILES` …). `.env.elk` and `.secrets/` are no longer used and can be deleted.
2. **Keep the project name:** 3.x ran as Compose project `radiomoni` (name of the directory), 4.0 is called `radio-monitoring`. To keep using the existing volumes (`radiomoni_elasticsearch-data`, `radiomoni_redis-data`), pin the old name in `.env`. Dockge also only recognizes the stack if the project name and the directory name match.
   ```bash
   echo "COMPOSE_PROJECT_NAME=radiomoni" >> .env
   ```
   The stopped 3.x containers have the same names as the new ones and must be removed (the data is in the volumes):
   ```bash
   docker rm radio-elasticsearch radio-logstash radio-kibana radio-metricbeat radio-filebeat \
     radio-redis radio-transcription-api radio-web-interface
   ```
3. **Backup** of the Elasticsearch volume (see [elk.md](elk.md#backup-1), volume `radiomoni_elasticsearch-data`). The ELK upgrade to 9.x cannot be undone.
4. **Elasticsearch and Kibana 8.11 → 8.19 → 9.5:** a direct jump is not possible. Kibana also has to run once with 8.19 so that it migrates its saved objects. Otherwise Kibana 9 aborts with `Kibana 8.11.3 deployment detected`.
   ```bash
   ELK_VERSION=8.19.23 docker compose up -d elasticsearch && ./scripts/setup-elk-users.sh
   ELK_VERSION=8.19.23 docker compose up -d kibana
   # wait until Kibana has finished the migration:
   until curl -fs http://127.0.0.1:5601/api/status | grep -q '"level":"available"'; do sleep 5; done
   docker compose up -d --build          # 9.5.5 (default)
   ./scripts/post-docker-setup.sh
   ```
5. **Web interface:** the new address of the API is `http://<host>:8080/api` (port 5000 is closed). Enter the API key once in the settings.

#### Forgot the Kibana step?

If Elasticsearch is already running 9.x, there is no way back to 8.19. Either restore the backup and repeat step 4, or discard the old Kibana objects (your own dashboards, data views and settings are lost, the radio data is kept). The Kibana indices are protected system indices, so this temporarily needs a dedicated role:

```bash
source .env; docker compose stop kibana
es() { docker exec radio-elasticsearch curl -s -u "$1" -H 'Content-Type: application/json' -X "$2" "localhost:9200$3" ${4:+-d "$4"}; echo; }
T=$(openssl rand -hex 16)
es "elastic:$ELASTIC_PASSWORD" PUT /_security/role/tmp_kibana_reset \
  '{"indices":[{"names":[".kibana*"],"privileges":["delete_index"],"allow_restricted_indices":true}]}'
es "elastic:$ELASTIC_PASSWORD" PUT /_security/user/tmp_kibana_reset "{\"password\":\"$T\",\"roles\":[\"tmp_kibana_reset\"]}"
# give the index names without wildcards (adjust the version, see GET /_cat/indices/.kibana*?expand_wildcards=all)
es "tmp_kibana_reset:$T" DELETE /.kibana_8.11.3_001,.kibana_alerting_cases_8.11.3_001,.kibana_analytics_8.11.3_001,.kibana_ingest_8.11.3_001,.kibana_security_solution_8.11.3_001,.kibana_task_manager_8.11.3_001,.kibana_security_session_1
es "elastic:$ELASTIC_PASSWORD" DELETE /_security/user/tmp_kibana_reset
es "elastic:$ELASTIC_PASSWORD" DELETE /_security/role/tmp_kibana_reset
docker compose start kibana && ./scripts/import-kibana-dashboards.sh
```

### What changes

| Area | 3.x | 4.0 |
|---|---|---|
| Ports | 5000, 5601, 6379, 9200, 9600–9604 open | only `WEB_PORT`; Kibana on localhost |
| Auth | Docker network without key, open without `API_KEYS` | key required, fail-closed, only `TRUSTED_IPS` |
| Gunicorn | 5 gevent workers with per-process state | 1 gthread worker; SDR lock and events in Redis |
| Decoding errors | silent simulation (fake data) | real error message; simulation only with `SIMULATION_MODE=true` |
| Index templates | never installed (callsigns as `text`) | `keyword` mappings, retention 90 days |
| `/capture` | synchronous, no limit | asynchronous, validated, SDR lock |
| Frontend | vanilla JS, `localhost:5000` hard-coded | Svelte 5, same origin, live events |
| Python / ELK / Redis | 3.11 / 8.11.3 / 7 | 3.13 / 9.5.5 / 8.10 |

Existing data in `radio-logs-*` and `metricbeat-*` is kept. New radio indices get the corrected mappings from the next daily index on.
