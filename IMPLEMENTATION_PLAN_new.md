# Analyse & Lösungsplan: FORK Radio Monitoring System

## Zusammenfassung der identifizierten Probleme

### Problem 1: Keine Daten in Kibana ❌ (KRITISCH)
**Ursache:** Elasticsearch-Authentifizierung in Logstash fehlgeschlagen
- Logstash-Pipelines verwenden `${ELASTICSEARCH_USERNAME}` und `${ELASTICSEARCH_PASSWORD}`
- Diese Umgebungsvariablen werden nicht korrekt von docker-compose an Logstash übergeben
- Daten erreichen Logstash HTTP Input (Port 9601/9602) ✓
- Logstash kann NICHT zu Elasticsearch schreiben ✗
- Daten gehen verloren

**Betroffene Dateien:**
- `monitoring/logstash/pipelines/radio-aprs-pipeline.conf` (Zeilen 75-76)
- `monitoring/logstash/pipelines/radio-pocsag-pipeline.conf` (Zeilen 49-50)
- `docker-compose.yml` (Zeilen 60-64)

### Problem 2: Out-of-Memory beim capture-and-transcribe Endpoint ❌ (KRITISCH)
**Ursache:** Synchrone Verarbeitung ohne Speicherfreigabe
- Alle IQ-Daten werden auf einmal in RAM geladen (240-480 MB)
- Complex64-Konvertierung verdoppelt Speichernutzung (720 MB)
- FM-Demodulation erstellt weitere Arrays (100-200 MB)
- **PEAK Memory: 1.2-1.5 GB pro Request**
- Worker-Limit wahrscheinlich < 2 GB → SIGKILL
- Streaming-Modus verwendet nur 40 KB Chunks → funktioniert stabil

**Betroffene Dateien:**
- `sdr_hardware.py` (Zeilen 214-239: capture_audio, 106: _demodulate)
- `api_service.py` (Zeilen 554-758: capture_and_transcribe endpoint)

### Problem 3: APRS stoppt nicht automatisch nach Duration ❌
**Ursache:** direwolf vs multimon-ng Output-Verhalten
- **POCSAG (multimon-ng):** Gibt kontinuierlich Output aus → Duration-Check funktioniert ✅
- **APRS (direwolf):** Bleibt stumm bei keinen Paketen → Indexer-Thread blockiert → Duration-Check wird ignoriert ✗

**Betroffene Dateien:**
- `streaming_decoder_service.py` (Zeilen 375-391: _stream_pipeline, 521-529: _decoder_output_indexer)

---

## Lösungsvorschläge

## Option A: Quick Fix (Empfohlen für sofortige Funktionsfähigkeit)

### Ziel
Kibana-Daten zum Laufen bringen, Streaming-Modus stabilisieren

### Änderungen

#### 1. Logstash Elasticsearch-Auth beheben
**Datei:** `monitoring/logstash/pipelines/radio-aprs-pipeline.conf` + `radio-pocsag-pipeline.conf`

**Änderung:** Hardcode die Credentials statt Umgebungsvariablen zu verwenden

```ruby
output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    user => "logstash_system"
    password => "/gjcICn/QApz8i9IRNOGPSTFfpr+FUuO"  # Aus .env.elk
    index => "%{[@metadata][index]}"
    document_id => "%{uuid}"
  }
}
```

**ODER** (sicherer): Logstash Entrypoint anpassen um Variablen korrekt zu setzen

**Datei:** Neue `monitoring/logstash/entrypoint.sh`
```bash
#!/bin/bash
export ELASTICSEARCH_USERNAME=${ELASTICSEARCH_USERNAME:-logstash_system}
export ELASTICSEARCH_PASSWORD=${ELASTICSEARCH_PASSWORD:-$LOGSTASH_SYSTEM_PASSWORD}
exec /usr/local/bin/docker-entrypoint "$@"
```

