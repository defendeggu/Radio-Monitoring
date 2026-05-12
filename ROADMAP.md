# RadioMoni — Roadmap & Offene Punkte

Stand: 2026-05-12 (nach v3.1.0 UI-Modernisierung)

---

## Stufe 1 — Visuelles Design & Layout ✅ Abgeschlossen

Alle Punkte in v3.1.0 umgesetzt:
- Collapsible Sidebar (w-60 / w-16, localStorage-Persistenz)
- Dark Theme (Slate-950 / Slate-900 / Glassmorphism-Cards)
- Inter + JetBrains Mono, Lucide SVG-Icons (keine Emojis mehr)
- Progress-Bars für Voice-, APRS- und POCSAG-Captures
- Toast-Notifications (top-right, auto-dismiss)
- Responsive Breakpoints (`sm:` / `md:`)

**Teilweise offen:**
- Mobiler Sidebar-Drawer: Hamburger-Button funktioniert, aber kein dunkles
  Backdrop-Overlay hinter der Sidebar und kein Click-outside-to-close.
  Fix: `#sidebar` auf `fixed z-40` setzen + `#mobile-overlay` Div hinzufügen
  (`frontend/index.html`, `frontend/src/style.css`, `frontend/src/modules/sidebar.js`)

---

## Stufe 2 — UX & Interaktivität (offen)

### 2a. API-Key-Eingabe im UI ❌
**Problem:** `api.js` liest `localStorage.getItem('api_key')`, aber es gibt kein
UI-Feld zum Setzen des Keys. Nutzer müssen aktuell Browser-DevTools verwenden.

**Plan:**
- Einstellungs-Icon (Lucide `Settings`) in der Sidebar-Footer
- Klick öffnet ein Modal mit einem `<input type="password">` für den API-Key
- Speichern via `localStorage.setItem('api_key', value)` + Toast-Bestätigung
- Betroffene Dateien: `frontend/index.html`, `frontend/src/modules/sidebar.js`
  (oder neues `frontend/src/modules/settings.js`)

---

### 2b. WebSockets statt Polling ❌
**Problem:** Status-Updates laufen aktuell über `setInterval` (2s-Polling auf
`/capture-status/` und `/stream-decode/<id>`). Das erzeugt unnötige Last und
verzögert Echtzeit-Feedback.

**Plan:**
- Backend: Flask-SocketIO einführen, Events emittieren bei Statusänderung,
  neuem APRS/POCSAG-Paket, Transkriptionsergebnis
- Frontend: `socket.io-client` in `api.js` integrieren, `setInterval`-Polling
  durch Event-Handler ersetzen
- Betrifft: `api_service.py`, `blueprints/streaming.py`,
  `frontend/src/modules/polling.js`, `aprs.js`, `pocsag.js`

---

### 2c. Interaktive APRS-Karte ❌
**Problem:** APRS-Pakete mit Koordinaten werden nur in einer Tabelle angezeigt.

**Plan:**
- Leaflet.js oder MapLibre GL JS als Dependency
- Karten-Container im APRS-Tab unterhalb der Paket-Tabelle
- Marker bei jedem Paket mit Koordinaten setzen; Klick zeigt Callsign + Message
- Betroffene Dateien: `frontend/index.html`, `frontend/src/modules/aprs.js`,
  `frontend/package.json`

---

## Stufe 3 — Technische Features / "Pro" (offen)

### 3a. Audio-Player (Wavesurfer.js) ❌
**Problem:** Transkriptions-Ergebnisse zeigen nur Text. Die zugehörige
Audiodatei kann nicht direkt im Browser abgespielt werden.

**Plan:**
- Wavesurfer.js als Dependency
- Nach einer erfolgreichen Voice-Transkription: Waveform-Player unterhalb
  des Transkriptionstexts einblenden
- API muss die Aufnahmedatei als `/recordings/<filename>` ausliefern
  (nginx-Location oder Flask-Route)
