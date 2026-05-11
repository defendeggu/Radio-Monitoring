# Radio Monitoring System - Benutzerhandbuch

Einfache Anleitung für die Bedienung des Radio-Monitoring-Systems.

---

## 📻 Was kann das System?

- **Voice Transcription**: Sprache von Radiosendern in Text umwandeln
- **APRS Decoding**: Digitale Funkpakete von Amateurfunkern empfangen und anzeigen
- **POCSAG Decoding**: Pager-Nachrichten dekodieren
- **Repeater Activity Monitoring**: Schweizer FM-Repeater auf Aktivität überwachen
- **Multi-Channel DDC** *(USRP N200)*: Einen breiten IQ-Datenstrom einmal erfassen und gleichzeitig 2–8 APRS/POCSAG-Kanäle per Software-Digital-Downconversion dekodieren
- **Datenanalyse**: Alle Aufnahmen durchsuchen und visualisieren

---

## 🆕 Neueste Updates

### Mai 2026

**Multi-Channel DDC für USRP N200 (11.05.2026)**
- Neuer Tab **📡📡 Multi-Channel (USRP)** im Web-Interface — erscheint nur wenn "USRP N200 (Ethernet)" im globalen SDR-Gerätewähler ausgewählt ist
- Ermöglicht das simultane Dekodieren von 2–8 APRS/POCSAG-Kanälen aus einem einzigen Breitband-IQ-Datenstrom des USRP N200 (bis zu 25 MS/s)
- Neuer API-Endpunkt `POST /stream/multi/start`
- Jedes dekodierte Paket enthält ein `channel_label`-Feld in Elasticsearch

### März 2026

**Kibana Performance (24.03.2026)**
- Node.js Heap von ~1.5 GB auf 2 GB erhöht → weniger GC-Pausen bei grossen Dashboard-Queries
- ES-Request-Timeout auf 90s erhöht → Aggregationen brechen nicht mehr ab
- HTTP-Komprimierung aktiviert → schnellere Übertragung zum Browser

**Chronologische Listen in Dashboards (24.03.2026)**
- **Logs-Dashboard**: Neues Panel ganz unten — letzte 100 Container-Logs chronologisch (Container, Stream, Meldung), blätterbar
- **POCSAG-Dashboard**: Neues Panel ganz unten — letzte 100 POCSAG-Meldungen chronologisch (Adresse, Typ, Baud, Text, Frequenz), blätterbar
- POCSAG "Message Types" Pie-Chart Fehlermeldung behoben: `message_type` → `message_type.keyword`

**7-Tage Log-Retention (24.03.2026)**
- Container-Logs (`radio-logs-*`) und Metricbeat-Metriken (`metricbeat-*`) werden automatisch nach **7 Tagen** gelöscht
- Radio-Daten (APRS, POCSAG, Voice, etc.) behalten die bestehende 90-Tage-Aufbewahrung

**Kibana-Dashboard-Fix: Alle Panels leer (24.03.2026)**
- Alle 48 Visualisierungen in 7 Dashboards hatten kein `indexRefName` im `searchSourceJSON` → Kibana konnte die Index-Pattern-Referenz nicht auflösen → leere Panels. Behoben in allen Dashboard-Dateien.
- Logs-Dashboard: `container.name` und `stream` durch `.keyword`-Felder ersetzt (Elasticsearch `terms`-Aggregationen benötigen Keyword-Felder)

**Bugfixes Web-Interface & Kibana-Import (24.03.2026)**
- `/help`-Seite gab 404 → behoben durch nginx-Konfiguration mit `.html`-Fallback
- Kibana-Dashboard-Import ignorierte Fehler still → behoben, alle Dashboards werden jetzt vollständig importiert

**Hilfe-Button, Filebeat & neue Kibana-Dashboards (24.03.2026)**
- **❓ Hilfe-Button** oben rechts im Web-Interface: öffnet das Benutzerhandbuch als gerenderte Webseite in einem neuen Tab
- **Filebeat** sammelt Logs aller Docker-Container (API, Elasticsearch, Logstash, Kibana, etc.) und speichert sie in `radio-logs-*` in Elasticsearch
- **Stack Health Dashboard** in Kibana: CPU/Memory-Timeline pro Container, Container-Status, Healthcheck-Status, Ressourcen-Übersichtstabelle
- **Stack Logs Dashboard** in Kibana: Log-Volumen, Timeline, stdout/stderr-Split, Container-Übersicht

**Stop-Buttons & HackRF Streaming-Fixes (24.03.2026)**
- **Stop-Button** in allen Web-Interface-Modulen (Voice, APRS, POCSAG): Jeder Button stoppt sofort den laufenden Task und gibt den HackRF frei
- HackRF USB-Stall nach ~6 Sekunden behoben: Multi-Stage-Dezimierung statt langsamer FFT-Resampling; `nice -n 10` Prioritätsdrosselung entfernt
- FM-Demodulations-Gain korrigiert: Audio-Pegel stieg von 0,45 % auf 96 % Vollaussteuerung → POCSAG/APRS-Pakete werden jetzt korrekt dekodiert
- Neuer Notfall-Endpunkt `POST /sdr/force-stop` stoppt alle laufenden SDR-Prozesse auf einmal
- POCSAG-Sessions laufen jetzt die volle konfigurierte Dauer (bis zu 3600s)

