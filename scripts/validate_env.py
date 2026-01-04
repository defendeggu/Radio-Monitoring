#!/usr/bin/env python3
"""
Environment Configuration Validator for Radio Monitoring System

Validates that .env file contains all required variables with valid values.
Usage:
    python3 scripts/validate_env.py
    python3 scripts/validate_env.py --strict  # Exit with error if warnings exist
"""

import os
import sys
import ipaddress
from pathlib import Path
from typing import List, Tuple, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load .env file
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    load_dotenv(env_file)
else:
    print(f"⚠️  No .env file found at {env_file}")
    print("💡 Create one by copying .env.example:")
    print("   cp .env.example .env")
    sys.exit(1)


# ============================================================================
# Configuration Variables
# ============================================================================

REQUIRED_VARS = {
    'ELASTICSEARCH_HOSTS': {
        'description': 'Elasticsearch cluster URL',
        'example': 'http://elasticsearch:9200',
        'validator': lambda v: v.startswith('http://') or v.startswith('https://')
    },
    'REDIS_HOST': {
        'description': 'Redis server hostname',
        'example': 'redis',
        'validator': lambda v: len(v) > 0
    },
}

REQUIRED_FOR_PRODUCTION = {
    'API_KEYS': {
        'description': 'API authentication keys (comma-separated)',
        'example': 'key1-32chars-here,key2-32chars-here',
        'validator': lambda v: len(v) > 0 and all(len(k.strip()) >= 32 for k in v.split(','))
    },
    'ELASTIC_PASSWORD': {
        'description': 'Elasticsearch password',
        'example': 'StrongPassword123!',
        'validator': lambda v: len(v) >= 8
    },
}

OPTIONAL_VARS = {
    'TRUSTED_IPS': {
        'description': 'Trusted IP addresses/networks (comma-separated)',
        'example': '192.168.1.0/24,10.0.0.0/8',
        'validator': 'validate_ip_list'
    },
    'WHISPER_MODEL': {
        'description': 'Whisper model size',
        'example': 'base',
        'validator': lambda v: v in ['tiny', 'base', 'small', 'medium', 'large']
    },
    'REDIS_PORT': {
        'description': 'Redis server port',
        'example': '6379',
        'validator': lambda v: v.isdigit() and 1 <= int(v) <= 65535
    },
    'REDIS_DB': {
        'description': 'Redis database number',
        'example': '0',
        'validator': lambda v: v.isdigit() and 0 <= int(v) <= 15
    },
    'FLASK_DEBUG': {
        'description': 'Flask debug mode (NEVER true in production!)',
        'example': 'false',
        'validator': lambda v: v.lower() in ['true', 'false', '0', '1']
    },
}


# ============================================================================
# Validation Functions
# ============================================================================

def validate_ip_list(value: str) -> Tuple[bool, Optional[str]]:
    """Validate comma-separated list of IP addresses/networks"""
    if not value:
        return True, None

    for ip_str in value.split(','):
        ip_str = ip_str.strip()
        if not ip_str:
            continue

        try:
            if '/' in ip_str:
                # CIDR network
                ipaddress.ip_network(ip_str)
            else:
                # Single IP
                ipaddress.ip_address(ip_str)
        except ValueError as e:
            return False, f"Invalid IP/network '{ip_str}': {e}"

    return True, None


def validate_variable(name: str, config: dict, value: str) -> Tuple[bool, Optional[str]]:
    """Validate a single environment variable"""
    validator = config.get('validator')

    if not validator:
        return True, None

    # String validator function name
    if isinstance(validator, str):
        if validator == 'validate_ip_list':
            return validate_ip_list(value)
        return False, "Unknown validator"

    # Callable validator
    try:
        if validator(value):
            return True, None
        else:
            return False, f"Validation failed (expected: {config['example']})"
    except Exception as e:
        return False, f"Validation error: {e}"


# ============================================================================
# Main Validation Logic
# ============================================================================

