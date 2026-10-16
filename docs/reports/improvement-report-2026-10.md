# RadioMoni – Verbesserungsbericht (Stand 2026-10-16)

> **Umsetzungsstand:** Mit Version 4.0.0 umgesetzt (siehe [CHANGELOG](../../CHANGELOG.md)).
> Abweichungen: ELK auf 9.5.5 statt 9.4 (neuere Linie verfügbar), Benutzer/Rollen (N10),
> APRS-IS-iGate (N6), PPM-Kalibrierung (N8) und DMR (Teil von N7) stehen weiterhin in der [ROADMAP](../../ROADMAP.md).
> Beim Umsetzen zusätzlich gefunden und behoben: nie installierte Index-Templates, APRS-Pakete mit
> Position wurden von Elasticsearch abgelehnt (doppeltes geo_point), Debian-readsb ohne RTL-SDR-Support,
> Repeater-Zusammenfassung ohne Daten (verschachtelte Metriken).

Prioritäten: 🔴 kritisch (sofort) · 🟠 hoch · 🟡 mittel · 🟢 nice-to-have.
Jeder Punkt nennt die **Datei**, das **Problem** und den **Fix**, damit er direkt umgesetzt werden kann.

## 1. Sicherheit

### 🔴 S1 – Kibana-Passwort im Klartext im Git-Repo (auch auf GitHub)
- **Datei:** `monitoring/kibana/config/kibana.yml:11` → `elasticsearch.password: "tGocFie…"`, seit Commit `ee52582` in der Historie, Remote ist `github.com/defendeggu/Radio-Monitoring`.
- **Fix:**
  1. Das Passwort von `kibana_system` sofort rotieren (`scripts/setup-elk-users.sh` oder `POST /_security/user/kibana_system/_password`).
  2. In `kibana.yml` die Zeilen `elasticsearch.username/password/hosts` löschen, denn die Werte kommen schon per ENV aus `docker-compose.yml`.
  3. Die Historie bereinigen: `git filter-repo --replace-text` und danach ein Force-Push. Bei einem öffentlichen Repo gilt das Secret als kompromittiert, auch wenn es aus der Historie entfernt wurde.
  4. Einen Secret-Scan in die CI aufnehmen (gitleaks oder trufflehog als GitHub Action).
- Ähnlich: `monitoring/pgadmin/pgpass` und `servers.json` (PostgreSQL ist entfernt) sowie `monitoring/prometheus/*` (Prometheus ist entfernt) als Altlasten löschen.

### 🔴 S2 – Die Auth lässt sich über die „Docker-Netz"-Ausnahme umgehen
- **Datei:** `api_service.py:162-227` (`is_trusted_ip`) und `check_api_key`.
- **Problem:** `172.16.0.0/12` gilt immer als vertrauenswürdig. Jeder Container im Netz (z. B. Logstash oder Kibana bei einer Kompromittierung) und je nach Docker-Setup (userland-proxy, rootless Docker, Zugriff über `localhost:5000`) **jede** Anfrage, die über das Bridge-Gateway `172.x.0.1` kommt, braucht keinen API-Key. Zusätzlich gilt: Ist `API_KEYS` leer, ist die API komplett offen, und sie hängt an `0.0.0.0:5000`.
- **Fix:**
  - Den Default-Trust auf Loopback beschränken; `TRUSTED_IPS` nur explizit setzen.
  - Die API **nicht mehr publishen** (`ports: "5000:5000"` entfernen) und nur über nginx unter `/api/` erreichbar machen (siehe F1). Optional: Auth in nginx (Basic Auth, oauth2-proxy oder Authelia).
  - Fail-closed: Ohne `API_KEYS` und ohne `ALLOW_INSECURE=true` startet die API nicht.
  - Key-Vergleich mit `hmac.compare_digest` gegen alle Keys statt Set-Lookup (Timing ist hier ein geringes Risiko, aber sauberer).

