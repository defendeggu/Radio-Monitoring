# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionierung nach [SemVer](https://semver.org/lang/de/).

## [Unreleased]

## [5.5.0] – 2026-11-06

### Neu
- RBN über einen DX-Cluster: `RBN_LOGIN_COMMANDS` schickt nach dem Login Befehle wie `SET/SKIMMER`; das Spot-Format von CC Cluster (z. B. GB7DXG) wird verstanden.

## [5.4.0] – 2026-11-06

### Neu
- SDRplay RSP (RSPduo, RSP1A, RSPdx …) über SoapySDR, wenn das Image mit `WITH_SDRPLAY=1` gebaut ist.
  - Die proprietäre API lädt der Build von sdrplay.com, mit fester Prüfsumme, ohne das Installer-Skript auszuführen. Sie steht nicht im Repo.
  - Eigener Streamer `sdrplay_rx` (int16-IQ nach stdout); der API-Dienst startet mit dem Container.
  - Antenne (Hi-Z auf Tuner A unter 30 MHz), Notch gegen Rundfunk, Bias-T und LNA-Stufe aus der Verstärkung; einstellbar mit `SDRPLAY_*`.
- RSPduo mit zwei Tunern gleichzeitig: Tuner A und B sind zwei Geräte mit eigener Sperre.
  - Der erste Job öffnet als Master, der zweite als Slave, beide mit bis zu 2 MS/s.
  - Einen Master mit laufendem Slave stoppt die API nur mit `?force=1`; die Oberfläche fragt nach. Ein Wasserfall auf dem Master weicht dann nicht.

## [5.3.0] – 2026-11-05

### Neu
- Mehrere SDRs gleichzeitig: Jedes Gerät hat seine eigene Sperre (`sdr:lock:<device_id>`), Jobs auf verschiedenen Geräten laufen parallel.
  - Die Geräteliste kommt aus sysfs, ohne ein Gerät zu öffnen.
  - `GET /sdr/devices` liefert die Liste; `/sdr/status` enthält jetzt `devices`.
  - Alle Starts nehmen `device_id`. ADS-B, AIS und ISM nehmen ohne Angabe ein freies passendes Gerät.
  - Notstopp pro Gerät mit `?device_id=`. Zeitpläne warten auf ihr eigenes Gerät.
  - Mehrere Skimmer laufen nebeneinander, ihre Spots werden zusammengeführt.
  - Oberfläche: Geräteauswahl auf den Startseiten und in den Einstellungen, Status pro Gerät in der Seitenleiste, Skimmer-Reiter auf der Contest-Seite.
  - Ohne Geräteangabe gilt das Standardgerät; mit einem SDR ändert sich nichts.

### Geändert
- Streaming ohne angeschlossenes SDR antwortet mit HTTP 503 wie die Einzelaufnahme (bisher 400).

### Behoben
- Ein Job verdrängte jeden Wasserfall des API-Prozesses, jetzt nur den Wasserfall auf seinem Gerät.
- Die Seitenleiste zeigte fest „v4.0“ statt der aktuellen Version.

## [5.2.0] – 2026-11-05

### Neu
- Contest-Skimmer in SSB (experimentell): Signalerkennung für Sprachsignale (2,4 kHz geglättet), ein USB/LSB-Empfänger pro Station mit geschätztem Träger, Sprachabschnitte in einer gemeinsamen Whisper-Warteschlange (Contest-Prompt, Buchstabieralphabet als `hotwords`, Sprache wählbar), Rufzeichen über den Phonetik-Parser und dieselbe Bestätigung wie bei CW. Jeder neue SSB-Spot speichert seinen Ausschnitt zum Nachhören; die Seite zeigt den gehörten Text und die Whisper-Auslastung. API: `mode: SSB`, `language`. Auswertung einer SSB-IQ-Aufnahme: `python -m radiomoni.skimmer.evaluate ssb-iq`.
- Phonetik-Parser: „HB9XYZ contest“ und „… QRZ“ gelten als Eigenidentifikation.

### Behoben
- Sicherheit: minimatch vor 11.0.1 erlaubte einen Denial of Service über Glob-Muster (GHSA-g3hv-75wg-m249, Dependabot). ESLint und typescript-eslint verlangen noch Version 10, ein npm-`override` setzt 11.0.4.
- Wasserfall, CW und Skimmer meldeten sich als „running“, bevor ihr Zustand veröffentlicht war; wer gleich danach umstimmte, bekam 409. Das liess die CI bei 5.0.0 und den Commits danach zeitweise scheitern.

