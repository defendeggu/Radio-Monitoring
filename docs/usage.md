# Bedienung der Weboberfläche

🇬🇧 **[English Version](#english-version)** below

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

---

<a id="english-version"></a>

## English Version

The web interface is in German. UI labels are quoted below in German with the English meaning in parentheses.

Open `http://<host>:8080`. On the first visit the settings dialog appears. Enter the **API key** there (`API_KEYS` in `.env`) and choose the **SDR device**. *Automatisch* (automatic) is usually enough; for a USRP N200 enter its IP address. The settings are only stored in this browser.

At the bottom left of the sidebar you see the SDR status:
- green: device free
- yellow, pulsing: busy, with the name of the job
- red: API not reachable or key missing

Next to it is the state of the live connection (● live).

### Dashboard

Figures per mode, activity per hour, SDR status, the latest alerts and APRS packets, and a live feed of all events. Set the time range at the top right (6 h to 7 days).

### Voice (*Sprache*)

Single recording followed by Whisper transcription.

1. Enter a frequency, e.g. `145.5`, `433.92M` or `118000000`, or click a bookmark.
2. Choose the modulation (FM/AM/USB/LSB), duration (1–600 s) and gain.
3. Optionally under *Whisper-Optionen* (Whisper options): language, beam size and a vocabulary hint (e.g. "HB9" and local place names).
4. *Aufnahme starten* (start recording): the progress bar shows waiting, recording and transcription.

The result shows the text, the segments with timestamps and an audio player with a waveform. *Als ZIP exportieren* (export as ZIP) gives you the WAV, the transcript and the metadata.

### VOX recording (*VOX-Aufnahme*)

For continuously monitoring a voice channel. Recording only happens while a signal is above the noise threshold. Each transmission becomes its own file and is optionally transcribed.

- **Squelch:** distance to the measured noise level in dB. Lower is more sensitive, but triggers falsely more often.
- **Hang time (*Nachlaufzeit*):** the recording stays open this long after the signal ends, so that short pauses do not split a transmission.
- Transmissions longer than 60 s are split into several files.

The list of transmissions updates live. Clicking an entry plays it.

### APRS and POCSAG

- **Continuous operation (streaming):** runs for up to 24 h and stores every packet immediately.
- **Single capture:** records first and decodes afterwards (APRS up to 300 s, POCSAG up to 120 s).

For APRS the map shows the last position of every station. The table also contains the Maidenhead locator. Use the search to filter by callsign (APRS) or RIC address (POCSAG). You can export as CSV, for APRS also as GeoJSON and as KML for Google Earth.

### ADS-B · AIS · ISM

These decoders control the SDR directly: ADS-B an **RTL-SDR or HackRF**, AIS and ISM an **RTL-SDR**. If an RTL-SDR is plugged in next to the HackRF, AIS and ISM use the RTL-SDR.

| Tab | Tool | Display |
|---|---|---|
| ADS-B | readsb (1090 MHz) | aircraft with identifier, altitude and speed, live on the map |
| AIS | rtl_ais (161.975/162.025 MHz) | ships with name and position |
| ISM | rtl_433 (433.92/868 MHz) | weather stations, thermometers, meters (last value per sensor) |

Leaving the gain empty means automatic gain control. The PPM correction is described in [hardware.md](hardware.md#frequency-correction-ppm).

### Repeater scan

Listens to the imported FM repeaters one after another and measures carrier, number of transmissions, activity in % and signal strength.

1. Choose the **canton** (*Kanton*, LU by default, or *Alle Kantone* for all cantons). The active FM repeaters of the canton appear below; untick the ones you want to skip.
2. **Scan duration** (*Dauer des Scans*): *Ein Durchgang* (one round), 30 minutes to 24 hours, or *Bis Stopp* (until stopped). With a duration, the repeaters are scanned again and again in rounds; a repeater is only started if its measurement ends before the duration is over.
3. Set the **seconds per repeater** (*Sekunden pro Repeater*, 5–600). The line above the list shows how long one round takes.
4. *Scan starten* (start scan). *Stopp* ends the scan immediately, even in the middle of a measurement.

The result table summarizes all rounds per repeater (measurements, those with a carrier, transmissions, average activity). Every single measurement is stored in `radio-repeater-activity-*` (Kibana: *RadioMoni · Repeater-Scan*). The table *Aktivste Repeater* (most active repeaters) shows the repeaters where a carrier was measured in the last 7 days. Import the repeater list with `./scripts/run_import.sh`.

### Multi-channel (USRP N200 only)

Only appears when *USRP N200* is selected in the settings. Enter the center frequency, the bandwidth and 2 to 8 channels (APRS/POCSAG). Channels outside the bandwidth are marked red.

### Recordings (*Aufnahmen*)

All WAV files with size and date. A click opens the player and, if available, the transcript. You can also download and delete files here. At the top you see the disk usage, the free space and the retention period.

### Bookmarks (*Lesezeichen*)

Your own frequencies with mode, modulation, tags and a note. Clicking the name opens the matching page with the frequency filled in. Import and export use JSON. As long as there are no bookmarks of your own, default frequencies are offered.

### Alerts (*Alarme*)

A rule consists of a source (e.g. POCSAG), a field (e.g. text), a comparison (contains, equals or regular expression) and a pattern. In addition there are the channels and a pause, so that the same rule does not fire every second. Triggered alerts appear as a notification in the interface, in the list and on the dashboard. *Test senden* (send test) checks the configured channels.

Examples:
- A specific callsign on APRS: source APRS, field callsign, *contains* `HB9XYZ`
- A keyword in radio traffic: source voice, field text, *regular expression* `\b(mayday|notfall)\b`

### Schedules (*Zeitpläne*)

Starts actions with a cron expression (`minute hour day month weekday`, time zone `TZ`). The parameters are the same as in the API; when you change the action, a template is inserted. If the SDR is busy at the start time, the schedule waits up to 60 s and is skipped otherwise. The column *Letzter Lauf* (last run) shows the reason. ▶ runs a schedule immediately.

### API

Lists all endpoints with parameters and body fields, including a `curl` command you can copy. The list is generated from `/api/openapi.json`.

### Appearance

In the settings you choose between system, dark and light. The sidebar can be collapsed. On a phone the ☰ icon opens the navigation.
