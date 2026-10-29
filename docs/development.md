# Entwicklung

## Struktur

```
radiomoni/                Python-Paket der API:
  api_service.py          Einstieg (Gunicorn: radiomoni.api_service:app)
  app_factory.py          Flask-App: Security, Fehler, Blueprints, Scheduler, Control-Listener
  config.py               alle Umgebungsvariablen
  schemas.py              pydantic-Schemas (Validierung + OpenAPI)
  api_docs.py             @api-Decorator, parse_body/parse_query, OpenAPI-Generator
  security.py / errors.py Auth, CORS, Header / einheitliche Fehlerantworten
  blueprints/             REST-Endpunkte
  jobs.py / actions.py    SDR-Jobs (Capture, Scan, Stream-Start) / gemeinsame Aktionen für API + Scheduler
  sdr_lock.py             SDR-Sperre in Redis (Lease mit Heartbeat)
  events.py               Event-Bus (Redis Pub/Sub) für SSE und Steuerbefehle
  streaming_decoder_service.py  APRS/POCSAG/Multi-Channel-Streaming
  vox_recorder.py         VOX (Squelch-Gate)
  external_decoders.py    readsb / rtl_ais / rtl_433
  alerts.py / scheduler.py  Alarmregeln + Benachrichtigung / Zeitpläne (APScheduler)
  storage.py              Storage-Interface; elasticsearch_service.py, storage_sqlite.py
  sdr_hardware.py         Hardware-Abstraktion (HackRF, RTL-SDR, Airspy HF+, USRP)
config/                   gunicorn_config.py, direwolf.conf (im Image unter /app)
tests/                    pytest; Konfiguration von pytest, mypy, coverage und ruff in pyproject.toml
frontend/                 Svelte 5 + TypeScript + Vite + Tailwind 4
monitoring/               ELK-Konfiguration, Templates, Dashboards
scripts/                  Setup, Import, Hardware-Tests
```

## Backend

Getestet wird im Docker-Image, das auch alle SDR-Werkzeuge enthält (Python 3.13):

```bash
docker build --target test -t radiomoni-api-test .
docker run --rm -v "$PWD":/src -w /src -e HOME=/tmp radiomoni-api-test pytest -q        # Coverage ≥ 60 %
docker run --rm -v "$PWD":/src -w /src radiomoni-api-test ruff check --exclude tests,scripts .
docker run --rm -v "$PWD":/src -w /src radiomoni-api-test ./scripts/run_mypy.sh          # strict
```

Die Tests laufen mit fakeredis, einer SQLite-Instanz pro Test und simulierter Hardware (`mock_sdr_hardware`). Hardware-Tests mit echtem Gerät liegen in `scripts/tests/manual-tests/`.

Lokale API ohne Docker (nur zum Entwickeln):

```bash
pip install -r requirements-dev.txt
ALLOW_INSECURE=true REDIS_FAKE=1 STORAGE_BACKEND=sqlite python3 -m radiomoni.api_service
```

## Frontend

```bash
cd frontend
npm ci
API_TARGET=http://localhost:8080/api npm run dev   # Vite-Dev-Server, proxied /api zum laufenden Stack
npm run check && npm run lint && npm test           # svelte-check, ESLint/Prettier, Vitest
npm run e2e                                         # Playwright mit gemockter API
```

Regeln:
- Radio-Daten nie per `{@html}` ausgeben (die Lint-Regel ist ein Fehler).
- Alle API-Aufrufe gehen über `src/lib/api.ts`, live-Daten über `live.on()` in `stores.svelte.ts`.

## Neuer Endpunkt

1. Ein pydantic-Modell in `schemas.py` anlegen.
2. Im Blueprint: `@bp.post(...)` + `@api('Beschreibung', tags=[...], body=Modell)`, im Handler `parse_body(Modell)`.
3. Erwartete Fehler als `ApiError` werfen, SDR-Aktionen über `call_action()` aufrufen (erzeugt 409/400/503).
4. Test schreiben. `test_all_routes_documented` stellt sicher, dass der Endpunkt im OpenAPI-Dokument auftaucht.

## CI

`.github/workflows/ci.yml`: gitleaks, ruff, mypy, pytest, pip-audit, ESLint, svelte-check, Vitest, npm audit, Playwright, Image-Build mit Trivy-Scan.

Entwickelt wird direkt auf `main`, deshalb gibt es kein Dependabot (es arbeitet nur mit eigenen Branches und Pull Requests). Veraltete Abhängigkeiten findest du so:

```bash
docker run --rm radiomoni-api-test pip list --outdated     # Python (Test-Image)
cd frontend && npm outdated                                  # Frontend
```

Neue Versionen in `requirements*.txt` bzw. `frontend/package.json` eintragen (bei npm danach `npm install`), die CI-Schritte lokal laufen lassen und direkt auf `main` committen. Ausnahmen: `av` bleibt auf 18.x, solange `faster-whisper` PyAV 19 nicht unterstützt; `typescript` bleibt auf 5.x, solange `svelte-check` TypeScript 7 nicht unterstützt.