## [5.1.0] – 2026-11-05

### Neu
- Contest-Skimmer: Regeln für die KW-, UKW- und Spezial-Contests der USKA (Weihnachtswettbewerb SSB und CW, NMD, Swiss Emergency Contest, SwAC, VHF/UHF März und Mai, H26 VHF, Mini Contest August) und die IARU-Region-1-UKW-Contests (50 MHz, VHF September, UHF/Microwaves Oktober, Marconi Memorial). Jede Regel nennt den üblichen Termin (`when`).
- Contest-Skimmer auf 6 m, 2 m, 70 cm und 23 cm (CW-Segmente nach IARU Region 1); das Log erkennt diese Bänder auch in ADIF, Cabrillo und N1MM+.

### Geändert
- README und `docs/security.md`: veröffentlichte Ports des Contest-Skimmers (DX-Cluster TCP 7300, N1MM+ UDP 12060), Architektur mit RBN, N1MM+ und Cluster, der Wasserfall als Ausnahme der SDR-Sperre, Bandpläne für KW und UKW, alle Contest-Seiten der USKA als Quelle.

## [5.0.0] – 2026-11-05

Neue Empfangsarten für Kurzwelle: Spektrum/Wasserfall mit Mithören, CW-Decoder, Reverse Beacon Network und Contest-Skimmer mit Anbindung an N1MM+.

### Neu
- Seite *Spektrum*: Wasserfall mit gemitteltem Spektrum, Zoom, Band-Schnellwahl und Lesezeichen-Marken; Mithören im Browser (FM, AM, USB, LSB, CW, Squelch). API: `POST /spectrum`, `GET /spectrum/{id}/stream` (binärer Live-Strom), `POST /spectrum/{id}/tune`.
- Laufende VOX-Sessions liefern ihr Spektrum mit; es lässt sich auf der Seite *Spektrum* ansehen.
- Seite *CW*: Morse live dekodieren (automatische Tempo- und Frequenzanpassung, Filter 100–500 Hz, Mithören), Durchgänge mit Text, Rufzeichen, Tempo und optional WAV in `radio-cw-*`, Kibana-Dashboard *RadioMoni · CW*, Alarmquelle `cw`. API: `POST /cw/start`, `POST /cw/{id}/tune`, `GET /cw/transmissions`.
- RBN-Fenster auf der CW-Seite: Ein Klick auf einen Spot stellt den Empfänger auf dessen Frequenz (innerhalb der Bandbreite ohne Neustart) oder startet die CW-Session.
- RTL-SDR auf Kurzwelle: unter 24 MHz automatisch Direct Sampling (`rtl_sdr -D`).
- Seite *Contest-Skimmer*: dekodiert alle CW-Signale eines Bandsegments gleichzeitig (Signalerkennung per FFT, ein Decoder pro Signal), bestätigt Rufzeichen mehrfach und stuft sie nach Contest-Regeln ein (neuer Multiplikator, selten nach Club Log Most Wanted, doppelt). Regeln für IARU-R1-Fieldday, IARU HF Championship, CQ WW, CQ WPX und den USKA Helvetia Contest. Spots in `radio-skimmer-*` (Kibana: *RadioMoni · Contest-Skimmer*), Alarmquelle `skimmer`, Zeitplan-Aktionen `skimmer` und `cw`. Anleitung: [docs/contest.md](docs/contest.md).
- DX-Cluster-Server (`CLUSTER_ENABLED`, TCP 7300) für die Bandmap von N1MM+; UDP-Empfänger für N1MM+ (`N1MM_ENABLED`, UDP 12060): gearbeitete QSOs live ins Log, Auswertung ausgeblendet, solange N1MM+ sendet. Log-Import aus ADIF und Cabrillo.
- Referenzdaten cty.csv, MASTER.SCP und Club Log Most Wanted, offline zwischengespeichert (`POST /contest/refdata/update`).
- Phase-0-Messung: IQ-Aufnahme des Segments mit RBN-Referenzspots und `python -m radiomoni.skimmer.evaluate` (Präzision und Ausbeute für CW und für SSB mit Whisper und Phonetik-Parser). Die Transkription nimmt `hotwords` an.
- Reverse Beacon Network: CW-Spots auf Kurzwelle der letzten 30 Minuten (`GET /rbn/spots`, `/rbn/status`), als Marken im Wasserfall und als Alarmquelle `rbn`. Optional, mit eigenem Rufzeichen (`RBN_ENABLED`, `RBN_CALLSIGN`).

