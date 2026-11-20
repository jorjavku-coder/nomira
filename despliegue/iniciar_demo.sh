#!/bin/bash
# Arranque del contenedor único: migraciones, API interna, demo opcional y la interfaz en $PORT.
# Si la API o la interfaz terminan, el contenedor termina también, para que la plataforma lo
# reinicie (antes, si se caía la API, la interfaz seguía arriba respondiendo errores).
set -e
# Los archivos de los despachos deben guardarse en el disco permanente. Si la carpeta no se puede
# escribir, es mejor no arrancar que aceptar archivos que se perderían.
mkdir -p "${STORAGE_DIR:-/datos/almacen}" 2>/dev/null || true
if ! ( touch "${STORAGE_DIR:-/datos/almacen}/.prueba_escritura" && rm -f "${STORAGE_DIR:-/datos/almacen}/.prueba_escritura" ); then
  echo "ERROR: no se puede escribir en ${STORAGE_DIR:-/datos/almacen}. Revise el disco permanente (Render > Disks)." >&2
  exit 1
fi
cd /app/backend
alembic upgrade head

uvicorn app.main:app --host 127.0.0.1 --port 8000 &
API=$!

if [ "${SEMBRAR_DEMO:-false}" = "true" ]; then
  # En segundo plano, para que la interfaz responda de inmediato aunque el equipo sea lento.
  # Durante el primer minuto la demo puede aparecer incompleta.
  (sleep 8; python -m scripts.sembrar_demo --restaurar || echo "No se pudo sembrar la demo") &
fi

cd /app/web
HOSTNAME=0.0.0.0 PORT="${PORT:-10000}" node server.js &
WEB=$!

# Reenvía la señal de apagado de la plataforma a ambos procesos.
trap 'kill -TERM "$API" "$WEB" 2>/dev/null; wait "$API" "$WEB" 2>/dev/null; exit 0' TERM INT

set +e
wait -n "$API" "$WEB"  # vuelve en cuanto cualquiera de los dos termina (no espera a la siembra)
codigo=$?
echo "Un proceso principal terminó (código $codigo); se detiene el contenedor." >&2
kill -TERM "$API" "$WEB" 2>/dev/null
wait "$API" "$WEB" 2>/dev/null
exit $(( codigo == 0 ? 1 : codigo ))
