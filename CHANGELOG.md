# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionierung nach [SemVer](https://semver.org/lang/de/).

## [4.0.0] – 2026-10-16

### Sicherheit
- API ist nur noch über nginx (`/api`) erreichbar; Elasticsearch, Logstash, Redis und die API haben keinen Host-Port mehr, Kibana bindet an `127.0.0.1`.
- Kein Auth-Bypass mehr über das Docker-Netz; die API startet nicht ohne `API_KEYS` (fail-closed), Key-Vergleich in konstanter Zeit.
- Path-Traversal in `/aprs/decode` und `/pocsag/decode` behoben; Symlinks werden aufgelöst.
- Validierung aller Eingaben mit pydantic (Frequenz, Gain, Dauer, USRP-IP, …), Body-Limit 1 MB.
- XSS-Schutz für Over-the-Air-Daten, CSP und Security-Header, keine Wildcard-CORS.
- Logstash-HTTP-Eingänge mit Basic-Auth, eigene Elasticsearch-Rollen für API, Logstash und Beats.
- Container-Härtung (`no-new-privileges`, Read-only-Root, `cap_drop`), `umask 027`.
- Klartext-Passwort aus `kibana.yml` entfernt und aus der Git-Historie getilgt; gitleaks, pip-audit, npm audit und Trivy in der CI.

### Neu
- Svelte-5-Weboberfläche mit Dashboard, Live-Events (SSE), APRS-Karte, Audio-Player, Dark/Light-Mode.
- VOX-Aufnahme (Squelch-gesteuert, mit Transkription).
- ADS-B (readsb), AIS (rtl_ais) und ISM-Sensoren (rtl_433).
- Alarmregeln mit ntfy, Telegram, Webhook und E-Mail.
- Zeitpläne (Cron), Frequenz-Lesezeichen, Export als CSV/GeoJSON/KML/ZIP.
- OpenAPI-3.1-Dokument und API-Seite in der Oberfläche.
- Whisper-Optionen (Sprache, Beam size, Vokabular-Hinweis, Übersetzen), GPU-Profil.
- Light-Profil ohne ELK (SQLite).
- Maidenhead-Locator für APRS-Positionen, Aufbewahrungsdauer für Aufnahmen, Speicherplatz-Prüfung.

### Geändert
- SDR-Sperre, Sessions und Steuerbefehle über Redis (mehrere Prozesse möglich), Gunicorn mit gthread.
- Fehler beim Dekodieren und Transkribieren werden gemeldet statt durch Fake-Daten ersetzt.
- Index-Templates und ILM korrigiert (keyword-Mappings, keine Rollover-Konflikte).
- Repeater-Metriken werden flach gespeichert, damit die Zusammenfassung funktioniert.
- Python 3.13, Elastic Stack 9.5.5, Redis 8.10, nginx 1.30, gunicorn 26, Flask 3.1, numpy 2.5, Vite 8, Tailwind 4.
- README neu gegliedert, Dokumentation unter `docs/`.

### Entfernt
- Alte Oberfläche (`web_interface.html`, `help.html`), Prometheus/pgAdmin-Reste, `archive/`, veraltete Skripte, `.env.elk`, Docker-Secrets.

## [3.1.0] – 2026-05

- Oberfläche mit Vite und Tailwind, Multi-Channel DDC für USRP N200, Airspy HF+.
