# Installation

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
./scripts/run_import.sh           # Repeater-Liste (scripts/repeaterbook_ch_fm.csv)
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
   Das API-Image wird dabei mit `WITH_CUDA=1` gebaut, also mit den CUDA-Bibliotheken als Python-Wheels. Eingestellt sind `WHISPER_DEVICE=cuda` und `float16`, Standardmodell ist `large-v3-turbo`.

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
