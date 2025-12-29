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
- **Grafana**: http://localhost:3000 (Dashboards & Visualisierung)
- **pgAdmin**: http://localhost:5050 (Datenbank-Browser)

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
   - In Grafana "Repeater Activity Dashboard" öffnen
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

## 📊 Grafana Dashboards

**Zugriff:** http://localhost:3000

**Login:**
- Credentials wurden beim Setup generiert
- Siehe `cat secrets/grafana_admin_password.txt`

### Was zeigt Grafana?

**Verfügbare Dashboards:**

1. **APRS Dashboard**
   - Anzahl empfangener APRS-Pakete
   - Top 15 aktivste Callsigns
   - Timeline: Wann wurden Pakete empfangen?
   - Karte mit APRS-Stationen
   - Nachrichtentypen (Position, Message, Weather, etc.)

2. **POCSAG Dashboard**
   - Anzahl POCSAG-Nachrichten
   - Eindeutige Pager-Adressen
   - Top 15 Adressen
   - Nachrichtentypen (Alphanumeric, Numeric, Tone)
   - Baud-Rate Verteilung (512, 1200, 2400)
   - Timeline der letzten 24 Stunden

3. **Repeater Activity Dashboard** (NEU)
   - Aktivste Repeater der letzten 24 Stunden
   - Scan-Rate (Anzahl Scans pro Minute)
   - Aktivität nach Band (2m vs 70cm)
   - Letzte 100 Scan-Ergebnisse mit Signalstärke
   - Aktivitäts-Trends nach Canton
   - Auto-Refresh alle 30 Sekunden

4. **System Performance**
   - API Requests
   - Erfolgsrate
   - CPU & Memory Usage

### Dashboard nutzen

**Navigation:**
- Links: Menü für Dashboard-Auswahl
- Oben rechts: Zeitbereich auswählen (z.B. "Last 24 hours")
- Auto-Refresh aktivieren für Live-Updates

**Panels:**
- Klicke auf Panel-Titel → "View" für Vollbild
- Zeitbereich mit Maus ziehen für Zoom
- Mouse-over auf Graphen für Details

**Tipps:**
- Dashboards aktualisieren sich automatisch alle 30 Sekunden
- Zeitbereich anpassen um historische Daten zu sehen
- Bei "No Data" → Erst Captures machen, dann Dashboard aktualisieren

---

## 🗄️ pgAdmin - Datenbank Browser

**Zugriff:** http://localhost:5050

**Login:**
- Credentials wurden beim Setup generiert
- Siehe `cat secrets/pgadmin_password.txt`

### Daten ansehen

**Server ist bereits konfiguriert:**

1. **Links in der Sidebar:**
   - Servers → Radio Monitoring Database → Databases → radio_monitoring → Schemas → public → Tables

2. **Tabellen:**
   - **captures** - Alle Voice-Aufnahmen
   - **aprs_messages** - APRS-Pakete
   - **pocsag_messages** - POCSAG-Nachrichten
   - **repeaters** - Schweizer FM-Repeater Verzeichnis (NEU)
   - **repeater_activity** - Repeater-Aktivitäts-Messungen (NEU)
   - **repeater_scan_sessions** - Scan-Sitzungen (NEU)

3. **Daten ansehen:**
   - Rechtsklick auf Tabelle → "View/Edit Data" → "All Rows"
   - Zeigt alle Einträge wie in Excel

### Einfache Suchen

**Query Tool öffnen:**
- Rechtsklick auf "radio_monitoring" → "Query Tool"

**Beispiel-Abfragen:**

```sql
-- Alle Aufnahmen von heute
SELECT * FROM captures
WHERE created_at::date = CURRENT_DATE;

-- APRS-Pakete eines bestimmten Callsigns
SELECT * FROM aprs_messages
WHERE source_callsign = 'N0CALL';

-- POCSAG-Nachrichten einer Adresse
SELECT * FROM pocsag_messages
WHERE address = 1234567;

-- Aktivste Repeater im Kanton Zürich
SELECT r.callsign, r.output_frequency / 1000000.0 AS freq_mhz,
       AVG(ra.activity_percentage) AS avg_activity
FROM repeaters r
JOIN repeater_activity ra ON r.id = ra.repeater_id
WHERE r.canton = 'ZH'
GROUP BY r.id
ORDER BY avg_activity DESC
LIMIT 10;
```

**Tipps:**
- Query schreiben → F5 drücken zum Ausführen
- "Download as CSV" für Export
- Nicht vergessen: Nach Suchen mit `LIMIT 100` die Ergebnisse begrenzen

### Daten exportieren

**CSV Export:**
1. Rechtsklick auf Tabelle → "Import/Export..."
2. "Export" wählen
3. Format: CSV
4. Dateinamen eingeben
5. "OK" klicken

**Datenbank-Backup:**
1. Rechtsklick auf "radio_monitoring" → "Backup..."
2. Format: "Custom" (komprimiert)
3. Dateinamen eingeben
4. "Backup" klicken

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

### Grafana zeigt keine Daten

**Ursachen:**
- Noch keine Captures gemacht
- Zeitbereich falsch gewählt

**Lösungen:**
- Erst Aufnahmen machen
- Zeitbereich auf "Last 24 hours" setzen
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

**Grafana:** http://localhost:3000
```bash
cat secrets/grafana_admin_user.txt
cat secrets/grafana_admin_password.txt
```

**pgAdmin:** http://localhost:5050
```bash
cat secrets/pgadmin_email.txt
cat secrets/pgadmin_password.txt
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

---

**Version:** 4.0
**Letztes Update:** Dezember 2025
**Features:** Voice, APRS, POCSAG, Repeater Activity Monitoring, Secrets Management
