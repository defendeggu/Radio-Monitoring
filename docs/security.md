# Sicherheit

🇬🇧 **[English Version](#english-version)** below

## Netzwerk

| Dienst | Erreichbar von |
|---|---|
| Weboberfläche (nginx) | Host-Port `WEB_PORT` (Standard alle Interfaces) |
| Kibana | `127.0.0.1:5601` (Host), per `KIBANA_BIND` änderbar |
| API, Redis, Elasticsearch, Logstash | nur im Docker-Netz, kein Host-Port |

Die Netze sind getrennt. `web` verbindet nur nginx und die API, `backend` verbindet die API mit Redis und ELK. Kibana, Logstash und die Beats können die API nicht ansprechen.

Für den Zugriff aus dem Internet gehört ein Reverse-Proxy mit TLS davor (Caddy, Traefik, nginx), idealerweise zusätzlich mit Login (z. B. Authelia oder oauth2-proxy) oder ein VPN (WireGuard, Tailscale).

## Authentifizierung

- Jede API-Anfrage ausser `/health*` und `/openapi.json` braucht `X-API-Key`. Verglichen wird in konstanter Zeit gegen alle Keys.
- **Fail-closed:** Ohne `API_KEYS` startet die API nicht. Zum lokalen Entwickeln gibt es nur das explizite Opt-out `ALLOW_INSECURE=true`.
- Ohne Key vertraut die API nur `localhost` im Container (Healthcheck). Das Docker-Netz gilt **nicht** als vertrauenswürdig. Zusätzliche Netze trägst du explizit in `TRUSTED_IPS` ein.
- nginx überschreibt `X-Forwarded-For` mit der echten Client-Adresse. Die API wertet genau einen Proxy aus (`PROXY_COUNT=1`).
- Die Weboberfläche speichert den Key im `localStorage` des Browsers und schickt ihn als Header mit, auch für Live-Events und Audio-Downloads.

## Eingaben

- Alle Endpunkte validieren mit pydantic-Schemas: Typen, Wertebereiche, Längen, Aufzählungen. Unbekannte Felder werden abgelehnt.
- Pfade zu Aufnahmen werden aufgelöst, auch Symlinks, und auf `recordings/` beschränkt. Nach aussen gehen nur Dateinamen.
- Die USRP-Adresse muss eine IP-Adresse sein. Das verhindert das Einschleusen zusätzlicher UHD-Argumente.
- Subprozesse laufen immer mit Argumentlisten, nie über eine Shell.
- Request-Bodies sind auf 1 MB begrenzt.

## Daten aus dem Äther sind nicht vertrauenswürdig

APRS-Nachrichten, Pager-Texte, Schiffsnamen und Transkripte kann jeder senden.

- Die Weboberfläche gibt sie ausschliesslich als Text aus. `{@html}` ist per Lint-Regel verboten, Karten-Popups werden mit DOM-Textknoten gebaut.
- Die Content-Security-Policy erlaubt nur eigene Skripte (`script-src 'self'`) und die OSM-Kacheln.
- CSV-Exporte entschärfen Zellen, die mit `= + - @` beginnen (Formel-Injection). KML wird escaped.

## Dienste und Container

- Elasticsearch-Benutzer mit minimalen Rechten: `radio_api` (lesen/schreiben `radio-*`), `logstash_writer`, `beats_writer`. Der Superuser `elastic` ist nur für Setup und Kibana-Login gedacht.
- Die HTTP-Eingänge von Logstash verlangen Basic-Auth (`LOGSTASH_HTTP_PASSWORD`), Redis ein Passwort.
- Die Container laufen mit `no-new-privileges`. API und Weboberfläche haben ein Read-only-Dateisystem, `cap_drop: ALL` und keinen Root-Benutzer.
- Metricbeat und Filebeat brauchen Root und den Docker-Socket (read-only) für Host-Metriken und Logs.
- Gunicorn schreibt Dateien mit `umask 027`.

## Secrets

- Alle Secrets liegen in `.env` (chmod 600, in `.gitignore`), erzeugt von `scripts/setup-env.sh`.
- Die CI prüft jeden Commit mit gitleaks.
- Rotieren: den Wert in `.env` ändern oder leeren, `./scripts/setup-env.sh` ausführen (füllt leere Werte neu), dann `./scripts/post-docker-setup.sh` und `docker compose up -d`.

## Abhängigkeiten

- Python-, npm- und Docker-Versionen sind fest gepinnt. Updates werden von Hand eingespielt (siehe [development.md](development.md#ci)).
- Die CI führt `pip-audit`, `npm audit` und Trivy (Images) aus.

## Bekannte Grenzen

- Es gibt keine Benutzerverwaltung: Wer einen API-Key hat, darf alles. Für mehrere Nutzer setzt du einen Login-Proxy davor.
- Elasticsearch läuft im internen Netz ohne TLS. Das ist akzeptabel, weil kein Port veröffentlicht ist.

---

<a id="english-version"></a>

## English Version

### Network

| Service | Reachable from |
|---|---|
| Web interface (nginx) | host port `WEB_PORT` (all interfaces by default) |
| Kibana | `127.0.0.1:5601` (host), changeable with `KIBANA_BIND` |
| API, Redis, Elasticsearch, Logstash | only inside the Docker network, no host port |

The networks are separated. `web` only connects nginx and the API, `backend` connects the API with Redis and ELK. Kibana, Logstash and the Beats cannot reach the API.

For access from the internet, put a reverse proxy with TLS in front (Caddy, Traefik, nginx), ideally with an additional login (e.g. Authelia or oauth2-proxy), or use a VPN (WireGuard, Tailscale).

### Authentication

- Every API request except `/health*` and `/openapi.json` needs `X-API-Key`. It is compared in constant time against all keys.
- **Fail-closed:** the API does not start without `API_KEYS`. For local development there is only the explicit opt-out `ALLOW_INSECURE=true`.
- Without a key, the API only trusts `localhost` inside the container (health check). The Docker network is **not** considered trusted. Additional networks have to be listed explicitly in `TRUSTED_IPS`.
- nginx overwrites `X-Forwarded-For` with the real client address. The API evaluates exactly one proxy (`PROXY_COUNT=1`).
- The web interface stores the key in the browser's `localStorage` and sends it as a header, also for live events and audio downloads.

### Input

- All endpoints validate with pydantic schemas: types, value ranges, lengths, enumerations. Unknown fields are rejected.
- Paths to recordings are resolved, including symlinks, and restricted to `recordings/`. Only file names are returned to the outside.
- The USRP address must be an IP address. This prevents injecting additional UHD arguments.
- Subprocesses always run with argument lists, never through a shell.
- Request bodies are limited to 1 MB.

### Data from the air is not trustworthy

Anyone can transmit APRS messages, pager texts, ship names and transcripts.

- The web interface only ever outputs them as text. `{@html}` is forbidden by a lint rule, map popups are built from DOM text nodes.
- The content security policy only allows our own scripts (`script-src 'self'`) and the OSM tiles.
- CSV exports defuse cells that start with `= + - @` (formula injection). KML is escaped.

### Services and containers

- Elasticsearch users with minimal privileges: `radio_api` (read/write `radio-*`), `logstash_writer`, `beats_writer`. The `elastic` superuser is only meant for setup and the Kibana login.
- The Logstash HTTP inputs require basic auth (`LOGSTASH_HTTP_PASSWORD`), Redis requires a password.
- The containers run with `no-new-privileges`. API and web interface have a read-only file system, `cap_drop: ALL` and no root user.
- Metricbeat and Filebeat need root and the Docker socket (read-only) for host metrics and logs.
- Gunicorn writes files with `umask 027`.

### Secrets

- All secrets are in `.env` (chmod 600, in `.gitignore`), generated by `scripts/setup-env.sh`.
- The CI checks every commit with gitleaks.
- Rotating: change or empty the value in `.env`, run `./scripts/setup-env.sh` (fills empty values again), then `./scripts/post-docker-setup.sh` and `docker compose up -d`.

### Dependencies

- Python, npm and Docker versions are pinned. Updates are applied by hand (see [development.md](development.md#ci-1)).
- The CI runs `pip-audit`, `npm audit` and Trivy (images).

### Known limitations

- There is no user management: whoever has an API key may do everything. For several users, put a login proxy in front.
- Elasticsearch runs without TLS in the internal network. This is acceptable because no port is published.
