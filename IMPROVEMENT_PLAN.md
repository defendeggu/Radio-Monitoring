# Radio Monitoring System - Verbesserungsplan

**Erstellt:** 04. Januar 2026
**Status:** Bereit zur Umsetzung
**Geschätzte Gesamtdauer:** 3-4 Wochen (kann schrittweise umgesetzt werden)

---

## 📋 Übersicht

Dieser Plan adressiert drei Hauptbereiche basierend auf der Projekt-Analyse:

1. **Testabdeckung erhöhen** (Höchste Priorität) - 40% der Arbeit
2. **Konfiguration vervollständigen** (Schnellste Umsetzung) - 10% der Arbeit
3. **API refaktorisieren** (Größte Verbesserung langfristig) - 50% der Arbeit

---

## 🎯 Phase 1: Konfiguration vervollständigen (QUICK WIN)

**Priorität:** Mittel
**Aufwand:** 1-2 Stunden
**Risiko:** Sehr niedrig

### 1.1 `.env.example` erweitern

**Problem:**
Die `.env.example` ist unvollständig und erschwert neuen Entwicklern die Einrichtung.

**Aktuelle `.env.example` (18 Zeilen):**
- Nur Basic-Konfiguration (Frequency, Whisper, etc.)
- **Fehlt:** API_KEYS, ELASTICSEARCH_*, REDIS_*, Security Credentials

**Lösung - Zu ergänzen:**

```bash
# ============================================================================
# API Security (REQUIRED for Production)
# ============================================================================
# Generate with: python3 scripts/generate_api_keys.py
# Comma-separated list of API keys
API_KEYS=your-api-key-1-here,your-api-key-2-here

# ============================================================================
# Elasticsearch Configuration
# ============================================================================
# Elasticsearch hosts (comma-separated)
ELASTICSEARCH_HOSTS=http://elasticsearch:9200
ELASTICSEARCH_URL=http://elastic:${ELASTIC_PASSWORD}@elasticsearch:9200
ELASTICSEARCH_URL_EXTERNAL=http://elastic:${ELASTIC_PASSWORD}@localhost:9200

# Index prefix for radio captures
INDEX_PREFIX=radio

# ============================================================================
# Redis Configuration (for Streaming Sessions)
# ============================================================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
# Optional Redis password
REDIS_PASSWORD=

# ============================================================================
# ELK Stack Security Credentials
# ============================================================================
# Generate with: ./setup-elk-security.sh
ELASTIC_PASSWORD=changeme
KIBANA_SYSTEM_PASSWORD=changeme
LOGSTASH_SYSTEM_PASSWORD=changeme
BEATS_SYSTEM_PASSWORD=changeme

# ============================================================================
# Streaming Decoder Configuration
# ============================================================================
# Session timeout in seconds
STREAM_SESSION_TIMEOUT=300
# Max concurrent streaming sessions
MAX_STREAMING_SESSIONS=10

# ============================================================================
# Repeater Scanner Configuration
# ============================================================================
# Max concurrent repeater scans
MAX_REPEATER_SCANS=5
# Session cleanup interval (hours)
REPEATER_SESSION_MAX_AGE_HOURS=24

# ============================================================================
# N8N Integration
# ============================================================================
N8N_WEBHOOK_URL=http://n8n:5678/webhook/radio-transcription
N8N_HOST=http://n8n:5679
```

**Schritte:**
1. [ ] `.env.example` mit allen Variablen ergänzen
2. [ ] Kommentare für jede Variable hinzufügen (Zweck erklären)
3. [ ] Placeholder-Werte (changeme, your-key-here) verwenden
4. [ ] In README.md auf `.env.example` verweisen
5. [ ] setup.sh Script prüfen ob es `.env.example` → `.env` kopiert

**Akzeptanzkriterien:**
- [ ] Alle in `.env` verwendeten Variablen sind in `.env.example` dokumentiert
- [ ] Neue Entwickler können `.env.example` → `.env` kopieren und System starten
- [ ] Jede Variable hat hilfreichen Kommentar

---

## 🧪 Phase 2: Testabdeckung erhöhen (HÖCHSTE PRIORITÄT)

**Priorität:** KRITISCH
**Aufwand:** 2-3 Tage
**Risiko:** Mittel (Test-Komplexität)

### 2.1 Repeater Scanning Tests

**Problem:**
Der gesamte Repeater-Scanning-Workflow ist ungetestet (0% Coverage).

**Aktuelle Situation:**
- `repeater_activity_analyzer.py`: 0 Tests
- API Endpoint `/scan_repeaters`: 0 Tests
- Session Management: 0 Tests
- Progress Tracking: 0 Tests

**Zu testende Komponenten:**

#### Test-Datei: `tests/test_repeater_scanning.py` (neu)

