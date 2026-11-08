#!/usr/bin/env bash
# Read-only GitHub access; never checks out, resets or builds the local branch.
# Usage: scripts/qa/sesion-resultado.sh <rama> [sha] [--carpeta DIR] [--espera SEGUNDOS]
# Defaults: local HEAD, qa-sesion-resultados/<sha>, wait at most 1800 s, poll every 15 s.
set -euo pipefail

if [[ $# == 0 || ${1:-} == --help || ${1:-} == -h ]]; then
  sed -n '2,5p' "$0"
  exit 0
fi
branch=$1
shift
git check-ref-format "refs/heads/$branch"
sha=HEAD
if [[ $# -gt 0 && $1 != --* ]]; then sha=$1; shift; fi
dest=qa-sesion-resultados
seconds=1800
while [[ $# -gt 0 ]]; do
  case $1 in
    --carpeta) dest=${2:?falta carpeta}; shift 2 ;;
    --espera) seconds=${2:?faltan segundos}; shift 2 ;;
    *) echo "Opción desconocida: $1" >&2; exit 2 ;;
  esac
done
[[ $seconds =~ ^[1-9][0-9]*$ ]] || { echo '--espera debe ser un entero positivo' >&2; exit 2; }
if resolved=$(git rev-parse --verify "$sha^{commit}" 2> /dev/null); then sha=$resolved; fi
[[ $sha =~ ^[0-9a-f]{40}$ ]] || { echo 'Usa un SHA completo o una referencia local válida.' >&2; exit 2; }
repo=${QA_REPO:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}
ref=$(python3 - "$branch" <<'PY'
from urllib.parse import quote
import sys
print(quote('qa-sesion/' + sys.argv[1], safe=''))
PY
)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
deadline=$((SECONDS + seconds))
echo "Esperando QA de $branch · $sha (máximo $seconds s)..."
while (( SECONDS < deadline )); do
  # Resolve the moving branch ONCE per poll. Metadata and archive then use that immutable commit,
  # so a simultaneous force-push cannot mix the SHA of one iteration with another's screenshots.
  if commit=$(gh api "repos/$repo/commits/$ref" --jq .sha 2> "$scratch/error.log") \
      && gh api "repos/$repo/contents/resultado.json?ref=$commit" --jq .content \
        | base64 --decode > "$scratch/resultado.json"; then
    found=$(jq -r .sha "$scratch/resultado.json")
    if [[ $found == "$sha" ]]; then
      out="$dest/$sha"
      if [[ -e $out ]]; then
        echo "La carpeta $out ya existe; elige otra con --carpeta para no sobrescribirla." >&2
        exit 2
      fi
      gh api "repos/$repo/tarball/$commit" > "$scratch/resultados.tar.gz"
      mkdir -p "$scratch/descarga" "$dest"
      tar -xzf "$scratch/resultados.tar.gz" --strip-components=1 --no-same-owner -C "$scratch/descarga"
      [[ $(jq -r .sha "$scratch/descarga/resultado.json") == "$sha" ]]
      mv "$scratch/descarga" "$out"
      cat "$out/resumen.md"
      echo "Resultados descargados en: $out"
      case $(jq -r .estado "$out/resultado.json") in
        ok|idle) exit 0 ;;
        *) exit 1 ;;
      esac
    fi
    echo "La última iteración corresponde a $found; sigo esperando $sha."
  elif grep -qE 'HTTP (401|403)' "$scratch/error.log"; then
    cat "$scratch/error.log" >&2
    exit 1
  fi
  sleep 15
done
echo "No llegaron resultados para $sha en $seconds s. Revisa qa-sesion.yml en GitHub." >&2
echo 'Solo se conserva la última iteración; un push posterior puede cancelar o reemplazar esta.' >&2
exit 124
