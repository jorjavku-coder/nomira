#!/bin/sh
# Arranque del contenedor único: migraciones, API interna, demo opcional y la interfaz en $PORT.
set -e
cd /app/backend
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
if [ "${SEMBRAR_DEMO:-false}" = "true" ]; then
  # En segundo plano, para que la interfaz responda de inmediato aunque el equipo sea lento.
  # Durante el primer minuto la demo puede aparecer incompleta.
  (sleep 8; python -m scripts.sembrar_demo --restaurar || echo "No se pudo sembrar la demo") &
fi
cd /app/web
exec env HOSTNAME=0.0.0.0 PORT="${PORT:-10000}" node server.js