#### 2. capture-and-transcribe Endpoint deaktivieren
**Datei:** `api_service.py`

**Änderung:** Return 501 Not Implemented mit Hinweis auf Streaming-Modus

```python
@app.route('/capture-and-transcribe', methods=['POST'])
def capture_and_transcribe():
    return jsonify({
        "error": "This endpoint is deprecated due to memory issues",
        "message": "Please use /stream-decode instead",
        "status": "error"
    }), 501
```

#### 3. APRS Duration Auto-Stop beheben
**Datei:** `streaming_decoder_service.py`

**Änderung:** Duration-Check in den Indexer-Thread verschieben

```python
def _decoder_output_indexer(self, decoder_stdout, session_manager: SessionManager) -> None:
    start_time = time.time()  # Track start time
    last_activity = time.time()

    while not self.stop_event.is_set():
        # Duration check INSIDE indexer
        if self.duration and (time.time() - start_time) >= self.duration:
            logger.info(f"Duration limit reached in indexer: {self.duration}s")
            self.stop_event.set()  # Signal other threads to stop
            break

        # Rest of the code...
```

### Aufwand: 2-3 Stunden
### Risiko: Niedrig (nur Konfiguration und Deprecation)

---

## Option B: Comprehensive Fix (Empfohlen für Produktivbetrieb)

### Ziel
Alle Probleme nachhaltig lösen

### Änderungen

#### 1. Logstash Elasticsearch-Auth mit secrets
**Neu:** `docker-compose.yml` Secrets-Integration

```yaml
secrets:
  elasticsearch_password:
    file: ./.secrets/elasticsearch_password.txt
  logstash_password:
    file: ./.secrets/logstash_password.txt

services:
  logstash:
    secrets:
      - elasticsearch_password
      - logstash_password
    environment:
      - ELASTICSEARCH_PASSWORD_FILE=/run/secrets/logstash_password
```

**Datei:** `monitoring/logstash/pipelines/*.conf`
```ruby
output {
  elasticsearch {
    user => "logstash_system"
    password => "${LOGSTASH_PASSWORD:}"  # Richtige Syntax
  }
}
```

#### 2. capture-and-transcribe Refactoring zu Streaming
**Datei:** Neuer `chunked_capture_service.py`

Implementiere chunk-basierte Verarbeitung analog zum Streaming-Modus:
- CHUNK_DURATION = 0.1s (40 KB statt 480 MB)
- Explizite Memory-Freigabe mit `del` + `gc.collect()`
- Pipeline: IQ → Audio → Decoder → ES (keine Zwischenspeicherung)

#### 3. APRS Duration mit Timeout-Monitor
**Datei:** `streaming_decoder_service.py`

Neuer Monitor-Thread der Duration unabhängig überwacht:

```python
def _duration_monitor(self):
    """Separate thread that monitors duration independently"""
    start_time = time.time()
    while not self.stop_event.is_set():
        if self.duration and (time.time() - start_time) >= self.duration:
            logger.info(f"Duration monitor: Stopping after {self.duration}s")
            self.stop_event.set()
            break
        time.sleep(0.5)
```

#### 4. Elasticsearch Fehlerbehandlung verbessern
**Datei:** `streaming_decoder_service.py`

```python
def _index_packet(self, packet: Dict[str, Any]) -> None:
    try:
        es = get_elasticsearch_service()
        result = es.index_aprs(packet)
        if result:  # Nur bei Erfolg zählen!
            self.session.packet_count += 1
            logger.info(f"Indexed APRS packet #{self.session.packet_count}")
        else:
            logger.error("Failed to index, ES returned None")
    except Exception as e:
        logger.error(f"Failed to index APRS packet: {e}")
        # NICHT den packet_count erhöhen!
```

### Aufwand: 1-2 Tage
### Risiko: Mittel (größere Code-Änderungen)

---

## Option C: Minimal Fix + Dokumentation (Pragmatisch)