```python
# Test-Kategorien:
1. RepeaterActivityAnalyzer Unit Tests (10 Tests)
   - analyze_repeater() - Aktivitätserkennung
   - _detect_transmissions() - Signal-Detection
   - _calculate_activity_percentage() - Berechnungen
   - Error Handling (keine Repeater-Daten, ungültige Parameter)

2. API Integration Tests (8 Tests)
   - POST /scan_repeaters - Start scan
   - GET /scan_repeaters/<session_id> - Status abrufen
   - GET /scan_repeaters/<session_id>/results - Ergebnisse
   - Cancel scan funktioniert
   - Concurrent scans (mehrere Sessions gleichzeitig)
   - Session cleanup nach MAX_AGE
   - Session limit (MAX_SESSIONS)
   - Invalid session ID handling

3. Progress Tracking Tests (4 Tests)
   - Progress updates während Scan
   - ETA Berechnung korrekt
   - Live-Updates über SSE (Server-Sent Events)
   - Abbruch stoppt Progress

4. Elasticsearch Integration Tests (3 Tests)
   - Ergebnisse werden in ES gespeichert
   - Index-Naming korrekt (radio-repeater-activity-YYYY.MM.DD)
   - Query-Performance akzeptabel
```

**Implementierungsschritte:**

1. [ ] Mock-Daten für Repeater erstellen (CH-Repeater CSV)
2. [ ] `tests/test_repeater_scanning.py` anlegen
3. [ ] Fixtures erstellen:
   - `mock_repeater_data` - Test-Repeater-Liste
   - `mock_audio_analysis` - Simulierte Audio-Analyse
   - `mock_elasticsearch` - ES Mock für Speicherung
4. [ ] Unit Tests schreiben (RepeaterActivityAnalyzer)
5. [ ] API Integration Tests schreiben
6. [ ] Progress Tracking Tests schreiben
7. [ ] ES Integration Tests schreiben
8. [ ] Coverage-Report prüfen (Ziel: >70% für repeater_activity_analyzer.py)

**Akzeptanzkriterien:**
- [ ] Mindestens 25 Tests für Repeater-Scanning
- [ ] Code Coverage >70% für `repeater_activity_analyzer.py`
- [ ] Alle kritischen Pfade getestet (start, progress, results, cancel)
- [ ] Concurrent scan scenarios getestet

---

### 2.2 Streaming Decoder Tests

**Problem:**
Streaming APRS/POCSAG Decoder sind ungetestet (0% Coverage).

**Aktuelle Situation:**
- `streaming_decoder_service.py`: 0 Tests
- `StreamingAPRSDecoder`: 0 Tests
- `StreamingPOCSAGDecoder`: 0 Tests
- `SessionManager` (Redis): 0 Tests

**Zu testende Komponenten:**

#### Test-Datei: `tests/test_streaming_decoders.py` (neu)

```python
# Test-Kategorien:
1. SessionManager Tests (8 Tests)
   - create_session() - Session erstellen
   - get_session() - Session abrufen
   - update_session() - Session updaten
   - delete_session() - Session löschen
   - Session expiry (TTL in Redis)
   - list_active_sessions()
   - Concurrent session access (Thread-Safety)
   - Redis connection failure handling

2. StreamingAPRSDecoder Tests (10 Tests)
   - start_stream() - Stream starten
   - stop_stream() - Stream stoppen
   - decode_packet() - APRS Paket dekodieren
   - _process_audio_stream() - Audio-Verarbeitung
   - Error handling (invalid packets, corrupt audio)
   - Decoder-Status Updates
   - Packet-Callback funktioniert
   - Multiple concurrent streams
   - Resource cleanup nach Stop
   - Elasticsearch logging

3. StreamingPOCSAGDecoder Tests (10 Tests)
   - Analog zu APRS (gleiche Test-Struktur)
   - POCSAG-spezifische Dekodierung
   - Baud rate detection (512, 1200, 2400)
   - Address filtering
   - Message type detection

4. API Integration Tests (6 Tests)
   - POST /stream/aprs/start
   - GET /stream/aprs/<session_id>/status
   - POST /stream/aprs/<session_id>/stop
   - GET /stream/aprs/<session_id>/packets
   - Same for POCSAG
   - Session limit enforcement
```

**Implementierungsschritte:**

1. [ ] Redis Mock Setup für Tests
2. [ ] `tests/test_streaming_decoders.py` anlegen
3. [ ] Test-Audio-Streams generieren (APRS/POCSAG Test-Signale)
4. [ ] Fixtures erstellen:
   - `redis_client` - Mock Redis Client
   - `sample_aprs_packets` - Test APRS-Daten
   - `sample_pocsag_packets` - Test POCSAG-Daten
   - `mock_sdr_stream` - Simulierter SDR-Stream
5. [ ] SessionManager Tests schreiben
6. [ ] StreamingAPRSDecoder Tests schreiben
7. [ ] StreamingPOCSAGDecoder Tests schreiben
8. [ ] API Integration Tests schreiben
9. [ ] Coverage-Report prüfen (Ziel: >70%)

**Akzeptanzkriterien:**
- [ ] Mindestens 34 Tests für Streaming Decoders
- [ ] Code Coverage >70% für `streaming_decoder_service.py`
- [ ] Redis SessionManager vollständig getestet
- [ ] Stream lifecycle (start → running → stop) getestet
- [ ] Concurrent streams getestet

