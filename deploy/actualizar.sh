#!/usr/bin/env bash
# Actualiza producción a la imagen nueva: copia de seguridad, descarga, arranque y limpieza.
# Uso (en el servidor, tras el merge a main y el workflow en verde): ./actualizar.sh
#
# Imágenes (Gustavo, 19/11/2026): de cada servicio quedan solo la imagen actual y la anterior. Al llegar una nueva, la
# que estaba en uso pasa a llamarse :anterior (para volver atrás: BARRIO_TAG=anterior docker compose ... up -d) y la
# anterior de antes se borra. El servicio navegador no se reinicia aquí (perfil navegador: cerraría la sesión de
# LinkedIn); su imagen en uso nunca se borra aunque llegue una más nueva.
set -Eeuo pipefail
cd -- "$(dirname -- "$0")"

compose=(docker compose -f compose.prod.yaml --env-file .env)
tag="${BARRIO_TAG:-latest}"
repos=(ghcr.io/gustavop-dev/barrio-ai-api ghcr.io/gustavop-dev/barrio-ai-web ghcr.io/gustavop-dev/barrio-ai-navegador)

declare -A antes
for repo in "${repos[@]}"; do
  antes[$repo]="$(docker image inspect --format '{{.Id}}' "$repo:$tag" 2>/dev/null || true)"
done

./backup.sh
"${compose[@]}" pull
"${compose[@]}" up -d

for repo in "${repos[@]}"; do
  ahora="$(docker image inspect --format '{{.Id}}' "$repo:$tag" 2>/dev/null || true)"
  # Only when a new image really arrived: a pull that brought nothing keeps the real previous one as :anterior.
  if [ -n "${antes[$repo]}" ] && [ -n "$ahora" ] && [ "${antes[$repo]}" != "$ahora" ]; then
    docker tag "${antes[$repo]}" "$repo:anterior"
  fi
done
# Whatever lost its name (the :anterior of before, older pulls) goes; images a container still uses are never removed.
docker image prune -f
docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}  {{.CreatedSince}}' | grep barrio-ai || true
df -h / | tail -n 1
