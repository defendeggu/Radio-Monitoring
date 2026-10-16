# Kibana-Objekte

NDJSON-Exporte (Data Views und Dashboards). Importieren mit `./scripts/import-kibana-dashboards.sh`, die Data Views werden dabei zuerst geladen.

| Datei | Inhalt |
|---|---|
| `index-patterns.ndjson` | Data Views für alle `radio-*`-Indizes und `metricbeat-*` |
| `radio-overview-dashboard.ndjson` | Übersicht über alle Betriebsarten |
| `aprs-dashboard.ndjson` | APRS mit Karte |
| `pocsag-dashboard.ndjson` | POCSAG |
| `repeater-activity-dashboard.ndjson` | Repeater-Aktivität |
| `logs-dashboard.ndjson` | Container-Logs (`radio-logs-*`) |
| `health-dashboard.ndjson` | Zustand von Host, Containern und Elasticsearch (Metricbeat) |

Eigene Dashboards exportierst du in Kibana unter *Stack Management → Saved Objects → Export* und legst sie hier ab.
