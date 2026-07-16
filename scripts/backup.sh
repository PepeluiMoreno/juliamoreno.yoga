#!/usr/bin/env bash
# Copia de seguridad cifrada con restic. Cron sugerido (root):
#   15 4 * * * /opt/juliamoreno/scripts/backup.sh >> /var/log/backup-jmy.log 2>&1
# Requiere: restic instalado, /root/.restic-env con:
#   export RESTIC_REPOSITORY=...   (sftp://otro-vps o s3:...)
#   export RESTIC_PASSWORD=...
set -euo pipefail
source /root/.restic-env
cd /opt/juliamoreno
mkdir -p /var/backups/jmy
# 1. volcado de las bases de datos
docker exec jmy-pg pg_dumpall -U julia > /var/backups/jmy/pg_dumpall.sql
docker exec jmy-facturas-db sh -c 'mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" --all-databases' \
  > /var/backups/jmy/mariadb.sql 2>/dev/null || true
# 2. respaldo: repo desplegado (con .env y secrets), volcados y volúmenes de fichero
restic backup /opt/juliamoreno /var/backups/jmy \
  /var/lib/docker/volumes/juliamoreno_nocodata \
  /var/lib/docker/volumes/juliamoreno_injadata \
  /var/lib/docker/volumes/juliamoreno_kumadata \
  --tag jmy
# 3. retención: 7 diarias, 4 semanales, 6 mensuales
restic forget --tag jmy --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
# 4. verificación ligera
restic check --read-data-subset=5%
