# Entwicklung

🇬🇧 **[English Version](#english-version)** below

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
  decoders/               aprs.py / pocsag.py (Einzeldatei), streaming.py (APRS/POCSAG/Multi-Channel-Streaming),
                          vox.py (VOX, Squelch-Gate), external.py (readsb / rtl_ais / rtl_433)
  alerts.py / scheduler.py  Alarmregeln + Benachrichtigung / Zeitpläne (APScheduler)
  storage/                base.py (Storage-Interface, get_storage), elasticsearch.py, sqlite.py
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

Die Tests laufen mit fakeredis, einer SQLite-Instanz pro Test und simulierter Hardware (`mock_sdr_hardware`).

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
- Texte der Oberfläche immer mit `t('Deutscher Text')` aus `src/lib/i18n.svelte.ts` ausgeben und die englische Übersetzung in `src/lib/i18n/en.ts` eintragen. Platzhalter: `t('{n} Pakete', { n })`. `i18n.test.ts` schlägt fehl, wenn eine Übersetzung fehlt oder übrig ist.

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

## Version und Release

Die Versionsnummer (SemVer) steht in `radiomoni/version.py`. Von dort liest sie `pyproject.toml`, die API (OpenAPI, `/health`) und `scripts/version.py`, das sie ins README-Badge und nach `frontend/package.json`/`package-lock.json` schreibt. Die CI bricht ab, wenn eine Stelle abweicht.

```bash
python3 scripts/version.py set 4.1.0     # alle Stellen setzen
python3 scripts/version.py check         # prüfen (läuft in der CI)
```

Release: Abschnitt `## [Unreleased]` im CHANGELOG in `## [4.1.0] – JJJJ-MM-TT` umbenennen und einen leeren `[Unreleased]`-Abschnitt darüber anlegen, Version setzen, committen, `git tag v4.1.0` und `git push --tags`.

---

<a id="english-version"></a>

## English Version

### Structure

```
radiomoni/                Python package of the API:
  api_service.py          entry point (Gunicorn: radiomoni.api_service:app)
  app_factory.py          Flask app: security, errors, blueprints, scheduler, control listener
  config.py               all environment variables
  schemas.py              pydantic schemas (validation + OpenAPI)
  api_docs.py             @api decorator, parse_body/parse_query, OpenAPI generator
  security.py / errors.py auth, CORS, headers / uniform error responses
  blueprints/             REST endpoints
  jobs.py / actions.py    SDR jobs (capture, scan, stream start) / shared actions for API + scheduler
  sdr_lock.py             SDR lock in Redis (lease with heartbeat)
  events.py               event bus (Redis pub/sub) for SSE and control commands
  decoders/               aprs.py / pocsag.py (single file), streaming.py (APRS/POCSAG/multi-channel streaming),
                          vox.py (VOX, squelch gate), external.py (readsb / rtl_ais / rtl_433)
  alerts.py / scheduler.py  alert rules + notification / schedules (APScheduler)
  storage/                base.py (storage interface, get_storage), elasticsearch.py, sqlite.py
  sdr_hardware.py         hardware abstraction (HackRF, RTL-SDR, Airspy HF+, USRP)
config/                   gunicorn_config.py, direwolf.conf (under /app in the image)
tests/                    pytest; configuration of pytest, mypy, coverage and ruff in pyproject.toml
frontend/                 Svelte 5 + TypeScript + Vite + Tailwind 4
monitoring/               ELK configuration, templates, dashboards
scripts/                  setup, import, hardware tests
```

### Backend

Tests run in the Docker image, which also contains all SDR tools (Python 3.13):

```bash
docker build --target test -t radiomoni-api-test .
docker run --rm -v "$PWD":/src -w /src -e HOME=/tmp radiomoni-api-test pytest -q        # coverage ≥ 60 %
docker run --rm -v "$PWD":/src -w /src radiomoni-api-test ruff check --exclude tests,scripts .
docker run --rm -v "$PWD":/src -w /src radiomoni-api-test ./scripts/run_mypy.sh          # strict
```

The tests run with fakeredis, one SQLite instance per test and simulated hardware (`mock_sdr_hardware`).

Local API without Docker (for development only):

```bash
pip install -r requirements-dev.txt
ALLOW_INSECURE=true REDIS_FAKE=1 STORAGE_BACKEND=sqlite python3 -m radiomoni.api_service
```

### Frontend

```bash
cd frontend
npm ci
API_TARGET=http://localhost:8080/api npm run dev   # Vite dev server, proxies /api to the running stack
npm run check && npm run lint && npm test           # svelte-check, ESLint/Prettier, Vitest
npm run e2e                                         # Playwright with a mocked API
```

Rules:
- Never output radio data with `{@html}` (the lint rule is an error).
- All API calls go through `src/lib/api.ts`, live data through `live.on()` in `stores.svelte.ts`.
- Always output UI texts with `t('German text')` from `src/lib/i18n.svelte.ts` and add the English translation to `src/lib/i18n/en.ts`. Placeholders: `t('{n} Pakete', { n })`. `i18n.test.ts` fails when a translation is missing or left over.

### New endpoint

1. Create a pydantic model in `schemas.py`.
2. In the blueprint: `@bp.post(...)` + `@api('Description', tags=[...], body=Model)`, in the handler `parse_body(Model)`.
3. Raise expected errors as `ApiError`, call SDR actions through `call_action()` (produces 409/400/503).
4. Write a test. `test_all_routes_documented` makes sure the endpoint appears in the OpenAPI document.

### CI

`.github/workflows/ci.yml`: gitleaks, ruff, mypy, pytest, pip-audit, ESLint, svelte-check, Vitest, npm audit, Playwright, image build with Trivy scan.

Development happens directly on `main`, so there is no Dependabot (it only works with its own branches and pull requests). To find outdated dependencies:

```bash
docker run --rm radiomoni-api-test pip list --outdated     # Python (test image)
cd frontend && npm outdated                                  # frontend
```

Enter new versions in `requirements*.txt` or `frontend/package.json` (for npm, run `npm install` afterwards), run the CI steps locally and commit directly to `main`. Exceptions: `av` stays on 18.x as long as `faster-whisper` does not support PyAV 19; `typescript` stays on 5.x as long as `svelte-check` does not support TypeScript 7.

### Version and release

The version number (SemVer) lives in `radiomoni/version.py`. `pyproject.toml`, the API (OpenAPI, `/health`) and `scripts/version.py` read it from there; the script writes it to the README badge and to `frontend/package.json`/`package-lock.json`. CI fails if any place differs.

```bash
python3 scripts/version.py set 4.1.0     # set all places
python3 scripts/version.py check         # check (runs in CI)
```

Release: rename the `## [Unreleased]` section in the CHANGELOG to `## [4.1.0] – YYYY-MM-DD` and add an empty `[Unreleased]` section above it, set the version, commit, `git tag v4.1.0` and `git push --tags`.
