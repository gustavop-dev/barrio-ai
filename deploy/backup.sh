#!/usr/bin/env bash
# Copia diaria (cron): 0 4 * * * /ruta/deploy/backup.sh  — conserva 14 días.
set -euo pipefail
cd -- "$(dirname -- "$0")"
umask 077
mkdir -p backups
docker compose -f compose.prod.yaml --env-file .env exec -T db pg_dump -U knowledge -d knowledge -Fc > "backups/knowledge-$(date -u +%Y%m%dT%H%M%SZ).dump"
find backups -name 'knowledge-*.dump' -mtime +14 -delete
