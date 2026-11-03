# Roadmap

Stand: 2026-11-03 (Version 4.1.0). Erledigtes steht im [CHANGELOG](CHANGELOG.md).

## Offen

| Thema | Beschreibung | Aufwand |
|---|---|---|
| CW-Decoder | | |
| Benutzer und Rollen | Lesende und steuernde Rollen, Login statt API-Key im Browser | mittel |
| APRS-IS-iGate | empfangene Pakete mit Rufzeichen und Passcode an APRS-IS weiterleiten | mittel |
| PPM-Kalibrierung | automatisch an einem bekannten Träger messen und pro Gerät speichern | klein |
| DMR / P25 | Digitalfunk mit dsd-fme (nicht in Debian, eigener Build nötig) | mittel |
| Mehrere SDRs | eine Sperre pro Gerät (Seriennummer), parallele Jobs | mittel |
| Wetterbilder | NOAA-/Meteor-APT- und LRPT-Dekodierung | mittel |

## Ideen

- Push-Benachrichtigungen im Browser (Web Push) zusätzlich zu ntfy und Telegram
- Statistik pro Rufzeichen (erste/letzte Sichtung, Heatmap)
- Export nach InfluxDB/Grafana für Sensorwerte aus rtl_433
- Breitband-Überblick im Wasserfall mit `hackrf_sweep` (1 MHz – 6 GHz in einem Bild)
- WebGL-Renderer für den Wasserfall, falls Canvas 2D bei grossen FFTs nicht reicht