- Betroffene Dateien: `frontend/src/modules/voice.js`, `frontend/index.html`,
  `monitoring/nginx/default.conf` oder `blueprints/capture.py`

---

### 3b. Dashboard-Startseite (Elasticsearch-Aggregationen) ❌
**Problem:** Es gibt keine Übersichtsseite mit Kennzahlen (Captures heute,
letzte APRS-Aktivität, System-Last etc.).

**Plan:**
- Neuer Tab "Dashboard" in der Sidebar (Lucide `LayoutDashboard`-Icon)
- Stat-Cards: Captures (24h), APRS-Pakete (24h), POCSAG-Messages (24h),
  letzte Aktivität
- Daten aus Elasticsearch via neuer Flask-Route `/dashboard/stats`
  (Aggregationen auf bestehenden Indizes `aprs-packets`, `pocsag-messages`,
  `voice-transcriptions`)
- Betroffene Dateien: `blueprints/` (neues `dashboard.py`), `api_service.py`,
  `frontend/index.html`, neues `frontend/src/modules/dashboard.js`

---

### 3c. Spektrum-Wasserfall (WebGL) ❌
**Problem:** Kein visuelles Feedback über das Funksignal vor/während einer
Aufnahme.

**Plan:**
- WebGL-basierter Wasserfall (z.B. via `wf.js` oder eigen implementiert mit
  `<canvas>`)
- API: Neuer Streaming-Endpoint `/sdr/spectrum` (SSE oder WebSocket), der
  FFT-Daten aus einem kurzen SDR-Sample liefert
- Nur verfügbar wenn kein anderer Capture aktiv (SDR ist belegt)
- Hoher Aufwand — sinnvoll erst nach 2b (WebSockets) umsetzen
- Betroffene Dateien: neue `blueprints/spectrum.py`, `api_service.py`,
  `frontend/index.html`, neues `frontend/src/modules/spectrum.js`

---

---

## Infrastruktur: ELK Stack 8.11.3 → 9.3.3

### Aktueller Stand

Alle fünf ELK-Komponenten laufen auf **8.11.3**:

| Komponente | Aktuell | Ziel |
|------------|---------|------|
| Elasticsearch | 8.11.3 | 9.3.3 |
| Logstash | 8.11.3 | 9.3.3 |
| Kibana | 8.11.3 | 9.3.3 |
| Metricbeat | 8.11.3 | 9.3.3 |
| Filebeat | 8.11.3 | 9.3.3 |
| elasticsearch-py (Python) | 8.11.0 | 9.x |

**Upgrade möglich? Ja** — mit einigen gezielten Anpassungen (kein Rewrite nötig).
Der grösste Teil der Konfiguration ist direkt kompatibel.

---

### Was ist kompatibel (kein Handlungsbedarf)

- Alle Python API-Calls (`search`, `count`, `index`, `get`, `cluster.health`) — stabil seit 7.x
- ILM-Policy-Format (hot/warm/cold/delete) — unverändert
- Index-Template-Format und alle Mappings (geo_point, nested, keyword) — unverändert
- Logstash-Pipeline-Syntax (date, mutate, ruby, uuid, prune) — stabil seit 6.x
- Kibana NDJSON-Dashboard-Format — cross-version kompatibel
- Alle Logstash HTTP-Input-Pipelines (Ports 9600–9605) — unverändert
- Security-Modell (Rollen, Users, Passwörter) — unverändert
- `xpack.security.http.ssl.enabled: false` — weiterhin unterstützt (single-node, intern)

---

### Breaking Changes & erforderliche Anpassungen

#### 1. `discovery.type: single-node` deprecated → `cluster.initial_master_nodes`
**Risiko:** Mittel — ES 9.x gibt Warning; in 9.x+ startet ES ggf. nicht mehr  
**Fix:** In `docker-compose.yml` (elasticsearch environment):
```yaml
# Ersetzen:
- discovery.type=single-node
# Durch:
- cluster.initial_master_nodes=elasticsearch
- discovery.seed_hosts=[]
```