---

### 2.3 APRS & POCSAG Decoder Tests

**Problem:**
APRS/POCSAG Dekodierpfade sind ungetestet (0% Coverage).

**Aktuelle Situation:**
- `aprs_decoder_service.py`: 0 Tests
- `pocsag_decoder_service.py`: 0 Tests
- Decode-Workflows: 0 Tests

**Zu testende Komponenten:**

#### Test-Datei: `tests/test_aprs_decoder.py` (neu)

```python
# Test-Kategorien:
1. APRSDecoder Unit Tests (12 Tests)
   - decode_capture() - Dekodierung
   - _parse_aprs_packet() - Packet Parsing
   - _extract_position() - GPS-Koordinaten
   - _extract_message() - Nachricht
   - Invalid packet handling
   - Verschiedene Pakettypen (Position, Message, Status, etc.)
   - Callsign parsing
   - Timestamp handling
   - Error cases (corrupt data, invalid format)

2. API Integration Tests (5 Tests)
   - POST /aprs/decode - Erfolgreicher Decode
   - Error handling (missing file, invalid format)
   - Elasticsearch logging
   - Multiple packets in one capture
   - Regional frequency handling (144.800 vs 144.390 MHz)
```

#### Test-Datei: `tests/test_pocsag_decoder.py` (neu)

```python
# Test-Kategorien:
1. POCSAGDecoder Unit Tests (12 Tests)
   - decode_capture() - Dekodierung
   - _parse_pocsag_message() - Message Parsing
   - _detect_baud_rate() - Baud Rate Detection
   - Address parsing
   - Message type detection (numeric, alphanumeric)
   - Function bits handling
   - Error correction
   - Invalid message handling
   - Multiple messages in capture

2. API Integration Tests (5 Tests)
   - POST /pocsag/decode
   - Different baud rates (512, 1200, 2400)
   - Different message types
   - Elasticsearch logging
   - Error handling
```

**Implementierungsschritte:**

1. [ ] Test-Captures erstellen (echte APRS/POCSAG Samples)
2. [ ] `tests/test_aprs_decoder.py` anlegen
3. [ ] `tests/test_pocsag_decoder.py` anlegen
4. [ ] Fixtures erstellen:
   - `aprs_test_packets` - Verschiedene APRS-Pakettypen
   - `pocsag_test_messages` - Verschiedene POCSAG-Nachrichten
   - `mock_direwolf` - Direwolf Mock
   - `mock_multimon_ng` - multimon-ng Mock
5. [ ] APRS Unit Tests schreiben
6. [ ] APRS API Tests schreiben
7. [ ] POCSAG Unit Tests schreiben
8. [ ] POCSAG API Tests schreiben
9. [ ] Coverage-Report prüfen (Ziel: >70%)

**Akzeptanzkriterien:**
- [ ] Mindestens 34 Tests für APRS/POCSAG Decoder
- [ ] Code Coverage >70% für beide Decoder-Services
- [ ] Verschiedene Paket-/Nachrichtentypen getestet
- [ ] Error-Handling getestet
- [ ] Elasticsearch Integration getestet

---

### 2.4 Elasticsearch Integration Tests

**Problem:**
Datenbank-Queries sind größtenteils ungetestet.

**Aktuelle Situation:**
- `elasticsearch_service.py`: Minimale Tests
- Index-Operationen: Nicht getestet
- Query-Performance: Nicht gemessen

**Zu testende Komponenten:**

#### Test-Datei: `tests/test_elasticsearch_integration.py` (neu)

```python
# Test-Kategorien:
1. Connection & Setup Tests (5 Tests)
   - get_elasticsearch_service() - Connection
   - Health check
   - Index creation
   - Index template setup
   - Connection failure handling

2. Document Operations Tests (8 Tests)
   - log_capture() - Voice capture logging
   - log_aprs_packet() - APRS logging
   - log_pocsag_message() - POCSAG logging
   - log_repeater_scan() - Repeater scan logging
   - log_streaming_session() - Stream session logging
   - Bulk operations
   - Error handling (invalid documents)
   - Document ID generation

3. Query Tests (6 Tests)
   - search_captures() - Suche funktioniert
   - filter_by_frequency()
   - filter_by_modulation()
   - time_range_queries()
   - Aggregations (top callsigns, etc.)
   - Performance (query time <100ms für 10k docs)

4. Index Management Tests (4 Tests)
   - Daily index rotation (YYYY.MM.DD)
   - Old index cleanup
   - Index alias handling
   - Reindexing
```

**Implementierungsschritte:**

1. [ ] Elasticsearch Test-Container Setup (docker-compose.test.yml)
2. [ ] `tests/test_elasticsearch_integration.py` anlegen
3. [ ] Fixtures erstellen:
   - `elasticsearch_client` - Test ES Client
   - `test_index` - Temporärer Test-Index
   - `sample_documents` - Test-Dokumente (100+)
4. [ ] Connection Tests schreiben
5. [ ] Document Operation Tests schreiben
6. [ ] Query Tests schreiben
7. [ ] Index Management Tests schreiben
8. [ ] Performance-Benchmarks hinzufügen
9. [ ] Coverage-Report prüfen

