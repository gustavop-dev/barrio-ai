#!/usr/bin/env bash
# Copia diaria (cron): 0 4 * * * /ruta/deploy/backup.sh  — conserva 14 días.
set -euo pipefail
cd -- "$(dirname -- "$0")"
umask 077
mkdir -p backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose -f compose.prod.yaml --env-file .env exec -T db pg_dump -U knowledge -d knowledge -Fc > "backups/knowledge-$stamp.dump"
# Private files of the capture button and the Galería (volume media), next to the database dump.
docker compose -f compose.prod.yaml --env-file .env exec -T api sh -c 'tar -C "${MEDIA_ROOT:-/app/media}" -czf - .' > "backups/media-$stamp.tar.gz"
find backups -name 'knowledge-*.dump' -mtime +14 -delete
find backups -name 'media-*.tar.gz' -mtime +14 -delete
