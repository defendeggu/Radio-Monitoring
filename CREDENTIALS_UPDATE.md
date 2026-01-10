# Credentials Update - 2026-01-10

## Elasticsearch Password Reset

**Date:** 2026-01-10
**Reason:** Password mismatch between Elasticsearch and .env configuration

### Updated Credentials

**Elasticsearch `elastic` user:**
- Previous password: `***REMOVED***` (in .env but not working in ES)
- New password: `***REMOVED***`
- Reset method: `elasticsearch-reset-password --auto --batch`

**Other credentials (unchanged):**
- `logstash_system`: `***REMOVED***` (working correctly)
- `kibana_system`: `***REMOVED***`
- `beats_system`: `***REMOVED***`

### Files Updated

1. `.env` - Line with ELASTIC_PASSWORD updated
2. `.env.elk` - Line with ELASTIC_PASSWORD updated

### Actions Taken

1. Verified Elasticsearch authentication failure with old password
2. Reset `elastic` user password using elasticsearch-reset-password tool
3. Updated both .env files with new password
4. Restarted radio-transcription-api container to pick up new credentials
5. Verified successful authentication and data access
6. Confirmed document counts in indices (30 captures, 4 APRS, 3 POCSAG)

### Verification

```bash
# Test access
curl -u "elastic:***REMOVED***" "http://localhost:9200/_cluster/health"

# Check data
curl -u "elastic:***REMOVED***" "http://localhost:9200/_cat/indices?v"
```

### Security Notes

⚠️ **IMPORTANT:**
- Store this password in your password manager
- Add to team secrets vault
- Do NOT commit this file to Git (already in .gitignore as *.md is not gitignored, but credentials are in .env files which ARE gitignored)
- Consider implementing Docker Secrets for production deployment
- Regularly rotate passwords using `setup-elk-security.sh`

### Rollback (if needed)

If you need to revert or generate new passwords:

```bash
# Regenerate all passwords
./scripts/setup-elk-security.sh

# Or manually reset elastic password
docker exec radio-elasticsearch bin/elasticsearch-reset-password -u elastic --auto --batch
```

## Container Status After Update

All containers healthy:
- radio-elasticsearch: ✅ healthy
- radio-logstash: ✅ healthy
- radio-kibana: ✅ healthy
- radio-transcription-api: ✅ healthy (restarted)
- radio-web-interface: ✅ healthy
- radio-redis: ✅ healthy
- radio-metricbeat: ✅ healthy
- radio-portainer: ✅ healthy

## Next Steps

1. ✅ Verify all services can connect to Elasticsearch
2. ✅ Test APRS/POCSAG data ingestion
3. ✅ Check Kibana dashboards are accessible
4. 📋 Update team documentation with new credentials
5. 📋 Set calendar reminder for next password rotation (recommended: 90 days)