**Akzeptanzkriterien:**
- [ ] Mindestens 23 Tests für Elasticsearch
- [ ] Code Coverage >80% für `elasticsearch_service.py`
- [ ] Query Performance getestet (< 100ms für typische Queries)
- [ ] Alle Index-Typen getestet (captures, aprs, pocsag, repeater)
- [ ] Error scenarios getestet

---

### 2.5 Test-Infrastruktur Verbesserungen

**Allgemeine Verbesserungen für alle Tests:**

1. [ ] **Docker Compose für Tests:**
   - `docker-compose.test.yml` erstellen
   - Redis Container für Session-Tests
   - Elasticsearch Container für ES-Tests
   - Automatischer Start vor Tests (pytest plugin)

2. [ ] **Test-Daten Repository:**
   - `tests/fixtures/` Verzeichnis
   - Sample APRS packets (JSON)
   - Sample POCSAG messages (JSON)
   - Sample audio files (WAV)
   - Sample IQ files (für SDR-Tests)
   - Repeater test data (CSV)

3. [ ] **Performance Tests:**
   - `tests/test_performance.py` anlegen
   - Load tests für API (100 concurrent requests)
   - Streaming performance (10 concurrent streams)
   - Elasticsearch query performance
   - Memory leak tests (long-running scans)

4. [ ] **Coverage-Ziele:**
   - Overall: 40% → 60%
   - Kritische Services: 70%+
   - API Endpoints: 80%+
   - Utilities: 50%+

5. [ ] **CI/CD Integration:**
   - GitHub Actions erweitern:
     - Docker Compose Test-Stack starten
     - Alle neuen Tests ausführen
     - Coverage-Report generieren
     - Coverage-Badge in README
     - Performance-Regression checks

**Akzeptanzkriterien:**
- [ ] Test-Infrastruktur vollständig automatisiert
- [ ] Tests lokal UND in CI lauffähig
- [ ] Coverage-Reports automatisch generiert
- [ ] Performance-Baseline dokumentiert

---

## 🔧 Phase 3: API Refactoring (Flask Blueprints)

**Priorität:** Hoch
**Aufwand:** 1-2 Wochen
**Risiko:** Mittel (Breaking Changes möglich)

### 3.1 Aktuelle Situation: Monolithische API

**Problem:**
`api_service.py` ist mit **1869 Zeilen** schwer wartbar.

**Aktuelle Struktur:**
```
api_service.py (1869 Zeilen)
├── Security (API Keys, Trusted IPs)
├── Health Endpoint
├── Capture Endpoints (/capture, /capture_and_transcribe)
├── Transcription Endpoints (/transcribe)
├── APRS Endpoints (/aprs/decode)
├── POCSAG Endpoints (/pocsag/decode)
├── Repeater Scan Endpoints (/scan_repeaters/*)
├── Streaming Endpoints (/stream/*)
├── Recording Management (/recordings/*)
└── Session Management (in-memory scan_sessions)
```

**Probleme:**
- Schwer zu navigieren (1869 Zeilen)
- Kein klares Separation of Concerns
- Session-Management im Hauptfile
- Schwer zu testen (alles in einer Datei)
- Import-Chaos (alle Services gemischt)

---

### 3.2 Ziel-Architektur: Modulare API mit Blueprints

**Flask Blueprints Pattern:**
https://flask.palletsprojects.com/en/3.0.x/blueprints/

**Neue Struktur:**

```
api/
├── __init__.py                    # App Factory
├── config.py                      # Configuration
├── middlewares/
│   ├── __init__.py
│   ├── auth.py                    # API Key Authentication
│   └── error_handlers.py          # Global Error Handlers
├── blueprints/
│   ├── __init__.py
│   ├── health.py                  # Health Check Blueprint
│   ├── capture.py                 # SDR Capture Blueprint
│   ├── transcription.py           # Transcription Blueprint
│   ├── aprs.py                    # APRS Decoder Blueprint
│   ├── pocsag.py                  # POCSAG Decoder Blueprint
│   ├── repeater.py                # Repeater Scanning Blueprint
│   ├── streaming.py               # Streaming Decoders Blueprint
│   └── recordings.py              # Recording Management Blueprint
├── services/                      # Business Logic (existing services)
│   ├── sdr_hardware.py           # (existing)
│   ├── transcription_service.py  # (existing)
│   ├── aprs_decoder_service.py   # (existing)
│   ├── pocsag_decoder_service.py # (existing)
│   ├── repeater_activity_analyzer.py # (existing)
│   ├── streaming_decoder_service.py  # (existing)
│   └── elasticsearch_service.py  # (existing)
├── models/                        # Data Models
│   ├── __init__.py
│   ├── capture.py                # CaptureRequest, CaptureResponse
│   ├── transcription.py          # TranscribeRequest, TranscribeResponse
│   ├── aprs.py                   # APRSPacket
│   ├── pocsag.py                 # POCSAGMessage
│   └── repeater.py               # RepeaterScanSession
└── utils/
    ├── __init__.py
    ├── session_manager.py        # Unified Session Manager (Redis)
    └── validators.py             # Input Validation

# Root-Level
api_service.py                     # Simplified Entry Point (50 lines)
wsgi.py                           # Gunicorn Entry Point (new)
```

