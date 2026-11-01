# Hardware

🇬🇧 **[English Version](#english-version)** below

## Übersicht

| Gerät | Bereich | Sample-Rate | Betriebsarten |
|---|---|---|---|
| RTL-SDR v3/v4 | 24 – 1766 MHz | 0.25 – 3.2 MS/s | alle, inkl. ADS-B/AIS/ISM |
| HackRF One | 1 MHz – 6 GHz | 2 – 20 MS/s | Sprache, VOX, APRS, POCSAG, Repeater, ADS-B |
| Airspy HF+ | 0.5 kHz – 31 MHz, 60 – 260 MHz | bis 912 kS/s | Sprache, VOX |
| USRP N200 + WBX | 50 MHz – 2.2 GHz | bis 25 MS/s | zusätzlich Multi-Channel DDC |

Erkennung: Ist *Automatisch* gewählt, wird in der Reihenfolge HackRF, Airspy HF+, RTL-SDR gesucht. Den USRP wählst du explizit über seine IP-Adresse.

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
| RTL-SDR v3/v4 | 24 – 1766 MHz | 0.25 – 3.2 MS/s | all, incl. ADS-B/AIS/ISM |
| HackRF One | 1 MHz – 6 GHz | 2 – 20 MS/s | voice, VOX, APRS, POCSAG, repeaters, ADS-B |
| Airspy HF+ | 0.5 kHz – 31 MHz, 60 – 260 MHz | up to 912 kS/s | voice, VOX |
| USRP N200 + WBX | 50 MHz – 2.2 GHz | up to 25 MS/s | additionally multi-channel DDC |

Detection: with *Detect automatically* selected, devices are searched in the order HackRF, Airspy HF+, RTL-SDR. The USRP is selected explicitly by its IP address.

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