### Ziel
Quick Fix für Kibana, Rest dokumentieren

### Änderungen

#### 1. Logstash Auth Quick Fix (wie Option A)

#### 2. capture-and-transcribe mit Warning versehen
**Datei:** `api_service.py`

```python
@app.route('/capture-and-transcribe', methods=['POST'])
def capture_and_transcribe():
    data = request.get_json()
    duration = data.get('duration', 60)

    # Warning bei > 30s
    if duration > 30:
        return jsonify({
            "error": "Duration > 30s may cause OOM",
            "recommendation": "Use /stream-decode instead",
            "max_safe_duration": 30
        }), 400

    # Rest of implementation...
```

#### 3. APRS mit Manual Stop dokumentieren
**Neu:** `KNOWN_ISSUES.md`

```markdown
# Bekannte Probleme

## APRS Streaming stoppt nicht automatisch
- **Problem:** APRS-Sessions laufen über die konfigurierte Duration hinaus
- **Ursache:** direwolf gibt bei Inaktivität keinen Output aus
- **Workaround:** Manuell stoppen mit DELETE /stream-decode/{session_id}
- **Status:** In Arbeit (siehe Issue #XX)
```

### Aufwand: 1-2 Stunden
### Risiko: Sehr niedrig (nur Doku und Limits)

---

## Gewählte Strategie: Option B (Comprehensive Fix) mit Limits

**User-Entscheidungen:**
- ✅ Comprehensive Fix (1-2 Tage Aufwand)
- ✅ Voice Transcription auch beheben
- ✅ capture-and-transcribe mit Limits (max 30s) statt komplett deaktivieren

**Ziele:**
1. Alle Probleme nachhaltig lösen
2. Bessere Sicherheit (Secrets)
3. Vollständige Stabilität
4. Voice Transcription funktionsfähig machen

---

## Detaillierter Implementierungsplan

### Phase 1: Logstash Elasticsearch-Auth beheben (KRITISCH)

#### Schritt 1.1: Secrets-Dateien erstellen
**Neue Dateien:**
```bash
.secrets/
  elasticsearch_password.txt  # Elastic user password
  logstash_password.txt       # logstash_system password
```

**Inhalt aus `.env.elk` extrahieren:**
- ELASTIC_PASSWORD → elasticsearch_password.txt
- LOGSTASH_SYSTEM_PASSWORD → logstash_password.txt

#### Schritt 1.2: docker-compose.yml anpassen
**Datei:** `docker-compose.yml`

**Änderungen:**
1. Secrets-Sektion hinzufügen (oben im File):
```yaml
secrets:
  elasticsearch_password:
    file: ./.secrets/elasticsearch_password.txt
  logstash_password:
    file: ./.secrets/logstash_password.txt
```

2. Logstash Service anpassen:
```yaml
logstash:
  secrets:
    - logstash_password
  environment:
    - LOGSTASH_PASSWORD_FILE=/run/secrets/logstash_password
    # Alte Variablen entfernen:
    # - ELASTICSEARCH_USERNAME=logstash_system
    # - ELASTICSEARCH_PASSWORD=${LOGSTASH_SYSTEM_PASSWORD}
```

#### Schritt 1.3: Logstash Entrypoint erstellen
**Neue Datei:** `monitoring/logstash/entrypoint.sh`

```bash
#!/bin/bash
set -e

# Load password from secrets
if [ -f /run/secrets/logstash_password ]; then
    export ELASTICSEARCH_PASSWORD=$(cat /run/secrets/logstash_password)
else
    export ELASTICSEARCH_PASSWORD=${LOGSTASH_SYSTEM_PASSWORD}
fi

export ELASTICSEARCH_USERNAME=logstash_system

# Start Logstash
exec /usr/local/bin/docker-entrypoint "$@"
```