---

### 3.3 Implementierungsplan - Schrittweises Refactoring

**Strategie:** Schrittweise Migration ohne Breaking Changes

#### Schritt 1: Projektstruktur vorbereiten (Tag 1)

1. [ ] `api/` Verzeichnis erstellen
2. [ ] `api/__init__.py` - App Factory Pattern
3. [ ] `api/config.py` - Configuration aus ENV
4. [ ] `api/blueprints/` Verzeichnis
5. [ ] `api/middlewares/` Verzeichnis
6. [ ] `api/models/` Verzeichnis
7. [ ] `api/utils/` Verzeichnis

**Code-Beispiel: `api/__init__.py` (App Factory)**

```python
"""
Flask Application Factory
"""
from flask import Flask
from flask_cors import CORS
from .config import Config
from .middlewares.auth import init_auth
from .middlewares.error_handlers import init_error_handlers

def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Enable CORS
    CORS(app)

    # Initialize middlewares
    init_auth(app)
    init_error_handlers(app)

    # Register blueprints
    from .blueprints import (
        health_bp,
        capture_bp,
        transcription_bp,
        aprs_bp,
        pocsag_bp,
        repeater_bp,
        streaming_bp,
        recordings_bp
    )

    app.register_blueprint(health_bp)
    app.register_blueprint(capture_bp, url_prefix='/api')
    app.register_blueprint(transcription_bp, url_prefix='/api')
    app.register_blueprint(aprs_bp, url_prefix='/api/aprs')
    app.register_blueprint(pocsag_bp, url_prefix='/api/pocsag')
    app.register_blueprint(repeater_bp, url_prefix='/api/repeater')
    app.register_blueprint(streaming_bp, url_prefix='/api/stream')
    app.register_blueprint(recordings_bp, url_prefix='/api/recordings')

    return app
```

---

#### Schritt 2: Blueprints erstellen (Tag 2-3)

**Reihenfolge:** Einfachste zuerst → Komplexeste zuletzt

**2.1 Health Blueprint (Einfachste)**

1. [ ] `api/blueprints/health.py` erstellen
2. [ ] `/health` Endpoint migrieren
3. [ ] Tests anpassen
4. [ ] Verifizieren dass Health Check funktioniert

**Code-Beispiel: `api/blueprints/health.py`**

```python
"""Health Check Blueprint"""
from flask import Blueprint, jsonify
from ..services.sdr_hardware import detect_sdr

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint (public, no auth required)"""
    sdr_type = detect_sdr()
    return jsonify({
        'status': 'healthy',
        'sdr_available': sdr_type is not None,
        'sdr_type': str(sdr_type) if sdr_type else None
    }), 200
```

**2.2 Capture Blueprint**

1. [ ] `api/blueprints/capture.py` erstellen
2. [ ] `/capture` Endpoint migrieren
3. [ ] `/capture_and_transcribe` Endpoint migrieren
4. [ ] Input Validation extrahieren
5. [ ] Tests anpassen

**2.3 Transcription Blueprint**

1. [ ] `api/blueprints/transcription.py` erstellen
2. [ ] `/transcribe` Endpoint migrieren
3. [ ] Tests anpassen

**2.4 APRS Blueprint**

1. [ ] `api/blueprints/aprs.py` erstellen
2. [ ] `/aprs/decode` Endpoint migrieren
3. [ ] Tests anpassen (oder erstellen falls noch nicht vorhanden)

**2.5 POCSAG Blueprint**

1. [ ] `api/blueprints/pocsag.py` erstellen
2. [ ] `/pocsag/decode` Endpoint migrieren
3. [ ] Tests anpassen

**2.6 Recordings Blueprint**

1. [ ] `api/blueprints/recordings.py` erstellen
2. [ ] `/recordings` Endpoint migrieren
3. [ ] File handling Logic
4. [ ] Tests anpassen

**2.7 Repeater Blueprint (Komplex)**

1. [ ] `api/blueprints/repeater.py` erstellen
2. [ ] `/scan_repeaters` Endpoints migrieren
3. [ ] **Session Manager nach Redis migrieren** (siehe Schritt 3)
4. [ ] Tests erstellen (Phase 2.1)

**2.8 Streaming Blueprint (Komplexeste)**

1. [ ] `api/blueprints/streaming.py` erstellen
2. [ ] `/stream/aprs/*` Endpoints migrieren
3. [ ] `/stream/pocsag/*` Endpoints migrieren
4. [ ] SSE (Server-Sent Events) handling
5. [ ] Tests erstellen (Phase 2.2)

---

#### Schritt 3: Session Management nach Redis migrieren (Tag 4-5)

**Problem:**
Repeater Scan Sessions sind in-memory (`scan_sessions` dict).

