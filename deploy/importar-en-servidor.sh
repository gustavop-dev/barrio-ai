#!/usr/bin/env bash
# Ejecutar en el servidor, en deploy/, con .env ya configurado. Restaura la base exportada
# en una base vacía y aplica las migraciones nuevas. Nunca sobre una base con datos.
set -euo pipefail
PAQUETE=${1:?Uso: ./importar-en-servidor.sh ~/barrio-ai-migracion-XXXX.tar.gz}
umask 077
TMP=$(mktemp -d); tar -C "$TMP" -xzf "$PAQUETE"; DIR=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d)
mkdir -p conocimiento backups && cp -r "$DIR/conocimiento/." conocimiento/
docker compose -f compose.prod.yaml --env-file .env up -d db
until docker compose -f compose.prod.yaml --env-file .env exec -T db pg_isready -U knowledge -d knowledge >/dev/null; do sleep 2; done
if [ "$(docker compose -f compose.prod.yaml --env-file .env exec -T db psql -U knowledge -d knowledge -tAc "select count(*) from information_schema.tables where table_schema='public'")" != "0" ]; then
  echo "La base del servidor ya tiene tablas; no se restaura encima." >&2; exit 1
fi
docker compose -f compose.prod.yaml --env-file .env exec -T db pg_restore -U knowledge -d knowledge --no-owner < "$DIR/knowledge.dump"
rm -rf "$TMP"
docker compose -f compose.prod.yaml --env-file .env up -d --build
echo "Restaurado. Revisa: docker compose -f compose.prod.yaml ps"