**Installations-Bugfixes (24.03.2026)**
- `session_store.py` und `maidenhead_grid.py` fehlten im Dockerfile → behoben
- `mqtt-bridge` Build-Kontext falsch konfiguriert → behoben
- `setup-elk-security.sh` schrieb `.env.elk` ins falsche Verzeichnis → behoben
- `setup-elk-security.sh` erstellt jetzt zusätzlich `.env` für Docker Compose Variable-Interpolation
- `setup-elk-users.sh` legt nun `logstash_writer`-Role und -User in Elasticsearch an (fehlte komplett)
- `post-docker-setup.sh` ruft User-Setup automatisch auf und startet Logstash/Metricbeat neu
- Logstash: `restart: on-failure` hinzugefügt (erholt sich automatisch nach User-Erstellung)

**Automatische IQ-Korrektur für HackRF**
- Softwareseitige DC-Offset-Entfernung, Amplituden- und Phasen-Imbalance-Korrektur für alle HackRF-Captures

**Projekt-Cleanup & Sicherheitshärtung**
- Alle toten Code-Bereiche entfernt (N8N, Grafana, PostgreSQL-Skripte)
- Kibana Encryption Key und Redis-Passwort werden jetzt von `setup-elk-security.sh` generiert
- 20 CI-Test-Fehler behoben (Streaming Decoder, SDR Hardware, Repeater Scanning)
- Branch von `fork-rtlsdr-elk` auf `main` umbenannt

### Januar 2026

**Duration Bug behoben (20.01.2026)**
- Streaming-Decoder-Sessions (APRS/POCSAG) beenden sich jetzt korrekt nach der konfigurierten Zeit
- Sessions bleiben nicht mehr im "running"-Status hängen

**RTL-SDR Erkennung verbessert (20.01.2026)**
- RTL-SDR Geräte werden nun auf allen Systemen zuverlässig erkannt
- Unicode-Fehler bei der Hardware-Erkennung behoben

**Docker Secrets implementiert (20.01.2026)**
- Produktionsreife Verwaltung von Passwörtern und Zugangsdaten
- Alle sensiblen Daten sind in separaten Dateien mit eingeschränkten Berechtigungen

### 📖 Weitere Informationen

Detaillierte technische Dokumentation unter `docs/current/` und `README.md`.

---

## 🔐 Sicherheit & API-Keys

### Was sind API-Keys?

Das System verwendet **API-Key-Authentifizierung** zum Schutz der API. Alle API-Zugriffe (außer `/health`) benötigen einen gültigen API-Key im `X-API-Key` Header.

### Warum API-Keys?

- **Zugriffskontrolle**: Verhindert unbefugten Zugriff auf dein Radio-Monitoring-System
- **Mehrere Keys**: Separate Keys für verschiedene Integrationen (N8N, Scripts, etc.)
- **Widerrufbar**: Kompromittierte Keys können deaktiviert werden

### API-Keys einrichten

**Automatisch (Empfohlen):**

Das Setup-Script generiert automatisch API-Keys:
```bash
./setup.sh
```

Das Script:
1. Generiert zwei sichere API-Keys (32-Byte Zufallstoken)
2. Fügt sie zur `.env` Datei hinzu als `API_KEYS=key1,key2`
3. Zeigt dir die Keys zum Speichern an

**⚠️ WICHTIG:** Speichere deine API-Keys in einem Passwort-Manager! Du brauchst sie für alle API-Anfragen.

**Manuell:**

API-Keys manuell generieren:
```bash
python3 scripts/generate_api_keys.py
```

Die Ausgabe zur `.env` Datei hinzufügen:
```bash
# API Security
API_KEYS=dein-key-1,dein-key-2
```

### API-Keys verwenden