**Lösung:**
Unified Session Manager mit Redis (wie Streaming Sessions).

**3.1 Unified Session Manager**

1. [ ] `api/utils/session_manager.py` erstellen
2. [ ] `UnifiedSessionManager` Klasse implementieren
3. [ ] Redis-Backend für alle Sessions
4. [ ] Support für verschiedene Session-Typen:
   - `repeater_scan`
   - `aprs_stream`
   - `pocsag_stream`

**Code-Beispiel: `api/utils/session_manager.py`**

```python
"""
Unified Session Manager with Redis Backend
Replaces in-memory session storage
"""
import json
import redis
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

class UnifiedSessionManager:
    """Redis-based session manager for all session types"""

    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 86400):
        self.redis = redis_client
        self.ttl = ttl_seconds

    def create_session(
        self,
        session_type: str,
        session_data: Dict[str, Any]
    ) -> str:
        """Create new session and return session ID"""
        session_id = str(uuid.uuid4())
        key = f"session:{session_type}:{session_id}"

        data = {
            'id': session_id,
            'type': session_type,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            **session_data
        }

        self.redis.setex(
            key,
            self.ttl,
            json.dumps(data)
        )

        return session_id

    def get_session(
        self,
        session_type: str,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        key = f"session:{session_type}:{session_id}"
        data = self.redis.get(key)

        if data:
            return json.loads(data)
        return None

    def update_session(
        self,
        session_type: str,
        session_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update session data"""
        session = self.get_session(session_type, session_id)
        if not session:
            return False

        session.update(updates)
        session['updated_at'] = datetime.utcnow().isoformat()

        key = f"session:{session_type}:{session_id}"
        self.redis.setex(key, self.ttl, json.dumps(session))

        return True

    def delete_session(
        self,
        session_type: str,
        session_id: str
    ) -> bool:
        """Delete session"""
        key = f"session:{session_type}:{session_id}"
        return self.redis.delete(key) > 0

    def list_sessions(
        self,
        session_type: str,
        filter_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all sessions of given type"""
        pattern = f"session:{session_type}:*"
        sessions = []

        for key in self.redis.scan_iter(match=pattern):
            data = self.redis.get(key)
            if data:
                session = json.loads(data)
                if filter_status is None or session.get('status') == filter_status:
                    sessions.append(session)

        return sessions
```

**3.2 Repeater Scanner auf Redis migrieren**

1. [ ] `repeater_activity_analyzer.py` anpassen
2. [ ] In-memory `scan_sessions` dict entfernen
3. [ ] `UnifiedSessionManager` verwenden
4. [ ] Session-Lifecycle anpassen:
   - create → Redis
   - update progress → Redis
   - get results → Redis
   - cleanup → Redis TTL
5. [ ] Tests anpassen

**3.3 Session Cleanup**

1. [ ] Automatischer Redis TTL (Time-To-Live)
2. [ ] Cleanup-Task entfernen (Redis handled das)
3. [ ] Session-Monitoring in Kibana

---

#### Schritt 4: Middlewares implementieren (Tag 6)

**4.1 Authentication Middleware**

1. [ ] `api/middlewares/auth.py` erstellen
2. [ ] API Key Validation extrahieren
3. [ ] Trusted IP Check extrahieren
4. [ ] Public Endpoints Config
5. [ ] Decorator `@require_api_key` für protected routes

**Code-Beispiel: `api/middlewares/auth.py`**

```python
"""API Authentication Middleware"""
import os
from functools import wraps
from flask import request, jsonify, current_app
from typing import Set

# Public endpoints (no auth required)
PUBLIC_ENDPOINTS: Set[str] = {'/health'}

def is_trusted_ip(ip_address: str) -> bool:
    """Check if IP is trusted (localhost, docker, private networks)"""
    # ... (existing logic)
    pass

def check_api_key() -> bool:
    """Validate API key from request header"""
    api_keys = current_app.config.get('API_KEYS', set())

    # No keys configured = allow all (dev mode)
    if not api_keys:
        return True

    # Check if endpoint is public
    if request.path in PUBLIC_ENDPOINTS:
        return True

    # Check if IP is trusted
    if is_trusted_ip(request.remote_addr):
        return True

    # Check API key header
    api_key = request.headers.get('X-API-Key')
    if api_key and api_key in api_keys:
        return True

    return False

def require_api_key(f):
    """Decorator to require API key for endpoint"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_api_key():
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Valid API key required'
            }), 401
        return f(*args, **kwargs)
    return decorated_function

def init_auth(app):
    """Initialize authentication for Flask app"""
    @app.before_request
    def before_request_auth():
        if not check_api_key():
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Valid API key required'
            }), 401
```

**4.2 Error Handlers**

1. [ ] `api/middlewares/error_handlers.py` erstellen
2. [ ] Globale Error Handler
3. [ ] Validation Errors
4. [ ] 404, 500 Errors
5. [ ] JSON-Format für alle Errors

---

#### Schritt 5: Models extrahieren (Tag 7)

**TypedDict → Pydantic Models (Optional, aber empfohlen)**

