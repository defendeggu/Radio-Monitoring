# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionierung nach [SemVer](https://semver.org/lang/de/).

## [Unreleased]

### Neu
- Repeater-Scan nach Kanton (voreingestellt LU) mit Auswahl einzelner Relais, Gesamtdauer (ein Durchgang, 30 min bis 24 h oder bis Stopp) und Sekunden pro Relais; Ergebnisse pro Relais über alle Runden zusammengefasst. API: `total_duration`, `until_stopped` und `POST /scan-repeaters/{id}/stop`.
- Schweizer Repeater-Liste aus der USKA HB Voice Repeater List (`scripts/update_repeaters_from_uska.py`).
- ADS-B auch mit dem HackRF.
- Kibana-Dashboards pro Modul der Weboberfläche, neu auch für ADS-B, AIS, ISM und Alarme.
- Weboberfläche auf Deutsch und Englisch umschaltbar; README und Dokumentation zusätzlich auf Englisch.

### Behoben
- SSB (USB/LSB) hörte beide Seitenbänder und Nachbarn bis ±8 kHz; jetzt nur noch 300–2700 Hz des gewählten Seitenbands (#7, danke HB9FLD).
- SDR nach einem Reboot des Hosts oder erneutem Einstecken im API-Container nicht mehr sichtbar: `/dev/bus/usb` wird jetzt als Bind-Mount eingebunden.
- Aufnahmen dauerten doppelt so lange wie verlangt.
- APRS: Kanal wird vor der FM-Demodulation gefiltert, damit Pakete dekodiert werden.
- Streaming-Sessions werden als fehlgeschlagen markiert, wenn der SDR-Prozess abbricht.
- VOX meldet fehlgeschlagene Transkriptionen statt endlos „transkribiere…“ anzuzeigen; PyAV auf 18 fixiert, weil 19 faster-whisper bricht.
- Gunicorn-Steuersocket abgeschaltet (Fehlermeldung im schreibgeschützten Container).
- Sicherheitsupdates von Alpine im nginx-Image.

### Geändert
- Python-Code im Paket `radiomoni/` mit Unterpaketen für Decoder und Speicher; Konfigurationsdateien unter `config/`, Tool-Einstellungen in `pyproject.toml`.
- Abhängigkeiten von Frontend und Tests aktualisiert; Dependabot entfernt.

### Entfernt
- Veraltete Endpunkte `POST /stream/aprs/start`, `POST /stream/pocsag/start` (ersetzt durch `POST /stream-decode`) und `GET /list-recordings` (ersetzt durch `/recordings`).
- RepeaterBook-Import und -Daten.
- Alte manuelle Hardware-Testskripte (`scripts/tests/`), der Verbesserungsbericht unter `docs/reports/` und ungenutzter Code.

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
