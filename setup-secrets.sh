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

# PostgreSQL Secrets
echo -e "${BLUE}PostgreSQL Secrets:${NC}"
create_secret "postgres_user.txt" "radio_user"
create_secret "postgres_password.txt" "$(generate_password)"
create_secret "postgres_db.txt" "radio_monitoring"

echo ""

# Grafana Secrets
echo -e "${BLUE}Grafana Secrets:${NC}"
create_secret "grafana_admin_user.txt" "admin"
create_secret "grafana_admin_password.txt" "$(generate_password)"

echo ""

# N8N Secrets
echo -e "${BLUE}N8N Secrets:${NC}"
create_secret "n8n_basic_auth_user.txt" "admin"
create_secret "n8n_basic_auth_password.txt" "$(generate_password)"

echo ""

# pgAdmin Secrets
echo -e "${BLUE}pgAdmin Secrets:${NC}"
create_secret "pgadmin_email.txt" "admin@admin.com"
create_secret "pgadmin_password.txt" "$(generate_password)"

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
echo -e "  ${BLUE}PostgreSQL:${NC}"
echo -e "    User:     $(cat $SECRETS_DIR/postgres_user.txt 2>/dev/null || echo 'Not set')"
echo -e "    Password: $(cat $SECRETS_DIR/postgres_password.txt 2>/dev/null || echo 'Not set')"
echo -e "    Database: $(cat $SECRETS_DIR/postgres_db.txt 2>/dev/null || echo 'Not set')"
echo ""
echo -e "  ${BLUE}Grafana (http://localhost:3000):${NC}"
echo -e "    User:     $(cat $SECRETS_DIR/grafana_admin_user.txt 2>/dev/null || echo 'Not set')"
echo -e "    Password: $(cat $SECRETS_DIR/grafana_admin_password.txt 2>/dev/null || echo 'Not set')"
echo ""
echo -e "  ${BLUE}N8N (http://localhost:5679):${NC}"
echo -e "    User:     $(cat $SECRETS_DIR/n8n_basic_auth_user.txt 2>/dev/null || echo 'Not set')"
echo -e "    Password: $(cat $SECRETS_DIR/n8n_basic_auth_password.txt 2>/dev/null || echo 'Not set')"
echo ""
echo -e "  ${BLUE}pgAdmin (http://localhost:5050):${NC}"
echo -e "    Email:    $(cat $SECRETS_DIR/pgadmin_email.txt 2>/dev/null || echo 'Not set')"
echo -e "    Password: $(cat $SECRETS_DIR/pgadmin_password.txt 2>/dev/null || echo 'Not set')"
echo ""
echo -e "${RED}⚠ SECURITY NOTICE:${NC}"
echo -e "  • These files contain sensitive information"
echo -e "  • They are excluded from git via .gitignore"
echo -e "  • Keep backups in a secure location (password manager, encrypted storage)"
echo -e "  • Never commit these files to version control"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo -e "  1. Save these credentials to your password manager"
echo -e "  2. Run: ${BLUE}docker compose down${NC}"
echo -e "  3. Run: ${BLUE}docker compose up -d${NC}"
echo ""
