# Hardware

🇬🇧 **[English Version](#english-version)** below

## Übersicht

| Gerät | Bereich | Sample-Rate | Betriebsarten |
|---|---|---|---|
| RTL-SDR v3/v4 | 24 – 1766 MHz, KW 0.5 – 24 MHz per Direct Sampling | 0.25 – 3.2 MS/s | alle, inkl. ADS-B/AIS/ISM |
| HackRF One | 1 MHz – 6 GHz | 2 – 20 MS/s | Sprache, VOX, APRS, POCSAG, Repeater, ADS-B |
| Airspy HF+ | 0.5 kHz – 31 MHz, 60 – 260 MHz | 768 kS/s | Sprache, VOX, Spektrum, CW |
| USRP N200 + WBX | 50 MHz – 2.2 GHz | bis 25 MS/s | zusätzlich Multi-Channel DDC |
| SDRplay RSPduo (`WITH_SDRPLAY=1`) | 1 kHz – 2 GHz, KW über Hi-Z | 2 MS/s pro Tuner | zwei Tuner gleichzeitig; Sprache, VOX, APRS, POCSAG, Spektrum, CW, Skimmer |

Erkennung: Ist *Automatisch* gewählt, wird in der Reihenfolge HackRF, Airspy HF+, RTL-SDR, SDRplay gesucht. Den USRP wählst du explizit über seine IP-Adresse.

### Mehrere SDRs gleichzeitig

Jedes angeschlossene SDR hat seine eigene Sperre. Jobs auf verschiedenen Geräten laufen also parallel, zum Beispiel APRS am HackRF und AIS am RTL-SDR.

- **Gerät wählen:** Die Liste kommt aus `/sys/bus/usb/devices`. Dabei wird kein Gerät geöffnet, ein laufender Job wird also nicht gestört.
  - In den *Einstellungen* wählst du ein bestimmtes Gerät als Standard.
  - Auf jeder Startseite erscheint die Auswahl *SDR*, sobald mehr als ein Gerät angeschlossen ist.
  - ADS-B, AIS und ISM nehmen ohne Auswahl das erste passende Gerät, das frei ist.
- **Geräte-IDs:** `hackrf:<Seriennummer>`, `rtlsdr:<Seriennummer>`, `airspyhf:<Seriennummer>`, `usrp:<IP>`. Ist die Seriennummer nicht eindeutig, steht der Index (`rtlsdr:0`, `rtlsdr:1`). Das ist bei vielen RTL-SDR-Sticks so, alle melden `00000001`. Eindeutige Nummern vergibst du mit `rtl_eeprom -d 1 -s RTL-2`, danach Stick neu einstecken.
- **Werkzeuge:** Nur wenn mehrere Geräte desselben Typs angeschlossen sind, bekommen sie die Geräteangabe (`-d …`). Mit einem Gerät pro Typ läuft alles wie bisher.
- **Grenze Airspy HF+:** Den Airspy HF+ unterstützt RadioMoni bisher nur einmal pro Rechner.
- **Notstopp:** `POST /sdr/force-stop?device_id=…` stoppt nur dieses Gerät, ohne Angabe alle.

## USB-Zugriff (Linux-Host)

Der API-Container bekommt `/dev/bus/usb` als Bind-Mount und läuft als UID 1000 in den Gruppen `plugdev` und `dialout`. Auf dem Host:

```bash
sudo apt install rtl-sdr hackrf          # bringt die udev-Regeln mit
sudo usermod -aG plugdev $USER           # neu anmelden
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtl.conf   # DVB-T-Treiber sperren
```

Prüfen, ob der Container das Gerät sieht:

```bash
docker compose exec radio-api rtl_test -t        # RTL-SDR
docker compose exec radio-api hackrf_info        # HackRF
docker compose exec radio-api airspyhf_info      # Airspy HF+
```

Geräte, die nach dem Containerstart eingesteckt werden oder nach einem Reboot eine neue USB-Nummer haben, sind ohne Neustart sichtbar. Die udev-Regeln auf dem Host sind dafür Voraussetzung: Ohne sie gehört das Gerät `root` und der Container meldet „Access denied“.

## Frequenzkorrektur (PPM)

Günstige RTL-SDR-Dongles weichen oft um 20 bis 80 ppm ab. Bei 433 MHz sind das bis zu 35 kHz. Messen:

```bash
docker compose exec radio-api rtl_test -p 60    # nach ~60 s den "cumulative PPM"-Wert ablesen
```

Den Wert trägst du beim Start von ADS-B, AIS oder ISM im Feld *Frequenzkorrektur* ein. Dongles mit TCXO (RTL-SDR Blog v3/v4) brauchen das meist nicht.

## HackRF-Hinweise

- **DC-Spike / IQ-Imbalance:** HackRF ist ein Direct-Conversion-Empfänger. Jede Aufnahme wird automatisch korrigiert (DC-Offset, Amplitude, Phase per Gram-Schmidt).
- **Lange Aufnahmen brechen ab:** 2 MS/s bedeuten etwa 4 MB/s über USB. Hilfreich sind ein kurzes, gutes Kabel, ein aktiver USB-Hub, Aufnahmen unter 60 s oder für den Dauerbetrieb ein RTL-SDR.
- POCSAG-Einzelaufnahmen mit HackRF sind aus Speichergründen auf 60 s begrenzt.
- **ADS-B:** readsb steuert den HackRF selbst. Ohne Angabe der Verstärkung gelten LNA 40 dB und VGA 48 dB (der HackRF hat keine automatische Regelung). Ein Wert im Feld *Verstärkung* setzt LNA (in 8-dB-Schritten, max. 40) und VGA wie bei den übrigen HackRF-Betriebsarten. Die Frequenzkorrektur (ppm) wird beim HackRF nicht angewendet.

## Kurzwelle (CW, SSB)

Für die CW-Seite und den Wasserfall auf 3–30 MHz eignen sich die Geräte unterschiedlich:

| Gerät | Kurzwelle | Hinweis |
|---|---|---|
| Airspy HF+ | **empfohlen** | für KW gebaut, hoher Dynamikbereich, kein DC-Spike |
| RTL-SDR v3 | brauchbar | unter 24 MHz schaltet RadioMoni automatisch auf Direct Sampling (`rtl_sdr -D`). Schlechtere Selektion als ein KW-Empfänger, starke Rundfunksender können übersteuern. |
| RTL-SDR v4 | prüfen | hat einen eingebauten KW-Konverter, den der Debian-Treiber `rtl-sdr` 2.0 noch nicht kennt. Erst `rtl_test` und eine Testaufnahme machen. |
| HackRF One | nur starke Signale | technisch ab 1 MHz, unterhalb 30 MHz aber unempfindlich und leicht zu übersteuern |

- **Antenne:** Die VHF/UHF-Antenne taugt auf Kurzwelle nicht. Ein Langdraht mit Unun (9:1), eine Endfed- oder eine aktive Magnetic-Loop-Antenne genügen für den Empfang. Ein Mantelwellen-Filter am Speisekabel hält Störungen aus dem Haus fern.
- **Übersteuerung:** Zeigt der Wasserfall viele Phantomsignale, die Verstärkung senken. Bei HackRF und RTL-SDR hilft ein KW-Hochpass, der Mittelwellen-Rundfunk unter 1.7 MHz abschneidet.
- **Abstimmen:** HackRF und RTL-SDR haben in der Mitte ihres Empfangsbereichs eine DC-Spitze. Die CW-Session stimmt die Hardware deshalb um ein Viertel der Bandbreite neben die gewünschte Frequenz und mischt das Signal digital zurück.
- **Testsignale:** Die Baken des [NCDXF/IARU International Beacon Project](https://www.ncdxf.org/beacon/) senden auf 14.100, 18.110, 21.150, 24.930 und 28.200 MHz reihum ihr Rufzeichen in CW (alle 3 Minuten jede Bake 10 s lang).

## SDRplay RSPduo

Der RSPduo hat zwei Tuner (1 kHz – 2 GHz, 14-Bit-ADC). Tuner 1 hat zusätzlich einen Hi-Z-Eingang für Kurzwelle. Andere RSPs (RSP1A, RSP1B, RSPdx) gehen ebenfalls, mit einem Tuner.

1. **Udev-Regel auf dem Host,** damit der Container das Gerät öffnen darf. Die Regel legt auch der Installer von SDRplay an:
   ```bash
   sudo tee /etc/udev/rules.d/66-sdrplay.rules >/dev/null <<'RULES'
   SUBSYSTEM=="usb",ENV{DEVTYPE}=="usb_device",ATTRS{idVendor}=="1df7",MODE:="0666"
   RULES
   sudo udevadm control --reload && sudo udevadm trigger
   ```
   Die SDRplay-API selbst braucht der Host nicht, sie läuft im Container.
2. **Image mit SDRplay bauen** (`WITH_SDRPLAY=1`, siehe [installation.md](installation.md#sdrplay-rsp)).
3. **Prüfen:** `docker compose exec radio-api SoapySDRUtil --find=driver=sdrplay` zeigt den RSPduo mit den Modi Single Tuner, Dual Tuner, Master und Slave.

**Zwei Geräte statt eines:** In der Geräteliste erscheint der RSPduo als *RSPduo Tuner A* und *RSPduo Tuner B*, jeder mit eigener Sperre. Ein Beispiel: Skimmer CW 40 m auf Tuner A und SSB 20 m auf Tuner B gleichzeitig.

- **Master und Slave:** Der erste Job auf einem der beiden Tuner öffnet den RSPduo als Master, ein Job auf dem anderen Tuner läuft danach als Slave. Beide laufen dann mit höchstens 2 MS/s.
- **Den Master stoppen:** Stoppt der Master, endet auch der Slave. Deshalb fragt die Oberfläche nach, bevor sie einen Master mit laufendem Slave stoppt. Die API antwortet ohne `?force=1` mit 409 und `dependent_sessions`.
- **Wasserfall:** Ein Wasserfall auf dem Master weicht nicht, solange ein Slave läuft.
- **Antenne:** Tuner A nutzt unter 30 MHz den Hi-Z-Eingang (`SDRPLAY_HIZ`), Tuner B den 50-Ω-Eingang. Bias-T gibt es nur auf Tuner B (`SDRPLAY_BIAS_T`, Standard aus).
- **Notch-Filter:** Gegen MW- und UKW-Rundfunk ist er unter 30 MHz an (`SDRPLAY_NOTCH=auto`). `on` schaltet zusätzlich den DAB-Notch ein, `off` schaltet beide aus.
- **Verstärkung:** RadioMonis Verstärkung (0–76 dB) wird auf die LNA-Stufe des Bandes abgebildet. Die ZF-Verstärkung regelt die AGC (`SDRPLAY_AGC`).
- **Grenzen:**
  - Den RSPduo-Modus *Single Tuner* mit bis zu 10 MS/s bietet RadioMoni noch nicht an.
  - ADS-B, AIS und ISM laufen nicht auf dem RSP.

**Lizenz der SDRplay-API:**
- **Weitergabe:** Die API ist proprietär und darf nicht weitergegeben werden. Darum steht sie nicht im Repo. Der Build lädt sie von sdrplay.com, mit fester Prüfsumme.
- **Annahme:** Wer mit `WITH_SDRPLAY=1` baut, nimmt die Lizenz an. Sie liegt im Image unter `/opt/sdrplay_api/sdrplay_license.txt`.
- **Datenübertragung:** Laut Abschnitt 6 der Lizenz darf die Software Gerätedaten an einen Server von SDRplay übermitteln und auf Firmware-Updates hinweisen.

## USRP N200

1. Den Host-Port mit einer statischen IP im Netz des N200 konfigurieren (Standard des N200: `192.168.10.2`):
   ```bash
   sudo ip addr add 192.168.10.1/24 dev enp3s0
   sudo ip link set enp3s0 mtu 9000      # optional, für hohe Raten
   ```
2. Das Image mit UHD bauen (`WITH_USRP=1`, siehe [installation.md](installation.md#usrp-n200)).
3. Prüfen: `docker compose exec radio-api uhd_find_devices --args addr=192.168.10.2`

Multi-Channel: Die Mittenfrequenz plus/minus die halbe Bandbreite muss alle Kanäle abdecken, zwischen den Kanälen braucht es mindestens 50 kHz Abstand.

## Antennen und Frequenzen (Beispiele Schweiz/Europa)

| Dienst | Frequenz | Modulation |
|---|---|---|
| APRS Europa | 144.800 MHz | FM (Streaming) |
| Amateurfunk 2 m / 70 cm Anruf | 145.500 / 433.500 MHz | FM |
| PMR446 Kanal 1 | 446.00625 MHz | FM (VOX) |
| Flugfunk | 118 – 137 MHz | AM |
| ADS-B | 1090 MHz | readsb |
| AIS | 161.975 / 162.025 MHz | rtl_ais |
| ISM-Sensoren | 433.92 / 868.3 MHz | rtl_433 |

## Fehlerbehebung

| Symptom | Ursache / Lösung |
|---|---|
| „Kein SDR erkannt“ | Gerät eingesteckt? `rtl_test -t` im Container; DVB-Treiber gesperrt? Container neu starten |
| „Access denied (insufficient permissions)“ | udev-Regeln fehlen auf dem Host: `sudo apt install rtl-sdr hackrf`, Gerät neu einstecken |
| HTTP 409 „SDR device is busy“ | Ein anderer Job nutzt das Gerät. Mit *Stopp* oder `POST /api/sdr/force-stop` beenden. |
| „Resource busy“ in Session-Fehlern | Ein Prozess ausserhalb des Containers (z. B. gqrx) belegt den Dongle |
| Transkription leer | Kein Sprachsignal; Gain auf 30–40 dB erhöhen; richtige Modulation (Flugfunk = AM) |
| Keine APRS-Pakete | APRS ist sporadisch, besser im Dauerbetrieb laufen lassen; Gain und Antenne prüfen |
| ADS-B zeigt nichts | 1090-MHz-Antenne mit freier Sicht; Gain auf *automatisch* (HackRF: LNA 40 / VGA 48) |

---

<a id="english-version"></a>

## English Version

### Overview

| Device | Range | Sample rate | Modes |
|---|---|---|---|
| RTL-SDR v3/v4 | 24 – 1766 MHz, HF 0.5 – 24 MHz via direct sampling | 0.25 – 3.2 MS/s | all, incl. ADS-B/AIS/ISM |
| HackRF One | 1 MHz – 6 GHz | 2 – 20 MS/s | voice, VOX, APRS, POCSAG, repeaters, ADS-B |
| Airspy HF+ | 0.5 kHz – 31 MHz, 60 – 260 MHz | 768 kS/s | voice, VOX, spectrum, CW |
| USRP N200 + WBX | 50 MHz – 2.2 GHz | up to 25 MS/s | additionally multi-channel DDC |
| SDRplay RSPduo (`WITH_SDRPLAY=1`) | 1 kHz – 2 GHz, HF via Hi-Z | 2 MS/s per tuner | two tuners at once; voice, VOX, APRS, POCSAG, spectrum, CW, skimmer |

Detection: with *Detect automatically* selected, devices are searched in the order HackRF, Airspy HF+, RTL-SDR, SDRplay. The USRP is selected explicitly by its IP address.

#### Several SDRs at the same time

Every connected SDR has its own lock, so jobs on different devices run in parallel, for example APRS on the HackRF and AIS on the RTL-SDR.

- **Choosing a device:** The list comes from `/sys/bus/usb/devices`. No device is opened for this, so a running job is not disturbed.
  - In the *Settings* you choose a specific device as the default.
  - Every start page shows a *SDR* selection as soon as more than one device is connected.
  - Without a choice, ADS-B, AIS and ISM take the first suitable device that is free.
- **Device ids:** `hackrf:<serial>`, `rtlsdr:<serial>`, `airspyhf:<serial>`, `usrp:<ip>`. If the serial is not unique, the index is used (`rtlsdr:0`, `rtlsdr:1`). That is the case with many RTL-SDR sticks, which all report `00000001`. Give them unique serials with `rtl_eeprom -d 1 -s RTL-2`, then replug the stick.
- **Tools:** Only when several devices of the same type are connected do the tools get a device selector (`-d …`). With one device per type everything works as before.
- **Airspy HF+ limit:** RadioMoni supports only one Airspy HF+ per machine so far.
- **Emergency stop:** `POST /sdr/force-stop?device_id=…` stops only that device, without an id all of them.

### USB access (Linux host)

The API container gets `/dev/bus/usb` as a bind mount and runs as UID 1000 in the groups `plugdev` and `dialout`. On the host:

```bash
sudo apt install rtl-sdr hackrf          # brings the udev rules
sudo usermod -aG plugdev $USER           # log in again
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtl.conf   # block the DVB-T driver
```

Check whether the container sees the device:

```bash
docker compose exec radio-api rtl_test -t        # RTL-SDR
docker compose exec radio-api hackrf_info        # HackRF
docker compose exec radio-api airspyhf_info      # Airspy HF+
```

Devices plugged in after the container has started, or with a new USB number after a reboot, are visible without a restart. This requires the udev rules on the host: without them the device belongs to `root` and the container reports "Access denied".

### Frequency correction (PPM)

Cheap RTL-SDR dongles are often off by 20 to 80 ppm. At 433 MHz that is up to 35 kHz. To measure:

```bash
docker compose exec radio-api rtl_test -p 60    # read the "cumulative PPM" value after ~60 s
```

Enter the value in the *Frequency correction (ppm)* field when starting ADS-B, AIS or ISM. Dongles with a TCXO (RTL-SDR Blog v3/v4) usually do not need it.

### HackRF notes

- **DC spike / IQ imbalance:** the HackRF is a direct-conversion receiver. Every recording is corrected automatically (DC offset, amplitude, phase via Gram-Schmidt).
- **Long recordings abort:** 2 MS/s means about 4 MB/s over USB. A short, good cable, a powered USB hub, recordings under 60 s or an RTL-SDR for continuous operation help.
- POCSAG single captures with the HackRF are limited to 60 s for memory reasons.
- **ADS-B:** readsb controls the HackRF itself. Without a gain setting, LNA 40 dB and VGA 48 dB apply (the HackRF has no automatic gain control). A value in the *Gain (dB)* field sets LNA (in 8 dB steps, max. 40) and VGA as in the other HackRF modes. The frequency correction (ppm) is not applied to the HackRF.

### Shortwave (CW, SSB)

For the CW page and the waterfall on 3–30 MHz the devices differ:

| Device | Shortwave | Note |
|---|---|---|
| Airspy HF+ | **recommended** | built for HF, high dynamic range, no DC spike |
| RTL-SDR v3 | usable | below 24 MHz RadioMoni switches to direct sampling automatically (`rtl_sdr -D`). Poorer selectivity than an HF receiver, strong broadcast stations can overload it. |
| RTL-SDR v4 | check first | has a built-in HF converter that the Debian driver `rtl-sdr` 2.0 does not know yet. Run `rtl_test` and a test recording first. |
| HackRF One | strong signals only | technically from 1 MHz, but insensitive below 30 MHz and easily overloaded |

- **Antenna:** the VHF/UHF antenna is no good on shortwave. A long wire with a 9:1 unun, an end-fed or an active magnetic loop is enough for receiving. A common-mode choke on the feed line keeps household noise out.
- **Overload:** if the waterfall shows many phantom signals, lower the gain. With the HackRF and the RTL-SDR an HF high-pass that cuts medium-wave broadcasting below 1.7 MHz helps.
- **Tuning:** the HackRF and the RTL-SDR have a DC spike in the middle of their receive range. The CW session therefore tunes the hardware a quarter of the bandwidth beside the wanted frequency and mixes the signal back digitally.
- **Test signals:** the beacons of the [NCDXF/IARU International Beacon Project](https://www.ncdxf.org/beacon/) send their callsign in CW in turn on 14.100, 18.110, 21.150, 24.930 and 28.200 MHz (every 3 minutes each beacon for 10 s).

### SDRplay RSPduo

The RSPduo has two tuners (1 kHz – 2 GHz, 14-bit ADC). Tuner 1 also has a Hi-Z input for shortwave. Other RSPs (RSP1A, RSP1B, RSPdx) work too, with one tuner.

1. **Udev rule on the host,** so the container may open the device. The SDRplay installer creates the same rule:
   ```bash
   sudo tee /etc/udev/rules.d/66-sdrplay.rules >/dev/null <<'RULES'
   SUBSYSTEM=="usb",ENV{DEVTYPE}=="usb_device",ATTRS{idVendor}=="1df7",MODE:="0666"
   RULES
   sudo udevadm control --reload && sudo udevadm trigger
   ```
   The host does not need the SDRplay API itself; it runs inside the container.
2. **Build the image with SDRplay** (`WITH_SDRPLAY=1`, see [installation.md](installation.md#sdrplay-rsp-1)).
3. **Check:** `docker compose exec radio-api SoapySDRUtil --find=driver=sdrplay` lists the RSPduo with the modes single tuner, dual tuner, master and slave.

**Two devices instead of one:** In the device list the RSPduo appears as *RSPduo Tuner A* and *RSPduo Tuner B*, each with its own lock. For example: skimmer CW 40 m on tuner A and SSB 20 m on tuner B at the same time.

- **Master and slave:** The first job on either tuner opens the RSPduo as master; a job on the other tuner then runs as slave. Both run at up to 2 MS/s.
- **Stopping the master:** When the master stops, the slave ends too. That is why the interface asks before it stops a master with a running slave. Without `?force=1` the API answers 409 with `dependent_sessions`.
- **Waterfall:** A waterfall on the master does not give way while a slave runs.
- **Antenna:** Tuner A uses the Hi-Z input below 30 MHz (`SDRPLAY_HIZ`), tuner B the 50 Ω input. Bias-T exists only on tuner B (`SDRPLAY_BIAS_T`, off by default).
- **Notch filters:** The MW/FM broadcast notch is on below 30 MHz (`SDRPLAY_NOTCH=auto`). `on` also enables the DAB notch, `off` disables both.
- **Gain:** RadioMoni's gain (0–76 dB) is mapped to the LNA state of the band. The IF gain is set by the AGC (`SDRPLAY_AGC`).
- **Limits:**
  - RadioMoni does not offer the RSPduo *single tuner* mode with up to 10 MS/s yet.
  - ADS-B, AIS and ISM do not run on an RSP.

**SDRplay API licence:**
- **Redistribution:** The API is proprietary and may not be redistributed, so it is not in the repository. The build downloads it from sdrplay.com with a pinned checksum.
- **Acceptance:** By building with `WITH_SDRPLAY=1` you accept its licence. It is in the image as `/opt/sdrplay_api/sdrplay_license.txt`.
- **Data:** Section 6 of the licence allows the software to send device details to an SDRplay server and to point out firmware updates.

### USRP N200

1. Configure the host port with a static IP in the N200's network (N200 default: `192.168.10.2`):
   ```bash
   sudo ip addr add 192.168.10.1/24 dev enp3s0
   sudo ip link set enp3s0 mtu 9000      # optional, for high rates
   ```
2. Build the image with UHD (`WITH_USRP=1`, see [installation.md](installation.md#usrp-n200-1)).
3. Check: `docker compose exec radio-api uhd_find_devices --args addr=192.168.10.2`

Multi-channel: the center frequency plus/minus half the bandwidth must cover all channels, and the channels must be at least 50 kHz apart.

### Antennas and frequencies (examples for Switzerland/Europe)

| Service | Frequency | Modulation |
|---|---|---|
| APRS Europe | 144.800 MHz | FM (streaming) |
| Amateur radio 2 m / 70 cm calling | 145.500 / 433.500 MHz | FM |
| PMR446 channel 1 | 446.00625 MHz | FM (VOX) |
| Airband | 118 – 137 MHz | AM |
| ADS-B | 1090 MHz | readsb |
| AIS | 161.975 / 162.025 MHz | rtl_ais |
| ISM sensors | 433.92 / 868.3 MHz | rtl_433 |

### Troubleshooting

| Symptom | Cause / solution |
|---|---|
| "No SDR detected" | Device plugged in? `rtl_test -t` in the container; DVB driver blocked? Restart the container |
| "Access denied (insufficient permissions)" | udev rules missing on the host: `sudo apt install rtl-sdr hackrf`, replug the device |
| HTTP 409 "SDR device is busy" | Another job is using the device. Stop it with *Stop* or `POST /api/sdr/force-stop`. |
| "Resource busy" in session errors | A process outside the container (e.g. gqrx) is using the dongle |
| Empty transcription | No voice signal; raise the gain to 30–40 dB; correct modulation (airband = AM) |
| No APRS packets | APRS is sporadic, better run it continuously; check gain and antenna |
| ADS-B shows nothing | 1090 MHz antenna with a clear view; gain empty = automatic (HackRF: LNA 40 / VGA 48) |
