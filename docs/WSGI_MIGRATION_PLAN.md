# WSGI Server Migration Plan

## Problem

Flask's built-in development server (`app.run()`) zeigt beim Start diese Warnung:

```
WARNING: This is a development server. Do not use it in a production deployment.
Use a production WSGI server instead.
```

**Warum ist das wichtig?**

Der Flask Development Server ist **nicht für Produktion geeignet** weil:

1. **Performance**: Nur ein Thread/Prozess, langsam bei mehreren Requests
2. **Sicherheit**: Nicht gehärtet gegen Attacks (DoS, slowloris, etc.)
3. **Stabilität**: Keine automatischen Restarts bei Crashes
4. **Skalierung**: Kann nicht mehrere Worker spawnen
5. **Long-running requests**: Keine Unterstützung für asynchrone Tasks

## Ist-Zustand

**Aktueller Start:**
```python
# api_service.py, Zeile 1861
app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
```

**Dockerfile CMD:**
```dockerfile
CMD ["python", "api_service.py"]
```

**Probleme mit unserem System:**
- Streaming Sessions laufen 1-24 Stunden (long-running requests)
- Mehrere gleichzeitige Benutzer möglich
- Background Threads für SDR Capture und Decoding
- Polling-basierte Stats-Updates (alle 2s)

## Soll-Zustand: Production WSGI Server

### Option 1: **Gunicorn + Gevent** (EMPFOHLEN)

**Vorteile:**
- ✅ Pure Python, einfach zu installieren
- ✅ Sehr stabil und weit verbreitet
- ✅ Gevent Workers = asynchrone I/O für long-running requests
- ✅ Unterstützt Graceful Restarts (kein Verbindungsverlust)
- ✅ Worker Management (auto-restart bei Crash)
- ✅ Pre-fork Model für bessere CPU Nutzung

**Nachteile:**
- ❌ Linux/Unix only (kein Windows - aber wir nutzen Docker)

**Perfekt für:**
- Streaming Sessions (gevent = non-blocking I/O)
- Polling-basierte Updates
- Background Tasks in Threads

---

### Option 2: uWSGI

**Vorteile:**
- ✅ Sehr performant (C-basiert)
- ✅ Viele Features (Caching, Monitoring, Load Balancing)
- ✅ Async Support

**Nachteile:**
- ❌ Komplexere Konfiguration
- ❌ Build-Dependencies (C compiler)
- ❌ Overkill für unser System

---

### Option 3: Waitress

**Vorteile:**
- ✅ Pure Python
- ✅ Windows-kompatibel
- ✅ Einfach

**Nachteile:**
- ❌ Weniger performant als Gunicorn
- ❌ Keine async Workers (schlecht für Streaming)

---

## Empfehlung: Gunicorn + Gevent

**Begründung:**
1. Unsere Streaming Sessions sind **long-running** (1-24h)
2. Gevent = **non-blocking I/O** = perfekt für viele gleichzeitige Streams
3. Einfache Integration, keine Code-Änderungen nötig
4. Production-ready, bewährt in tausenden Projekten

## Implementierungsplan

### Phase 1: Grundsetup (30 Min)

**1.1 Dependencies hinzufügen**
```bash
# requirements.txt
gunicorn==21.2.0
gevent==24.2.1
```

**1.2 Gunicorn Config erstellen**
```python
# gunicorn_config.py
import multiprocessing
import os

# Server Socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker Processes
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'gevent'  # Async workers for long-running requests
worker_connections = 1000
max_requests = 1000  # Restart workers after N requests (prevent memory leaks)
max_requests_jitter = 50
timeout = 120  # 2 minutes (important for streaming sessions)
keepalive = 5

# Logging
accesslog = '-'  # stdout
errorlog = '-'   # stderr
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = 'radio-api'

# Server Mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Graceful Timeout (for streaming sessions)
graceful_timeout = 30
```

**1.3 Dockerfile anpassen**
```dockerfile
# OLD:
CMD ["python", "api_service.py"]

# NEW:
CMD ["gunicorn", "--config", "gunicorn_config.py", "api_service:app"]
```

**1.4 api_service.py anpassen**
```python
# OLD:
def main() -> None:
    os.makedirs(RECORDING_DIR, exist_ok=True)
    port = int(os.getenv('API_PORT', '5000'))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)

if __name__ == '__main__':
    main()

# NEW:
def main() -> None:
    """
    Initialize application (called by Gunicorn or for local development)
    """
    os.makedirs(RECORDING_DIR, exist_ok=True)

if __name__ == '__main__':
    # Local development mode (Flask dev server)
    port = int(os.getenv('API_PORT', '5000'))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    print("⚠️  Running Flask development server (for development only)")
    print("   For production, use: gunicorn --config gunicorn_config.py api_service:app")
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)

# Call main on import (Gunicorn imports the module)
main()
```

