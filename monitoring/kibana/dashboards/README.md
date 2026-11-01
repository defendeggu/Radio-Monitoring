# Kibana-Objekte

NDJSON-Exporte (Data Views und Dashboards). Importieren mit `./scripts/import-kibana-dashboards.sh`: Die Data Views werden zuerst geladen, bestehende Objekte überschrieben und die Dashboards früherer Versionen (`../obsolete-objects.txt`) entfernt.

Die Dashboards heissen wie die Module der Weboberfläche (`RadioMoni · <Modul>`) und werden von `../build_dashboards.py` erzeugt. Änderungen also dort vornehmen und neu generieren:

```bash
python3 monitoring/kibana/build_dashboards.py
./scripts/import-kibana-dashboards.sh
```

| Datei | Dashboard | Daten |
|---|---|---|
| `index-patterns.ndjson` | – | Data Views für alle `radio-*`-Indizes und `metricbeat-*` |
| `overview-dashboard.ndjson` | RadioMoni · Übersicht | Kennzahlen und Verläufe aller Betriebsarten |
| `voice-dashboard.ndjson` | RadioMoni · Sprache | `radio-captures-*`, `mode: voice` |
| `vox-dashboard.ndjson` | RadioMoni · VOX-Aufnahme | `radio-captures-*`, `mode: vox` |
| `aprs-dashboard.ndjson` | RadioMoni · APRS | `radio-aprs-*`, mit Stationskarte |
| `pocsag-dashboard.ndjson` | RadioMoni · POCSAG | `radio-pocsag-*` |
| `adsb-dashboard.ndjson` | RadioMoni · ADS-B | `radio-adsb-*`, mit Flugzeugkarte |
| `ais-dashboard.ndjson` | RadioMoni · AIS | `radio-ais-*`, mit Schiffskarte |
| `ism-dashboard.ndjson` | RadioMoni · ISM-Sensoren | `radio-ism-*`, Temperatur und Luftfeuchte je Sensor |
| `repeater-dashboard.ndjson` | RadioMoni · Repeater-Scan | `radio-repeater-activity-*` |
| `alerts-dashboard.ndjson` | RadioMoni · Alarme | `radio-alerts-*` |
| `logs-dashboard.ndjson` | RadioMoni · System – Logs | Container-Logs (`radio-logs-*`) |
| `health-dashboard.ndjson` | RadioMoni · System – Zustand | Host, Container, Elasticsearch und GPU (Metricbeat; GPU nur mit `docker-compose.gpu.yml`). Von Hand gepflegt, nicht von `build_dashboards.py` erzeugt |

Die Karten sind Kibana-Maps auf dem Feld `position` und laden die Grundkarte vom Elastic Maps Service (Internetzugang im Browser nötig). Multi-Channel-Sessions schreiben in die APRS- und POCSAG-Indizes (Feld `channel_label`) und erscheinen dort.

Eigene Dashboards exportierst du in Kibana unter *Stack Management → Saved Objects → Export*. Lege sie unter einem eigenen Dateinamen hier ab, damit `build_dashboards.py` sie nicht überschreibt.
