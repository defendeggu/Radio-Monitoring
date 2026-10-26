# Sicherheit

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
