#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
umask 077
mkdir -p backups
backup_path="backups/knowledge-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose exec -T db pg_dump -U knowledge -d knowledge -Fc > "$backup_path"
echo "Copia guardada: $backup_path"
