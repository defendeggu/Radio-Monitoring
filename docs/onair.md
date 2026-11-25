# OnAir (on-air.dev)

[OnAir](https://on-air.dev/) ist ein eigenständiger SDR-Empfänger mit rund 400 Betriebsarten. RadioMoni bindet ihn als **eigenen Container** ein: `onair-server` dekodiert, RadioMoni steuert ihn, speichert die Meldungen, zeigt sie live, auf der Karte und in Kibana und prüft sie gegen die Alarmregeln.

Sinnvoll ist das für Betriebsarten, die RadioMoni selbst nicht hat: ACARS, VDL2 und HFDL (Luftfahrt), Radiosonden, Digitalfunk (DMR, P25, NXDN, dPMR, D-STAR, YSF, M17), Wettersatelliten (Meteor-M LRPT), LoRa/Meshtastic, DAB und mehr.

> Based on OnAir by Kristijonas Adomaitis - https://on-air.dev · [OnAir contributors](https://github.com/adswill/OnAir/blob/main/CONTRIBUTORS.md)

OnAir steht unter GPL-3.0 mit Zusatzbedingungen zur Namensnennung. Es ist **nicht Teil dieses Repositorys**: `onair/Dockerfile` lädt beim Build das offizielle Release-Paket in fester Version und prüft die Prüfsumme. RadioMoni bleibt MIT; die beiden Programme reden nur über HTTP miteinander.

## Einrichten

1. `./scripts/setup-env.sh` ausführen. Das Skript legt `ONAIR_TOKEN` an, falls er noch fehlt.
2. In `.env` setzen:
   ```
   COMPOSE_PROFILES=elk,onair
   ONAIR_URL=http://onair:8765
   ```
3. `docker compose up -d --build`. Vorher prüfen, dass keine SDR-Session läuft (`/api/sdr/status`).
4. Mit ELK: `./scripts/setup-elk-users.sh` (Index-Template `radio-onair`) und `./scripts/import-kibana-dashboards.sh` (Dashboard *RadioMoni · OnAir*).

Danach steht die Seite **OnAir** unter *Empfang* in der Weboberfläche.

| Variable | Standard | Bedeutung |
|---|---|---|
| `ONAIR_URL` | leer | API von `onair-server`; leer = Einbindung aus |
| `ONAIR_TOKEN` | – | Token für API und OnAir-Seite (mindestens 16 Zeichen) |
| `ONAIR_ALL_MODES` | `false` | alle OnAir-Betriebsarten anbieten, nicht nur die ausgewählten Gruppen |
| `ONAIR_STORE_INSIGHTS` | `true` | OnAirs „Insights“ speichern (z. B. „Pager still“, „APRS-Flut“) |
| `ONAIR_BIND`, `ONAIR_PORT` | `127.0.0.1`, `8765` | OnAir-Seite über nginx; `0.0.0.0` nur in einem vertrauenswürdigen Netz (der Token geht unverschlüsselt) |
| `ONAIR_PUBLIC_URL` | leer | Adresse der OnAir-Seite für den Link; leer = `http://<RadioMoni-Host>:ONAIR_PORT` |
| `ONAIR_CODEC_DIR` | `./onair/codecs` | Ordner mit Sprachcodec-Plugins (siehe unten) |

## So arbeiten RadioMoni und OnAir zusammen

- **Ein SDR, eine Sperre.** OnAir öffnet das SDR nur zwischen `/start` und `/stop`. RadioMoni nimmt vorher die SDR-Sperre (Art `onair`) und gibt sie erst nach dem Stopp frei. Während OnAir läuft, bekommen alle anderen Jobs „SDR belegt“, und umgekehrt. Getestet mit dem HackRF One: Läuft OnAir, meldet das Gerät für andere Programme `Resource busy`. Nach dem Stopp ist es sofort frei.
- **Nie ohne Sperre.** Der Container setzt bei jedem Start `autostart=0`. Ein Wächter in der API stoppt OnAir, wenn keine OnAir-Session eine Sperre hält, z. B. nach einem Neustart der API.
- **Meldungen.** Der Headless-Server hat keinen Event-Stream über die API. Er schreibt die dekodierten Meldungen als JSON-Lines in sein Datenvolume (`events/onair-events.jsonl`, rotiert bei 50 MB). RadioMoni liest dieses Volume nur und speichert jede Meldung in `radio-onair-*`.
- **Kein Senden.** Die OnAir-API kann senden, der HackRF auch. RadioMoni ruft nur eine feste Liste von Empfangspfaden auf, alles andere (`tx`, RDS, Aufnahmen, Rotor) lehnt der Client ab. Der Headless-Server selbst antwortet auf `tx` mit „not supported“.
- **Netz.** Der Container hängt nur an einem internen Docker-Netz ohne Internetzugang. Nur die API und der nginx-Proxy erreichen ihn. Update-Prüfung, Web-Relay, OnAir Web und die rtl_tcp-Freigabe sind aus.
- **Geräte.** HackRF und RTL-SDR. SDRplay-Geräte sind im OnAir-Image nicht eingebunden.

## Betriebsarten

Die Auswahl ist nach Gruppen geordnet:

| Gruppe | Modi |
|---|---|
| Luftfahrt | ACARS, VDL2, HFDL, UAT |
| Radiosonden | Radiosonde (RS41, DFM, M10 …), Horus |
| Digitalfunk | DMR, P25 (Phase 1 und 2), NXDN, dPMR, D-STAR, YSF, M17 |
| Satelliten | Meteor-M LRPT, NOAA APT, CubeSats, ISS, Orbcomm |
| Seefunk | AIS, Seefunk-UKW, SITOR, NAVTEX |
| LoRa / Mesh | Meshtastic, LoRa, LoRaWAN, FANET, OGN, FLARM |
| Rundfunk | DAB, UKW (RDS) |
| Sensoren / Pager | ISM-Sensoren, wM-Bus, Pager |

Bewusst nicht angeboten werden Modi für Behördennetze (TETRA, TETRAPOL), Mobilfunk, WLAN, DECT, Bluetooth und militärische Kurzwelle. `ONAIR_ALL_MODES=true` bietet alle an; die Verantwortung liegt dann bei dir.

Getestet am HackRF One: ACARS (131,525–131,825 MHz, echte Meldungen mit Position) und APRS (144,800 MHz). Die übrigen Modi kommen von OnAir und sind dort zum Teil nur mit erzeugten Signalen geprüft.

**Digitalfunk mit Sprache:** OnAir enthält keine patentierten Sprachcodecs. Rufe, Talkgroups und IDs gehen ohne. Für die Sprache braucht es Plugins, die du selbst baust oder beschaffst (OnAir: `docs/CODECS.md`, `tools/codec-builder/build-codecs.sh`). Sie kommen in `ONAIR_CODEC_DIR` und nie ins Repository. Verschlüsselte Rufe dekodiert OnAir nie.

**Bilder** (Meteor, SSTV …): Ist ein Bild fertig, erscheint es in der Galerie der OnAir-Seite. Die Datei liegt im OnAir-Volume.

## OnAir-Seite

*OnAir-Seite öffnen* zeigt die eigene Seite von OnAir mit Wasserfall, Mithören und Telemetrie. Sie läuft über nginx auf Port 8765 und braucht den Token; der Link bringt ihn mit. Die Seite steuert dasselbe Gerät: Abstimmen ist dort möglich, Starten nur über RadioMoni, damit die SDR-Sperre stimmt.

## Kibana und Metriken

- Index `radio-onair-*`. Felder: `event_type` (z. B. `acars.message`, `sonde.update`, `session.call`), `family`, `mode`, `ident`, `text` (eine lesbare Zeile), `fields` (alle Felder der Meldung, flattened), `position`, `altitude` und `frequency`.
- Dashboard *RadioMoni · OnAir*: Meldungen nach Familie, Sender, Karte und Liste, dazu Last und verlorene Samples des Empfängers.
- Metricbeat liest die Prometheus-Metriken von OnAir über die API (`/metrics/onair`, Metrics-Key) nach `metricbeat-*`. Felder: `prometheus.metrics.onair_*`.

## Alarme

Quelle `onair`, Feld *OnAir-Ereignistyp* (z. B. `sonde.landed`, `session.call`) oder *Text*. Beispiele: eine Regel für Notfall-Squawks im ACARS-Text oder eine für eine bestimmte Talkgroup.

## Rechtliches

Mithören ist in der Schweiz für den Eigengebrauch erlaubt. Inhalte nicht öffentlicher Funkverbindungen (Flugfunk, Betriebsfunk, Pager, Digitalfunk) darfst du aber weder weitergeben noch veröffentlichen (Fernmeldegeheimnis, FMG). Verschlüsseltes zu entschlüsseln ist verboten. RadioMoni gibt OnAir-Meldungen nur dorthin weiter, wo du es selbst einrichtest (Alarme, Export).

---

<a id="english-version"></a>

## English Version

[OnAir](https://on-air.dev/) is a standalone SDR receiver with about 400 modes. RadioMoni runs it as **a container of its own**: `onair-server` decodes, RadioMoni drives it, stores the messages, shows them live, on the map and in Kibana, and checks them against the alert rules. Use it for modes RadioMoni does not have itself: ACARS, VDL2, HFDL, radiosondes, digital voice (DMR, P25, NXDN, dPMR, D-STAR, YSF, M17), weather satellites (Meteor-M LRPT), LoRa/Meshtastic, DAB and more.

> Based on OnAir by Kristijonas Adomaitis - https://on-air.dev · [OnAir contributors](https://github.com/adswill/OnAir/blob/main/CONTRIBUTORS.md)

OnAir is GPL-3.0 with additional attribution terms and is **not part of this repository**: `onair/Dockerfile` downloads the official release package at build time, pinned by version and checksum. RadioMoni stays MIT; the two programs only talk over HTTP.

### Setup

1. Run `./scripts/setup-env.sh` (adds `ONAIR_TOKEN` when missing).
2. In `.env`: `COMPOSE_PROFILES=elk,onair` and `ONAIR_URL=http://onair:8765`.
3. `docker compose up -d --build`. Check first that no SDR session is running.
4. With ELK: `./scripts/setup-elk-users.sh` and `./scripts/import-kibana-dashboards.sh`.

The variables are listed in the German table above.

### How it works

- **One SDR, one lock.** OnAir opens the radio only between `/start` and `/stop`. RadioMoni takes the SDR lock (kind `onair`) first and releases it after the stop. Tested with the HackRF One: while OnAir runs, the device is busy for others, and it is free right after the stop.
- **Never without a lock.** The container sets `autostart=0` at every start. A watchdog in the API stops OnAir when no OnAir session holds a lock.
- **Messages.** The headless server has no event stream on its API. It writes the decoded messages as JSON lines into its data volume, which RadioMoni reads read-only and stores in `radio-onair-*`.
- **No transmitting.** RadioMoni calls a fixed list of receive paths only; the client refuses everything else (`tx`, RDS, recordings, rotator).
- **Network.** The container is on an internal Docker network without internet access. The update check, web relay, OnAir Web and the rtl_tcp share are off.
- **Devices:** HackRF and RTL-SDR.

### Modes

Grouped: aviation, radiosondes, digital voice, satellites, maritime, LoRa/mesh, broadcast, sensors/pagers. Modes for public-safety networks (TETRA, TETRAPOL), mobile phone, Wi-Fi, DECT, Bluetooth and military HF are left out on purpose; `ONAIR_ALL_MODES=true` offers all of them (your responsibility). Tested on the HackRF One: ACARS and APRS. Digital voice audio needs codec plug-ins that you get yourself, in `ONAIR_CODEC_DIR`, never in the repository.

### OnAir page, Kibana, alerts

*Open OnAir page* opens OnAir's own page (waterfall, Listen) through nginx on port 8765, with the token. The index is `radio-onair-*`, the dashboard is *RadioMoni · OnAir*, and Metricbeat reads OnAir's metrics through `/metrics/onair`. Alert rules use the source `onair` and the field *OnAir event type*.

### Legal

Listening for your own use is allowed in Switzerland. You must not pass on or publish the content of non-public radio traffic (telecommunications secrecy, FMG), and you must not decrypt encrypted traffic.
