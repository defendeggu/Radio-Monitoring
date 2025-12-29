#!/bin/bash
# pgAdmin Entrypoint Script with Secrets Support

# Read secrets from Docker secrets files
export PGADMIN_DEFAULT_EMAIL=$(cat /run/secrets/pgadmin_email)
export PGADMIN_DEFAULT_PASSWORD=$(cat /run/secrets/pgadmin_password)

# Start pgAdmin with the original entrypoint
exec python /pgadmin4/pgAdmin4.py