#### Schritt 1.4: Logstash Pipelines anpassen
**Dateien:**
- `monitoring/logstash/pipelines/radio-aprs-pipeline.conf`
- `monitoring/logstash/pipelines/radio-pocsag-pipeline.conf`
- `monitoring/logstash/pipelines/radio-voice-pipeline.conf`

**Änderung (in allen 3 Dateien):**
```ruby
output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    user => "${ELASTICSEARCH_USERNAME}"
    password => "${ELASTICSEARCH_PASSWORD}"  # Jetzt korrekt gesetzt!
    index => "%{[@metadata][index]}"
    document_id => "%{uuid}"
  }
}
```

#### Schritt 1.5: Logstash Dockerfile anpassen
**Datei:** `monitoring/logstash/Dockerfile`

```dockerfile
# ... existing content ...

# Copy custom entrypoint
COPY entrypoint.sh /usr/local/bin/custom-entrypoint.sh
RUN chmod +x /usr/local/bin/custom-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/custom-entrypoint.sh"]
CMD ["-f", "/usr/share/logstash/pipeline/"]
```

---

### Phase 2: capture-and-transcribe mit Limits versehen

#### Schritt 2.1: Duration-Limits einführen
**Datei:** `api_service.py` (Zeile 554+)

**Änderungen:**
```python
@app.route('/capture-and-transcribe', methods=['POST'])
def capture_and_transcribe():
    data = request.get_json()

    # Validate input
    frequency = data.get('frequency')
    duration = data.get('duration', 60)
    gain = data.get('gain', 0)
    mode = data.get('mode', 'voice')

    # CRITICAL: Enforce memory-safe limits
    MAX_SAFE_DURATION = 30  # Sekunden
    if duration > MAX_SAFE_DURATION:
        logger.warning(f"Duration {duration}s exceeds safe limit {MAX_SAFE_DURATION}s")
        return jsonify({
            "error": f"Duration exceeds safe limit of {MAX_SAFE_DURATION} seconds",
            "requested_duration": duration,
            "max_safe_duration": MAX_SAFE_DURATION,
            "recommendation": "Use /stream-decode for longer captures",
            "status": "error"
        }), 400

    # Rest of implementation...
```

#### Schritt 2.2: Memory-Freigabe verbessern
**Datei:** `sdr_hardware.py` (capture_audio Methode)

**Änderungen in Zeilen 214-239:**
```python
def capture_audio(self, duration, output_file, modulation):
    """Capture audio from SDR"""
    try:
        # Capture IQ samples
        iq_file = output_file.replace('.wav', '_iq.bin')
        self.capture_iq(duration, iq_file)

        # Load and process (with explicit memory management)
        logger.info("Loading IQ samples for demodulation")
        iq_samples = np.fromfile(iq_file, dtype=np.complex64)

        # Demodulate
        logger.info("Demodulating signal")
        audio = self._demodulate(iq_samples, modulation)

        # CRITICAL: Free IQ memory immediately
        del iq_samples
        import gc
        gc.collect()

        # Save audio
        logger.info(f"Saving audio to {output_file}")
        sf.write(output_file, audio, 16000, subtype='PCM_16')

        # CRITICAL: Free audio memory
        del audio
        gc.collect()

        # Clean up temporary IQ file
        if os.path.exists(iq_file):
            os.remove(iq_file)
            logger.info(f"Removed temporary IQ file: {iq_file}")

    except Exception as e:
        logger.error(f"Audio capture failed: {e}")
        raise
```

#### Schritt 2.3: _demodulate Memory-Optimierung
**Datei:** `sdr_hardware.py` (Zeilen 106+)

