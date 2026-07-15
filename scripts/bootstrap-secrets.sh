#!/usr/bin/env bash
# Genera secretos iniciales. Ejecutar UNA vez en el VPS, nunca en local versionado.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && { echo ".env ya existe, aborto"; exit 1; }
PG=$(openssl rand -hex 24)
printf '%s' "$PG" > secrets/pg_password.txt
chmod 600 secrets/pg_password.txt
cat > .env << EOV
PG_PASSWORD=$PG
UMAMI_SECRET=$(openssl rand -hex 32)
CALCOM_SECRET=$(openssl rand -hex 32)
CALCOM_ENC_KEY=$(openssl rand -hex 32)
N8N_KEY=$(openssl rand -hex 32)
IN_DB_PASSWORD=$(openssl rand -hex 24)
IN_APP_KEY=base64:$(openssl rand -base64 32)
POSTIZ_JWT=$(openssl rand -hex 32)
EOV
chmod 600 .env
echo "Secretos generados en .env y secrets/pg_password.txt"
