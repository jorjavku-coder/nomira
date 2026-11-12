#!/bin/sh
# Arranque del contenedor único: migraciones, demo opcional, API interna y la interfaz en $PORT.
set -e
cd /app/backend
alembic upgrade head
if [ "${SEMBRAR_DEMO:-false}" = "true" ]; then
  python -m scripts.sembrar_demo --restaurar
fi
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
cd /app/web
exec env HOSTNAME=0.0.0.0 PORT="${PORT:-10000}" node server.js
