# Bedienung der Weboberfläche

Öffne `http://<host>:8080`. Beim ersten Aufruf erscheint der Einstellungsdialog. Trage dort den **API-Key** ein (`API_KEYS` in `.env`) und wähle das **SDR-Gerät**. *Automatisch* genügt meist, für einen USRP N200 die IP-Adresse eintragen. Die Einstellungen bleiben nur in diesem Browser gespeichert.

Unten links in der Seitenleiste siehst du den SDR-Status:
- grün: Gerät frei
- gelb, pulsierend: belegt, mit Angabe des Jobs
- rot: API nicht erreichbar oder Key fehlt

Daneben steht der Zustand der Live-Verbindung (● live).

## Dashboard

Kennzahlen pro Betriebsart, Aktivität pro Stunde, SDR-Status, die letzten Alarme und APRS-Pakete sowie ein Live-Feed aller Ereignisse. Den Zeitraum stellst du oben rechts ein (6 h bis 7 Tage).

## Sprache

Einzelaufnahme mit anschliessender Whisper-Transkription.

1. Frequenz eingeben, z. B. `145.5`, `433.92M` oder `118000000`, oder ein Lesezeichen anklicken.
2. Modulation (FM/AM/USB/LSB), Dauer (1–600 s) und Verstärkung wählen.
3. Optional unter *Whisper-Optionen*: Sprache, Beam size und ein Vokabular-Hinweis (z. B. „HB9“ und lokale Ortsnamen).
4. *Aufnahme starten*: Der Fortschrittsbalken zeigt Warten, Aufnahme und Transkription.

Das Ergebnis zeigt den Text, die Segmente mit Zeitstempeln und einen Audio-Player mit Wellenform. Über *Als ZIP exportieren* bekommst du WAV, Transkript und Metadaten.

## VOX-Aufnahme

Für die Dauerüberwachung eines Sprachkanals. Aufgezeichnet wird nur, solange ein Signal über der Rauschschwelle liegt. Jeder Durchgang wird eine eigene Datei und wird optional transkribiert.

- **Squelch:** Abstand zum gemessenen Rauschpegel in dB. Niedriger ist empfindlicher, löst aber häufiger fehl aus.
- **Nachlaufzeit:** So lange bleibt die Aufnahme nach dem Signalende offen, damit kurze Pausen einen Durchgang nicht zerteilen.
- Durchgänge über 60 s werden in mehrere Dateien aufgeteilt.

Die Liste der Durchgänge aktualisiert sich live. Ein Klick auf einen Eintrag spielt ihn ab.

## APRS und POCSAG

- **Dauerbetrieb (Streaming):** läuft bis zu 24 h und speichert jedes Paket sofort.
- **Einzelaufnahme:** zeichnet auf und dekodiert anschliessend (APRS bis 300 s, POCSAG bis 120 s).

Bei APRS zeigt die Karte die letzte Position jeder Station. Die Tabelle enthält zusätzlich den Maidenhead-Locator. Über die Suche filterst du nach Rufzeichen (APRS) bzw. RIC-Adresse (POCSAG). Exportieren kannst du als CSV, bei APRS zusätzlich als GeoJSON und KML für Google Earth.

## ADS-B · AIS · ISM

Diese Decoder steuern das SDR direkt: ADS-B einen **RTL-SDR oder HackRF**, AIS und ISM einen **RTL-SDR**. Steckt neben dem HackRF ein RTL-SDR, nehmen AIS und ISM den RTL-SDR.

| Reiter | Werkzeug | Anzeige |
|---|---|---|
| ADS-B | readsb (1090 MHz) | Flugzeuge mit Kennung, Höhe und Geschwindigkeit, live auf der Karte |
| AIS | rtl_ais (161.975/162.025 MHz) | Schiffe mit Name und Position |
| ISM | rtl_433 (433.92/868 MHz) | Wetterstationen, Thermometer, Zähler (letzter Wert pro Sensor) |

