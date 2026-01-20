# Optimization Roadmap - Follow-up Tasks

**Status:** Optional optimizations for future implementation
**Priority:** Low - system is stable and functional

## 1. Chunked Processing Implementation

**Goal:** Reduce memory usage from 460 MB → ~40 MB for capture-and-transcribe

**Current Status:**
- Duration limits prevent OOM (max 600s)
- Memory peak: 900 MiB for 60s capture
- No crashes observed

**Implementation Plan:**
1. Create new `chunked_capture_service.py`
2. Implement chunk-based processing (CHUNK_DURATION = 0.1s)
3. Pipeline: IQ → Audio → Decoder → ES (no intermediate storage)
4. Explicit memory release with `del` + `gc.collect()`
5. Update `capture-and-transcribe` endpoint to use chunked service

**Estimated Effort:** 3-4 hours
**Risk:** Medium (requires testing with all decoders)
**Benefit:** Lower memory footprint, better for concurrent requests

**Reference:** IMPLEMENTATION_PLAN_new.md Option B, Section 2

---

## 2. Docker Secrets Integration

**Goal:** Replace environment variables with Docker Secrets for production security

**Current Status:**
- Passwords in `.env` and `.env.elk` files (gitignored)
- Works correctly but not production-best-practice

**Implementation Plan:**

### Step 1: Create secrets directory
```bash
mkdir -p .secrets
echo "***REMOVED***" > .secrets/elasticsearch_password.txt
echo "***REMOVED***" > .secrets/logstash_password.txt
echo "***REMOVED***" > .secrets/kibana_password.txt
chmod 600 .secrets/*
```

### Step 2: Update docker-compose.yml
```yaml
secrets:
  elasticsearch_password:
    file: ./.secrets/elasticsearch_password.txt
  logstash_password:
    file: ./.secrets/logstash_password.txt
  kibana_password:
    file: ./.secrets/kibana_password.txt

services:
  elasticsearch:
    secrets:
      - elasticsearch_password
    environment:
      - ELASTIC_PASSWORD_FILE=/run/secrets/elasticsearch_password

  logstash:
    secrets:
      - logstash_password
    environment:
      - ELASTICSEARCH_PASSWORD_FILE=/run/secrets/logstash_password

  kibana:
    secrets:
      - kibana_password
    environment:
      - KIBANA_SYSTEM_PASSWORD_FILE=/run/secrets/kibana_password
```

### Step 3: Update Logstash pipelines
Modify `monitoring/logstash/pipelines/*.conf`:
```ruby
output {
  elasticsearch {
    user => "logstash_system"
    password => "${LOGSTASH_PASSWORD:}"  # Reads from env or file
    hosts => ["http://elasticsearch:9200"]
  }
}
```

### Step 4: Update .gitignore
```
.secrets/
!.secrets/.gitkeep
```

**Estimated Effort:** 2-3 hours
**Risk:** Low (well-documented Docker feature)
**Benefit:** Production-ready security, easier credential rotation

**Reference:** IMPLEMENTATION_PLAN_new.md Option B, Section 1

---

## 3. Additional Optimizations (Nice to Have)

### Enhanced Error Handling for Elasticsearch
- Retry logic for transient failures
- Circuit breaker pattern
- Detailed error logging

### Automated Password Rotation
- Script to rotate all ELK passwords
- Update secrets files automatically
- Restart containers as needed

### Performance Monitoring
- Add Prometheus metrics export
- Monitor memory usage per endpoint
- Track decoder success rates

---

## Current System Status

✅ **All critical issues resolved**
- Elasticsearch authentication: Working
- Data ingestion: Logstash → ES functional
- APRS/POCSAG streaming: Auto-stop working correctly
- Memory usage: Within acceptable limits

🔧 **Optional improvements listed above**
- Not required for stability
- Recommended for production deployment
- Can be implemented incrementally

---

## Priority

1. **HIGH:** APRS/POCSAG live testing (next task)
2. **MEDIUM:** Docker Secrets (before production deployment)
3. **LOW:** Chunked Processing (if memory becomes issue)
4. **LOW:** Additional monitoring/metrics

---

**Last Updated:** 2026-01-10