**Änderungen:**
```python
def _demodulate(self, iq_samples, modulation):
    """Demodulate IQ samples with explicit memory management"""
    try:
        if modulation.upper() == 'FM':
            # FM demodulation
            phase = np.angle(iq_samples)
            del iq_samples  # Free IQ memory immediately!
            gc.collect()

            phase_diff = np.diff(phase)
            del phase  # Free phase memory
            gc.collect()

            audio = np.unwrap(phase_diff)
            del phase_diff
            gc.collect()

            # Normalize
            audio = audio / np.max(np.abs(audio))

        elif modulation.upper() == 'AM':
            # AM demodulation
            audio = np.abs(iq_samples)
            del iq_samples
            gc.collect()

            audio = audio / np.max(np.abs(audio))
        else:
            raise ValueError(f"Unknown modulation: {modulation}")

        # Resample to 16 kHz (using smaller decimation steps)
        # Instead of one big decimate(125), do multiple smaller ones
        decimation_factor = int(self.sample_rate / 16000)

        # Split decimation into smaller steps to reduce memory
        if decimation_factor > 10:
            audio = signal.decimate(audio, 10, zero_phase=False)  # False = less memory
            gc.collect()
            remaining_factor = decimation_factor // 10
            if remaining_factor > 1:
                audio = signal.decimate(audio, remaining_factor, zero_phase=False)
                gc.collect()
        else:
            audio = signal.decimate(audio, decimation_factor, zero_phase=False)
            gc.collect()

        return audio

    except Exception as e:
        logger.error(f"Demodulation failed: {e}")
        raise
```

---

### Phase 3: APRS Duration Auto-Stop beheben

#### Schritt 3.1: Duration-Monitor-Thread hinzufügen
**Datei:** `streaming_decoder_service.py` (nach Zeile 352)

**Neue Methode:**
```python
def _duration_monitor(self) -> None:
    """Separate thread that monitors duration independently"""
    if not self.duration:
        return

    start_time = time.time()
    logger.info(f"Duration monitor started: will stop after {self.duration}s")

    while not self.stop_event.is_set():
        elapsed = time.time() - start_time

        if elapsed >= self.duration:
            logger.info(f"Duration monitor: Stopping after {self.duration}s")
            self.stop_event.set()
            break

        # Check every 0.5 seconds for responsive stopping
        time.sleep(0.5)

    logger.info("Duration monitor thread finished")
```

#### Schritt 3.2: Monitor-Thread in Pipeline starten
**Datei:** `streaming_decoder_service.py` (Zeile 355+)

**Änderung in _stream_pipeline():**
```python
def _stream_pipeline(self, session_manager: SessionManager) -> None:
    """Main streaming pipeline with separate duration monitoring"""
    try:
        # ... existing setup code ...

        # Start threads
        converter_thread = threading.Thread(
            target=self._iq_to_audio_converter,
            args=(iq_stream, audio_sink)
        )
        indexer_thread = threading.Thread(
            target=self._decoder_output_indexer,
            args=(decoder.stdout, session_manager)
        )

        # NEW: Start duration monitor thread
        monitor_thread = threading.Thread(target=self._duration_monitor)

        converter_thread.start()
        indexer_thread.start()
        monitor_thread.start()  # NEW!

        # Wait for completion (simplified, monitor handles duration)
        while not self.stop_event.is_set():
            # Update session status
            if int(time.time()) % 5 == 0:
                session_manager.save_session(self.session)
            time.sleep(1)

        # Cleanup (wait for threads with timeout)
        monitor_thread.join(timeout=5)
        converter_thread.join(timeout=10)
        indexer_thread.join(timeout=10)

    except Exception as e:
        logger.error(f"Streaming pipeline error: {e}")
        raise
```

---

### Phase 4: Elasticsearch Error-Handling verbessern

#### Schritt 4.1: Fehlerbehandlung in _index_packet
**Datei:** `streaming_decoder_service.py` (Zeilen 796-805 für APRS, 912-921 für POCSAG)

