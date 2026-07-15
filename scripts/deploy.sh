#!/usr/bin/env bash
# Despliegue en el VPS: trae cambios y regenera la web.
# Uso manual:  ./scripts/deploy.sh
# Uso como webhook: exponer con un pequeno listener (ver docs/cicd-despliegue.md)
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
python3 scripts/build-web.py
docker compose --profile web up -d
echo "Despliegue completado: $(date)"