#### 2. `elasticsearch-py` Library auf 9.x bumpen
**Risiko:** Niedrig — alle verwendeten Methoden sind stabil; aber Versionsmismatch erzeugt Deprecation-Warnings  
**Fix:** `requirements.txt`:
```
# Ändern:
elasticsearch==8.11.0
# Auf:
elasticsearch>=9.0.0,<10.0.0
```
Danach alle Search-Calls und Aggregationen einmal testen (regression-check).

#### 3. `setup-elk-users.sh` — Metricbeat-Template-Mutation prüfen
**Risiko:** Mittel — Script liest `_index_template/metricbeat` per GET und schreibt ILM-Policy zurück per PUT; in 9.x ändert Metricbeat eventuell das Template-Schema  
**Fix:** Script nach dem Upgrade einmal manuell ausführen und prüfen ob der PUT-Request erfolgreich ist. Fallback: ILM direkt am Metricbeat-Index über Kibana setzen.

#### 4. Image-Tags in `docker-compose.yml` aktualisieren
**Aufwand:** 5 Zeilen ändern  
**Dateien:** `docker-compose.yml` — alle 5 Dienste:
```yaml
image: docker.elastic.co/elasticsearch/elasticsearch:9.3.3
image: docker.elastic.co/logstash/logstash:9.3.3
image: docker.elastic.co/kibana/kibana:9.3.3
image: docker.elastic.co/beats/metricbeat:9.3.3
image: docker.elastic.co/beats/filebeat:9.3.3
```

---

### Empfohlene Upgrade-Reihenfolge

1. **Datensicherung:** Elasticsearch-Snapshot erstellen (oder Stack kurz herunterfahren — kein Prod-System)
2. **`docker-compose.yml`** — Image-Tags auf 9.3.3 setzen + `discovery.type` ersetzen
3. **`requirements.txt`** — `elasticsearch==9.x` setzen
4. **`docker compose build radio-api`** — Python-Image neu bauen
5. **`docker compose up -d`** — Stack hochfahren
6. **`scripts/post-docker-setup.sh`** neu ausführen — ILM-Policies, Index-Templates, Users neu anlegen (idempotent)
7. **Metricbeat-Template** prüfen (`setup-elk-users.sh` testen)
8. Kibana öffnen → Index Patterns prüfen → Dashboards verifizieren

**Gesamtaufwand:** ~2–3 Stunden (inkl. Test)  
**Downtime:** Einmaliger Neustart des gesamten Stacks (~2–5 Minuten)

---

### Betroffene Dateien

| Datei | Änderung |
|-------|---------|
| `docker-compose.yml` | 5× Image-Tag + `discovery.type` ersetzen |
| `requirements.txt` | `elasticsearch==8.11.0` → `>=9.0.0,<10.0.0` |
| `scripts/post-docker-setup.sh` | Erneut ausführen (kein Code-Change nötig) |
| `scripts/setup-elk-users.sh` | Nach Upgrade manuell testen |

---

## Priorisierung (Empfehlung)

| Priorität | Feature | Aufwand | Nutzen |
|-----------|---------|---------|--------|
| 1 | API-Key-UI (2a) | Klein (1–2h) | Hoch — nötig für Docker-Auth |
| 2 | ELK 8.11.3 → 9.3.3 Upgrade | Mittel (2–3h) | Hoch — Security & Features |
| 3 | Mobile Drawer Backdrop | Klein (30min) | Mittel — UX-Polishing |
| 4 | APRS-Karte (2c) | Mittel (4–6h) | Hoch — visuell beeindruckend |
| 5 | Audio-Player (3a) | Mittel (3–4h) | Mittel — komfortabel |
| 6 | Dashboard (3b) | Gross (1–2 Tage) | Hoch — professionell |
| 7 | WebSockets (2b) | Gross (1–2 Tage) | Mittel — nice-to-have |
| 8 | Wasserfall (3c) | Sehr gross (3–5 Tage) | Hoch — Killer-Feature |
