# Hardware

## Übersicht

| Gerät | Bereich | Sample-Rate | Betriebsarten |
|---|---|---|---|
| RTL-SDR v3/v4 | 24 – 1766 MHz | 0.25 – 3.2 MS/s | alle, inkl. ADS-B/AIS/ISM |
| HackRF One | 1 MHz – 6 GHz | 2 – 20 MS/s | Sprache, VOX, APRS, POCSAG, Repeater, ADS-B |
| Airspy HF+ | 0.5 kHz – 31 MHz, 60 – 260 MHz | bis 912 kS/s | Sprache, VOX |
| USRP N200 + WBX | 50 MHz – 2.2 GHz | bis 25 MS/s | zusätzlich Multi-Channel DDC |

Erkennung: Ist *Automatisch* gewählt, wird in der Reihenfolge HackRF, Airspy HF+, RTL-SDR gesucht. Den USRP wählst du explizit über seine IP-Adresse.

## USB-Zugriff (Linux-Host)

Der API-Container bekommt `/dev/bus/usb` und läuft als UID 1000 in den Gruppen `plugdev` und `dialout`. Auf dem Host:

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

Wird ein Gerät erst nach dem Containerstart eingesteckt: `docker compose restart radio-api`.

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
| HTTP 409 „SDR device is busy“ | Ein anderer Job nutzt das Gerät. Mit *Stopp* oder `POST /api/sdr/force-stop` beenden. |
| „Resource busy“ in Session-Fehlern | Ein Prozess ausserhalb des Containers (z. B. gqrx) belegt den Dongle |
| Transkription leer | Kein Sprachsignal; Gain auf 30–40 dB erhöhen; richtige Modulation (Flugfunk = AM) |
| Keine APRS-Pakete | APRS ist sporadisch, besser im Dauerbetrieb laufen lassen; Gain und Antenne prüfen |
| ADS-B zeigt nichts | 1090-MHz-Antenne mit freier Sicht; Gain auf *automatisch* (HackRF: LNA 40 / VGA 48) |