### 🔴 S3 – Interne Dienste auf allen Interfaces publiziert
- **Datei:** `docker-compose.yml`. Elasticsearch `9200`, Kibana `5601`, Redis `6379`, Logstash `9600–9604`, API `5000` sind alle als `0.0.0.0` exponiert.
- **Problem:** Die Logstash-HTTP-Inputs (`monitoring/logstash/pipelines/*.conf`) haben **keine Authentifizierung** und senden `Access-Control-Allow-Origin: *`. Jeder im LAN, und jede Webseite im Browser des Nutzers, kann beliebige Dokumente in ES schreiben. ES läuft ohne TLS.
- **Fix:** Die Ports von ES, Redis und Logstash komplett entfernen (die Dienste reden ohnehin über `radio-network`). Kibana nur als `127.0.0.1:5601:5601` oder hinter nginx. Bei den Logstash-Inputs `user`/`password` setzen und den CORS-Header entfernen.

### 🟠 S4 – Path Traversal und beliebige Dateien in `/aprs/decode` und `/pocsag/decode`
- **Dateien:** `blueprints/aprs.py:128ff`, `blueprints/pocsag.py:102ff`. `audio_file` geht ungeprüft an direwolf bzw. multimon-ng. `/transcribe` nutzt dagegen korrekt `validate_file_path`.
- **Fix:** `validate_file_path(data['audio_file'])` aus `api_service.py:556` auch hier verwenden. Ebenso ein Pfad-Check in `RepeaterActivityAnalyzer.analyze_iq_file`, falls dieser künftig von außen erreichbar wird.

### 🟠 S5 – Keine oder unvollständige Eingabevalidierung (DoS, Argument-Injection)
- `blueprints/capture.py:/capture`: Dauer unbegrenzt, keine Busy-Prüfung, synchron → blockiert einen Worker bis zu 660 s und belegt die SDR parallel zu laufenden Jobs.
- `blueprints/streaming.py`: In `/stream/aprs/start`, `/stream/pocsag/start` und `/stream-decode` werden `frequency`, `gain`, `sample_rate` und `duration` nicht typgeprüft. `device_address` landet ungefiltert in `--args=addr=…` (UHD-Arg-Injection, z. B. `1.2.3.4,fpga=/pfad`). `/stream/aprs|pocsag/start` prüfen außerdem **nicht**, ob die SDR belegt ist. `MAX_STREAMING_SESSIONS` und `STREAM_SESSION_TIMEOUT` aus `.env.example` werden nirgends verwendet.
- `blueprints/repeater.py`: `duration_per_repeater`, `sample_rate`, `gain` und `repeater_ids` sind unvalidiert.
- **Fix:** Ein zentrales Request-Schema mit **pydantic v2** (oder marshmallow) pro Endpoint, mit Grenzen aus `sdr_hardware.get_frequency_range()`. `device_address` per `ipaddress.ip_address()` validieren. Eine gemeinsame `ensure_sdr_free()`-Funktion für alle SDR-Endpoints.

### 🟠 S6 – Stored XSS per Funk (Over-the-Air-Injection)
- APRS- und POCSAG-Texte kommen von **beliebigen Sendern**. Die Tabellen escapen per `escHtml`, aber:
  - `frontend/src/modules/toast.js:21` setzt `message` ungefiltert per `innerHTML`. Server-Fehler (`str(e)`) und Nutzer-Labels fließen dort hinein.
  - `voice.js:stat()` gibt `transcription.language` unescaped aus.
  - `escHtml` ist in jedem Modul dupliziert und escapt keine Quotes. Das ist ein Risiko, sobald Werte in Attribute geschrieben werden, z. B. `id="multiPkt_${ch.label}"` in `multi.js:141`.
  - Die Kibana-Dashboards sind unkritisch, weil Kibana escapt.
- **Fix:** Ein zentrales `frontend/src/modules/dom.js` mit `esc()` (inkl. `"` und `'`) bzw. `textContent`. `toast()` nutzt `textContent`. Labels nicht in IDs verwenden (stattdessen `data-*` plus Index).