Die Verstärkung leer lassen heisst automatische Regelung. Die PPM-Korrektur ist beschrieben in [hardware.md](hardware.md#frequenzkorrektur-ppm).

## Repeater-Scan

Hört die importierten FM-Relais nacheinander ab und misst Träger, Anzahl Durchgänge, Aktivität in % und Signalstärke.

1. **Kanton** wählen (voreingestellt LU, oder *Alle Kantone*). Darunter erscheinen die aktiven FM-Relais des Kantons; mit den Häkchen wählst du einzelne ab.
2. **Dauer des Scans:** *Ein Durchgang*, 30 Minuten bis 24 Stunden, oder *Bis Stopp*. Bei einer Dauer werden die Relais in Runden immer wieder abgehört; ein Relais wird nur noch begonnen, wenn seine Messung vor Ablauf der Dauer endet.
3. **Sekunden pro Repeater** einstellen (5–600). Die Zeile über der Liste zeigt, wie lange eine Runde dauert.
4. **Scan starten.** *Stopp* beendet den Scan sofort, auch mitten in einer Messung.

Die Ergebnistabelle fasst alle Runden pro Relais zusammen (Messungen, davon mit Träger, Durchgänge, Ø Aktivität). Jede einzelne Messung landet in `radio-repeater-activity-*` (Kibana: *RadioMoni · Repeater-Scan*). Die Tabelle *Aktivste Repeater* zeigt die Relais, bei denen in den letzten 7 Tagen ein Träger gemessen wurde. Die Repeater-Liste importierst du mit `./scripts/run_import.sh`.

## Multi-Channel (nur USRP N200)

Erscheint erst, wenn in den Einstellungen *USRP N200* gewählt ist. Gib Mittenfrequenz, Bandbreite und 2 bis 8 Kanäle (APRS/POCSAG) an. Kanäle ausserhalb der Bandbreite werden rot markiert.

## Aufnahmen

Alle WAV-Dateien mit Grösse und Datum. Ein Klick öffnet den Player und, falls vorhanden, das Transkript. Hier kannst du auch herunterladen und löschen. Oben stehen Speicherbedarf, freier Platz und die Aufbewahrungsdauer.

## Lesezeichen

Eigene Frequenzen mit Betriebsart, Modulation, Tags und Notiz. Ein Klick auf den Namen öffnet die passende Seite mit vorausgefüllter Frequenz. Import und Export erfolgen als JSON. Solange keine eigenen Lesezeichen existieren, werden Standard-Frequenzen angeboten.

## Alarme

Eine Regel besteht aus Quelle (z. B. POCSAG), Feld (z. B. Text), Vergleich (enthält, ist gleich oder regulärer Ausdruck) und Muster. Dazu kommen die Kanäle und eine Pause, damit dieselbe Regel nicht im Sekundentakt meldet. Ausgelöste Alarme erscheinen als Hinweis in der Oberfläche, in der Liste und im Dashboard. Mit *Test senden* prüfst du die konfigurierten Kanäle.

Beispiele:
- Ein bestimmtes Rufzeichen auf APRS: Quelle APRS, Feld Rufzeichen, *enthält* `HB9XYZ`
- Stichwort im Funkverkehr: Quelle Sprache, Feld Text, *regulärer Ausdruck* `\b(mayday|notfall)\b`

## Zeitpläne

Startet Aktionen per Cron-Ausdruck (`Minute Stunde Tag Monat Wochentag`, Zeitzone `TZ`). Die Parameter sind dieselben wie in der API, beim Wechsel der Aktion wird eine Vorlage eingefügt. Ist das SDR zum Startzeitpunkt belegt, wartet der Zeitplan bis zu 60 s und wird sonst übersprungen. Den Grund zeigt die Spalte *Letzter Lauf*. Mit ▶ führst du einen Zeitplan sofort aus.

## API

Listet alle Endpunkte mit Parametern und Body-Feldern auf, inklusive kopierbarem `curl`-Befehl. Die Liste wird aus `/api/openapi.json` erzeugt.

## Darstellung

In den Einstellungen wählst du zwischen System, Dunkel und Hell. Die Seitenleiste lässt sich einklappen. Auf dem Handy öffnet das ☰-Symbol die Navigation.
