# Contest-Skimmer

🇬🇧 **[English Version](#english-version)** below

Der Contest-Skimmer läuft am Contest neben der eigenen Station mit einem eigenen SDR und einer eigenen Empfangsantenne:

- **Dekodieren:** Er dekodiert alle CW-Signale eines Bandsegments gleichzeitig.
- **Spot erzeugen:** Er liest die Rufzeichen und bestätigt sie mehrfach, bevor sie als Spot gelten.
- **Einstufen:** Jeden Spot prüft er gegen das Contest-Reglement und das eigene Log.
- **Melden:**
  - in die Bandmap von N1MM+ (über einen eingebauten DX-Cluster),
  - auf der Seite *Contest-Skimmer*,
  - per Alarm (ntfy, Telegram, E-Mail, Webhook).

SSB folgt erst, wenn die Messung (Phase 0, siehe unten) zeigt, dass Whisper auf Contest-SSB genug Rufzeichen richtig erkennt.

## Vor dem Einsatz

### Reglement

Ein eigener Skimmer gilt in fast allen Contests als Hilfe („Assisted“, „Assistance“). In Multi-Op-Kategorien ist das meist erlaubt, in Single-Op-„Unassisted“ nicht. Das gleiche gilt für die RBN-Spots, die der Skimmer auf Wunsch dazunimmt. Die Seite zeigt zu jedem Contest einen Hinweis. Massgebend ist die aktuelle Ausschreibung der gewählten Kategorie.

### Schutz des SDR

Ein Sender mit 100 W oder mehr wenige Meter neben dem SDR übersteuert es oder zerstört den Eingang.

- **Antenne:** Eine eigene Empfangsantenne mit Abstand, zum Beispiel eine aktive Loop, möglichst quer zur Sendeantenne.
- **Schutzschaltung:** Preselektor oder Bandpass und ein Empfänger-Begrenzer vor dem SDR.
- **Ausblenden:** RadioMoni blendet die Auswertung aus, solange N1MM+ sendet (`IsTransmitting`) oder das SDR übersteuert. N1MM+ meldet `IsTransmitting` aber nur, wenn es selbst tastet. Fussschalter und Paddle sieht es nicht, für diese Fälle bleibt nur die Erkennung der Übersteuerung.

Diese Software-Massnahmen ersetzen den Hardware-Schutz nicht.

### Hardware

| SDR | Segment | Bemerkung |
|---|---|---|
| Airspy HF+ | bis etwa 600 kHz | Empfehlung für Kurzwelle; ein ganzes CW- und SSB-Segment eines Bandes |
| HackRF | bis etwa 800 kHz | auf Kurzwelle unempfindlich und leicht übersteuert, nur für Tests |
| RTL-SDR | bis etwa 500 kHz | unter 24 MHz mit Direct Sampling, mässige Empfindlichkeit |

Ein CW-Segment (zum Beispiel 14,000–14,070 MHz) braucht etwa einen halben CPU-Kern für 24 Decoder.

## Einrichten

1. **Referenzdaten laden:** Auf der Seite *Contest-Skimmer* unter *Referenzdaten* auf *Aktualisieren* klicken. Alternativ:
   ```bash
   docker compose exec radio-api python -m radiomoni.contest.refdata --update
   ```
   Geladen werden `cty.csv` (Land, Zonen), `MASTER.SCP` (aktive Contest-Rufzeichen) und die Most-Wanted-Liste von Club Log. Sie liegen im Volume `api-data`, also auch ohne Internet am Contest-Platz. Am besten einige Tage vor dem Contest aktualisieren.
2. **`.env` ergänzen** (siehe [configuration.md](configuration.md#contest-skimmer)), danach `docker compose up -d radio-api`:
   ```bash
   SKIMMER_CALLSIGN=HB9XYZ        # Spotter in den Cluster-Zeilen (sonst RBN_CALLSIGN)
   CLUSTER_ENABLED=true           # DX-Cluster für die N1MM+-Bandmap, TCP 7300
   N1MM_ENABLED=true              # N1MM+-Broadcasts empfangen, UDP 12060
   N1MM_ALLOWED=192.168.1.0/24    # nur Pakete aus dem Contest-Netz
   CONTEST_BIND=0.0.0.0           # beide Ports im LAN öffnen (Standard: nur dieser Rechner)
   ```
3. **N1MM+ einrichten** (Windows-PC im selben Netz):
   - *Config → Configure Ports… → Broadcast Data*: *Radio* und *Contacts* einschalten, als Ziel `IP-des-RadioMoni-Rechners:12060`.
   - Im *Telnet*-Fenster einen Cluster `IP-des-RadioMoni-Rechners:7300` anlegen und verbinden. Nach dem Login erscheinen die Spots in der Bandmap, ein Klick stellt den Transceiver ein.
4. **Log importieren:** Wer nicht von Anfang an mit N1MM+ verbunden ist, importiert das Log auf der Seite (*ADIF / Cabrillo importieren*). Neue QSOs kommen danach live von N1MM+ dazu, auch von mehreren Logplätzen.

## Am Contest

1. **Contest wählen.** Die Regeln bestimmen Bänder, Multiplikatoren und Doppelte. Sie stehen in `radiomoni/contest/rules/*.yaml`:

   | Contest | Multiplikatoren | Doppelte |
   |---|---|---|
   | IARU Region 1 Fieldday CW / SSB | DXCC pro Band, `/P` hervorgehoben | pro Band |
   | IARU HF World Championship | ITU-Zone pro Band (HQ-Stationen nicht erkennbar) | pro Band und Betriebsart |
   | CQ WW DX CW / SSB | CQ-Zone und DXCC pro Band | pro Band |
   | CQ WPX CW / SSB | WPX-Präfix einmal pro Contest | pro Band |
   | USKA Helvetia Contest | DXCC pro Band, Schweizer Stationen hervorgehoben (Kantone kommen aus dem Austausch und sind nicht erkennbar) | pro Band und Betriebsart |
   | Allgemein | keine, nur neue und seltene Stationen | pro Band und Betriebsart |

   Der Field Day der USKA ist der IARU-Region-1-Fieldday. Die Regeln des Helvetia Contest sind nicht gegen das aktuelle Reglement-PDF geprüft, weil dessen Download hinter einer Bot-Prüfung liegt. Für Weihnachtswettbewerb und NMD gibt es noch keine Regeldatei. Eine neue Datei im Ordner `rules/` genügt, das Format steht in `radiomoni/contest/rules.py`.
2. **Band wählen und *Skimmer starten*.**
   - Das SDR wird neben das CW-Segment gelegt, damit die DC-Spitze nicht stört.
   - Ein laufender Wasserfall weicht.
   - *Laufzeit 0* läuft bis zum Stoppen, höchstens 72 h.
   - Startet ein Zeitplan den Skimmer (Aktion `skimmer`), beginnt er pünktlich mit dem Contest.
3. **Spots lesen.** Die Liste zeigt Alter, Frequenz, Rufzeichen, Land, Tempo, SNR und Hinweise:

   | Hinweis | Bedeutung |
   |---|---|
   | **MULT** (rot) | neuer Multiplikator; der Tooltip nennt ihn |
   | **RARE #n** | DXCC-Gebiet auf Platz n der Most-Wanted-Liste (bis `SKIMMER_RARE_RANK`, Standard 100) |
   | **DUPE** (grau) | schon im Log |
   | **/P**, **HB** | portabel bzw. Schweizer Station, wenn der Contest das hervorhebt |
   | **?SCP** | nicht in MASTER.SCP: echt, aber selten im Contest, oder falsch gelesen |

   Im Wasserfall sind neue Multiplikatoren und seltene Stationen rot markiert, Doppelte grau, alle anderen orange. Ein Klick auf einen Spot öffnet die CW-Seite auf dessen Frequenz zum Mithören.
4. **Alarme:** Nur Spots mit hoher Priorität (Multiplikator oder selten) erreichen die Alarmregeln, Quelle `skimmer`. Eine Regel wie *Feld Text enthält MULT* mit einer Pause von einigen Minuten verhindert, dass der Operator mit Meldungen überflutet wird.

### Wann wird aus einem Rufzeichen ein Spot?

Ein falscher Spot kostet den Operator mehr als ein verpasster. Darum zählt eine einzelne Dekodierung nie:

- **Station selbst:** Gezählt wird nur ein Rufzeichen, das die Station selbst sendet, also nach `CQ`, `TEST`, `DE`, `TU`, `QRZ` oder zweimal hintereinander. Ein Rufzeichen, das die Run-Station ihrem Partner zusammen mit dem Rapport schickt, zählt nicht.
- **Prüfung:** Das Rufzeichen muss zu einem DXCC-Gebiet gehören, sofern `cty.csv` geladen ist.
- **Hits:** Nötig sind zwei Treffer auf (fast) derselben Frequenz innerhalb von 10 Minuten. Kennt MASTER.SCP das Rufzeichen nicht, braucht es drei. Kennt MASTER.SCP es und kam es nach `CQ`/`TEST`, genügt einer.
- **Wiederholung:** Dieselbe Station wird nach 10 Minuten erneut gemeldet, wie bei RBN.

## Phase 0: messen, ob es reicht

Bevor der Skimmer am Contest zählt, wird er an echten Aufnahmen gemessen, mit Präzision und Ausbeute getrennt:

- **Präzision:** Anteil der richtigen Spots. Ziel: mindestens 90 %.
- **Ausbeute:** Anteil der gefundenen Stationen. Ziel für SSB: mindestens 30 %.

### CW

1. **Aufnehmen:** Den Skimmer an einem Contest-Wochenende (zum Beispiel CQ WW CW) mit *IQ des Segments aufnehmen* und eingeschaltetem RBN (`RBN_ENABLED=true`) laufen lassen.
2. **Dateien:** Unter `recordings/skimmer/` entstehen drei Dateien:
   - die WAV-Datei mit dem Segment (etwa 1,4 GB pro Stunde),
   - eine JSON-Datei mit Mittenfrequenz und Abtastrate,
   - `*.rbn.jsonl`, die RBN-Spots aus derselben Zeit als Referenz.
3. **Auswerten:**
   ```bash
   docker compose exec radio-api python -m radiomoni.skimmer.evaluate cw \
     recordings/skimmer/skimmer_20261128_120000_14035kHz.wav
   ```
   Die Ausgabe nennt Präzision, Ausbeute und die Rufzeichen, die RBN nicht kennt. Diese sind nicht automatisch falsch: RBN hört nicht alles, was die eigene Antenne hört. Sie lohnt sich deshalb von Hand anzusehen.

### SSB

SSB-Ausschnitte (WAV) und eine Textdatei mit den Rufzeichen, die darin vorkommen:
```bash
docker compose exec radio-api python -m radiomoni.skimmer.evaluate ssb --reference calls.txt \
  --model turbo --hotwords "Alfa Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliett Kilo Lima Mike" \
  --prompt "CQ contest, five nine, QRZ" clips/*.wav
```
Ausgegeben werden die Werte für alle erkannten Rufzeichen (`raw`) und für die bestätigten (`confirmed`). Bestätigt heisst: Das Rufzeichen kam nach CQ, „contest“, „this is“ und Ähnlichem, oder es ist mindestens zweimal gefallen. Am besten mehrere Modelle (`small`, `turbo`, `large-v3`) mit und ohne `--prompt`/`--hotwords` vergleichen.

## Grenzen

- **Nur CW:** Live gibt es nur CW. SSB folgt nach der Messung.
- **Multiplikatoren aus dem Austausch:** Kantone, Seriennummern und HQ-Stationen sind am Rufzeichen nicht erkennbar.
- **Ein SDR, ein Segment:** Mehrere Bänder brauchen mehrere SDRs, das steht in der Roadmap unter „Mehrere SDRs“.
- **Ein Logprogramm:** Den Cluster versteht jedes Logprogramm. „Schon gearbeitet“ und das Ausblenden beim Senden gibt es nur mit N1MM+.

---

## English Version

The contest skimmer runs next to the contest station with its own SDR and its own receive antenna:

- **Decoding:** It decodes every CW signal of a band segment at once.
- **Spotting:** It reads the callsigns and confirms each one several times before it counts as a spot.
- **Classifying:** It checks every spot against the contest rules and your log.
- **Reporting:**
  - to the N1MM+ bandmap (through a built-in DX cluster),
  - on the *Contest skimmer* page,
  - as an alert (ntfy, Telegram, e-mail, webhook).

SSB follows once the evaluation (phase 0, see below) shows that Whisper reads enough callsigns correctly on contest SSB.

### Before you use it

**Rules.** In almost every contest a skimmer of your own counts as assistance ("assisted"). That is usually allowed in multi-operator categories and not in single-operator "unassisted". The same applies to the RBN spots the skimmer can add. The page shows a note for each contest. The current rules of your category decide.

**Protect the SDR.** A transmitter with 100 W or more a few metres away overloads the SDR or destroys its input.

- **Antenna:** Use a separate receive antenna at a distance, for example an active loop, ideally at right angles to the transmit antenna.
- **Protection:** Put a preselector or band-pass filter and a receiver limiter in front of the SDR.
- **Blanking:** RadioMoni blanks the evaluation while N1MM+ transmits (`IsTransmitting`) or the SDR clips. N1MM+ only reports `IsTransmitting` when it keys the radio itself. It does not see a foot switch or a paddle, so only clipping detection covers those.

These software measures do not replace the hardware protection.

**Hardware**

| SDR | Segment | Remark |
|---|---|---|
| Airspy HF+ | up to about 600 kHz | recommended for shortwave; a whole CW and SSB segment of a band |
| HackRF | up to about 800 kHz | insensitive on shortwave and easily overloaded, for tests only |
| RTL-SDR | up to about 500 kHz | direct sampling below 24 MHz, modest sensitivity |

A CW segment (for example 14.000–14.070 MHz) needs about half a CPU core for 24 decoders.

### Setup

1. **Load the reference data:** On the *Contest skimmer* page click *Refresh* under *Reference data*. Alternatively:
   ```bash
   docker compose exec radio-api python -m radiomoni.contest.refdata --update
   ```
   This loads `cty.csv` (country, zones), `MASTER.SCP` (active contest callsigns) and the Club Log Most Wanted list. They are kept in the `api-data` volume, so they also work at a contest site without internet. Update them a few days before the contest.
2. **Add to `.env`** (see [configuration.md](configuration.md#contest-skimmer-1)), then run `docker compose up -d radio-api`:
   ```bash
   SKIMMER_CALLSIGN=HB9XYZ        # spotter in the cluster lines (default RBN_CALLSIGN)
   CLUSTER_ENABLED=true           # DX cluster for the N1MM+ bandmap, TCP 7300
   N1MM_ENABLED=true              # receive the N1MM+ broadcasts, UDP 12060
   N1MM_ALLOWED=192.168.1.0/24    # only packets from the contest network
   CONTEST_BIND=0.0.0.0           # open both ports to the LAN (default: this computer only)
   ```
3. **Set up N1MM+** (Windows PC in the same network):
   - *Config → Configure Ports… → Broadcast Data*: enable *Radio* and *Contacts*, destination `IP-of-the-RadioMoni-host:12060`.
   - In the *Telnet* window, add a cluster `IP-of-the-RadioMoni-host:7300` and connect. After the login the spots appear in the bandmap, and a click tunes the transceiver.
4. **Import the log:** If N1MM+ was not connected from the start, import the log on the page (*Import ADIF / Cabrillo*). After that, new QSOs come live from N1MM+, also from several logging positions.

### During the contest

1. **Select the contest.** Its rules set the bands, multipliers and dupes. They live in `radiomoni/contest/rules/*.yaml`:

   | Contest | Multipliers | Dupes |
   |---|---|---|
   | IARU Region 1 Fieldday CW / SSB | DXCC per band, `/P` highlighted | per band |
   | IARU HF World Championship | ITU zone per band (HQ stations cannot be detected) | per band and mode |
   | CQ WW DX CW / SSB | CQ zone and DXCC per band | per band |
   | CQ WPX CW / SSB | WPX prefix once per contest | per band |
   | USKA Helvetia Contest | DXCC per band, Swiss stations highlighted (cantons come from the exchange and cannot be detected) | per band and mode |
   | General | none, only new and rare stations | per band and mode |

   The USKA Field Day is the IARU Region 1 Fieldday. The Helvetia rules have not been checked against the current rules PDF, because its download sits behind a bot check. The Christmas contest and NMD have no rule file yet. A new file in the `rules/` folder is enough; the format is described in `radiomoni/contest/rules.py`.
2. **Pick the band and click *Start skimmer*.**
   - The SDR is tuned beside the CW segment so its DC spike does not get in the way.
   - A running waterfall gives way.
   - *Duration 0* runs until you stop it, at most 72 h.
   - A schedule (action `skimmer`) can start the skimmer exactly when the contest begins.
3. **Read the spots.** The list shows age, frequency, callsign, country, speed, SNR and notes:

   | Note | Meaning |
   |---|---|
   | **MULT** (red) | new multiplier; the tooltip names it |
   | **RARE #n** | DXCC entity at rank n of the Most Wanted list (up to `SKIMMER_RARE_RANK`, default 100) |
   | **DUPE** (grey) | already in the log |
   | **/P**, **HB** | portable or Swiss station, when the contest highlights it |
   | **?SCP** | not in MASTER.SCP: genuine but rarely active in contests, or misread |

   In the waterfall, new multipliers and rare stations are marked red, dupes grey and all others orange. A click on a spot opens the CW page on its frequency so you can listen.
4. **Alerts:** Only high-priority spots (multiplier or rare) reach the alert rules, source `skimmer`. A rule such as *field text contains MULT* with a cooldown of a few minutes keeps the operator from being flooded.

**When does a callsign become a spot?** A wrong spot costs the operator more than a missed one, so a single decode never counts:

- **The station itself:** Only a callsign the station sends itself counts, that is after `CQ`, `TEST`, `DE`, `TU`, `QRZ`, or twice in a row. A call that the run station sends to its partner together with the report does not count.
- **Check:** The callsign must belong to a DXCC entity, if `cty.csv` is loaded.
- **Hits:** It needs two hits on (nearly) the same frequency within 10 minutes. If MASTER.SCP does not know the call, it needs three. If MASTER.SCP knows it and it came after `CQ`/`TEST`, one is enough.
- **Repeat:** The same station is reported again after 10 minutes, like RBN does.

### Phase 0: measure whether it is good enough

Before the skimmer counts at a contest, it is measured on real recordings, with precision and recall reported separately:

- **Precision:** share of the spots that are right. Target: at least 90 %.
- **Recall:** share of the stations that were found. Target for SSB: at least 30 %.

**CW**

1. **Record:** Run the skimmer during a contest weekend (for example CQ WW CW) with *Record the segment IQ* and RBN on (`RBN_ENABLED=true`).
2. **Files:** Three files are written to `recordings/skimmer/`:
   - the WAV file with the segment (about 1.4 GB per hour),
   - a JSON file with the centre frequency and sample rate,
   - `*.rbn.jsonl`, the RBN spots of the same time as the reference.
3. **Evaluate:**
   ```bash
   docker compose exec radio-api python -m radiomoni.skimmer.evaluate cw \
     recordings/skimmer/skimmer_20261128_120000_14035kHz.wav
   ```
   The output lists precision, recall and the callsigns RBN does not know. Those are not wrong by default: RBN does not hear everything your antenna hears. They are worth checking by hand.

**SSB**

SSB clips (WAV) and a text file with the callsigns heard in them:
```bash
docker compose exec radio-api python -m radiomoni.skimmer.evaluate ssb --reference calls.txt \
  --model turbo --hotwords "Alfa Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliett Kilo Lima Mike" \
  --prompt "CQ contest, five nine, QRZ" clips/*.wav
```
The output gives the values for all recognised calls (`raw`) and for confirmed ones (`confirmed`). Confirmed means the call came after CQ, "contest", "this is" and similar, or was heard at least twice. Compare several models (`small`, `turbo`, `large-v3`) with and without `--prompt`/`--hotwords`.

### Limits

- **CW only:** Live operation is CW only. SSB follows after the evaluation.
- **Multipliers from the exchange:** Cantons, serial numbers and HQ stations cannot be told from the callsign.
- **One SDR, one segment:** Several bands need several SDRs; see "Several SDRs" in the roadmap.
- **One logger:** Any logger understands the cluster. "Already worked" and TX blanking are available with N1MM+ only.