1. [ ] `requirements.txt` → `pydantic` hinzufügen
2. [ ] `api/models/capture.py` - CaptureRequest, CaptureResponse
3. [ ] `api/models/transcription.py` - TranscribeRequest, TranscribeResponse
4. [ ] `api/models/aprs.py` - APRSPacket, APRSDecodeRequest
5. [ ] `api/models/pocsag.py` - POCSAGMessage, POCSAGDecodeRequest
6. [ ] `api/models/repeater.py` - RepeaterScanRequest, RepeaterScanSession
7. [ ] Input Validation mit Pydantic
8. [ ] Automatic OpenAPI Schema Generation

**Vorteil:**
- Automatische Validation
- Better type checking
- OpenAPI/Swagger Docs automatisch
- IDE Autocomplete

---

#### Schritt 6: Entry Point vereinfachen (Tag 8)

**Aktuell:** `api_service.py` (1869 Zeilen)
**Ziel:** `api_service.py` (~50 Zeilen)

1. [ ] `api_service.py` drastisch vereinfachen
2. [ ] Nur noch App Factory aufrufen
3. [ ] `wsgi.py` für Gunicorn erstellen

**Code-Beispiel: Neuer `api_service.py`**

```python
#!/usr/bin/env python3
"""
Flask API Service Entry Point
Simplified with Application Factory Pattern
"""
import logging
from api import create_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app using factory
app = create_app()

if __name__ == '__main__':
    # Development server only
    logger.warning("Running Flask development server")
    logger.warning("For production use: gunicorn -c gunicorn_config.py api_service:app")
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
```

**Code-Beispiel: `wsgi.py` (für Gunicorn)**

```python
"""
WSGI Entry Point for Gunicorn
"""
from api import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
```

---

#### Schritt 7: Tests migrieren (Tag 9-10)

1. [ ] Alle Tests auf neue Blueprint-Struktur anpassen
2. [ ] `test_api_service.py` → Aufteilen in:
   - `test_health_blueprint.py`
   - `test_capture_blueprint.py`
   - `test_transcription_blueprint.py`
   - etc.
3. [ ] App Factory in conftest.py verwenden
4. [ ] Alle 67 bestehenden Tests müssen weiterhin passen
5. [ ] Neue Tests für Blueprints hinzufügen
6. [ ] Integration Tests aktualisieren

**Code-Beispiel: Updated `tests/conftest.py`**

```python
import pytest
from api import create_app
from api.config import TestConfig

@pytest.fixture
def app():
    """Create app with test configuration"""
    app = create_app(TestConfig)
    yield app

@pytest.fixture
def client(app):
    """Flask test client"""
    return app.test_client()
```

---

#### Schritt 8: Dokumentation & Deployment (Tag 11)

1. [ ] README.md aktualisieren
   - Neue Projekt-Struktur dokumentieren
   - Blueprint-Architektur erklären
   - Migration Guide für Entwickler
2. [ ] API-Dokumentation generieren (OpenAPI/Swagger)
3. [ ] Docker-Container anpassen
   - Neue Verzeichnisstruktur
   - wsgi.py verwenden
4. [ ] `gunicorn_config.py` aktualisieren
5. [ ] CI/CD Pipeline anpassen
6. [ ] Performance testen (Before/After Vergleich)

---

### 3.4 Migration Checklist

**Pre-Migration:**
- [ ] Alle bestehenden Tests laufen (67/67)
- [ ] Coverage Baseline dokumentiert (27%)
- [ ] Performance Baseline gemessen
- [ ] Backup von `api_service.py`

**Post-Migration Validation:**
- [ ] Alle 67 Tests laufen weiterhin
- [ ] Keine Performance-Regression
- [ ] Coverage mindestens gleich (27%+)
- [ ] Alle API Endpoints funktionieren
- [ ] Docker Deployment funktioniert
- [ ] Production Test (Staging)

**Rollback Plan:**
- [ ] Git Branch für Refactoring
- [ ] Kann jederzeit zu main zurück
- [ ] Feature Flag für neue Architektur (optional)

---

### 3.5 Vorteile nach Refactoring

**Wartbarkeit:**
- ✅ Klare Trennung der Concerns
- ✅ Jedes Blueprint ~100-200 Zeilen statt 1869
- ✅ Einfacher zu navigieren
- ✅ Leichter zu verstehen für neue Entwickler

**Testbarkeit:**
- ✅ Blueprints einzeln testbar
- ✅ Mocking einfacher
- ✅ Klarere Test-Struktur

**Skalierbarkeit:**
- ✅ Neue Features = Neues Blueprint
- ✅ Teams können parallel arbeiten
- ✅ Microservices-ready (jedes Blueprint → eigener Service möglich)

**Code-Qualität:**
- ✅ Bessere Type Hints mit Pydantic
- ✅ Automatische Validation
- ✅ OpenAPI Docs automatisch
- ✅ Weniger Code-Duplizierung

---

## 📊 Zusammenfassung & Priorisierung

### Empfohlene Umsetzungs-Reihenfolge