### 🟠 S7 – CORS komplett offen und keine Security-Header
- `api_service.py:90` `CORS(app)` erlaubt jede Origin. Zusammen mit S2 kann jede Webseite im Browser des Nutzers die SDR steuern (CSRF-ähnlich, weil keine Credentials nötig sind).
- **Fix:** `CORS(app, origins=os.getenv('CORS_ORIGINS','').split(','))`. Fällt bei Same-Origin über den nginx-Proxy ganz weg. In `monitoring/nginx/default.conf`: `Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`.

### 🟡 S8 – Weitere Härtungen
| Datei | Problem | Fix |
|---|---|---|
| `gunicorn_config.py:73` | `umask = 0` → Aufnahmen und JSON-Dateien sind world-writable | `umask = 0o027` |
| `Dockerfile:67` | `COPY .env.example .env` backt `changeme`-Defaults ins Image | entfernen, Defaults im Code |
| `.env.example` | `REDIS_PASSWORD` doppelt (`changeme` und leer) | nur ein Eintrag |
| `docker-compose.yml` metricbeat/filebeat | nutzen den Superuser `elastic` | eigene `beats_writer`-Rolle (das Secret `beats_password` existiert schon, wird aber nicht genutzt) |
| `docker-compose.yml:41` | ES-Healthcheck mit Passwort in der Kommandozeile (sichtbar in `docker inspect`) | `curl -u elastic:$$(cat /run/secrets/…)` oder einen unauthentifizierten Endpoint |
| `docker-compose.yml` redis healthcheck | `redis-cli ping` ohne `-a` → meldet „healthy" trotz NOAUTH | `redis-cli -a "$$REDIS_PASSWORD" ping \| grep PONG` |
| Docker Secrets | definiert, aber Passwörter laufen parallel per ENV | einheitlich: Secrets **oder** `.env.elk`, nicht beides |
| Alle Blueprints | `return jsonify({'error': str(e)}), 500` leakt Interna | generischer Fehlertext plus Correlation-ID, Details nur ins Log |
| `/list-recordings` | gibt absolute Serverpfade zurück | nur `filename` |
| `package.json` (Root) | Abhängigkeit `codex@^0.2.3`, nirgends genutzt (mögliches Typosquat-Paket) | Root-`package.json` und `package-lock.json` löschen |
| Container | kein `read_only`, `cap_drop`, `no-new-privileges` | `security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]` für nginx und API |
| CI | kein Dependency- oder Image-Scan | `pip-audit`, `npm audit`, `trivy image`, Dependabot (`.github/dependabot.yml`) |

## 2. Funktionen – was gut ist, was nicht

### ✅ Gut umgesetzt
- **Hardware-Abstraktion** (`sdr_hardware.py`): 4 SDR-Typen mit Auto-Detect und Frequenzbereich-Validierung in `get_sdr_instance`.
- **Asynchroner Capture-Flow** `/capture-and-transcribe` → `202` plus `capture_id` und Status in Redis mit TTL. Sauberes Polling-Modell.
- **Multi-Channel-DDC** (`MultiChannelStreamingDecoder`): durchdachte Validierung (Bandbreite, 50-kHz-Abstand, Kanal-Limits). Das beste Endpoint-Beispiel im Repo.
- **Structured Logging mit Correlation-ID** (`logging_config.py`) als gute Basis fürs ELK.
- **ILM-Policies, Index-Templates und Dashboards als Code** (`monitoring/elasticsearch`, `monitoring/kibana/dashboards`).
- Non-root-Container, Multi-Stage-Build, `subprocess` immer mit Listen-Argumenten (kein `shell=True`).
- Typisierung und mypy in der CI.

