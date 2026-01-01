# ELK Stack Security Configuration

## Overview

The ELK stack is now secured with authentication enabled. All services require valid credentials to access Elasticsearch.

## Credentials

Credentials are stored in `.env` file (merged from `.env.elk`). This file contains:

- `ELASTIC_PASSWORD` - Superuser account for Elasticsearch
- `KIBANA_SYSTEM_PASSWORD` - Kibana service account
- `LOGSTASH_SYSTEM_PASSWORD` - Logstash service account
- `BEATS_SYSTEM_PASSWORD` - Metricbeat service account

**⚠️ IMPORTANT:** Never commit `.env` or `.env.elk` files to Git!

## Accessing Services

### Kibana (Web UI)

**URL:** http://localhost:5601

**Login:**
- Username: `elastic`
- Password: See `ELASTIC_PASSWORD` in `.env` file

```bash
# Get password from .env
grep "^ELASTIC_PASSWORD=" .env | cut -d= -f2
```

### Elasticsearch (API)

**URL:** http://localhost:9200

**Authentication required** for all requests:

```bash
# Example: Get cluster health
ELASTIC_PW=$(grep "^ELASTIC_PASSWORD=" .env | cut -d= -f2)
curl -u "elastic:${ELASTIC_PW}" http://localhost:9200/_cluster/health?pretty
```

### Radio API

**URL:** http://localhost:5000

The API automatically authenticates with Elasticsearch using the credentials from `.env`.

## Setup Process

### Initial Setup (Already Completed)

1. Generate passwords:
   ```bash
   ./setup-elk-security.sh
   ```

2. Start the stack:
   ```bash
   docker compose -f docker-compose.elk.yml up -d
   ```

3. Configure built-in users:
   ```bash
   ./setup-elk-users.sh
   ```

4. Restart services:
   ```bash
   docker compose -f docker-compose.elk.yml restart logstash kibana metricbeat radio-api
   ```

### Resetting Passwords

If you need to regenerate all passwords:

```bash
# Backup current .env
cp .env .env.backup

# Generate new passwords
./setup-elk-security.sh

# Stop and remove containers
docker compose -f docker-compose.elk.yml down

# Start with new credentials
docker compose -f docker-compose.elk.yml up -d

# Configure users
./setup-elk-users.sh

# Restart services
docker compose -f docker-compose.elk.yml restart logstash kibana metricbeat radio-api
```

## Security Features Enabled

✅ **Authentication Required**
- All Elasticsearch requests require valid credentials
- HTTP 401 returned for unauthenticated requests

✅ **Built-in User Accounts**
- `elastic` - Superuser with full access
- `kibana_system` - Limited to Kibana operations
- `logstash_system` - Write access for Logstash pipelines
- `beats_system` - Write access for Metricbeat

✅ **Secure Password Generation**
- 25-character random passwords
- Generated using `openssl rand`

✅ **Encrypted Communications** (Future Enhancement)
- Currently: HTTP with authentication
- Recommended for production: Enable TLS/SSL

## Troubleshooting

### "Authentication failed" errors

1. Verify credentials in `.env`:
   ```bash
   cat .env | grep PASSWORD
   ```

2. Test Elasticsearch connection:
   ```bash
   ELASTIC_PW=$(grep "^ELASTIC_PASSWORD=" .env | cut -d= -f2)
   curl -u "elastic:${ELASTIC_PW}" http://localhost:9200
   ```

### Logstash pipeline failures

Check Logstash logs:
```bash
docker logs radio-logstash --tail 50
```

If you see authentication errors, run:
```bash
./setup-elk-users.sh
docker compose -f docker-compose.elk.yml restart logstash
```

### Lost `.env` file

If `.env` is lost, you must:
1. Stop all containers
2. Delete Elasticsearch data volume
3. Re-run setup from scratch

```bash
docker compose -f docker-compose.elk.yml down -v
./setup-elk-security.sh
docker compose -f docker-compose.elk.yml up -d
./setup-elk-users.sh
docker compose -f docker-compose.elk.yml restart logstash kibana metricbeat radio-api
```

## Production Recommendations

For production deployment, consider:

1. **Enable TLS/SSL**
   - Set `xpack.security.http.ssl.enabled=true`
   - Generate and configure certificates

2. **Use Docker Secrets**
   - Replace environment variables with Docker Secrets
   - See docker-compose documentation

3. **Implement Role-Based Access Control (RBAC)**
   - Create custom roles with minimal privileges
   - Avoid using `elastic` superuser for applications

4. **Regular Password Rotation**
   - Change passwords every 90 days
   - Use a password manager

5. **Audit Logging**
   - Enable Elasticsearch audit logs
   - Monitor for suspicious activity

6. **Network Isolation**
   - Use private networks
   - Restrict port exposure
   - Implement firewall rules

## Files Reference

- `.env` - Contains all credentials (DO NOT COMMIT)
- `.env.elk` - Backup of credentials (DO NOT COMMIT)
- `setup-elk-security.sh` - Password generation script
- `setup-elk-users.sh` - User configuration script
- `docker-compose.elk.yml` - ELK stack configuration with security

## Support

For issues or questions about ELK security configuration, refer to:
- [Elasticsearch Security Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/security-settings.html)
- Project README.md