**Im Web-Interface:**
- Keine API-Keys nötig! Das Web-Interface (http://localhost:8080) funktioniert direkt

**In curl/API-Aufrufen:**
```bash
curl -X POST http://localhost:5000/capture \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dein-api-key-hier" \
  -d '{...}'
```

### Container-Sicherheit

Der Docker-Container läuft als **nicht-root User** (`radiouser`, UID 1000):
- Minimale Berechtigungen
- USB-Zugriff durch Gruppenmitgliedschaft (plugdev, dialout)
- Automatisch konfiguriert, keine Benutzeraktion nötig

### Öffentliche Endpoints

Der folgende Endpoint benötigt **keine** Authentifizierung:
- `GET /health` - Health Check für Monitoring

Alle anderen Endpoints benötigen einen gültigen API-Key.

---

## 🚀 System Starten

### Erstinstallation (einmalig)

```bash
# 1. Repository klonen
git clone https://github.com/defendeggu/Radio-Monitoring
cd Radio-Monitoring

# 2. ELK-Zugangsdaten generieren (erzeugt .env.elk und .env)
./scripts/setup-elk-security.sh

# 3. Stack starten
docker compose up -d

# 4. Elasticsearch-User einrichten + Kibana-Dashboards importieren
./scripts/post-docker-setup.sh
```

> **Wichtig:** Schritt 4 (`post-docker-setup.sh`) ist bei der Erstinstallation zwingend erforderlich. Er legt den `logstash_writer`-User in Elasticsearch an, ohne den Logstash nicht starten kann.

### Normaler Start (nach Erstinstallation)

```bash
cd Radio-Monitoring
docker compose up -d
```

**Wichtige URLs:**
- **Web-Interface**: http://localhost:8080 (Hauptsteuerung)
- **Kibana**: http://localhost:5601 (Dashboards & Visualisierung)
  - Login: `elastic` / Passwort aus `.env.elk` (Variable `ELASTIC_PASSWORD`)
- **Elasticsearch**: http://localhost:9200 (Datenbank API)
- **Dockge**: http://localhost:5001 (Stack-Verwaltung)

---

## 🎛️ Web Interface Bedienung

### Hilfe-Button

Oben rechts im Header befindet sich der **❓ Hilfe**-Button. Ein Klick darauf öffnet dieses Benutzerhandbuch als gerenderte Webseite in einem neuen Tab — jederzeit verfügbar, ohne den laufenden Betrieb zu unterbrechen.

### SDR-Gerätewähler

Oben, oberhalb der Tabs, befindet sich der **globale SDR-Gerätewähler** — er gilt für alle Tabs:

- **Auto-Erkennung** (Standard): Das System wählt automatisch das erste erkannte Gerät
- **HackRF One / RTL-SDR / Airspy HF+**: Erzwingt ein bestimmtes USB-SDR
- **USRP N200 (Ethernet)**: Aktiviert das IP-Adressfeld und schaltet den Multi-Channel-Tab frei

Bei Auswahl von "USRP N200 (Ethernet)" erscheint ein Eingabefeld für die IP-Adresse (z.B. `192.168.10.2`). Die Einstellungen werden im Browser-Speicher gespeichert.

### Tabs oben

Das Web-Interface hat 4 feste Tabs (und einen 5. für USRP N200):
- **🎤 Voice Transcription** - Sprache aufnehmen und transkribieren
- **📡 APRS** - APRS-Pakete empfangen
- **📟 POCSAG** - Pager-Nachrichten empfangen
- **📻 Repeater Scan** - FM-Repeater-Aktivität überwachen
- **📡📡 Multi-Channel (USRP)** - Mehrere Kanäle gleichzeitig dekodieren *(nur sichtbar bei USRP N200-Auswahl)*

### Voice Transcription verwenden

1. **Klicke auf den Tab "Voice Transcription"**

2. **Wähle eine Frequenz:**
   - **Preset-Button klicken** (z.B. "FM Radio" für 88.5 MHz) ODER
   - **Manuell eingeben** im Feld "Frequency (Hz)"

3. **Einstellungen prüfen:**
   - **Modulation**: FM für UKW-Radio, AM für Flugfunk
   - **Duration**: 30 Sekunden ist ein guter Start
   - **RF Gain**: 20 dB standardmäßig (erhöhen bei schwachem Signal)
   - **Language**: Leer lassen für Auto-Erkennung, oder "de", "en", etc.

4. **Aufnahme starten:**
   - Button "Start Recording & Transcription" klicken
   - Warten bis fertig (Dauer = Aufnahme + ~10-30 Sek. Verarbeitung)

5. **Aufnahme vorzeitig stoppen:**
   - Button "Stop Recording" klicken
   - HackRF wird sofort freigegeben

6. **Ergebnis ansehen:**
   - Text erscheint in einer Box
   - Metadata zeigt: Sprache, Frequenz, Dauer

**Tipps:**
- Bei "No text detected" → Keine Sprache erkannt (nur Musik/Rauschen)
- Gain erhöhen wenn Signal zu schwach
- Gain verringern wenn verzerrt

### APRS verwenden

1. **Klicke auf den Tab "APRS"**

2. **Region wählen:**
   - Klicke Preset-Button (z.B. "Europe" für 144.8 MHz)
   - Oder wähle aus Dropdown

3. **Duration auf 300 Sekunden setzen** (APRS braucht länger)

4. **"Start APRS Capture" klicken**

5. **Session vorzeitig stoppen:**
   - Button "Stop APRS" klicken → Session endet sofort, HackRF wird freigegeben

6. **Ergebnis:**
   - Tabelle mit APRS-Paketen
   - Spalten: Time, Callsign, Type, Position, Message

**Tipps:**
- APRS-Aktivität ist sporadisch → Längere Captures (5-10 Min)
- Keine Pakete? → Andere Tageszeit versuchen

### POCSAG verwenden

1. **Klicke auf den Tab "POCSAG"**

2. **Frequenz wählen:**
   - Schweiz: 147.325 MHz
   - Oder andere Preset-Buttons

3. **Duration auf 300 Sekunden setzen**

4. **"Start POCSAG Capture" klicken**

5. **Session vorzeitig stoppen:**
   - Button "Stop POCSAG" klicken → Session endet sofort, HackRF wird freigegeben

6. **Ergebnis:**
   - Tabelle mit Pager-Nachrichten
   - Spalten: Time, Address, Type, Baud, Message

### Repeater Scan verwenden (NEU)

1. **Klicke auf den Tab "Repeater Scan"**

2. **Band & Region wählen:**
   - **Band**: 2m (144-146 MHz) oder 70cm (430-440 MHz)
   - **Canton**: Optional - Filter nach Kanton (ZH, BE, GR, etc.)
   - **Preset-Buttons** verfügbar: "All 2m", "All 70cm", "Zürich 2m", "Bern 2m"

3. **Scan-Parameter einstellen:**
   - **Duration per Repeater**: 30-300 Sekunden (Empfohlen: 120s)
   - **RF Gain**: 20 dB standardmäßig
   - Längere Dauer = präzisere Messungen

4. **"Start Repeater Scan" klicken**

5. **Live-Fortschritt beobachten:**
   - Progress Bar zeigt aktuellen Fortschritt
   - Zeigt welcher Repeater gerade gescannt wird
   - Geschätzte verbleibende Zeit (ETA)
   - Live-Tabelle mit Zwischenergebnissen

6. **Ergebnis:**
   - **Tabelle mit Repeater-Aktivität:**
     - **Status**: 🟢 Aktiv (Transmissionen erkannt) / ⚫ Ruhig (keine Aktivität)
     - **Callsign**: Repeater-Rufzeichen (z.B. HB9GR)
     - **Frequency**: Ausgabefrequenz in MHz
     - **Transmissions**: Anzahl erkannter Funkvorgänge
     - **Activity %**: Prozentsatz der Zeit mit Aktivität
     - **Signal (dB)**: Durchschnittliche Signalstärke

7. **Daten analysieren:**
   - In Kibana "Repeater Activity Dashboard" öffnen
   - Historische Trends ansehen
   - Aktivste Repeater identifizieren

**Tipps:**
- **Scan dauert lange:** 10 Repeater × 120s = 20 Minuten
- **Selektiv scannen:** Band/Canton-Filter nutzen um Zeit zu sparen
- **Beste Resultate:** Scans zu aktiven Zeiten (Wochenende, Abend)
- **Keine Aktivität?** Normal - viele Repeater sind selten genutzt

### Multi-Channel DDC verwenden *(USRP N200)*

Voraussetzung: Im SDR-Gerätewähler "USRP N200 (Ethernet)" auswählen und IP-Adresse eingeben.

1. **Klicke auf den Tab "📡📡 Multi-Channel (USRP)"**
   *(Tab erscheint erst nach Auswahl von USRP N200 im Gerätewähler)*

2. **Center-Frequenz setzen:**
   - Mittenfrequenz des Breitband-Empfangsfensters (50 MHz – 2.2 GHz bei WBX)
   - Alle Kanäle müssen innerhalb von ±Wideband-Rate/2 um diese Frequenz liegen

3. **Wideband Sample Rate wählen:**
   - **5 MS/s** (±2.5 MHz) — Empfohlen für 4+ Kanäle, geringster CPU-Bedarf
   - **10 MS/s** (±5 MHz) — Standard, bis zu 4 Kanäle problemlos
   - **20/25 MS/s** — Maximal, nur 2–3 Kanäle gleichzeitig empfohlen

4. **Gain und Duration einstellen**

5. **Kanäle konfigurieren:**
   - Vorbefüllt mit APRS 144.8 MHz und POCSAG 147.325 MHz
   - "+ Add Channel" für weitere Kanäle (max. 8)
   - Pro Kanal: Modus (APRS/POCSAG), Frequenz in Hz, Label
   - Der **Span-Hinweis** zeigt das genaue Empfangsfenster an
   - Minimaler Kanalabstand: 50 kHz

6. **"Start Multi-Channel" klicken**

7. **Live-Statistiken beobachten:**
   - Tabelle mit Paket-Counter pro Kanal
   - Gesamt-Pakete und Laufzeit
   - "Stop"-Button beendet alle Decoder sofort

**Beispielkonfiguration** (10 MS/s um 146 MHz):
- APRS: 144.800 MHz (−1.2 MHz vom Center)
- POCSAG: 147.325 MHz (+1.325 MHz vom Center)
- Beide Kanäle liegen innerhalb ±5 MHz → passt bei 10 MS/s

**Tipps:**
- Bei 8 Kanälen Sample Rate auf 5 MS/s reduzieren (CPU-Ersparnis ~50%)
- In Kibana: Pakete in `radio-aprs-*` und `radio-pocsag-*` mit `channel_label`-Filter filtern
- Der `decimation_factor` in der Startantwort zeigt die tatsächliche Dezimierung an

---

## 📊 Kibana Dashboards

**Zugriff:** http://localhost:5601

**Login:** `elastic` / Passwort aus `.secrets/elasticsearch_password.txt` (X-Pack Security ist aktiv)

### Was zeigt Kibana?

**Verfügbare Funktionen:**

1. **Discover** (Radio Captures Explorer)
   - Volltext-Suche in allen Transkriptionen
   - Filter nach Modulation, Frequenz, Sprache
   - Zeitbasierte Filterung (15m, 1h, 24h, 7d, 30d)
   - Real-time Updates mit Auto-Refresh

2. **APRS Dashboard**
   - Total APRS Packets: Gesamtanzahl empfangener Pakete
   - Unique Callsigns: Anzahl eindeutiger Rufzeichen
   - Top 15 Callsigns: Aktivste Stationen (Balkendiagramm)
   - APRS Stations Map: Geo-Karte mit Stationspositionen
   - Message Types: Verteilung der Pakettypen (Pie Chart)
   - APRS Timeline: Pakete über Zeit (Liniendiagramm)
   - Recent Packets Table: Letzte 50 APRS-Nachrichten

3. **POCSAG Dashboard**
   - Total Messages: Gesamtanzahl POCSAG-Nachrichten
   - Unique Addresses: Eindeutige Pager-Adressen
   - Top 15 Addresses: Aktivste Adressen
   - Message Types: Nachrichtentypen-Verteilung
   - Baud Rates: Verteilung (512, 1200, 2400 Baud)
   - Timeline: Nachrichten der letzten 24h
   - **POCSAG Messages – Chronological List**: Letzte 100 Nachrichten in Listenform (Adresse, Typ, Baud, Text, Frequenz), blätterbar

4. **Repeater Activity Dashboard**
   - Most Active Repeaters (24h): Tabelle mit avg. Activity %
   - Activity by Band: 2m vs 70cm Verteilung (Pie Chart)
   - Scan Rate: Scan-Operationen über Zeit
   - Recent Scans: Letzte 100 Scan-Ergebnisse mit Signalstärke

5. **Stack Health Dashboard**
   - Running Containers: Anzahl aktiver Container
   - Container Status: Verteilung (running/stopped/paused)
   - CPU Usage by Container: Timeline-Liniendiagramm pro Container
   - Memory Usage by Container: Timeline-Liniendiagramm pro Container
   - Container Resource Summary: Tabelle mit avg/max CPU und Memory pro Container
   - Container Health Status: Healthcheck-Ergebnisse (healthy/unhealthy) pro Container
   - Zeitfenster: Standard 1h, Auto-Refresh alle 30s

6. **Stack Logs Dashboard**
   - Total Log Events: Gesamtanzahl aller Log-Einträge
   - Log Stream: Verteilung stdout vs. stderr (Donut-Chart)
   - Log Events Timeline: Log-Volumen über Zeit, aufgeteilt nach Container
   - Log Volume by Container: Balkendiagramm — welcher Container schreibt am meisten
   - Log Summary Table: Aufschlüsselung nach Container und Stream
   - **Container Logs – Chronological List**: Letzte 100 Log-Einträge in Listenform (Container, Stream, Meldung), blätterbar, neueste zuerst
   - Zeitfenster: Standard 24h, Auto-Refresh alle 30s

7. **System Metrics** (Metricbeat)
   - Container CPU & Memory Usage
   - System Performance
   - Docker Statistiken

### Kibana nutzen

**Navigation:**
- Links: Hauptmenü (Discover, Dashboard, Visualize, Dev Tools)
- Oben rechts: Zeitbereich auswählen (Quick Select: Last 15 minutes, Last 24 hours, etc.)
- Auto-Refresh aktivieren (z.B. alle 30s)

**Suchen in Discover:**
- Suchfeld nutzen: `transcription: "amateur"` oder `modulation: "FM"`
- Filter hinzufügen: "Add filter" → Feld → Wert
- Felder aus der Sidebar hinzufügen/entfernen

**Dashboard-Funktionen:**
- Klick auf Visualisierung für Drilldown
- Zeitbereich mit Maus ziehen für Zoom
- Filter durch Klick auf Diagrammelemente
- Dashboards mit "Share" exportieren

**Tipps:**
- Index Pattern erstellen: Kibana → Stack Management → Index Patterns → Create
- Dashboards refreshen sich automatisch (wenn Auto-Refresh aktiviert)
- Bei "No Data" → Erst Captures machen, Index Pattern prüfen
- Zeitbereich erweitern wenn keine Daten angezeigt werden

---

## 🗄️ Kibana Dev Tools - Elasticsearch Konsole

**Zugriff:** http://localhost:5601/app/dev_tools#/console

**Login:** `elastic` / Passwort aus `.secrets/elasticsearch_password.txt`

### Indices ansehen

**Verfügbare Indices:**
- **radio-captures-YYYY.MM.DD** - Voice-Aufnahmen (täglich, 90d Retention)
- **radio-aprs-YYYY.MM.DD** - APRS-Pakete (90d Retention)
- **radio-pocsag-YYYY.MM.DD** - POCSAG-Nachrichten (90d Retention)
- **radio-repeater-activity-YYYY.MM.DD** - Repeater-Aktivität (90d Retention)
- **radio-metrics-YYYY.MM.DD** - System-Metriken (90d Retention)
- **radio-logs-YYYY.MM.DD** - Container-Logs aller Docker-Services (7d Retention)
- **metricbeat-YYYY.MM.DD** - Metricbeat System-/Container-Metriken (7d Retention)

**Indices auflisten:**
```json
GET /_cat/indices/radio-*?v
```

### Einfache Suchen

**Dev Tools Konsole öffnen:**
- Kibana → Dev Tools (linkes Menü)

**Beispiel-Abfragen:**

```json
// Alle Aufnahmen von heute
POST /radio-captures-*/_search
{
  "query": {
    "range": {
      "@timestamp": {
        "gte": "now/d"
      }
    }
  },
  "size": 100
}

// APRS-Pakete eines bestimmten Callsigns
POST /radio-aprs-*/_search
{
  "query": {
    "term": {
      "source_callsign": "N0CALL"
    }
  }
}

// POCSAG-Nachrichten einer Adresse
POST /radio-pocsag-*/_search
{
  "query": {
    "term": {
      "address": 1234567
    }
  }
}

// Aktivste Repeater mit Aggregation
POST /radio-repeater-activity-*/_search
{
  "size": 0,
  "query": {
    "range": {
      "@timestamp": {"gte": "now-24h"}
    }
  },
  "aggs": {
    "by_repeater": {
      "terms": {
        "field": "repeater_callsign",
        "size": 10,
        "order": {"avg_activity": "desc"}
      },
      "aggs": {
        "avg_activity": {
          "avg": {"field": "activity_percentage"}
        }
      }
    }
  }
}
```

**Tipps:**
- Query schreiben → Grüner Pfeil (▶) klicken zum Ausführen
- Strg+Enter für schnelles Ausführen
- Auto-Completion mit Strg+Space
- Ergebnisse werden rechts angezeigt

### Daten exportieren

**JSON Export:**
```json
// Scroll API für große Datenmengen
POST /radio-captures-*/_search?scroll=5m
{
  "size": 1000,
  "query": {"match_all": {}}
}
```

**Index-Snapshot (Backup):**
```json
// Snapshot Repository konfigurieren
PUT /_snapshot/radio_backup
{
  "type": "fs",
  "settings": {
    "location": "/usr/share/elasticsearch/backup"
  }
}

// Snapshot erstellen
PUT /_snapshot/radio_backup/snapshot_1?wait_for_completion=true
```

---

## 🔍 Häufige Fragen

### Keine Aufnahme / "No text detected"

**Ursachen:**
- Keine Sprache auf der Frequenz (nur Musik/Rauschen)
- Signal zu schwach
- Falsche Modulation

**Lösungen:**
- RF Gain erhöhen (30-40 dB probieren)
- Andere Frequenz versuchen
- Modulation prüfen (FM für UKW, AM für Flugfunk)
- Antenne anschließen

### HackRF nicht erkannt

**Prüfen:**
```bash
hackrf_info
```

**Lösung:**
```bash
docker compose restart
```

### HackRF: DC-Spike / IQ-Artefakte im Spektrum

HackRF verwendet eine Direct-Conversion-Architektur (Zero-IF), die ohne Korrektur einen DC-Spike bei der Mittenfrequenz und IQ-Imbalance erzeugt. Das System wendet bei jedem HackRF-Capture automatisch eine softwareseitige IQ-Korrektur an:

1. DC-Offset-Entfernung (I- und Q-Mittelwert subtrahieren)
2. Amplituden-Imbalance-Korrektur
3. Phasen-Imbalance-Korrektur (Gram-Schmidt)

Es sind keine manuellen Einstellungen erforderlich.

### HackRF Capture bricht nach ~13 Sekunden ab

**Problem:** Bei langen Captures (>120s) kann HackRF USB-Transfer-Probleme haben.

**Ursache:** USB-Bandbreite bei 2 MHz Sample Rate (~4 MB/s sustained) kann instabil werden.

**Lösungen:**
1. **RTL-SDR verwenden** (empfohlen für lange Captures >120s) - exzellente USB-Stabilität
2. **Kürzere Captures** (<60s) verwenden mit HackRF
3. **Powered USB Hub** verwenden für stabilere Stromversorgung
4. **USB-Kabel** tauschen (hochwertiges, kurzes Kabel verwenden)

### Kibana zeigt keine Daten

**Ursachen:**
- Noch keine Captures gemacht
- Zeitbereich falsch gewählt
- Index Pattern noch nicht erstellt

**Lösungen:**
- Erst Aufnahmen machen
- Zeitbereich auf "Last 24 hours" setzen
- Index Pattern prüfen: Kibana → Stack Management → Index Patterns
- Index Pattern erstellen für `radio-captures-*`, `radio-aprs-*`, etc.
- Dashboard refreshen (Reload-Button oben rechts)

### Keine APRS-Pakete

**Ursachen:**
- APRS-Aktivität ist sporadisch
- Zu kurze Aufnahmedauer
- Falsche Frequenz für Region

**Lösungen:**
- Duration auf 300-600 Sekunden erhöhen
- Richtige Region-Frequenz wählen:
  - Europa: 144.800 MHz
  - Nordamerika: 144.390 MHz
- Andere Tageszeit versuchen (tagsüber mehr Aktivität)
- VHF-Antenne verwenden (2m Band)

### System ist langsam

**Lösungen:**
- Duration reduzieren (15-30 Sek statt 300)
- Alte Aufnahmen löschen
- Datenbank aufräumen (alte Captures löschen)

---

## ⚡ Schnellreferenz

### Häufige Frequenzen (Schweiz/Europa)

| Service | Frequenz | Modulation | Beschreibung |
|---------|----------|------------|--------------|
| **UKW Radio** | 88.5 - 108 MHz | FM | Kommerzielle Radiosender |
| **Flugfunk** | 118 - 137 MHz | AM | Piloten-Kommunikation |
| **APRS Europa** | 144.800 MHz | FM | Amateur-Funk Positionsdaten |
| **POCSAG CH** | 147.325 MHz | FM | Pager-Nachrichten |
| **PMR** | 446 MHz | FM | Walkie-Talkies |
| **Amateur 2m** | 145.500 MHz | FM | VHF Amateurfunk |
| **Amateur 70cm** | 433.5 MHz | FM | UHF Amateurfunk |

### System-Befehle

```bash
# System starten
docker compose up -d

# System stoppen
docker compose down

# Status prüfen
docker compose ps

# Logs ansehen
docker compose logs -f radio-api

# HackRF prüfen
hackrf_info

# USRP N200 prüfen (Gigabit Ethernet)
uhd_find_devices
uhd_usrp_probe --args="addr=192.168.10.2"

# USRP N200 Netzwerk konfigurieren (einmalig)
sudo ip addr add 192.168.10.1/24 dev eth0

# API-Keys ansehen
cat .env | grep API_KEYS

# API-Keys generieren (neu)
python3 scripts/generate_api_keys.py

# Elasticsearch Passwort ansehen
cat .secrets/elasticsearch_password.txt
```

### Zugangsdaten

**Kibana:** http://localhost:5601
- User: `elastic`, Passwort: `cat .secrets/elasticsearch_password.txt`

**Hinweis:** Alle ELK-Passwörter werden von `scripts/setup-elk-security.sh` generiert und in `.secrets/` gespeichert.

---

## 🧪 Entwicklung & Testing

### CI/CD Pipeline

Das Projekt verfügt über eine umfassende GitHub Actions CI/CD-Pipeline, die bei jedem Push ausgeführt wird:

**Pipeline-Schritte:**
1. ✅ **Code Checkout**: Sauberer Checkout mit vollständiger Git-Historie
2. ✅ **MyPy Type Checking**: Statische Typanalyse im Strict-Mode
3. ✅ **Pytest Test Suite**: 200 Tests über alle Hauptkomponenten
4. ✅ **Docker Build**: Verifizierung dass Docker Image erfolgreich gebaut wird

**Test-Abdeckung:**
- **200 Tests Total** über 7 Test-Suites
- **API Tests (25)**: Flask Endpoints, Authentifizierung, Fehlerbehandlung
- **SDR Hardware Tests (25)**: HackRF/RTL-SDR/Airspy Erkennung, Capture, Validierung
- **Transcription Tests (17)**: Whisper Integration, Dateibehandlung
- **APRS Decoder Tests (37)**: APRS-Paket-Dekodierung
- **POCSAG Decoder Tests (34)**: Pager-Nachrichten-Dekodierung
- **Streaming Decoder Tests (34)**: Echtzeit-Streaming-Sessions
- **Repeater Scanning Tests (28)**: Repeater-Aktivitäts-Analyse

### Tests lokal ausführen

**Vollständige Test-Suite:**

```bash
# Virtual Environment aktivieren
source venv/bin/activate

# Alle 200 Tests ausführen
pytest

# Tests mit Coverage-Report
./scripts/run_coverage.sh

# Type Checking mit MyPy
./scripts/run_mypy.sh

# Spezifische Test-Suite ausführen
pytest tests/test_api.py          # Nur API-Tests
pytest tests/test_sdr_hardware.py # Nur SDR-Tests
pytest tests/test_transcription.py # Nur Transkriptions-Tests

# Mit verbose Output
pytest -v

# Nur failed Tests erneut ausführen
pytest --lf
```

**Test-Ergebnisse:**
- ✅ 200 Tests über alle 7 Test-Suites
- ✅ Vollständige MyPy Type Checking Compliance
- ✅ Automatisierte CI/CD Pipeline auf GitHub Actions

### Development vs. Production Mode

**Development Mode (Manuell):**

```bash
# Flask Development Server starten (Port 5000)
source venv/bin/activate
python api_service.py

# In anderem Terminal: Web Interface (Port 8080)
python -m http.server 8080

# Vorteile:
# - Schnelle Code-Änderungen
# - Auto-Reload bei File-Änderungen
# - Direktes Debugging
# - Keine API-Keys erforderlich (API_KEYS='')
```

**Production Mode (Docker):**

```bash
# Docker mit Gunicorn + kompletter ELK Stack
docker compose up -d

# Services zugreifen:
# - Web Interface: http://localhost:8080
# - API:           http://localhost:5000
# - Kibana:        http://localhost:5601
# - Elasticsearch: http://localhost:9200
# - Dockge:         http://localhost:5001

# Vorteile:
# - Gunicorn WSGI Server (production-ready)
# - Gevent Workers für Concurrency
# - ELK Stack für Monitoring
# - API-Key Authentifizierung aktiv
# - Memory Limits (API: 4 GB)
# - Container-Isolation
# - Automatisches Restart
```

### Test-Umgebung Details

**Mocking & Simulation:**

Das Test-System nutzt umfassende Mocking-Strategien:

- **SDR Hardware**: Automatische Simulation wenn keine Hardware vorhanden
- **Whisper Model**: Mock zur Vermeidung von CUDA-Fehlern
- **Temporäre Verzeichnisse**: Session-scoped für saubere Tests
- **API-Keys**: Automatisch deaktiviert in Tests (API_KEYS='')

**Test-Fixtures:**
- `client`: Flask Test Client mit localhost IP
- `sample_audio_file`: Generiert 1s Test-Audio (16kHz, 440Hz Ton)
- `temp_recording_dir`: Session-scoped temp directory
- `mock_sdr_hardware`: HackRF/RTL-SDR Simulation
- `mock_transcription_service`: Whisper Model Mock

### Code-Qualitätsstandards

**Type Checking:**

```bash
# MyPy Strict Mode
./scripts/run_mypy.sh

# Prüft:
# - Vollständige Typ-Annotationen
# - Type Safety
# - Optional/None Handling
# - Return Types
```

**Coverage:**

```bash
# Coverage Report generieren
./scripts/run_coverage.sh

# Öffnet HTML-Report:
# - Zeile-für-Zeile Coverage
# - Branch Coverage
# - Fehlende Coverage rot markiert

# Öffnet HTML-Report mit Zeile-für-Zeile Coverage
```

**Kontinuierliche Integration:**

Die GitHub Actions Pipeline stellt sicher:
- ✅ Alle Tests bestehen vor Merge
- ✅ Type Checking ohne Fehler
- ✅ Docker Image baut erfolgreich
- ✅ Code-Standards eingehalten

### Development-Workflow

**Typischer Entwicklungs-Zyklus:**

1. **Feature Branch erstellen:**
   ```bash
   git checkout -b feature/neue-funktionalität
   ```

2. **Code ändern und testen:**
   ```bash
   # Tests während Entwicklung
   pytest tests/test_mein_feature.py -v

   # Type Checking
   ./scripts/run_mypy.sh
   ```

3. **Vollständige Tests vor Commit:**
   ```bash
   # Alle Tests
   pytest

   # Coverage prüfen
   ./scripts/run_coverage.sh
   ```

4. **Commit & Push:**
   ```bash
   git add .
   git commit -m "feat: Neue Funktionalität XYZ"
   git push origin feature/neue-funktionalität
   ```

5. **CI/CD prüft automatisch:**
   - MyPy Type Checking
   - Pytest Suite (200 Tests)
   - Docker Build

6. **Merge nach erfolgreicher CI:**
   ```bash
   gh pr create
   gh pr merge
   ```

### Hilfreiche Development-Befehle

```bash
# Tests mit Watch-Mode (bei Änderung neu ausführen)
pytest-watch

# Test Coverage nur für geänderte Files
pytest --cov=. --cov-report=term-missing

# Spezifischen Test mit Output ausführen
pytest tests/test_api.py::test_health -v -s

# Debug-Modus (Breakpoints erlaubt)
pytest --pdb

# Performance-Profiling
pytest --durations=10

# Parallel Tests (schneller)
pytest -n auto
```

---

## 📚 Für technische Details

Siehe **README.md** für:
- Installation & Setup
- Docker-Konfiguration
- API-Dokumentation
- Datenbank-Schema
- Secrets-Management
- Troubleshooting (erweitert)
- Vollständige Projekt-Struktur
- Erweiterte Entwicklungs-Dokumentation

---

**Version:** 5.2
**Letztes Update:** Mai 2026
**Features:** Voice, APRS, POCSAG, Repeater Activity Monitoring, Multi-Channel DDC (USRP N200), ELK Stack, Help-Button, Filebeat Logs, Stack Health/Logs Dashboards, 7-Tage Log-Retention, Docker Secrets, CI/CD Pipeline
