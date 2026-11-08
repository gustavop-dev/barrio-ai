#!/usr/bin/env bash
# CI only; invoked from movil with the apk job's shared QA environment.
set -euo pipefail
out=${1:?directorio de exportación}
mkdir -p "$out/assets" "$out/res"
entry=$(node -e "require('expo/scripts/resolveAppEntry')" "$PWD" android absolute)
# Match RN 0.88 BundleHermesCTask: release Metro output, then the dependency's
# own Hermes compiler with -O. Keep maps outside assets/ so they aren't shipped.
npx --no-install expo export:embed --platform android --dev false --minify false \
  --entry-file "$entry" --bundle-output "$out/assets/index.android.bundle" \
  --assets-dest "$out/res" --sourcemap-output "$out/index.android.bundle.packager.map"
hermes_dir=$(node --print "require('path').dirname(require.resolve('hermes-compiler/package.json'))")
"$hermes_dir/hermesc/linux64-bin/hermesc" -w -emit-binary -max-diagnostic-width=80 -O \
  -out "$out/index.android.hbc" "$out/assets/index.android.bundle"
mv "$out/index.android.hbc" "$out/assets/index.android.bundle"
