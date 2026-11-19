#!/usr/bin/env bash
# Copia diaria (cron): 0 4 * * * /ruta/deploy/backup.sh  — conserva la última copia y la anterior (BACKUP_KEEP).
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
# Retention (Gustavo, 19/11/2026): only the newest copy and the one before it stay; older ones go as soon as a new one
# is complete. BACKUP_KEEP changes how many (never fewer than 2). An empty or failed copy never reaches this line (set -e).
keep="${BACKUP_KEEP:-2}"
case "$keep" in ''|*[!0-9]*) keep=2 ;; esac
[ "$keep" -ge 2 ] || keep=2
for patron in 'knowledge-*.dump' 'media-*.tar.gz'; do
  # Names carry a UTC stamp, so reverse name order is newest first.
  find backups -maxdepth 1 -type f -name "$patron" | sort -r | tail -n "+$((keep + 1))" | while IFS= read -r viejo; do
    rm -f -- "$viejo"
  done
done
