# Roadmap

Stand: 2026-11-06 (Version 5.5.0). Erledigtes steht im [CHANGELOG](CHANGELOG.md).

## Offen

| Thema | Beschreibung | Aufwand |
|---|---|---|
| Benutzer und Rollen | Lesende und steuernde Rollen, Login statt API-Key im Browser | mittel |
| APRS-IS-iGate | empfangene Pakete mit Rufzeichen und Passcode an APRS-IS weiterleiten | mittel |
| PPM-Kalibrierung | automatisch an einem bekannten Träger messen und pro Gerät speichern | klein |
| DMR / P25 | Digitalfunk mit dsd-fme (nicht in Debian, eigener Build nötig) | mittel |
| RSPduo am Gerät prüfen | Stufe 2 und 3 sind mit simuliertem Gerät gebaut; am echten RSPduo prüfen: Erkennung, Hi-Z und Notch, Master/Slave mit zwei Skimmern, Stopp des Masters, CPU-Last | klein |
| RSPduo Single Tuner | Modus *Single Tuner* mit bis zu 10 MS/s als drittes Gerät neben Tuner A und B (schliesst die beiden Tuner solange aus) | klein |
| Wetterbilder | NOAA-/Meteor-APT- und LRPT-Dekodierung | mittel |
| Contest-Skimmer SSB messen | SSB ist experimentell eingebaut; an echten Contest-Aufnahmen Präzision (Ziel ≥ 90 %) und Ausbeute (≥ 30 %) messen und Prompt, Modell und Schwellen einstellen ([contest.md](docs/contest.md)) | mittel |
| Contest-Messung CW | IQ am CQ WW CW (28.–29. November 2026) aufnehmen und gegen RBN auswerten; Ziel: Einsatz am IARU-R1-Fieldday CW (Juni 2027) | klein |
| Contest-Regeln prüfen | Bänder und Details der USKA-Contests (Helvetia, Weihnachtswettbewerb, NMD, SEC) gegen die Reglement-PDFs prüfen | klein |
| KrakenSDR als fünf Empfänger | Die fünf kohärenten Kanäle (24 MHz – 1,7 GHz) als fünf RTL-SDR nutzen, z. B. APRS, POCSAG, ADS-B, AIS und VOX gleichzeitig; am Gerät prüfen: Erkennung über die Seriennummern 1000–1004, Strom und USB-Last, Bias-T | klein |
| KrakenSDR-Peilung | Heimdall DAQ und `krakensdr_doa` (GPL-3) als eigener Container; RadioMoni liest die Peilungen, zeigt sie als Peillinie auf der Karte und speichert sie in Elasticsearch; eine Sperre für alle fünf Kanäle | gross |

## Ideen

- Push-Benachrichtigungen im Browser (Web Push) zusätzlich zu ntfy und Telegram
- Statistik pro Rufzeichen (erste/letzte Sichtung, Heatmap)
- Export nach InfluxDB/Grafana für Sensorwerte aus rtl_433
- Breitband-Überblick im Wasserfall mit `hackrf_sweep` (1 MHz – 6 GHz in einem Bild)
- WebGL-Renderer für den Wasserfall, falls Canvas 2D bei grossen FFTs nicht reicht
- RTTY- und FT8-Spots des RBN (Port 7001) anzeigen
- Contest-Skimmer auf mehreren Bändern gleichzeitig (setzt „Mehrere SDRs“ voraus)
- Multiplikatoren aus dem Austausch (Kantone, Seriennummern) aus dem dekodierten Text lesen
- KrakenSDR: Richtung zu VOX-Aufnahmen, Repeater-Scan und APRS-Paketen speichern (Störer, Missbrauch auf Relais)
- KrakenSDR: Störquellen suchen mit Dauerpeilung, Alarm und Richtungs-Heatmap in Kibana
- KrakenSDR: Kreuzpeilung von zwei Standorten oder mobil mit GPS (Fuchsjagd auf 2 m und 70 cm)
