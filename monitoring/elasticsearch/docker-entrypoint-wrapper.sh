#!/bin/bash
# Elasticsearch Docker Secrets Wrapper
# Reads passwords from Docker Secrets and sets as environment variables

set -e

# Function to read secret file if it exists
read_secret() {
    local secret_name=$1
    local env_var=$2
    local secret_file="/run/secrets/${secret_name}"

    if [ -f "$secret_file" ]; then
        echo "Loading secret: $secret_name"
        export "$env_var"="$(cat "$secret_file")"
    elif [ -z "${!env_var}" ]; then
        echo "WARNING: Neither secret file $secret_file nor env var $env_var is set!"
    fi
}

# Read Elasticsearch password from secret or use environment variable
read_secret "elasticsearch_password" "ELASTIC_PASSWORD"

# Execute the original entrypoint
exec /usr/local/bin/docker-entrypoint.sh "$@"