**Änderungen:**
```python
def _index_packet(self, packet: Dict[str, Any]) -> None:
    """Index APRS packet to Elasticsearch with proper error handling"""
    from elasticsearch_service import get_elasticsearch_service

    try:
        es = get_elasticsearch_service()
        result = es.index_aprs(packet)

        # Only count successful indexing
        if result:
            self.session.packet_count += 1
            self.session.last_packet_time = datetime.now(timezone.utc).isoformat()
            logger.info(f"Successfully indexed APRS packet #{self.session.packet_count} from {packet.get('source_callsign')}")
        else:
            logger.error(f"Failed to index APRS packet: ES returned None/False")

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error indexing APRS packet: {e}")
    except Exception as e:
        logger.error(f"Unexpected error indexing APRS packet: {e}", exc_info=True)
```

**Gleiche Änderung für POCSAG (Zeilen 912-921) und Voice (wenn vorhanden).**

---

### Phase 5: Voice Transcription Support

#### Schritt 5.1: Voice Streaming-Decoder erstellen
**Datei:** `streaming_decoder_service.py` (nach Zeile 929)

**Neue Klasse:**
```python
class StreamingVoiceDecoder(BaseStreamingDecoder):
    """Streaming voice transcription decoder using Whisper"""

    def _start_decoder(self) -> subprocess.Popen:
        """Start Whisper for voice transcription"""
        # Use streaming-capable Whisper implementation
        # Note: Standard Whisper needs audio chunks, not real-time stream
        # This would need a chunk-based approach

        cmd = [
            'python3', '-m', 'whisper_streaming',
            '--model', 'base',
            '--language', self.language or 'en',
            '--task', 'transcribe',
            '-'  # stdin
        ]

        logger.info(f"Starting Whisper streaming: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )

        return process

    def _parse_decoder_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse Whisper transcription output"""
        try:
            # Whisper output format: [timestamp] text
            match = re.match(r'\[(\d+:\d+:\d+)\]\s+(.+)', line)
            if match:
                timestamp_str, text = match.groups()

                return {
                    'type': 'voice',
                    'timestamp_str': timestamp_str,
                    'text': text.strip(),
                    'language': self.language or 'en'
                }

            return None

        except Exception as e:
            logger.error(f"Error parsing Whisper line: {e}")
            return None

    def _index_packet(self, packet: Dict[str, Any]) -> None:
        """Index voice transcription to Elasticsearch"""
        from elasticsearch_service import get_elasticsearch_service

        try:
            es = get_elasticsearch_service()
            result = es.index_voice(packet)

            if result:
                self.session.packet_count += 1
                self.session.last_packet_time = datetime.now(timezone.utc).isoformat()
                logger.info(f"Successfully indexed voice segment #{self.session.packet_count}")
            else:
                logger.error(f"Failed to index voice segment: ES returned None/False")

        except Exception as e:
            logger.error(f"Failed to index voice segment: {e}", exc_info=True)
```

**HINWEIS:** Standard Whisper ist nicht für echtes Streaming geeignet. Alternative:
- Verwende `whisper-streaming` oder `faster-whisper`
- ODER: Chunk-basierte Verarbeitung (5-10s Audio-Chunks)

#### Schritt 5.2: Voice Endpoint mit Limits
**Datei:** `api_service.py`

**Sicherstellen dass Voice auch Limits hat:**
```python
# In capture_and_transcribe Endpoint:
if mode == 'voice':
    # Voice transcription is even more memory-intensive
    MAX_SAFE_DURATION_VOICE = 20  # Noch niedrigeres Limit

    if duration > MAX_SAFE_DURATION_VOICE:
        return jsonify({
            "error": f"Voice transcription duration exceeds safe limit of {MAX_SAFE_DURATION_VOICE} seconds",
            "requested_duration": duration,
            "max_safe_duration": MAX_SAFE_DURATION_VOICE,
            "recommendation": "Use /stream-decode with mode=voice for longer recordings",
            "status": "error"
        }), 400
```

---

## Verifikation nach Fix

