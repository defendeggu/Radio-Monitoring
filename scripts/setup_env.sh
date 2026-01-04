#!/bin/bash
# ============================================================================
# Radio Monitoring System - Environment Setup Helper
# ============================================================================
#
# This script helps set up the .env file for first-time users
#
# Usage:
#   ./scripts/setup_env.sh
#   ./scripts/setup_env.sh --force  # Overwrite existing .env

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# ============================================================================
# Main Setup Process
# ============================================================================

echo ""
print_header "Radio Monitoring System - Environment Setup"
echo ""

# Check if .env already exists
if [ -f .env ] && [ "$1" != "--force" ]; then
    print_warning ".env file already exists!"
    echo ""
    echo "Options:"
    echo "  1. Keep existing .env (recommended if already configured)"
    echo "  2. Backup and create new .env"
    echo "  3. Cancel"
    echo ""
    read -p "Choose option (1-3): " choice

    case $choice in
        1)
            print_info "Keeping existing .env file"
            ;;
        2)
            backup_file=".env.backup.$(date +%Y%m%d_%H%M%S)"
            cp .env "$backup_file"
            print_success "Backed up to $backup_file"
            ;;
        3)
            print_info "Setup cancelled"
            exit 0
            ;;
        *)
            print_error "Invalid choice. Exiting."
            exit 1
            ;;
    esac
fi

# Copy .env.example if needed
if [ ! -f .env ] || [ "$choice" = "2" ]; then
    if [ ! -f .env.example ]; then
        print_error ".env.example not found!"
        exit 1
    fi

    cp .env.example .env
    print_success "Created .env from .env.example"
fi

echo ""
print_header "Configuration Options"
echo ""

# Ask for key configuration options
echo "Choose your setup type:"
echo "  1. Development (localhost, no security)"
echo "  2. Production (requires API keys and passwords)"
echo ""
read -p "Setup type (1-2): " setup_type

if [ "$setup_type" = "2" ]; then
    echo ""
    print_info "Production setup requires:"
    echo "  - API Keys (for authentication)"
    echo "  - Elasticsearch passwords"
    echo ""

    # Generate API keys
    if command -v python3 &> /dev/null; then
        if [ -f scripts/generate_api_keys.py ]; then
            print_info "Generating API keys..."
            api_key=$(python3 scripts/generate_api_keys.py --count 1 --quiet 2>/dev/null || echo "")
            if [ -n "$api_key" ]; then
                # Update .env with generated key
                if grep -q "^API_KEYS=" .env; then
                    sed -i "s/^API_KEYS=.*/API_KEYS=$api_key/" .env
                    print_success "Generated and added API key"
                fi
            fi
        fi
    fi

    # Generate Elasticsearch password
    print_info "Generating Elasticsearch password..."
    elastic_pass=$(openssl rand -base64 24 2>/dev/null || echo "changeme-$(date +%s)")
    if grep -q "^ELASTIC_PASSWORD=" .env; then
        sed -i "s/^ELASTIC_PASSWORD=.*/ELASTIC_PASSWORD=$elastic_pass/" .env
        print_success "Generated Elasticsearch password"
    fi

    print_warning "Remember to run ./setup-elk-security.sh for full ELK setup!"
fi

echo ""
print_header "Validation"
echo ""

# Validate the configuration
if command -v python3 &> /dev/null; then
    if [ -f scripts/validate_env.py ]; then
        print_info "Validating configuration..."
        echo ""
        python3 scripts/validate_env.py || true
    else
        print_warning "Validation script not found (scripts/validate_env.py)"
    fi
else
    print_warning "Python3 not found - skipping validation"
fi

echo ""
print_header "Setup Complete!"
echo ""

print_success ".env file is ready!"
echo ""
print_info "Next steps:"
echo "  1. Review and edit .env if needed: nano .env"
echo "  2. Validate configuration: python3 scripts/validate_env.py"

if [ "$setup_type" = "2" ]; then
    echo "  3. Setup ELK security: ./setup-elk-security.sh"
    echo "  4. Start services: docker compose up -d"
else
    echo "  3. Start services: docker compose up -d"
fi

echo ""
print_info "Important files:"
echo "  - .env          : Your configuration (NEVER commit to Git!)"
echo "  - .env.example  : Template with all variables"
echo ""

# Set secure permissions
chmod 600 .env
print_success "Set secure file permissions (chmod 600 .env)"

echo ""
print_success "All done! 🎉"
echo ""
