#!/usr/bin/env bash
# Downloads the artifacts of a «QA móvil» run (.github/workflows/qa-movil.yml) into a folder, so a reviewer, a person
# or an agent, can look at the screenshots, videos, Maestro reports, logcat and API log. Only reads from GitHub
# (GitHub CLI, `gh auth login` once); it builds or runs nothing on this machine.
#
#   scripts/qa/descargar.sh [carpeta] [--pr N | --rama RAMA | --run ID]
#
# Without options it takes the latest finished run of any branch. The files land in <carpeta>/<run id>/
# (default carpeta: qa-descargas). Start with informe.html and resumen.md; see movil/.maestro/README.md.
set -euo pipefail

REPO=${QA_REPO:-gustavop-dev/barrio-ai}
dest=qa-descargas
if [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; then dest=$1; shift; fi
run=""; branch=""
while [ $# -gt 0 ]; do
  case "$1" in
    --run) run=${2:?falta el id}; shift 2 ;;
    --pr) branch=$(gh pr view "${2:?falta el número}" -R "$REPO" --json headRefName --jq .headRefName); shift 2 ;;
    --rama) branch=${2:?falta la rama}; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Opción desconocida: $1 (usa --pr N, --rama RAMA o --run ID)" >&2; exit 2 ;;
  esac
done

if [ -z "$run" ]; then
  args=(-R "$REPO" --workflow qa-movil.yml --status completed --limit 1 --json databaseId --jq '.[0].databaseId')
  [ -n "$branch" ] && args+=(--branch "$branch")
  run=$(gh run list "${args[@]}")
fi
if [ -z "$run" ] || [ "$run" = "null" ]; then
  echo "No hay ejecuciones terminadas de qa-movil.yml${branch:+ en la rama $branch}." >&2
  exit 1
fi

name=$(gh api "repos/$REPO/actions/runs/$run/artifacts" --jq '[.artifacts[] | select(.name | startswith("qa-movil-")) | select(.expired | not)][0].name')
if [ -z "$name" ] || [ "$name" = "null" ]; then
  echo "La ejecución $run no tiene artefactos de QA (caducaron a los 14 días o el job no llegó a subirlos)." >&2
  echo "Detalle: gh run view $run -R $REPO --log-failed" >&2
  exit 1
fi

out="$dest/$run"
rm -rf "$out"; mkdir -p "$out"
gh run download "$run" -R "$REPO" -n "$name" -D "$out"

echo "Ejecución: https://github.com/$REPO/actions/runs/$run"
echo "Artefactos en: $out"
[ -f "$out/resumen.md" ] && cat "$out/resumen.md"
echo
echo "Abre $out/informe.html (capturas por flujo, videos y fallos); logcat en $out/logcat/, API en $out/api.log."
