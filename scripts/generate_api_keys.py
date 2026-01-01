#!/usr/bin/env python3
"""
Generate secure API keys for the Radio Transcription API

This script generates cryptographically secure API keys that can be used
to authenticate requests to the Radio Transcription API.

Usage:
    python3 scripts/generate_api_keys.py

The script will generate two API keys and print them in a format that can be
directly added to the .env file.
"""

import secrets


def generate_api_key() -> str:
    """
    Generate a cryptographically secure API key.

    Returns:
        A URL-safe base64 encoded random string (32 bytes = 256 bits of entropy)
    """
    return secrets.token_urlsafe(32)


def main() -> None:
    """Generate and print API keys"""
    print("=" * 80)
    print("Radio Transcription API - Secure API Key Generator")
    print("=" * 80)
    print()

    # Generate two API keys
    api_key_1 = generate_api_key()
    api_key_2 = generate_api_key()

    print("Generated API Keys:")
    print()
    print(f"  N8N Integration Key:  {api_key_1}")
    print(f"  Admin/Dev Key:        {api_key_2}")
    print()
    print("=" * 80)
    print("Add these to your .env file as:")
    print("=" * 80)
    print()
    print(f"API_KEYS={api_key_1},{api_key_2}")
    print()
    print("=" * 80)
    print("IMPORTANT:")
    print("  - Keep these keys secret!")
    print("  - Do NOT commit them to Git!")
    print("  - Store them in a secure password manager")
    print("  - For N8N: Set environment variable RADIO_API_KEY to the first key")
    print("=" * 80)


if __name__ == '__main__':
    main()