### Phase 2: Optimierungen (Optional)

**2.1 Worker Count Tuning**

Formel: `(2 x $num_cores) + 1`

Beispiel:
- 4 CPU Cores = 9 Workers
- 8 CPU Cores = 17 Workers

Environment Variable für Flexibilität:
```yaml
# docker-compose.yml
environment:
  GUNICORN_WORKERS: 5  # Override default
```

**2.2 Timeout Anpassung**

Für lange Streaming Sessions:
```python
# gunicorn_config.py
timeout = 300  # 5 minutes für sehr lange Requests
graceful_timeout = 60  # Zeit für graceful shutdown
```

**2.3 Health Check**

Neuer Endpoint für Container Health:
```python
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for load balancers"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    }), 200
```

Docker Compose Update:
```yaml
radio-api:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

### Phase 3: Testing & Monitoring

**3.1 Performance Testing**

Vor Migration:
```bash
# Load test mit Apache Bench
ab -n 1000 -c 10 http://localhost:5000/detect-sdr
```

Nach Migration:
```bash
ab -n 1000 -c 10 http://localhost:5000/detect-sdr
```

Vergleich:
- Requests per second
- Time per request
- Failed requests

**3.2 Streaming Test**

Teste lange Sessions:
```bash
# Start 3 parallel streaming sessions
for i in {1..3}; do
  curl -X POST http://localhost:5000/stream-decode \
    -H "Content-Type: application/json" \
    -d '{"mode":"pocsag","frequency":147325000,"duration":3600,"gain":20}' &
done

# Monitor Gunicorn workers
docker compose exec radio-api ps aux | grep gunicorn
```

**3.3 Monitoring**

Gunicorn Stats:
```bash
# Worker Status
docker compose logs radio-api | grep "Booting worker\|Worker exiting"

# Request Stats (access log)
docker compose logs radio-api | grep "GET\|POST" | tail -20
```

## Risiken & Mitigation

### Risiko 1: Background Threads funktionieren nicht

**Problem:** Streaming Sessions nutzen Background Threads für SDR capture

**Mitigation:**
- Gevent patcht automatisch Threading für non-blocking I/O
- Teste explizit: `gevent.monkey.patch_all()` in api_service.py (falls nötig)

### Risiko 2: Worker Crashes bei langen Sessions

**Problem:** Worker stirbt während 24h Streaming Session

**Mitigation:**
- `graceful_timeout = 60` = genug Zeit für sauberen Shutdown
- Redis Session Manager persistiert State
- Sessions überleben Worker Restarts

### Risiko 3: Mehr Memory Usage

**Problem:** Mehrere Worker = mehr RAM

**Mitigation:**
- Start mit wenigen Workers (z.B. 3-5)
- Monitore RAM Usage: `docker stats radio-transcription-api`
- Adjust `max_requests` für Memory Leak Prevention

## Rollback Plan

Falls Probleme auftreten:

**Quick Rollback:**
```bash
# 1. Alte Version vom Container nutzen
docker compose down
git revert <commit-hash>
docker compose build --no-cache radio-api
docker compose up -d
```

**Emergency Fallback:**
```dockerfile
# Dockerfile - zurück zu Flask dev server
CMD ["python", "api_service.py"]
```

## Timeline

**Phase 1 (Grundsetup):** 30 Minuten
- Requirements update
- gunicorn_config.py erstellen
- Dockerfile anpassen
- api_service.py refactoring
- Build & Test

**Phase 2 (Optimierungen):** 1 Stunde
- Worker Tuning
- Health Check
- Timeout Anpassung

**Phase 3 (Testing):** 1 Stunde
- Performance Tests
- Streaming Tests
- Monitoring Setup

**Total:** ~2.5 Stunden

## Success Criteria

✅ Keine Flask Warning beim Start
✅ Mehrere Workers laufen
✅ Streaming Sessions funktionieren (24h Test)
✅ Performance besser oder gleich
✅ Health Check funktioniert
✅ Graceful Shutdown ohne Session-Verlust

## Nächste Schritte

1. **Review dieses Plans** - Feedback?
2. **Entscheidung:** Gunicorn implementieren? (JA/NEIN)
3. **Zeitpunkt:** Wann soll Migration durchgeführt werden?
4. **Backup:** Commit aktueller Stand vor Migration

## Referenzen

- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Gevent Documentation](http://www.gevent.org/)
- [Flask Deployment Options](https://flask.palletsprojects.com/en/3.0.x/deploying/)
- [Docker + Gunicorn Best Practices](https://github.com/tiangolo/meinheld-gunicorn-docker)