def validate_environment(strict: bool = False) -> bool:
    """
    Validate environment configuration

    Args:
        strict: If True, treat warnings as errors

    Returns:
        bool: True if valid, False otherwise
    """
    errors = []
    warnings = []
    info = []

    print("🔍 Validating environment configuration...")
    print()

    # Check required variables
    print("📋 Required Variables:")
    for var_name, config in REQUIRED_VARS.items():
        value = os.getenv(var_name, '')

        if not value:
            errors.append(f"❌ {var_name}: MISSING (required)")
            print(f"   ❌ {var_name}: MISSING")
            print(f"      Description: {config['description']}")
            print(f"      Example: {config['example']}")
        else:
            is_valid, error_msg = validate_variable(var_name, config, value)
            if is_valid:
                print(f"   ✅ {var_name}: OK")
                info.append(f"✅ {var_name}: {value[:50]}..." if len(value) > 50 else f"✅ {var_name}: {value}")
            else:
                errors.append(f"❌ {var_name}: {error_msg}")
                print(f"   ❌ {var_name}: INVALID - {error_msg}")

    print()

    # Check production-required variables
    print("🔐 Production Security Variables:")
    for var_name, config in REQUIRED_FOR_PRODUCTION.items():
        value = os.getenv(var_name, '')

        if not value:
            warnings.append(f"⚠️  {var_name}: Not set (required for production)")
            print(f"   ⚠️  {var_name}: NOT SET (OK for development)")
            print(f"      Description: {config['description']}")
            print(f"      Example: {config['example']}")
        else:
            is_valid, error_msg = validate_variable(var_name, config, value)
            if is_valid:
                # Don't print actual passwords/keys
                if 'PASSWORD' in var_name or 'KEY' in var_name:
                    print(f"   ✅ {var_name}: SET (***hidden***)")
                else:
                    print(f"   ✅ {var_name}: OK")
            else:
                warnings.append(f"⚠️  {var_name}: {error_msg}")
                print(f"   ⚠️  {var_name}: {error_msg}")

    print()

    # Check optional variables
    print("⚙️  Optional Variables:")
    for var_name, config in OPTIONAL_VARS.items():
        value = os.getenv(var_name, '')

        if not value:
            print(f"   ➖ {var_name}: Not set (using default)")
        else:
            is_valid, error_msg = validate_variable(var_name, config, value)
            if is_valid:
                print(f"   ✅ {var_name}: OK")
            else:
                warnings.append(f"⚠️  {var_name}: {error_msg}")
                print(f"   ⚠️  {var_name}: {error_msg}")

    print()
    print("="*80)

    # Summary
    if errors:
        print()
        print(f"❌ VALIDATION FAILED: {len(errors)} error(s)")
        for error in errors:
            print(f"   {error}")
        return False

    if warnings:
        print()
        if strict:
            print(f"❌ VALIDATION FAILED (strict mode): {len(warnings)} warning(s)")
        else:
            print(f"⚠️  VALIDATION WARNINGS: {len(warnings)} warning(s)")
        for warning in warnings:
            print(f"   {warning}")

        if strict:
            return False

        print()
        print("💡 Warnings are OK for development but should be fixed for production")

    if not errors and not warnings:
        print()
        print("✅ ALL VALIDATIONS PASSED!")

    return True


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == '__main__':
    strict = '--strict' in sys.argv

    print()
    print("="*80)
    print("🔍 Radio Monitoring System - Environment Validator")
    print("="*80)
    print()

    success = validate_environment(strict=strict)

    print()

    if success:
        print("✅ Environment configuration is valid!")
        sys.exit(0)
    else:
        print("❌ Environment configuration has errors. Please fix them before continuing.")
        print()
        print("💡 Quick start:")
        print("   1. Copy template:  cp .env.example .env")
        print("   2. Edit values:    nano .env")
        print("   3. Re-validate:    python3 scripts/validate_env.py")
        sys.exit(1)
