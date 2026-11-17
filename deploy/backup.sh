#!/usr/bin/env bash
# Copia diaria (cron): 0 4 * * * /ruta/deploy/backup.sh  — conserva 14 días.
set -Eeuo pipefail
cd -- "$(dirname -- "$0")"
umask 077

# Si algo falla, avisa en el canal de alertas de Slack (SLACK_WEBHOOK_URL del .env; vacío = sin aviso). La URL nunca
# se imprime ni queda en la línea de órdenes: curl la lee de un archivo de configuración efímero.
avisar_fallo() {
  local codigo=$? linea=${1:-?} url=''
  trap - ERR
  if [ -r .env ]; then
    url="$(sed -n 's/^SLACK_WEBHOOK_URL=//p' .env | tail -n 1 | tr -d '\r')" || url=''
    url="${url%\"}"; url="${url#\"}"; url="${url%\'}"; url="${url#\'}"
  fi
  if [ -n "$url" ]; then
    local texto="Barrio · La copia de seguridad diaria falló ($(date '+%d/%m %H:%M'), línea $linea, código $codigo). La base y los archivos de hoy no están copiados; revisa deploy/backup.sh y deploy/backups en el servidor."
    printf '{"text":"%s"}' "$texto" |
      curl -fsS -m 10 -o /dev/null -H 'Content-Type: application/json' --data-binary @- \
        --config <(printf 'url = "%s"\n' "$url") >/dev/null 2>&1 ||
      echo "backup.sh: tampoco salió el aviso a Slack." >&2
  fi
  exit "$codigo"
}
trap 'avisar_fallo $LINENO' ERR

mkdir -p backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose -f compose.prod.yaml --env-file .env exec -T db pg_dump -U knowledge -d knowledge -Fc > "backups/knowledge-$stamp.dump"
# Private files of the capture button and the Galería (volume media), next to the database dump.
docker compose -f compose.prod.yaml --env-file .env exec -T api sh -c 'tar -C "${MEDIA_ROOT:-/app/media}" -czf - .' > "backups/media-$stamp.tar.gz"
find backups -name 'knowledge-*.dump' -mtime +14 -delete
find backups -name 'media-*.tar.gz' -mtime +14 -delete