### Geändert
- Der Wasserfall belegt das SDR nur, solange es niemand anders braucht: Jeder Job (auch per Zeitplan) beendet ihn und übernimmt das SDR. `/sdr/status` meldet dafür `preemptible`.
- Gemeinsame Signalverarbeitung mit Zustand über die Datenblöcke hinweg (`radiomoni/dsp.py`).
- Das Compose-File veröffentlicht zwei weitere Ports des API-Containers: TCP 7300 (DX-Cluster) und UDP 12060 (N1MM+), standardmässig nur auf `127.0.0.1` (`CONTEST_BIND`, `CLUSTER_PORT`, `N1MM_PORT`). Belegt ein anderer Dienst diese Ports, startet der Container nicht; dann die Ports in `.env` ändern.
- Zeitpläne kennen die Aktionen `cw` und `skimmer`.
- Neue Abhängigkeit PyYAML (Contest-Regeln); das API-Image muss neu gebaut werden.

### Behoben
- RBN: Spots von Skimmern mit Buchstaben-Zusatz im Rufzeichen (z. B. `DF4UE-RP`) wurden verworfen.

### Update von 4.x
1. `git pull`, dann `./scripts/setup-env.sh` (ergänzt die neuen Einstellungen in `.env`) und `docker compose build radio-api web-interface && docker compose up -d`.
2. `./scripts/setup-elk-users.sh` (Index-Template `radio-skimmer`) und `./scripts/import-kibana-dashboards.sh` (Dashboards *CW* und *Contest-Skimmer*).
3. Für den Contest-Skimmer einmal die Referenzdaten laden: Seite *Contest-Skimmer* → *Referenzdaten aktualisieren*.

## [4.1.0] – 2026-11-01

### Neu
- Die Versionsnummer wird mit `scripts/version.py` überall gesetzt (README-Badge, Frontend); die CI prüft, dass alle Stellen zu `radiomoni/version.py` passen.
- Sprachauswahl für Whisper (VOX-Aufnahme und Sprache) als Dropdown: automatisch, Englisch, Deutsch, Italienisch, Französisch oder „Andere…“ mit freiem ISO-Code.
- GPU-Auslastung, -Speicher und -Temperatur im Kibana-Dashboard *System – Zustand* (GPU-Setup): API-Endpunkt `/metrics/gpu`, den Metricbeat mit dem eigenen, nur dafür gültigen `METRICS_API_KEY` liest.
- Play-Button in Kibana: Sprach- und VOX-Aufnahmen lassen sich direkt aus den Dashboard-Listen abspielen (Feld `audio_url`, signierte Links mit `RECORDING_LINK_SECRET`).
- Repeater-Scan nach Kanton (voreingestellt LU) mit Auswahl einzelner Relais, Gesamtdauer (ein Durchgang, 30 min bis 24 h oder bis Stopp) und Sekunden pro Relais; Ergebnisse pro Relais über alle Runden zusammengefasst. API: `total_duration`, `until_stopped` und `POST /scan-repeaters/{id}/stop`.
- Schweizer Repeater-Liste aus der USKA HB Voice Repeater List (`scripts/update_repeaters_from_uska.py`).
- ADS-B auch mit dem HackRF.
- Kibana-Dashboards pro Modul der Weboberfläche, neu auch für ADS-B, AIS, ISM und Alarme.
- Weboberfläche auf Deutsch und Englisch umschaltbar; README und Dokumentation zusätzlich auf Englisch.

### Behoben
- Whisper auf einer nicht unterstützten oder zu kleinen GPU: Jede Transkription scheiterte (z. B. `cudaErrorInvalidDevice` auf Maxwell-Karten). Nach dem Laden prüft die API die GPU jetzt mit einer kurzen Probe und weicht sonst mit Warnung auf die CPU aus; `/health/ready` zeigt das genutzte Gerät. Die Installationsanleitung nennt die nötige Kartengeneration (ab Pascal).
- Aufnahmen schlugen fehl, wenn Docker `./recordings` und `./captures` beim ersten Start als root anlegte; `setup-env.sh` legt die Ordner jetzt selbst an und warnt bei falschem Besitzer.
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
