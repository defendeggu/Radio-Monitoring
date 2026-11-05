# Roadmap

Stand: 2026-11-05 (Version 5.3.0). Erledigtes steht im [CHANGELOG](CHANGELOG.md).

## Offen

| Thema | Beschreibung | Aufwand |
|---|---|---|
| Benutzer und Rollen | Lesende und steuernde Rollen, Login statt API-Key im Browser | mittel |
| APRS-IS-iGate | empfangene Pakete mit Rufzeichen und Passcode an APRS-IS weiterleiten | mittel |
| PPM-Kalibrierung | automatisch an einem bekannten Träger messen und pro Gerät speichern | klein |
| DMR / P25 | Digitalfunk mit dsd-fme (nicht in Debian, eigener Build nötig) | mittel |
| SDRplay RSPduo, ein Tuner (Stufe 2; Stufe 1 „Mehrere SDRs“ ist erledigt) | SDRplay-API 3.x (selbst geladener Installer, `WITH_SDRPLAY=1`), SoapySDR und SoapySDRPlay3, eigener Streamer nach stdout; Antennenwahl (Hi-Z für Kurzwelle), Notch-Filter, Verstärkung; Live-Test sobald das Gerät da ist | mittel |
| SDRplay RSPduo, Dual-Tuner (Stufe 3) | Tuner A und B als zwei Geräte im Master/Slave-Betrieb (vermutlich je 2 MS/s), Regeln für den Stopp des Masters; z. B. Skimmer CW 40 m und SSB 20 m gleichzeitig | mittel |
| Wetterbilder | NOAA-/Meteor-APT- und LRPT-Dekodierung | mittel |
| Contest-Skimmer SSB messen | SSB ist experimentell eingebaut; an echten Contest-Aufnahmen Präzision (Ziel ≥ 90 %) und Ausbeute (≥ 30 %) messen und Prompt, Modell und Schwellen einstellen ([contest.md](docs/contest.md)) | mittel |
| Contest-Messung CW | IQ am CQ WW CW (28.–29. November 2026) aufnehmen und gegen RBN auswerten; Ziel: Einsatz am IARU-R1-Fieldday CW (Juni 2027) | klein |
| Contest-Regeln prüfen | Bänder und Details der USKA-Contests (Helvetia, Weihnachtswettbewerb, NMD, SEC) gegen die Reglement-PDFs prüfen | klein |

## Ideen

- Push-Benachrichtigungen im Browser (Web Push) zusätzlich zu ntfy und Telegram
- Statistik pro Rufzeichen (erste/letzte Sichtung, Heatmap)
- Export nach InfluxDB/Grafana für Sensorwerte aus rtl_433
- Breitband-Überblick im Wasserfall mit `hackrf_sweep` (1 MHz – 6 GHz in einem Bild)
- WebGL-Renderer für den Wasserfall, falls Canvas 2D bei grossen FFTs nicht reicht
- RTTY- und FT8-Spots des RBN (Port 7001) anzeigen
- Contest-Skimmer auf mehreren Bändern gleichzeitig (setzt „Mehrere SDRs“ voraus)
- Multiplikatoren aus dem Austausch (Kantone, Seriennummern) aus dem dekodierten Text lesen