| Phase | Aufgabe | Priorität | Aufwand | Impact | Risiko |
|-------|---------|-----------|---------|--------|--------|
| **1.1** | `.env.example` vervollständigen | Mittel | 1-2h | Mittel | Niedrig |
| **2.1** | Repeater Scanning Tests | KRITISCH | 1-2 Tage | Hoch | Mittel |
| **2.2** | Streaming Decoder Tests | KRITISCH | 1-2 Tage | Hoch | Mittel |
| **2.3** | APRS/POCSAG Tests | Hoch | 1 Tag | Hoch | Niedrig |
| **2.4** | Elasticsearch Tests | Hoch | 1 Tag | Mittel | Niedrig |
| **2.5** | Test-Infrastruktur | Mittel | 0.5 Tag | Hoch | Niedrig |
| **3.1-3.8** | API Refactoring komplett | Hoch | 2 Wochen | Sehr Hoch | Mittel |

### Quick Wins (Sofort umsetzbar)

1. **`.env.example` vervollständigen** (1-2h)
   - Sofortiger Nutzen für neue Entwickler
   - Kein Risiko
   - Dokumentation verbessert

2. **Elasticsearch Tests schreiben** (1 Tag)
   - Relativ einfach
   - Hoher Impact auf Coverage
   - Niedriges Risiko

### High Impact (Wichtigste Verbesserungen)

1. **Repeater Scanning Tests** (KRITISCH)
   - Komplexeste Funktion völlig ungetestet
   - Höchstes Fehler-Risiko
   - Sollte ASAP umgesetzt werden

2. **API Refactoring** (Langfristig wichtigste Verbesserung)
   - Drastische Verbesserung der Wartbarkeit
   - Basis für zukünftige Features
   - Ermöglicht parallele Entwicklung

### Zeitplan (Beispiel für vollständige Umsetzung)

**Woche 1:**
- Tag 1: `.env.example` vervollständigen
- Tag 2-3: Repeater Scanning Tests
- Tag 4-5: Streaming Decoder Tests

**Woche 2:**
- Tag 1-2: APRS/POCSAG Tests
- Tag 3: Elasticsearch Tests
- Tag 4-5: Test-Infrastruktur

**Woche 3-4:**
- API Refactoring (Blueprint Migration)

**Woche 5:**
- Session Management → Redis Migration
- Integration Tests
- Dokumentation

---

## 🎯 Akzeptanzkriterien (Gesamtprojekt)

### Nach vollständiger Umsetzung

**Test Coverage:**
- [ ] Overall Coverage: 27% → 60%+
- [ ] Kritische Services: 70%+
- [ ] Alle API Endpoints: 80%+
- [ ] Mindestens 150 Tests total (aktuell: 67)

**Code-Qualität:**
- [ ] `api_service.py`: 1869 Zeilen → ~50 Zeilen
- [ ] 8 Blueprints mit je ~100-200 Zeilen
- [ ] MyPy strict mode: 0 Errors
- [ ] Pydantic Models für alle Requests
- [ ] OpenAPI/Swagger Docs verfügbar

**Session Management:**
- [ ] Alle Sessions in Redis
- [ ] Kein in-memory State
- [ ] Container-Restart-safe
- [ ] Session-Monitoring in Kibana

**Konfiguration:**
- [ ] `.env.example` vollständig
- [ ] Alle ENV-Variablen dokumentiert
- [ ] Setup in <10 Minuten möglich

**CI/CD:**
- [ ] Alle Tests in GitHub Actions
- [ ] Coverage-Badge in README
- [ ] Automatische Deployment-Tests
- [ ] Performance-Regression-Checks

---

## 📝 Notizen & Referenzen

### Nützliche Links

- **Flask Blueprints:** https://flask.palletsprojects.com/en/3.0.x/blueprints/
- **Pydantic:** https://docs.pydantic.dev/
- **pytest fixtures:** https://docs.pytest.org/en/stable/fixture.html
- **Redis Python Client:** https://redis-py.readthedocs.io/

### Bestehende Code-Referenzen

- `streaming_decoder_service.py` - Bereits Redis SessionManager (als Vorbild)
- `elasticsearch_service.py` - Service-Pattern (als Vorbild)
- `tests/conftest.py` - Fixtures (erweitern)

### Bekannte Herausforderungen

1. **Streaming SSE während Refactoring:**
   - Server-Sent Events komplex
   - Sorgfältiges Testen erforderlich

2. **Redis Dependency:**
   - Redis muss laufen für Tests
   - Docker Compose für Tests nötig

3. **Breaking Changes vermeiden:**
   - API-Kompatibilität wahren
   - URL-Pfade gleich halten (oder Redirects)

---

## ✅ Nächste Schritte

1. **Review dieses Plans** mit Team/Stakeholder
2. **Priorisierung festlegen** - Welche Phase zuerst?
3. **Branch erstellen** für jede Phase
4. **Milestone in GitHub** erstellen
5. **Los geht's!** 🚀

---

**Plan-Version:** 1.0
**Erstellt:** 04. Januar 2026
**Autor:** Claude Code
**Status:** Ready for Implementation
