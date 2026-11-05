# Bedienung der Weboberfläche

🇬🇧 **[English Version](#english-version)** below

Öffne `http://<host>:8080`. Beim ersten Aufruf erscheint der Einstellungsdialog. Trage dort den **API-Key** ein (`API_KEYS` in `.env`) und wähle das **SDR-Gerät**. *Automatisch* genügt meist, für einen USRP N200 die IP-Adresse eintragen. Die Einstellungen bleiben nur in diesem Browser gespeichert.

Unten links in der Seitenleiste siehst du den SDR-Status:
- grün: Gerät frei
- gelb, pulsierend: belegt, mit Angabe des Jobs
- rot: API nicht erreichbar oder Key fehlt

Daneben steht der Zustand der Live-Verbindung (● live).

Mit mehreren SDRs zeigt die Seitenleiste jedes Gerät mit seinem Zustand, und jede Startseite bekommt die Auswahl *SDR*. Jobs auf verschiedenen Geräten laufen gleichzeitig. Auf der Seite *Contest-Skimmer* stehen laufende Skimmer als Reiter, *Weiteren Skimmer starten* öffnet das Formular für das nächste Gerät (siehe [hardware.md](hardware.md#mehrere-sdrs-gleichzeitig)).

## Dashboard

Kennzahlen pro Betriebsart, Aktivität pro Stunde, SDR-Status, die letzten Alarme und APRS-Pakete sowie ein Live-Feed aller Ereignisse. Den Zeitraum stellst du oben rechts ein (6 h bis 7 Tage).

## Spektrum

Wasserfall eines Frequenzbereichs mit Mithören. Der Wasserfall belegt das SDR nur, solange es niemand anders braucht: Startest du einen Job (Aufnahme, VOX, APRS, Zeitplan …), wird er automatisch beendet. In der Seitenleiste steht dann „Wasserfall — frei für Jobs“.

1. Mittenfrequenz, Bandbreite (HackRF 2–10 MHz, RTL-SDR bis 2,4 MHz, Airspy HF+ 768 kHz), Verstärkung und FFT-Grösse wählen oder ein Band antippen, dann *Wasserfall starten*.
2. Oben das Spektrum (gemittelt, grau die Spitzenwerte), darunter der Wasserfall. *Auto-Pegel* passt den Farbbereich laufend an.
3. **Bedienung:** Klick stimmt den Mithör-Kanal ab, Ziehen verschiebt die Mittenfrequenz, das Mausrad zoomt. Mit der Tastatur: Pfeiltasten stimmen ab (Umschalt = 10×), `+`/`-` zoomen. Lesezeichen erscheinen als violette Marken, auf Kurzwelle die CW-Spots des Reverse Beacon Network als orange Marken mit Rufzeichen (siehe [configuration.md](configuration.md#reverse-beacon-network-cw-spots)). Ein Klick auf eine Marke stimmt genau auf deren Frequenz ab.
4. **Mithören:** *Hören* startet den Ton im Browser (FM, AM, USB, LSB oder CW mit 250/500/1000 Hz Filter, optional Squelch). Die Verzögerung liegt bei etwa einer halben Sekunde.
5. *Aufnehmen*, *VOX starten* und *CW dekodieren* öffnen die jeweilige Seite mit der Frequenz des Kanals.

Ist niemand mehr verbunden, endet der Wasserfall nach einer Minute und gibt das SDR frei. Läuft eine VOX- oder CW-Session, kannst du ihr Spektrum ansehen (*Laufende Session ansehen*), ohne sie zu stören.

## CW

Morse live dekodieren, gedacht für Kurzwelle (passendes SDR und Antenne siehe [hardware.md](hardware.md#kurzwelle-cw-ssb)).

1. Band antippen (CW-Segmente nach IARU Region 1) oder Frequenz eingeben, dazu Verstärkung, erwartetes Tempo (der Decoder passt sich an), Decoder-Filter (100–500 Hz) und Tonhöhe beim Mithören. *Durchgänge als WAV speichern* legt jeden Durchgang als Aufnahme ab.
2. *CW-Decoder starten.* Der Text erscheint live, darüber Tempo (WPM), Signal-Rausch-Abstand und die automatische Nachführung (AFC, ±300 Hz). *Mithören* spielt den Ton im Browser.
3. Ein Durchgang endet nach 3 s Funkstille. Er landet mit Text, Rufzeichen, Tempo und Frequenz in der Liste, in `radio-cw-*` (Kibana: *RadioMoni · CW*) und bei den Alarmregeln (Quelle *CW*).
4. **RBN-Spots:** Rechts zeigt das Fenster die CW-Stationen, die das [Reverse Beacon Network](https://www.reversebeacon.net/) in den letzten 15 Minuten auf dem Band gehört hat (Rufzeichen, SNR, Tempo, Anzahl Skimmer). **Ein Klick auf einen Spot stellt den Empfänger sofort auf dessen Frequenz** – läuft noch keine CW-Session, startet sie. Belegt ein anderer Job das SDR, fragt die Seite, ob er gestoppt werden soll. Spots auf der aktuellen Frequenz sind grün hervorgehoben. Einrichten: [configuration.md](configuration.md#reverse-beacon-network-cw-spots).
5. Im kleinen Wasserfall stimmt ein Klick ebenfalls um; die NCDXF-Baken sind als Testsignale markiert.

Zuverlässig dekodiert wird ab etwa 10 dB Signal-Rausch-Abstand im Decoder-Filter und bis etwa 30 WPM. Schwächere Signale ergeben einzelne falsche Zeichen, im reinen Rauschen erscheinen gelegentlich `E` und `T`.

## Contest-Skimmer

Alle CW-Signale eines Bandsegments gleichzeitig dekodieren. Die Rufzeichen werden gegen das Contest-Reglement und das eigene Log eingestuft und als Spots gemeldet: in der Liste, im Wasserfall, als Alarm und über einen DX-Cluster in die Bandmap von N1MM+. Contest wählen, Band antippen, *Skimmer starten*. Rote Spots sind neue Multiplikatoren oder seltene Stationen, graue Doppelte. Ein Klick öffnet die CW-Seite auf der Frequenz. In der Betriebsart *SSB* (experimentell) hört Whisper die Sprachkanäle ab; ein Klick auf einen SSB-Spot zeigt den gehörten Text und den Ausschnitt zum Nachhören. Einrichtung, Reglement und Schutz des SDR vor dem eigenen Sender: [contest.md](contest.md).

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

## Sprache und Darstellung

Die Oberfläche gibt es auf Deutsch und Englisch. Sie richtet sich nach der Sprache des Browsers; umschalten kannst du mit dem Knopf **EN/DE** unten in der Seitenleiste oder unter *Einstellungen → Sprache / Language*. Die Wahl bleibt im Browser gespeichert.

In den Einstellungen wählst du ausserdem zwischen System, Dunkel und Hell. Die Seitenleiste lässt sich einklappen. Auf dem Handy öffnet das ☰-Symbol die Navigation.

---

<a id="english-version"></a>

## English Version

The web interface is available in German and English. It follows the browser language; switch it with the **EN/DE** button at the bottom of the sidebar or under *Settings → Sprache / Language*. The choice is stored in the browser.

Open `http://<host>:8080`. On the first visit the settings dialog appears. Enter the **API key** there (`API_KEYS` in `.env`) and choose the **SDR device**. *Detect automatically* is usually enough; for a USRP N200 enter its IP address. The settings are only stored in this browser.

At the bottom left of the sidebar you see the SDR status:
- green: device free
- yellow, pulsing: busy, with the name of the job
- red: API not reachable or key missing

Next to it is the state of the live connection (● live).

With several SDRs the sidebar shows every device with its state, and every start page gets a *SDR* selection. Jobs on different devices run at the same time. On the *Contest skimmer* page running skimmers appear as tabs; *Start another skimmer* opens the form for the next device (see [hardware.md](hardware.md#several-sdrs-at-the-same-time)).

### Dashboard

Figures per mode, activity per hour, SDR status, the latest alerts and APRS packets, and a live feed of all events. Set the time range at the top right (6 h to 7 days).

### Spectrum

Waterfall of a frequency range with live listening. The waterfall only uses the SDR while nobody else needs it: when you start a job (recording, VOX, APRS, schedule …) it is stopped automatically. The sidebar then shows "Waterfall — free for jobs".

1. Choose the centre frequency, bandwidth (HackRF 2–10 MHz, RTL-SDR up to 2.4 MHz, Airspy HF+ 768 kHz), gain and FFT size or tap a band, then *Start waterfall*.
2. The spectrum (averaged, peaks in grey) is on top, the waterfall below. *Auto level* keeps adjusting the colour range.
3. **Controls:** click tunes the listening channel, drag moves the centre frequency, the mouse wheel zooms. Keyboard: arrow keys tune (Shift = 10×), `+`/`-` zoom. Bookmarks appear as purple markers; on shortwave the CW spots of the Reverse Beacon Network appear as orange markers with callsign (see [configuration.md](configuration.md#reverse-beacon-network-cw-spots-1)). A click on a marker tunes exactly to its frequency.
4. **Listening:** *Listen* plays the audio in the browser (FM, AM, USB, LSB or CW with a 250/500/1000 Hz filter, optional squelch). The delay is about half a second.
5. *Record*, *Start VOX* and *Decode CW* open the respective page with the channel frequency.

When nobody is connected anymore, the waterfall stops after one minute and frees the SDR. While a VOX or CW session runs you can watch its spectrum (*Watch a running session*) without disturbing it.

### CW

Decode Morse live, meant for shortwave (suitable SDR and antenna see [hardware.md](hardware.md#shortwave-cw-ssb)).

1. Tap a band (CW segments of the IARU Region 1 band plan) or enter a frequency, plus gain, expected speed (the decoder adapts), decoder filter (100–500 Hz) and the pitch for listening. *Save transmissions as WAV* stores every transmission as a recording.
2. *Start CW decoder.* The text appears live, above it the speed (WPM), signal-to-noise ratio and the automatic frequency control (AFC, ±300 Hz). *Listen* plays the tone in the browser.
3. A transmission ends after 3 s of silence. It goes into the list with text, callsigns, speed and frequency, into `radio-cw-*` (Kibana: *RadioMoni · CW*) and to the alert rules (source *CW*).
4. **RBN spots:** the window on the right shows the CW stations the [Reverse Beacon Network](https://www.reversebeacon.net/) heard on the band in the last 15 minutes (callsign, SNR, speed, number of skimmers). **A click on a spot tunes the receiver to its frequency right away** – if no CW session runs yet, it starts one. If another job holds the SDR, the page asks whether to stop it. Spots on the current frequency are highlighted in green. Setup: [configuration.md](configuration.md#reverse-beacon-network-cw-spots-1).
5. A click in the small waterfall also retunes; the NCDXF beacons are marked as test signals.

Decoding is reliable from about 10 dB signal-to-noise ratio in the decoder filter and up to about 30 WPM. Weaker signals give single wrong characters; pure noise occasionally shows `E` and `T`.

### Contest skimmer

Decode every CW signal of a band segment at once. The callsigns are classified against the contest rules and your log and reported as spots: in the list, in the waterfall, as an alert and through a DX cluster to the N1MM+ bandmap. Select the contest, pick the band, *Start skimmer*. Red spots are new multipliers or rare stations, grey ones dupes. A click opens the CW page on the frequency. In *SSB* mode (experimental) Whisper listens to the voice channels; a click on an SSB spot shows the heard text and the clip to listen back. Setup, contest rules and protecting the SDR from your own transmitter: [contest.md](contest.md#english-version).

### Voice

Single recording followed by Whisper transcription.

1. Enter a frequency, e.g. `145.5`, `433.92M` or `118000000`, or click a bookmark.
2. Choose the modulation (FM/AM/USB/LSB), duration (1–600 s) and gain.
3. Optionally under *Show Whisper options*: language, beam size and a vocabulary hint (e.g. "HB9" and local place names).
4. *Start recording*: the progress bar shows waiting, recording and transcription.

The result shows the text, the segments with timestamps and an audio player with a waveform. *Export as ZIP* gives you the WAV, the transcript and the metadata.

### VOX recording

For continuously monitoring a voice channel. Recording only happens while a signal is above the noise threshold. Each transmission becomes its own file and is optionally transcribed.

- **Squelch:** distance to the measured noise level in dB. Lower is more sensitive, but triggers falsely more often.
- **Hang time:** the recording stays open this long after the signal ends, so that short pauses do not split a transmission.
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

1. Choose the **canton** (LU by default, or *All cantons*). The active FM repeaters of the canton appear below; untick the ones you want to skip.
2. **Scan duration:** *One round*, 30 minutes to 24 hours, or *Until stopped*. With a duration, the repeaters are scanned again and again in rounds; a repeater is only started if its measurement ends before the duration is over.
3. Set the **seconds per repeater** (5–600). The line above the list shows how long one round takes.
4. *Start scan*. *Stop* ends the scan immediately, even in the middle of a measurement.

The result table summarizes all rounds per repeater (measurements, those with a carrier, transmissions, average activity). Every single measurement is stored in `radio-repeater-activity-*` (Kibana: *RadioMoni · Repeater-Scan*). The table *Most active repeaters* shows the repeaters where a carrier was measured in the last 7 days. Import the repeater list with `./scripts/run_import.sh`.

### Multi-channel (USRP N200 only)

Only appears when *USRP N200* is selected in the settings. Enter the center frequency, the bandwidth and 2 to 8 channels (APRS/POCSAG). Channels outside the bandwidth are marked red.

### Recordings

All WAV files with size and date. A click opens the player and, if available, the transcript. You can also download and delete files here. At the top you see the disk usage, the free space and the retention period.

### Bookmarks

Your own frequencies with mode, modulation, tags and a note. Clicking the name opens the matching page with the frequency filled in. Import and export use JSON. As long as there are no bookmarks of your own, default frequencies are offered.

### Alerts

A rule consists of a source (e.g. POCSAG), a field (e.g. text), a comparison (contains, equals or regular expression) and a pattern. In addition there are the channels and a pause, so that the same rule does not fire every second. Triggered alerts appear as a notification in the interface, in the list and on the dashboard. *Send test* checks the configured channels.

Examples:
- A specific callsign on APRS: source APRS, field callsign, *contains* `HB9XYZ`
- A keyword in radio traffic: source voice, field text, *regular expression* `\b(mayday|notfall)\b`

### Schedules

Starts actions with a cron expression (`minute hour day month weekday`, time zone `TZ`). The parameters are the same as in the API; when you change the action, a template is inserted. If the SDR is busy at the start time, the schedule waits up to 60 s and is skipped otherwise. The column *Last run* shows the reason. ▶ runs a schedule immediately.

### API

Lists all endpoints with parameters and body fields, including a `curl` command you can copy. The list is generated from `/api/openapi.json`.

### Language and appearance

In the settings you also choose between system, dark and light. The sidebar can be collapsed. On a phone the ☰ icon opens the navigation.
