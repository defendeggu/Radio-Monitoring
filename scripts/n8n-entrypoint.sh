#!/bin/sh
# N8N Entrypoint Script with Secrets Support

# Read secrets from Docker secrets files
export N8N_BASIC_AUTH_USER=$(cat /run/secrets/n8n_basic_auth_user)
export N8N_BASIC_AUTH_PASSWORD=$(cat /run/secrets/n8n_basic_auth_password)

# Start N8N with the original entrypoint
exec /docker-entrypoint.sh "$@"