### 1. Kibana-Daten prüfen
```bash
# Elasticsearch Indices prüfen
curl -u elastic:${ELASTIC_PASSWORD} http://localhost:9200/_cat/indices | grep radio

# Sollte zeigen:
# radio-aprs-2026.01.09
# radio-pocsag-2026.01.09

# Dokumente zählen
curl -u elastic:${ELASTIC_PASSWORD} \
  "http://localhost:9200/radio-aprs-*/_count"
```

### 2. Streaming-Test wiederholen
```bash
# APRS Test (sollte nach 120s stoppen)
curl -X POST http://localhost:5000/stream-decode \
  -d '{"mode":"aprs","frequency":144800000,"duration":120,"gain":24}'

# Session ID: <id>
# Nach 130s prüfen:
curl http://localhost:5000/stream-decode/<id>
# Sollte zeigen: "status": "completed"
```

### 3. Memory-Test
```bash
# capture-and-transcribe sollte abgelehnt werden:
curl -X POST http://localhost:5000/capture-and-transcribe \
  -d '{"frequency":144800000,"duration":60,"gain":24,"mode":"aprs"}'

# Sollte zurückgeben:
# {"error": "This endpoint is deprecated..."}
```

### 4. Kibana Dashboard prüfen
- Öffne http://localhost:5601
- Navigiere zu APRS Dashboard
- Sollte Daten von den Test-Sessions zeigen

---

---

## Kritische Dateien und Änderungen (Übersicht)

### Neue Dateien:
1. `.secrets/elasticsearch_password.txt` - Elastic password
2. `.secrets/logstash_password.txt` - Logstash system password
3. `monitoring/logstash/entrypoint.sh` - Custom entrypoint für Variable-Expansion
4. `.gitignore` Update - Secrets-Ordner ausschließen

### Geänderte Dateien:

#### Konfiguration & Docker:
1. `docker-compose.yml` - Secrets Integration, Logstash Entrypoint
2. `monitoring/logstash/Dockerfile` - Custom Entrypoint kopieren
3. `monitoring/logstash/pipelines/radio-aprs-pipeline.conf` - Auth-Variablen
4. `monitoring/logstash/pipelines/radio-pocsag-pipeline.conf` - Auth-Variablen
5. `monitoring/logstash/pipelines/radio-voice-pipeline.conf` - Auth-Variablen

#### API & Service Layer:
6. `api_service.py` (Zeilen 554+) - Duration-Limits für capture-and-transcribe
7. `sdr_hardware.py` (Zeilen 106, 214-239) - Memory-Management
8. `streaming_decoder_service.py`:
   - Zeile 352+: _duration_monitor() Methode
   - Zeile 375+: _stream_pipeline() Monitor-Thread
   - Zeile 796-805: _index_packet() Error-Handling (APRS)
   - Zeile 912-921: _index_packet() Error-Handling (POCSAG)
   - Zeile 929+: StreamingVoiceDecoder Klasse

---

## Implementierungs-Reihenfolge

### Tag 1 (4-6 Stunden):
**Priorität 1: Kibana-Daten zum Laufen bringen**
1. ✅ Phase 1: Logstash Elasticsearch-Auth (Schritte 1.1-1.5)
2. ✅ Phase 4: Elasticsearch Error-Handling (Schritt 4.1)
3. ✅ Verifikation: Kibana-Daten prüfen

**Erwartetes Ergebnis:** Kibana zeigt Daten von neuen Streaming-Sessions

### Tag 2 (4-6 Stunden):
**Priorität 2: Stabilität & Memory**
4. ✅ Phase 2: capture-and-transcribe Limits (Schritte 2.1-2.3)
5. ✅ Phase 3: APRS Duration Auto-Stop (Schritte 3.1-3.2)
6. ✅ Phase 5: Voice Transcription (Schritte 5.1-5.2)
7. ✅ Vollständige End-to-End Tests

