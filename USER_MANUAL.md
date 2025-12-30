# Radio Monitoring System - Benutzerhandbuch

Einfache Anleitung für die Bedienung des Radio-Monitoring-Systems.

---

## 📻 Was kann das System?

- **Voice Transcription**: Sprache von Radiosendern in Text umwandeln
- **APRS Decoding**: Digitale Funkpakete von Amateurfunkern empfangen und anzeigen
- **POCSAG Decoding**: Pager-Nachrichten dekodieren
- **Repeater Activity Monitoring**: Schweizer FM-Repeater auf Aktivität überwachen (NEU)
- **Datenanalyse**: Alle Aufnahmen durchsuchen und visualisieren

---

## 🚀 System Starten

```bash
cd /home/spia/my-project
docker compose up -d
```

**Wichtige URLs:**
- **Web-Interface**: http://localhost:8080 (Hauptsteuerung)
- **Kibana**: http://localhost:5601 (Dashboards & Visualisierung)
- **Elasticsearch**: http://localhost:9200 (Datenbank API)

---

## 🎛️ Web Interface Bedienung

### Tabs oben

Das Web-Interface hat 4 Tabs:
- **🎤 Voice Transcription** - Sprache aufnehmen und transkribieren
- **📡 APRS** - APRS-Pakete empfangen
- **📟 POCSAG** - Pager-Nachrichten empfangen
- **📻 Repeater Scan** - FM-Repeater-Aktivität überwachen (NEU)

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

5. **Ergebnis ansehen:**
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

5. **Ergebnis:**
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

5. **Ergebnis:**
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

**Repeater-Daten importieren:**
```bash
# CSV mit Repeater-Liste importieren
docker exec radio-transcription-api python /app/scripts/import_repeaters_csv.py /app/scripts/example_repeaters.csv
```

Siehe `scripts/README.md` für CSV-Format.

---

## 📊 Kibana Dashboards

**Zugriff:** http://localhost:5601

**Login:** Keine Authentifizierung erforderlich (für Produktion X-Pack Security aktivieren)

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

4. **Repeater Activity Dashboard**
   - Most Active Repeaters (24h): Tabelle mit avg. Activity %
   - Activity by Band: 2m vs 70cm Verteilung (Pie Chart)
   - Scan Rate: Scan-Operationen über Zeit
   - Recent Scans: Letzte 100 Scan-Ergebnisse mit Signalstärke

5. **System Metrics** (Metricbeat)
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

**Login:** Keine Authentifizierung erforderlich

### Indices ansehen

**Verfügbare Indices:**
- **radio-captures-YYYY.MM.DD** - Voice-Aufnahmen (täglich)
- **radio-aprs-YYYY.MM.DD** - APRS-Pakete
- **radio-pocsag-YYYY.MM.DD** - POCSAG-Nachrichten
- **radio-repeater-activity-YYYY.MM.DD** - Repeater-Aktivität
- **radio-metrics-YYYY.MM.DD** - System-Metriken

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

# Credentials ansehen
./setup-secrets.sh  # Zeigt alle Passwörter
```

### Zugangsdaten

**Kibana:** http://localhost:5601
- Keine Authentifizierung erforderlich

**N8N:** http://localhost:5679
```bash
cat secrets/n8n_basic_auth_user.txt
cat secrets/n8n_basic_auth_password.txt
```

**Hinweis:** Für Produktion X-Pack Security für Elasticsearch/Kibana aktivieren

---

## 📚 Für technische Details

Siehe **README.md** für:
- Installation & Setup
- Docker-Konfiguration
- API-Dokumentation
- Datenbank-Schema
- Secrets-Management
- Troubleshooting (erweitert)

---

**Version:** 4.0
**Letztes Update:** Dezember 2025
**Features:** Voice, APRS, POCSAG, Repeater Activity Monitoring, Secrets Management
