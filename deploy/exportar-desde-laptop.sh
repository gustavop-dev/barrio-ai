#!/usr/bin/env bash
# Ejecutar en la laptop. Empaqueta la base de datos y el archivo de política que el
# runtime necesita, para subirlos al servidor. El paquete contiene datos privados.
set -euo pipefail
umask 077
RUNTIME=${RUNTIME:-/home/cerrotico/personal/linkedin/agentes-linkedin/infra}
SOURCE_ROOT=${SOURCE_ROOT:-/home/cerrotico/personal/linkedin}
OUT=${OUT:-$PWD/barrio-ai-migracion-$(date -u +%Y%m%dT%H%M%SZ)}
mkdir -p "$OUT/conocimiento/LinkedIn Sales - Procesamiento completo/conocimiento-para-agentes"
(cd "$RUNTIME" && docker compose exec -T db pg_dump -U knowledge -d knowledge -Fc) > "$OUT/knowledge.dump"
cp "$SOURCE_ROOT/LinkedIn Sales - Procesamiento completo/conocimiento-para-agentes/politica-de-uso.json" \
   "$OUT/conocimiento/LinkedIn Sales - Procesamiento completo/conocimiento-para-agentes/"
tar -C "$(dirname "$OUT")" -czf "$OUT.tar.gz" "$(basename "$OUT")"
rm -rf "$OUT"
echo "Paquete listo: $OUT.tar.gz  (subir con: scp $OUT.tar.gz usuario@servidor:~/)"
