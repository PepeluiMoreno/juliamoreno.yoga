#!/usr/bin/env bash
# Despliegue en el VPS: trae cambios y regenera la web desde NocoDB.
# Los HTML y contenido.json son artefactos regenerables: los cambios
# locales del VPS se descartan siempre antes del pull (la fuente de
# verdad de datos es NocoDB; la de código, git).
set -euo pipefail
cd "$(dirname "$0")/.."
git checkout -- sitio/ data/contenido.json 2>/dev/null || true
git pull --ff-only
python3 scripts/build-web.py
docker compose --profile web up -d
echo "Despliegue completado: $(date)"
