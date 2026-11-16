#!/usr/bin/env bash
# Ejecutar en la laptop. Empaqueta la base de datos y los archivos de política de uso, para
# subirlos al servidor. Los agentes leen hoy solo la de «Procesamiento completo»; la de las
# clases 08–12 viaja con ella para no perderla. El paquete contiene datos privados.
set -euo pipefail
umask 077
RUNTIME=${RUNTIME:-/home/cerrotico/personal/linkedin/agentes-linkedin/infra}
SOURCE_ROOT=${SOURCE_ROOT:-/home/cerrotico/personal/linkedin}
OUT=${OUT:-$PWD/barrio-ai-migracion-$(date -u +%Y%m%dT%H%M%SZ)}
for carpeta in "LinkedIn Sales - Procesamiento completo" "LinkedIn Sales - Procesamiento clases 08-12"; do
  mkdir -p "$OUT/conocimiento/$carpeta/conocimiento-para-agentes"
  cp "$SOURCE_ROOT/$carpeta/conocimiento-para-agentes/politica-de-uso.json" "$OUT/conocimiento/$carpeta/conocimiento-para-agentes/"
done
(cd "$RUNTIME" && docker compose exec -T db pg_dump -U knowledge -d knowledge -Fc) > "$OUT/knowledge.dump"
tar -C "$(dirname "$OUT")" -czf "$OUT.tar.gz" "$(basename "$OUT")"
rm -rf "$OUT"
echo "Paquete listo: $OUT.tar.gz  (subir con: scp $OUT.tar.gz usuario@servidor:~/)"
