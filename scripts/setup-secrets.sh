#!/bin/bash

# Radio Monitoring System - Secrets Setup Script
# This script initializes secret files for Docker Compose secrets management

set -e

SECRETS_DIR="./secrets"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Radio Monitoring - Secrets Setup${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Check if secrets directory exists
if [ ! -d "$SECRETS_DIR" ]; then
    echo -e "${YELLOW}Creating secrets directory...${NC}"
    mkdir -p "$SECRETS_DIR"
fi

# Function to generate random password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# Function to create secret file
create_secret() {
    local secret_name=$1
    local secret_value=$2
    local secret_file="$SECRETS_DIR/$secret_name"

    if [ -f "$secret_file" ]; then
        echo -e "${YELLOW}  ⚠ $secret_name already exists, skipping...${NC}"
        return
    fi

    echo "$secret_value" > "$secret_file"
    chmod 600 "$secret_file"
    echo -e "${GREEN}  ✓ Created: $secret_name${NC}"
}

echo -e "${BLUE}Creating secret files...${NC}"
echo ""

# Elasticsearch Secrets
echo -e "${BLUE}Elasticsearch Secrets:${NC}"
create_secret "elasticsearch_password.txt" "$(generate_password)"
create_secret "kibana_password.txt" "$(generate_password)"
create_secret "logstash_password.txt" "$(generate_password)"
create_secret "beats_password.txt" "$(generate_password)"

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Secrets Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${YELLOW}Important Information:${NC}"
echo ""
echo -e "Your credentials have been generated and stored in: ${BLUE}$SECRETS_DIR/${NC}"
echo ""
echo -e "${YELLOW}To view your credentials:${NC}"
echo ""
echo -e "  ${BLUE}Elasticsearch:${NC}"
echo -e "    elastic password:  $(cat $SECRETS_DIR/elasticsearch_password.txt 2>/dev/null || echo 'Not set')"
echo -e "    kibana_system:     $(cat $SECRETS_DIR/kibana_password.txt 2>/dev/null || echo 'Not set')"
echo -e "    logstash_writer:   $(cat $SECRETS_DIR/logstash_password.txt 2>/dev/null || echo 'Not set')"
echo -e "    beats_system:      $(cat $SECRETS_DIR/beats_password.txt 2>/dev/null || echo 'Not set')"
echo ""
echo -e "${RED}⚠ SECURITY NOTICE:${NC}"
echo -e "  • These files contain sensitive information"
echo -e "  • They are excluded from git via .gitignore"
echo -e "  • Keep backups in a secure location (password manager, encrypted storage)"
echo -e "  • Never commit these files to version control"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo -e "  1. Save these credentials to your password manager"
echo -e "  2. Run: ${BLUE}./setup-elk-security.sh${NC} to apply credentials to the ELK stack"
echo -e "  3. Run: ${BLUE}docker compose up -d${NC}"
echo ""
