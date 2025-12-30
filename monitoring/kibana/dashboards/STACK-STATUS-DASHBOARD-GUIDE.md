# Stack Status Monitor Dashboard - Erstellungsanleitung

Da das automatische Dashboard-Import aufgrund komplexer JSON-Strukturen fehlschlägt,
hier die Anleitung zum manuellen Erstellen des **Stack Status Monitor Dashboards** in Kibana.

## Dashboard erstellen

1. **Öffne Kibana**: http://localhost:5601

2. **Gehe zu Dashboards**:
   - Klicke im Menü auf "Analytics" → "Dashboard"
   - Klicke auf "Create dashboard"

3. **Dashboard-Titel**: "Stack Status Monitor"

---

## Visualisierungen hinzufügen

### 1. Total Captures (Metric)

- Klicke auf "Create visualization"
- Wähle "Aggregation based" → "Metric"
- Data view: `radio-captures-*`
- Metrics: Count
- Speichern als: "Total Captures"

### 2. Total APRS Messages (Metric)

- Neue Visualization hinzufügen
- Typ: "Metric"
- Data view: `radio-aprs-*`
- Metrics: Count
- Speichern als: "Total APRS Messages"

### 3. Total POCSAG Messages (Metric)

- Neue Visualization hinzufügen
- Typ: "Metric"
- Data view: `radio-pocsag-*`
- Metrics: Count
- Speichern als: "Total POCSAG Messages"

### 4. Total Repeater Scans (Metric)

- Neue Visualization hinzufügen
- Typ: "Metric"
- Data view: `radio-repeater-activity-*`
- Metrics: Count
- Speichern als: "Total Repeater Scans"

### 5. Captures Over Time (Area Chart)

- Neue Visualization hinzufügen
- Typ: "Lens" → "Area"
- Data view: `radio-captures-*`
- Horizontal axis: `@timestamp` (Date histogram, Auto interval)
- Vertical axis: Count of records
- Split by: `mode` (Terms)
- Speichern als: "Captures Over Time"

### 6. Captures by Mode (Donut Chart)

- Neue Visualization hinzufügen
- Typ: "Lens" → "Donut"
- Data view: `radio-captures-*`
- Slice by: `mode` (Terms)
- Size by: Count of records
- Speichern als: "Captures by Mode"

### 7. Top Frequencies (Bar Chart)

- Neue Visualization hinzufügen
- Typ: "Lens" → "Bar horizontal"
- Data view: `radio-captures-*`
- Y-axis: `frequency_mhz` (Terms, Top 15)
- X-axis: Count of records
- Speichern als: "Top Frequencies"

### 8. Recent Captures (Table)

- Klicke auf "Add from library" oder "Create visualization"
- Wähle "Discover" oder erstelle eine Tabelle
- Data view: `radio-captures-*`
- Columns:
  - `@timestamp`
  - `frequency_mhz`
  - `modulation`
  - `mode`
  - `sdr_type`
- Sort: `@timestamp` descending
- Speichern als: "Recent Captures"

---

## Dashboard-Layout

Arrangiere die Visualisierungen wie folgt:

```
┌──────────────────────────────────────────────────────────┐
│  Total       Total APRS    Total POCSAG   Total Repeater │
│  Captures    Messages      Messages       Scans          │
│  [Metric]    [Metric]      [Metric]       [Metric]       │
├──────────────────────────────────────────────────────────┤
│  Captures Over Time              │  Captures by Mode     │
│  [Area Chart]                    │  [Donut Chart]        │
│                                  │                       │
├──────────────────────────────────────────────────────────┤
│  Top Frequencies (Bar Chart - Horizontal)                │
│                                                           │
├──────────────────────────────────────────────────────────┤
│  Recent Captures (Table)                                 │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

---

## Dashboard-Einstellungen

1. **Auto-Refresh aktivieren**:
   - Klicke auf die Uhr oben rechts
   - Setze "Refresh every" auf `1 minute`

2. **Time Range**:
   - Setze auf "Last 24 hours"

3. **Dashboard speichern**:
   - Klicke auf "Save"
   - Name: "Stack Status Monitor"
   - Description: "Monitor ELK Stack health, performance, and system status"

---

## Zusätzliche Metriken (Optional)

Falls **Metricbeat** läuft, kannst du auch System-Metriken hinzufügen:

### CPU Usage
- Data view: `metricbeat-*`
- Visualization: Line chart
- Field: `system.cpu.total.pct`

### Memory Usage
- Data view: `metricbeat-*`
- Visualization: Line chart
- Field: `system.memory.actual.used.pct`

### Disk Usage
- Data view: `metricbeat-*`
- Visualization: Gauge
- Field: `system.filesystem.used.pct`

---

## Fertig! 🎉

Dein Stack Status Monitor Dashboard ist jetzt einsatzbereit und zeigt:
- ✅ Anzahl aller Captures, APRS, POCSAG, Repeater-Scans
- ✅ Timeline der Captures
- ✅ Verteilung nach Modus
- ✅ Top verwendete Frequenzen
- ✅ Letzte Captures in Echtzeit

**Auto-Refresh** sorgt dafür, dass das Dashboard immer aktuelle Daten anzeigt!
