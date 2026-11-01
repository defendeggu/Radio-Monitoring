# Installation

🇬🇧 **[English Version](#english-version)** below

## Voraussetzungen

- Linux-Host (getestet mit Ubuntu 24.04 und Debian 13), Docker Engine mit Compose v2.20 oder neuer
- Ein SDR am USB-Port oder ein USRP N200 im Netzwerk. Ohne SDR startet der Stack trotzdem, Aufnahmen schlagen dann mit „Kein SDR erkannt“ fehl.
- RAM: Vollausbau etwa 6 GB (Elasticsearch 2 GB Heap, Logstash 1 GB, Kibana 1 GB, Whisper `small` etwa 1 GB). Light-Profil etwa 2 GB.
- Speicherplatz: etwa 6 GB für die Images. Dazu kommen die Aufnahmen (30 s WAV mit 16 kHz entsprechen etwa 1 MB).

## Erstinstallation

```bash
./scripts/setup-env.sh            # .env mit zufälligen Secrets (chmod 600)
python3 scripts/validate_env.py   # optional: Konfiguration prüfen
docker compose up -d --build
./scripts/post-docker-setup.sh    # ES-Benutzer und -Rollen, ILM, Templates, Kibana-Dashboards
./scripts/run_import.sh           # Repeater-Liste der USKA (scripts/repeaters_ch.csv)
```

Weboberfläche: `http://<host>:8080`. Den API-Key (`API_KEYS` in `.env`) gibst du dort unter *Einstellungen* ein.

`setup-env.sh` ist idempotent. Bestehende Werte bleiben unverändert, fehlende Variablen werden ergänzt, Platzhalter wie `changeme` ersetzt. Nach einem Update kannst du es einfach erneut ausführen.

## Profile

| Profil | Start | Speicher | Kibana |
|---|---|---|---|
| Vollausbau (Standard) | `COMPOSE_PROFILES=elk` | Elasticsearch | ja |
| Light | `./scripts/setup-env.sh --light` (setzt `COMPOSE_PROFILES=` und `STORAGE_BACKEND=sqlite`) | SQLite in Volume `api-data` | nein |

Dashboard, Suche, Export, Alarme und Zeitpläne der Weboberfläche funktionieren in beiden Profilen.

## Whisper auf der GPU

faster-whisper (CTranslate2) nutzt NVIDIA-GPUs über CUDA 12 und cuDNN 9.

1. Auf dem Host den NVIDIA-Treiber und das [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) installieren. `docker run --rm --gpus all ubuntu nvidia-smi` muss funktionieren.
2. Starten mit dem Override:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
   ```
   Das API-Image wird dabei mit `WITH_CUDA=1` gebaut, also mit den CUDA-Bibliotheken als Python-Wheels. Eingestellt sind `WHISPER_DEVICE=cuda` und `float16`, Standardmodell ist `large-v3-turbo`. Zusätzlich liest Metricbeat die GPU-Auslastung über `/metrics/gpu` der API (mit `METRICS_API_KEY` aus `.env`); sie erscheint im Kibana-Dashboard *System – Zustand*.

Grobe Richtwerte: `small` auf der CPU braucht etwa die halbe Echtzeit, `large-v3-turbo` auf einer Mittelklasse-GPU ist mehr als 20-mal schneller als Echtzeit. Die Modelle werden beim ersten Gebrauch in das Volume `whisper-models` geladen (100 MB bis 1.6 GB).

> Der GPU-Pfad ist vorbereitet, aber nicht auf jeder Kombination aus Treiber und Karte getestet.

## USRP N200

Das Standard-Image enthält kein UHD bzw. GNU Radio (etwa 1 GB). Für den USRP:

```bash
echo "WITH_USRP=1" >> .env
docker compose build radio-api && docker compose up -d radio-api
docker compose exec radio-api uhd_images_downloader   # FPGA-Images (einmalig)
```

Die IP-Adresse des Geräts trägst du in der Weboberfläche unter *Einstellungen* ein. Netzwerk-Setup: siehe [hardware.md](hardware.md#usrp-n200).

## Dockge / Portainer

Der Stack nutzt relative Bind-Mounts und liest alle Werte aus `.env`. Du kannst das Verzeichnis direkt als Stack in Dockge verwenden. Den Port der Weboberfläche setzt du mit `WEB_PORT`.

## Update

```bash
git pull
./scripts/setup-env.sh            # neue Variablen ergänzen
docker compose up -d --build
./scripts/post-docker-setup.sh    # Templates/Rollen aktualisieren (idempotent)
```

Bei einem Major-Update von Elasticsearch: siehe [elk.md](elk.md#upgrade). Für den Sprung von 3.x auf 4.0: siehe [upgrade-4.0.md](upgrade-4.0.md).

## Deinstallation

```bash
docker compose down            # Container stoppen, Daten bleiben
docker compose down -v         # zusätzlich alle Volumes löschen (Elasticsearch, Redis, Modelle)
```

Die Aufnahmen liegen in `./recordings` und bleiben in beiden Fällen erhalten.

---

<a id="english-version"></a>

## English Version

### Requirements

- Linux host (tested with Ubuntu 24.04 and Debian 13), Docker Engine with Compose v2.20 or newer
- An SDR on a USB port or a USRP N200 on the network. The stack also starts without an SDR; recordings then fail with "No SDR detected".
- RAM: about 6 GB for the full stack (Elasticsearch 2 GB heap, Logstash 1 GB, Kibana 1 GB, Whisper `small` about 1 GB). Light profile about 2 GB.
- Disk space: about 6 GB for the images, plus the recordings (30 s of WAV at 16 kHz is about 1 MB).

### First installation

```bash
./scripts/setup-env.sh            # .env with random secrets (chmod 600)
python3 scripts/validate_env.py   # optional: check the configuration
docker compose up -d --build
./scripts/post-docker-setup.sh    # ES users and roles, ILM, templates, Kibana dashboards
./scripts/run_import.sh           # USKA repeater list (scripts/repeaters_ch.csv)
```

Web interface: `http://<host>:8080`. Enter the API key (`API_KEYS` in `.env`) there under *Settings*.

`setup-env.sh` is idempotent. Existing values stay unchanged, missing variables are added and placeholders such as `changeme` are replaced. You can simply run it again after an update.

### Profiles

| Profile | Start | Storage | Kibana |
|---|---|---|---|
| Full (default) | `COMPOSE_PROFILES=elk` | Elasticsearch | yes |
| Light | `./scripts/setup-env.sh --light` (sets `COMPOSE_PROFILES=` and `STORAGE_BACKEND=sqlite`) | SQLite in the `api-data` volume | no |

Dashboard, search, export, alerts and schedules of the web interface work in both profiles.

### Whisper on the GPU

faster-whisper (CTranslate2) uses NVIDIA GPUs via CUDA 12 and cuDNN 9.

1. Install the NVIDIA driver and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) on the host. `docker run --rm --gpus all ubuntu nvidia-smi` must work.
2. Start with the override:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
   ```
   The API image is then built with `WITH_CUDA=1`, i.e. with the CUDA libraries as Python wheels. `WHISPER_DEVICE=cuda` and `float16` are set, the default model is `large-v3-turbo`. In addition, Metricbeat reads the GPU usage from the API's `/metrics/gpu` (with `METRICS_API_KEY` from `.env`); it appears in the Kibana dashboard *System – Zustand* (health).

Rough figures: `small` on the CPU takes about half of real time, `large-v3-turbo` on a mid-range GPU is more than 20 times faster than real time. The models are downloaded into the `whisper-models` volume on first use (100 MB to 1.6 GB).

> The GPU path is prepared, but not tested with every combination of driver and card.

### USRP N200

The default image does not contain UHD or GNU Radio (about 1 GB). For the USRP:

```bash
echo "WITH_USRP=1" >> .env
docker compose build radio-api && docker compose up -d radio-api
docker compose exec radio-api uhd_images_downloader   # FPGA images (once)
```

Enter the device's IP address in the web interface under *Settings*. Network setup: see [hardware.md](hardware.md#usrp-n200-1).

### Dockge / Portainer

The stack uses relative bind mounts and reads all values from `.env`. You can use the directory directly as a stack in Dockge. Set the port of the web interface with `WEB_PORT`.

### Update

```bash
git pull
./scripts/setup-env.sh            # add new variables
docker compose up -d --build
./scripts/post-docker-setup.sh    # update templates/roles (idempotent)
```

For a major update of Elasticsearch: see [elk.md](elk.md#upgrade-1). For the step from 3.x to 4.0: see [upgrade-4.0.md](upgrade-4.0.md#english-version).

### Uninstalling

```bash
docker compose down            # stop the containers, data is kept
docker compose down -v         # also delete all volumes (Elasticsearch, Redis, models)
```

The recordings are stored in `./recordings` and are kept in both cases.
