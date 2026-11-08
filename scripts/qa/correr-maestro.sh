#!/usr/bin/env bash
# Runs inside reactivecircus/android-emulator-runner (.github/workflows/qa-movil.yml): installs the QA APK, sizes the
# screen to 390x844 dp, and runs every Maestro flow of movil/.maestro on its own. Before each flow the backend is
# re-seeded (seed_qa), so a flow never depends on what another one changed. Each flow gets a screen recording,
# its JUnit report and Maestro's own output. It always exits 0: scripts/qa/informe.py decides pass or fail.
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${QA_OUT:?QA_OUT sin definir}
INFRA=${INFRA_DIR:-$ROOT/agentes-linkedin/infra}
FLOWS="$ROOT/movil/.maestro"
APP=co.projectapp.office
export MAESTRO_CLI_NO_ANALYTICS=1 MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true

mkdir -p "$OUT"/capturas/fallos "$OUT"/videos "$OUT"/junit "$OUT"/maestro "$OUT"/logcat
: > "$OUT/flujos.txt"

log() { echo "[qa] $*"; }

adb wait-for-device
# The design boards are 390x844 dp: 1170x2532 px at 480 dpi (3x) on the emulator's pixel_6 panel.
adb shell wm size 1170x2532
adb shell wm density 480
adb shell svc power stayon true
adb shell settings put system screen_off_timeout 1800000
# Same zone as the backend (America/Bogota), so «hoy» and «mañana» match on both sides.
adb root > /dev/null 2>&1 && sleep 2 && adb wait-for-device
adb shell setprop persist.sys.timezone America/Bogota || true
adb shell cmd alarm set-timezone America/Bogota > /dev/null 2>&1 || true
adb shell date
log "pantalla: $(adb shell wm size | tr -d '\r' | tail -n1) · $(adb shell wm density | tr -d '\r' | tail -n1)"

log "instalando ${QA_APK:?QA_APK sin definir}"
adb install -r -g "$QA_APK"

adb logcat -c
adb logcat -v threadtime > "$OUT/logcat/logcat-completo.txt" 2>&1 &
LOGCAT_PID=$!

REC_FLAG=""
REC_PID=""
record_start() {
  REC_FLAG=$(mktemp)
  adb shell rm -rf /sdcard/qa-rec > /dev/null 2>&1
  adb shell mkdir -p /sdcard/qa-rec
  (
    part=0
    while [ -f "$REC_FLAG" ]; do
      # screenrecord stops at 180 s: record consecutive parts until the flow ends.
      adb shell screenrecord --bit-rate 3000000 --time-limit 170 "/sdcard/qa-rec/$1-parte$part.mp4" > /dev/null 2>&1
      part=$((part + 1))
    done
  ) &
  REC_PID=$!
}
record_stop() {
  rm -f "$REC_FLAG"
  adb shell pkill -INT screenrecord > /dev/null 2>&1
  wait "$REC_PID" 2> /dev/null
  sleep 1
  adb pull /sdcard/qa-rec/. "$OUT/videos/" > /dev/null 2>&1 || log "no se pudo copiar el video de $1"
  adb shell rm -rf /sdcard/qa-rec > /dev/null 2>&1
}

for flow in "$FLOWS"/[0-9][0-9]-*.yaml; do
  name=$(basename "$flow" .yaml)
  log "flujo $name: sembrando el mundo de QA"
  (cd "$INFRA" && uv run python manage.py seed_qa >> "$OUT/seed.log" 2>&1) || log "seed_qa falló antes de $name"
  record_start "$name"
  start=$(date +%s)
  maestro test "$flow" \
    --format junit --output "$OUT/junit/$name.xml" \
    --test-output-dir "$OUT/maestro/$name" \
    --debug-output "$OUT/maestro/$name/debug" --flatten-debug-output \
    -e QA_USER=qa -e QA_PASSWORD="${QA_PASSWORD:?}" \
    > "$OUT/maestro/$name.log" 2>&1
  code=$?
  end=$(date +%s)
  record_stop "$name"
  log "flujo $name: código $code en $((end - start)) s"
  echo "$name $code $((end - start))" >> "$OUT/flujos.txt"
  # takeScreenshot files are named NN-screen-step; Maestro's failure screenshots go apart, prefixed by the flow.
  while IFS= read -r png; do
    base=$(basename "$png")
    case "$base" in
      [0-9][0-9]-*) cp "$png" "$OUT/capturas/$base" ;;
      *) cp "$png" "$OUT/capturas/fallos/$name--$base" ;;
    esac
  done < <(find "$OUT/maestro/$name" -name '*.png' 2> /dev/null)
done

# The app's state at the end, for the record.
adb shell dumpsys activity processes 2> /dev/null | grep -i "$APP" > "$OUT/logcat/procesos.txt" || true
kill "$LOGCAT_PID" 2> /dev/null
wait "$LOGCAT_PID" 2> /dev/null
log "listo"
exit 0
