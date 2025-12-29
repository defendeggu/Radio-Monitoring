# Docker Secrets Directory

This directory contains sensitive credentials used by the Radio Monitoring System. Secrets are stored as individual text files and mounted into Docker containers at `/run/secrets/`.

## 🔐 Security Notice

**⚠️ IMPORTANT: Never commit actual secret files to version control!**

- All `.txt` files in this directory are excluded from git via `.gitignore`
- Keep backups of your secrets in a secure location (password manager, encrypted storage)
- Rotate passwords regularly, especially after initial setup

## 📋 Required Secret Files

The following secret files must be created before starting the system:

### PostgreSQL Secrets
- `postgres_user.txt` - Database username
- `postgres_password.txt` - Database password
- `postgres_db.txt` - Database name

### Grafana Secrets
- `grafana_admin_user.txt` - Grafana admin username
- `grafana_admin_password.txt` - Grafana admin password

### N8N Secrets
- `n8n_basic_auth_user.txt` - N8N basic auth username
- `n8n_basic_auth_password.txt` - N8N basic auth password

### pgAdmin Secrets
- `pgadmin_email.txt` - pgAdmin login email
- `pgadmin_password.txt` - pgAdmin password

## 🚀 Quick Setup

### Automatic Setup (Recommended)

Run the setup script from the project root:

```bash
./setup-secrets.sh
```

This script will:
- Generate strong random passwords for all services
- Create all required secret files
- Set proper file permissions (600)
- Display your credentials for safekeeping

### Manual Setup

Create each file manually with your own credentials:

```bash
cd secrets

# PostgreSQL
echo "radio_user" > postgres_user.txt
echo "your_strong_password_here" > postgres_password.txt
echo "radio_monitoring" > postgres_db.txt

# Grafana
echo "admin" > grafana_admin_user.txt
echo "your_grafana_password" > grafana_admin_password.txt

# N8N
echo "admin" > n8n_basic_auth_user.txt
echo "your_n8n_password" > n8n_basic_auth_password.txt

# pgAdmin
echo "admin@admin.com" > pgadmin_email.txt
echo "your_pgadmin_password" > pgadmin_password.txt

# Set proper permissions
chmod 600 *.txt
```

## 🔄 Using Secrets

Secrets are automatically loaded by Docker Compose when you start the services:

```bash
docker compose up -d
```

Inside containers, secrets are available at:
```
/run/secrets/secret_name
```

For example:
```bash
cat /run/secrets/postgres_password
```

## 🔧 How It Works

### Docker Compose Integration

In `docker-compose.yml`, secrets are defined as:

```yaml
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
```

And mounted in services:

```yaml
services:
  postgres:
    secrets:
      - postgres_password
    environment:
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
```

### Application Code

The `database_service.py` automatically reads secrets using the helper function:

```python
def read_secret(secret_name: str) -> Optional[str]:
    secret_path = Path(f'/run/secrets/{secret_name}')
    if secret_path.exists():
        return secret_path.read_text().strip()
    return None
```

## 🔐 Best Practices

1. **Strong Passwords**: Use the auto-generated passwords or create strong ones (20+ characters, mixed case, numbers, symbols)
2. **Password Manager**: Store credentials in a password manager (1Password, Bitwarden, etc.)
3. **Backup**: Keep an encrypted backup of your secrets
4. **Rotation**: Change passwords regularly (every 90 days minimum)
5. **Access Control**: Limit who has access to this directory
6. **File Permissions**: Always keep secret files at 600 (read/write for owner only)

## 📝 Viewing Your Credentials

After running `setup-secrets.sh`, you can view your credentials:

```bash
# PostgreSQL
cat secrets/postgres_user.txt
cat secrets/postgres_password.txt

# Grafana (http://localhost:3000)
cat secrets/grafana_admin_user.txt
cat secrets/grafana_admin_password.txt

# N8N (http://localhost:5679)
cat secrets/n8n_basic_auth_user.txt
cat secrets/n8n_basic_auth_password.txt

# pgAdmin (http://localhost:5050)
cat secrets/pgadmin_email.txt
cat secrets/pgadmin_password.txt
```

## 🆘 Troubleshooting

### Secrets not found error

**Problem**: Container fails to start with "secret not found" error

**Solution**:
```bash
# Check if all secret files exist
ls -la secrets/*.txt

# Re-run setup script if any are missing
./setup-secrets.sh
```

### Permission denied error

**Problem**: Cannot read secret files in container

**Solution**:
```bash
# Fix file permissions
chmod 600 secrets/*.txt
```

### Wrong password

**Problem**: Services reject the password

**Solution**:
```bash
# Update the secret file
echo "new_password" > secrets/postgres_password.txt

# Restart services
docker compose restart
```

## 🔄 Changing Passwords

To change a password:

1. Update the secret file:
   ```bash
   echo "new_strong_password" > secrets/service_password.txt
   ```

2. Restart the affected service:
   ```bash
   docker compose restart service_name
   ```

3. For PostgreSQL, you may need to reset the database:
   ```bash
   docker compose down
   docker volume rm my-project_postgres-data
   docker compose up -d
   ```

## 📚 Further Reading

- [Docker Secrets Documentation](https://docs.docker.com/engine/swarm/secrets/)
- [Docker Compose Secrets](https://docs.docker.com/compose/use-secrets/)
- [Password Security Best Practices](https://www.nist.gov/password-guidelines)