### ❌ Schwächen und Bugs
1. 🔴 **In-Process-State bei 5 Gunicorn-Workern** (`docker-compose.yml: GUNICORN_WORKERS=5`):
   - `_capture_busy` (threading.Event), `capture_thread_pool`, `scan_thread_pool` und die **Decoder-Registry** in `SessionManager` (`register_decoder`/`get_all_active_decoders`) existieren **pro Prozess**.
   - Folge: Die Busy-Prüfung greift nur, wenn der Request zufällig im selben Worker landet. Parallele Captures können um die SDR kämpfen. `DELETE /stream-decode/<id>` auf einem anderen Worker findet den Decoder nicht und fällt auf den **SIGKILL-pkill** aller SDR-Prozesse zurück. Der Cleanup-Thread läuft fünfmal.
   - **Fix (kurzfristig):** `GUNICORN_WORKERS=1` (gevent ist für I/O ohnehin konkurrent).
   - **Fix (sauber):** Eine SDR-Sperre in Redis (`SET sdr_lock <owner> NX EX`), Stop-Kommandos über Redis Pub/Sub. Oder die SDR-Arbeit in einen eigenen **Worker-Prozess** auslagern (z. B. RQ, Dramatiq oder ein kleiner „sdr-agent"-Service), der die Hardware exklusiv besitzt. Die API bleibt dann zustandslos.
2. 🟠 **gevent plus Threads, NumPy und Subprocesses**: `gevent`-Worker ohne explizites `monkey.patch_all()` im Zusammenspiel mit `ThreadPoolExecutor`, blockierendem NumPy-DSP und `subprocess.Popen` ist fehleranfällig. Wechsel auf `gthread`-Worker (`worker_class='gthread'`, `threads=8`), solange die SDR-Arbeit im API-Prozess läuft.
3. 🟠 **`MockRedis`-Fallback** (`streaming_decoder_service.py:34`): Ist Redis nicht erreichbar, wird stillschweigend im Speicher weitergearbeitet. Die Sessions gehen verloren und unterscheiden sich pro Worker. Besser: Fail-fast oder nur im Testmodus.
4. 🟠 **Doppelter Code**: Die drei Capture-Modi in `_capture_worker` (`api_service.py:374-553`) sind zu ca. 80 % identisch (Capture-Doc bauen, indexieren). Die Streaming-Start-Endpoints gibt es dreifach (`/stream/aprs/start`, `/stream/pocsag/start`, `/stream-decode`), ebenso `scan_session_manager` und `SessionManager` (zwei Redis-Session-Systeme). **Fix:** Eine Funktion `build_capture_doc()` und eine Decoder-Strategie pro Modus. Die Legacy-Stream-Endpoints deprecaten. Die Migration in Blueprints abschließen (`capture-and-transcribe`, `stats`, `captures` aus `api_service.py` herausziehen) und eine App-Factory (`create_app()`) einführen. Das beseitigt die zirkulären Imports.
5. 🟡 **`/captures/<int:capture_id>`** erwartet ein `int`, die Dokumente nutzen aber UUIDs → Der Endpoint findet praktisch nie etwas.
6. 🟡 **`/health`** prüft weder Redis noch ES noch die SDR. Ein `/health/ready` mit Abhängigkeiten ergänzen, Version aus einer zentralen Konstante (aktuell steht dort fest `2.0.0`, das README nennt v3.1.0).
7. 🟡 **Dead Code / Kommentare**: auskommentierte Prometheus-Blöcke, „Record Prometheus metrics" ohne Wirkung (`api_service.py:918-921`), ungenutzte Variablen (`capture_duration_seconds`, `transcription_duration_seconds`), `.env.example` mit N8N- und Postgres-Variablen, `archive/`, `scripts/legacy/`, `web_interface.html` (2275 Zeilen, alte UI) und `help.html` neben dem neuen Frontend.
8. 🟡 **Aufräumen der Aufnahmen**: WAV- und JSON-Dateien in `recordings/` werden nie gelöscht (nur IQ-Dateien beim Repeater-Scan). Eine Retention (z. B. `RECORDING_RETENTION_DAYS`) plus Disk-Space-Check vor dem Capture.
9. 🟡 **Tests**: `--cov-fail-under=15` ist sehr niedrig. Die Blueprints `streaming`, `repeater` und `aprs/pocsag decode` haben keine API-Tests für Fehlerpfade und Validierung. Ziel: 60 %, Security-Regressionstests für S2, S4 und S5.
10. 🟢 Zeitstempel sind gemischt (`datetime.now()` lokal vs. UTC) → überall UTC verwenden.

## 3. Vorschläge für neue Funktionen
Ergänzend zur bestehenden `ROADMAP.md` (API-Key-UI, WebSockets, APRS-Karte, Audio-Player, Dashboard, Wasserfall). Ich empfehle, diese zuerst umzusetzen. Die API-Key-UI erledigt sich durch F1 und Auth in nginx.

| # | Feature | Nutzen | Aufwand |
|---|---|---|---|
| N1 | **Server-Sent Events** statt WebSockets für Live-Pakete (`/stream-decode/<id>/events`, Redis Pub/Sub als Quelle) | einfacher als Socket.IO, passt zu Flask und nginx | M |
| N2 | **Scheduler / Zeitpläne** („jeden Tag 07:00–09:00 APRS 144.800") mit APScheduler und Redis-Jobstore | Unbeaufsichtigter Betrieb | M |
| N3 | **Alerts / Watchlists**: Benachrichtigung bei Callsign X, POCSAG-RIC Y, Schlüsselwort in der Transkription → ntfy, Telegram, Matrix, E-Mail, Webhook (ersetzt die verwaiste N8N-Integration) | hoher Praxisnutzen | M |
| N4 | **Frequenz-Bookmarks und Presets** in ES/Redis plus UI (statt `rtlsdr-example.conf`) | UX | S |
| N5 | **Squelch-/VOX-gesteuerte Voice-Aufnahme**: nur bei Träger aufnehmen und transkribieren (Analyzer existiert schon in `repeater_activity_analyzer.py`) | spart CPU und Speicher, ermöglicht Dauerbetrieb | M |
| N6 | **APRS-IS-iGate-Upload** (optional, mit Callsign und Passcode) und **APRS-Wetterstationen** als eigenes Panel | Community-Nutzen | M |
| N7 | **Weitere Decoder**: ADS-B (dump1090/readsb), AIS (AIS-catcher), rtl_433 (ISM-Sensoren), DMR/P25 (dsd-fme), NOAA/Meteor-APT | erweitert den Einsatzbereich stark | je M |
| N8 | **PPM- und Auto-Gain-Kalibrierung** (kalibrieren mit `kal` oder einem bekannten Träger) | Signalqualität | S–M |
| N9 | **Export** (CSV, GeoJSON, KML für APRS; WAV und Transkript als ZIP) | Auswertung | S |
| N10 | **Benutzer und Rollen** (Viewer darf nur lesen, Operator darf die SDR steuern) über nginx und oauth2-proxy oder Flask-Login | Mehrbenutzerbetrieb | M–L |
| N11 | **OpenAPI-Spezifikation und Swagger-UI** (z. B. via `flask-smorest` oder `spectree` zusammen mit pydantic aus S5) | ersetzt ca. 700 Zeilen API-Doku im README | M |
| N12 | **Whisper-Verbesserungen**: Modell `large-v3-turbo`, VAD-Filter (`vad_filter=True`), Batch-Pipeline, GPU-Profil in Compose (`deploy.resources.devices`) | Qualität und Tempo | S |
| N13 | **„Light"-Deployment-Profil** ohne ELK (SQLite oder OpenSearch-light, Compose-Profile `--profile elk`), denn ELK braucht ca. 5 GB RAM | Raspberry Pi / kleine Hosts | M |

## 4. README überarbeiten
**Ist-Zustand:** `README.md` hat **2306 Zeilen**. Es mischt Marketing-Feature-Liste, Changelog („Recent Updates"), RTL-SDR-Tutorial, vollständige API-Referenz, Kibana-Dev-Tools-Kurs, Secrets-Anleitung und Projektstruktur, dazu viele Emojis. Hinzu kommen `USER_MANUAL.md`, `docs/current/QUICKSTART.md`, `docs/README.md` und `help.html` mit Überschneidungen. Mehrere Aussagen sind veraltet (Versionen, Prometheus, Postgres, N8N).

**Ziel-Struktur** (README ≤ ca. 250 Zeilen, Rest in `docs/`):
```
README.md
  1. Titel + 1-Satz-Beschreibung + Screenshot + Badges (CI, License)
  2. Features (max. 8 Bullets, ohne Emojis)
  3. Unterstützte Hardware (Tabelle: Gerät | Frequenzbereich | Hinweise)
  4. Quick Start (Docker) – 5 Befehle: clone → setup-secrets → up → post-setup → Browser
  5. Architektur (1 Diagramm, Mermaid)
  6. Weiterführende Doku (Linkliste)
  7. Rechtlicher Hinweis (Empfang/Fernmeldegeheimnis, kurz)
  8. License

docs/
  installation.md      (Docker + manuell, Systemvoraussetzungen)
  configuration.md     (ENV-Tabelle, generiert aus .env.example)
  hardware.md          (RTL-SDR/HackRF/Airspy/USRP Setup, PPM, Troubleshooting)
  usage.md             (Web-UI, die 5 Modi, Frequenzbeispiele)
  api.md               (oder: Link auf /api/docs aus N11)
  security.md          (Secrets, API-Keys, Netz-Exposition – nach S1–S8 aktualisiert)
  elk.md               (Kibana-Dashboards, ILM, Dev-Tools-Beispiele, Backup)
  development.md       (Tests, mypy, CI, Projektstruktur)
CHANGELOG.md           ("Recent Updates" aus README → Keep-a-Changelog-Format)
```
- `USER_MANUAL.md` (deutsch) als `docs/de/benutzerhandbuch.md` behalten oder die Inhalte in `usage.md` zusammenführen. Eine Sprache konsequent wählen.
- `docs/archive/*`, `logs/archive/*`, `docs/current/FINAL_SUMMARY_*`/`TEST_REPORT_*`: aus dem Repo entfernen (die Git-Historie reicht) oder klar unter `docs/archive/` lassen und nicht verlinken.
- Optional: **MkDocs Material** und GitHub Pages für die `docs/`.

## 5. Front-End modernisieren
**Ist-Zustand:** Vite 5, Tailwind 3, Vanilla-ES-Module (ca. 1500 Zeilen JS), eine `index.html` mit 561 Zeilen und dem Markup aller Tabs. `API_BASE_URL = 'http://localhost:5000'` ist hart codiert, deshalb funktioniert die UI **nur auf dem Host selbst**. `frontend/dist` ist eingecheckt. Polling per `setInterval`, `escHtml` mehrfach dupliziert, `alert()` in `api.js`.

**Empfohlene Schritte** (inkrementell, ohne Big-Bang):
1. **F1 – Same-Origin-API über nginx** 🔴 (zugleich der Sicherheitsfix S2/S3/S7):
   `monitoring/nginx/default.conf`: `location /api/ { proxy_pass http://radio-api:5000/; proxy_read_timeout 700s; }` plus SSE-Settings (`proxy_buffering off`). In `api.js`: `API_BASE_URL = import.meta.env.VITE_API_BASE ?? '/api'`. Port 5000 nicht mehr publishen.
2. **F2 – Build im Container** statt eingechecktem `dist/`: ein Multi-Stage-`frontend/Dockerfile` (`node:22-alpine` build → `nginx:alpine`). `frontend/dist` in `.gitignore`.
3. **F3 – Tooling-Upgrade**: Vite 5 → **8**, Tailwind 3 → **4** (`@tailwindcss/vite` ≥ 4.2.2, CSS-first-Config mit `@theme`; `tailwind.config.js`, `postcss.config.js` und `autoprefixer` entfallen; Migration per `npx @tailwindcss/upgrade`). Lucide aktualisieren.
4. **F4 – Framework-Entscheidung**: Bei ca. 1500 Zeilen ist ein leichtes reaktives Framework sinnvoll. Empfehlung: **Svelte 5** (oder Vue 3), mit TypeScript, eine Komponente pro Tab, ein `api.ts` mit typisierten Responses und einem zentralen Store für SDR-Status und aktive Session. Alternative ohne Rewrite: **Alpine.js** oder **htmx** auf das bestehende Markup setzen.
5. **F5 – UX**:
   - globaler **SDR-Status-Indikator** (frei/belegt, welcher Modus), statt dass Fehler erst als 409 auffallen
   - Live-Updates per SSE (N1)
   - APRS-Karte mit **MapLibre GL** oder Leaflet (ROADMAP 2c)
   - Audio-Player mit **wavesurfer.js** (ROADMAP 3a)
   - Mobile Drawer mit Backdrop (ROADMAP Stufe 1)
   - Light/Dark-Umschaltung, `prefers-reduced-motion`
   - Barrierefreiheit: Fokus-Stile, `aria-live` für Toasts, Labels an allen Inputs
   - Formular-Validierung clientseitig (Frequenzbereich je Gerät aus `/sdr/detect`)
   - `alert()` durch Toasts oder Inline-Fehler ersetzen
6. **F6 – Qualität**: ESLint und Prettier, **Vitest** für `api`/Utilities, **Playwright**-Smoke-Test in der CI (UI lädt, Tab-Wechsel, Mock-API).

## 6. Updates der COTS-Komponenten
Stand der Recherche: 16.10.2026. Bei Werten mit „~" konnte ich die exakte Patch-Version nicht verifizieren. Vor dem Pinnen bitte mit `pip index versions <pkg>`, `npm view <pkg> version` bzw. Docker Hub gegenprüfen.

### Container-Images
| Komponente | Aktuell | Verfügbar | Hinweise |
|---|---|---|---|
| Elasticsearch / Logstash / Kibana / Metricbeat / Filebeat | **8.11.3** (Dez. 2023) | **9.4.x** (~9.4.3); LTS-Linie **8.19.x** | 8.11 ist nicht mehr supported. ROADMAP plant 9.3.3 → direkt auf 9.4.x. Pfad: 8.11 → **8.19** (Upgrade Assistant, Deprecations prüfen) → 9.x. Ein Major-Sprung erfordert ein Zwischen-Upgrade auf 8.19. |
| Redis | `redis:7-alpine` | **8.x** (~8.10) | Redis 8 hat wieder eine OSS-Lizenz (AGPLv3, zusätzlich RSAL/SSPL). Alternativ **Valkey 8/9** (BSD) als Drop-in. Tag pinnen (`redis:8.x-alpine`). |
| nginx | `nginx:alpine` (unpinned) | stable **1.30.x**, mainline **1.31.x** | auf `nginx:1.30-alpine` pinnen; 2026 gab es mehrere Security-Releases. |
| Python-Base | `python:3.11-slim` (bookworm) | **3.13** / **3.14** (3.14.8, Sep. 2026) | 3.11 erhält nur noch Security-Fixes (EOL 10/2027). Empfehlung: `python:3.13-slim-trixie` (Debian 13, neuere direwolf-, multimon-ng- und uhd-Pakete). Erfordert numpy ≥ 2.x. |
| direwolf / multimon-ng / hackrf / rtl-sdr / uhd | Debian-bookworm-Pakete | neuere Versionen in trixie | Mit dem Base-Image-Wechsel automatisch. rtl-sdr-blog-Treiber für RTL-SDR v4 prüfen. |

### Python (`requirements.txt`)
| Paket | Aktuell | Verfügbar (ca.) | Hinweise |
|---|---|---|---|
| gunicorn | 21.2.0 | **26.x** | 🔴 21.2 hat bekannte Request-Smuggling-CVEs (CVE-2024-1135, CVE-2024-6827), gefixt ab 22.0/23.0 |
| flask | 3.0.0 | **3.1.3+** | |
| flask-cors | 6.0.0 | 6.x | ok |
| gevent | 24.2.1 | 25.x | entfällt evtl. (gthread, siehe Funktionen Punkt 2) |
| faster-whisper | 1.0.3 | **1.2.x** | unterstützt `large-v3-turbo`, bessere VAD |
| numpy | 1.24.3 | **2.x** | Pflicht für Python ≥ 3.12; die DSP-Code-Pfade testen (dtype-Promotion NEP 50) |
| scipy | 1.11.4 | **1.16+** | |
| elasticsearch (py) | 8.11.0 | **9.x** (muss zur Server-Major passen) | |
| redis (py) | 5.0.1 | **6.x / 7.x** | |
| requests | 2.32.4 | 2.32.x latest | |
| psutil | 5.9.8 | **7.x** | |
| python-dotenv | 1.0.0 | 1.1+ | |
| python-json-logger | 2.0.7 | **3.x** | Import-Pfad geändert (`pythonjsonlogger.json`) |
| beautifulsoup4 | 4.12.3 | 4.13+ | prüfen, ob überhaupt genutzt (sonst entfernen) |
| pyHackRF | 0.2.0 | unmaintained | prüfen, ob genutzt; die Captures laufen über `hackrf_transfer` |
| mypy / pytest / pytest-cov / coverage | 1.11 / 8.3 / 6.0 / 7.6 | aktuelle Minor-Versionen | **Dev-Deps in `requirements-dev.txt` auslagern**, damit sie nicht ins Produktions-Image kommen |
| `types-Flask-Cors` | ungepinnt | – | pinnen oder entfernen |

### Frontend (`frontend/package.json`)
| Paket | Aktuell | Verfügbar |
|---|---|---|
| vite | ^5.4.19 | **8.x** (seit 12.03.2026) |
| tailwindcss | ^3.4.17 | **4.3.x** (+ `@tailwindcss/vite`) |
| postcss / autoprefixer | ^8.5 / ^10.4 | entfallen mit Tailwind 4 |
| lucide | ^0.511.0 | aktuelle 0.5xx/1.x – per `npm view lucide version` |

### Empfohlene Upgrade-Reihenfolge
1. Gunicorn, Flask, Redis-Image und nginx-Image pinnen und updaten (geringes Risiko, Security-Gewinn).
2. Base-Image auf Python 3.13 plus numpy 2, scipy und faster-whisper (Tests laufen lassen, DSP-Ausgaben vergleichen).
3. ELK 8.11 → 8.19 → 9.4, elasticsearch-py synchron (Snapshot vorher; `discovery.type`-Hinweis aus der ROADMAP beachten).
4. Frontend Vite 8 und Tailwind 4 (zusammen mit F1/F2).
5. Dependabot einrichten, damit das nicht wieder 3 Jahre liegen bleibt.

## 7. Umsetzungsreihenfolge (Gesamtübersicht)
1. **Sofort (½ Tag):** S1 (Rotation + History), S3 (Ports schließen), Workaround `GUNICORN_WORKERS=1`, gunicorn-Update.
2. **Woche 1:** F1 (nginx-Proxy) zusammen mit S2/S7, S4, S6, S8-Kleinkram, Altlasten löschen.
3. **Woche 2:** S5 (pydantic-Schemas), App-Factory und Refactor `_capture_worker`, Redis-SDR-Lock, Tests auf 60 %.
4. **Woche 3:** Stack-Updates (Abschnitt 6), README-Restrukturierung (Abschnitt 4).
5. **Danach:** Frontend F2–F6 und neue Features (N1, N3, N5 zuerst).

Quellen der Versionsrecherche: [isitpatched – Elasticsearch](https://www.isitpatched.com/elasticsearch), [releasealert.dev – redis](https://releasealert.dev/dockerhub/_/redis), [Tailwind/Vite 8 Diskussion](https://github.com/tailwindlabs/tailwindcss/discussions/19624), [endoflife.date – Tailwind](https://endoflife.date/tailwind-css), [piwheels – faster-whisper](https://www.piwheels.org/project/faster-whisper), [CERN PyPI mirror – gunicorn](https://simple-repository.app.cern.ch/project/gunicorn), [versio.io – gunicorn](https://www.versio.io/de/product-release-end-of-life-eol-benoit-chesneau-gunicorn.html), [depscope – Flask](https://depscope.dev/pkg/pypi/Flask), [nginx news 2026](https://nginx.org/2026.html), [Python 3.14.8](https://www.python.org/downloads/release/python-3148/).