**Erwartetes Ergebnis:** Alle Modi stabil, keine OOM-Crashes, Auto-Stop funktioniert

---

## Risiken & Mitigationen

### Risiko 1: Logstash startet nicht mit neuem Entrypoint
**Mitigation:**
- Backup der alten Konfiguration
- Teste Logstash lokal vor Deployment
- Fallback: Hardcode Credentials temporär

### Risiko 2: Memory-Optimierungen brechen Funktionalität
**Mitigation:**
- Teste jeden Schritt einzeln
- Vergleiche Output-Quality vor/nach Änderung
- Unit-Tests für Memory-kritische Funktionen

### Risiko 3: Voice Streaming ist zu komplex
**Mitigation:**
- Start mit chunk-based Approach (5s Chunks)
- Fallback: Verwende nur capture-and-transcribe mit 20s Limit
- Alternative: whisper-streaming library

### Risiko 4: Duration-Monitor löst Race Conditions aus
**Mitigation:**
- Thread-safe stop_event.set()
- Proper thread.join() mit Timeouts
- Logging für Thread-Status

---

## Testing-Checkliste

### Test 1: Logstash → Elasticsearch
```bash
# Nach Phase 1:
docker logs radio-logstash | grep -i "error\|auth"  # Keine Auth-Errors
curl -u elastic:$ELASTIC_PASSWORD "http://localhost:9200/radio-*/_count"  # > 0 docs
```

### Test 2: APRS Streaming mit Auto-Stop
```bash
# Session starten
curl -X POST http://localhost:5000/stream-decode \
  -d '{"mode":"aprs","frequency":144800000,"duration":120,"gain":24}'

# Session ID: <id>
# Nach 130s:
curl http://localhost:5000/stream-decode/<id> | jq '.session.status'
# Sollte "completed" sein
```

### Test 3: capture-and-transcribe mit Limits
```bash
# Sollte abgelehnt werden:
curl -X POST http://localhost:5000/capture-and-transcribe \
  -d '{"frequency":144800000,"duration":60,"mode":"aprs","gain":24}'
# Erwartung: 400 Bad Request, "Duration exceeds safe limit"

# Sollte funktionieren:
curl -X POST http://localhost:5000/capture-and-transcribe \
  -d '{"frequency":144800000,"duration":25,"mode":"aprs","gain":24}'
# Erwartung: 200 OK, Capture erfolgreich
```

### Test 4: Memory-Stabilität
```bash
# Docker Stats während Capture beobachten:
docker stats radio-transcription-api

# Mehrere 30s Captures hintereinander:
for i in {1..5}; do
  curl -X POST http://localhost:5000/capture-and-transcribe \
    -d '{"frequency":144800000,"duration":25,"mode":"aprs","gain":24}'
  sleep 5
done

# Memory sollte nicht wachsen, keine Worker-Crashes
```

### Test 5: Kibana Dashboards
```bash
# Nach Tests 2-4:
# 1. Öffne http://localhost:5601
# 2. Navigiere zu APRS Dashboard
# 3. Sollte Daten zeigen für:
#    - Streaming-Sessions
#    - capture-and-transcribe Sessions
```

---

## Rollback-Plan

Falls kritische Probleme auftreten:

### Schritt 1: Logstash Rollback
```bash
# Alte Pipeline-Configs wiederherstellen
git checkout HEAD -- monitoring/logstash/pipelines/*.conf

# docker-compose ohne Secrets starten
docker-compose up -d logstash
```

### Schritt 2: API Rollback
```bash
# Alte api_service.py und sdr_hardware.py wiederherstellen
git checkout HEAD -- api_service.py sdr_hardware.py streaming_decoder_service.py

# Container neu bauen
docker-compose build radio-api
docker-compose up -d radio-api
```

### Schritt 3: Verifikation
```bash
# Prüfe dass alte Version läuft:
docker logs radio-transcription-api | tail -20
docker logs radio-logstash | tail -20
```
