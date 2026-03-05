#!/bin/bash
#
# ELK Security Setup Script
# Generates random passwords and creates environment file for secure ELK stack
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.elk"

echo "=========================================="
echo "ELK Security Setup"
echo "=========================================="
echo ""

# Function to generate random password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# Check if .env.elk already exists
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  Warning: $ENV_FILE already exists!"
    echo ""
    read -p "Do you want to regenerate passwords? This will RESET all credentials! (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted. Existing passwords kept."
        exit 0
    fi
    echo ""
    # Backup existing file
    cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✅ Backup created: ${ENV_FILE}.backup.*"
fi

# Generate passwords
echo "🔐 Generating secure passwords..."
ELASTIC_PASSWORD=$(generate_password)
KIBANA_PASSWORD=$(generate_password)
LOGSTASH_PASSWORD=$(generate_password)
BEATS_PASSWORD=$(generate_password)
LOGSTASH_WRITER_PASSWORD=$(generate_password)
KIBANA_ENCRYPTION_KEY=$(openssl rand -hex 32)
REDIS_PASSWORD=$(generate_password)

# Create .env.elk file
cat > "$ENV_FILE" << EOF
# ============================================================================
# ELK Stack Security Credentials
# Generated: $(date)
# ============================================================================
#
# ⚠️  SECURITY WARNING:
# - These are sensitive credentials - do NOT commit to Git!
# - Keep this file secure and backed up separately
# - For production: Use Docker Secrets instead of environment variables
#
# ============================================================================

# Elasticsearch built-in user passwords
ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
KIBANA_SYSTEM_PASSWORD=${KIBANA_PASSWORD}
LOGSTASH_SYSTEM_PASSWORD=${LOGSTASH_PASSWORD}
BEATS_SYSTEM_PASSWORD=${BEATS_PASSWORD}
LOGSTASH_WRITER_PASSWORD=${LOGSTASH_WRITER_PASSWORD}
KIBANA_ENCRYPTION_KEY=${KIBANA_ENCRYPTION_KEY}
REDIS_PASSWORD=${REDIS_PASSWORD}

# Elasticsearch connection URLs (with authentication)
ELASTICSEARCH_URL=http://elastic:\${ELASTIC_PASSWORD}@elasticsearch:9200
ELASTICSEARCH_URL_EXTERNAL=http://elastic:\${ELASTIC_PASSWORD}@localhost:9200
EOF

echo "✅ Generated .env.elk with secure passwords"
echo ""

# Update .gitignore to exclude .env.elk
if ! grep -q "^\.env\.elk$" "${SCRIPT_DIR}/.gitignore" 2>/dev/null; then
    echo ".env.elk" >> "${SCRIPT_DIR}/.gitignore"
    echo "✅ Added .env.elk to .gitignore"
fi

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Review generated credentials:"
echo "   cat .env.elk"
echo ""
echo "2. Start the secured ELK stack:"
echo "   docker compose down"
echo "   docker compose up -d"
echo ""
echo "3. Run post-setup to import dashboards:"
echo "   ./scripts/post-docker-setup.sh"
echo ""
echo "   This will:"
echo "   - Wait for all services to be healthy"
echo "   - Import Kibana dashboards automatically"
echo "   - Display access URLs and credentials"
echo ""
echo "4. Access Kibana at http://localhost:5601"
echo "   Username: elastic"
echo "   Password: (see ELASTIC_PASSWORD in .env.elk)"
echo ""
echo "⚠️  IMPORTANT: Save your .env.elk file securely!"
echo "   If lost, you'll need to reset the entire cluster."
echo ""
