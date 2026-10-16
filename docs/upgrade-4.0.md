# Upgrade von 3.x auf 4.0

Version 4.0 baut Sicherheit, Datenhaltung und Oberfläche um. Ein bestehender Stack lässt sich so übernehmen:

1. **Backup** des Elasticsearch-Volumes (siehe [elk.md](elk.md#backup)). Das ELK-Upgrade auf 9.x ist nicht umkehrbar.
2. **Konfiguration:** `./scripts/setup-env.sh` ergänzt die neuen Variablen (`LOGSTASH_HTTP_PASSWORD`, `BEATS_WRITER_PASSWORD`, `COMPOSE_PROFILES` …). `.env.elk` und `.secrets/` werden nicht mehr benutzt und können gelöscht werden.
3. **Elasticsearch 8.11 → 8.19 → 9.5:** Ein direkter Sprung ist nicht möglich.
   ```bash
   ELK_VERSION=8.19.23 docker compose up -d elasticsearch && ./scripts/setup-elk-users.sh
   docker compose up -d --build          # 9.5.5 (Standard)
   ./scripts/post-docker-setup.sh
   ```
4. **Weboberfläche:** neue Adresse für die API ist `http://<host>:8080/api` (Port 5000 ist zu). Den API-Key einmal in den Einstellungen eintragen.

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
