#!/usr/bin/env bash
# Runs inside reactivecircus/android-emulator-runner (.github/workflows/qa-movil.yml): installs the QA APK on the
# 390x844 dp emulator (the workflow defines it at that size), and runs the Maestro flows of this emulator job (QA_FLOWS, names separated by spaces; all of
# movil/.maestro when empty) one by one. Before each flow the backend is re-seeded (seed_qa), so a flow never depends
# on what another one changed. Each flow gets a screen recording, its JUnit report and Maestro's own output; files
# shared by the job carry its number (QA_SHARD) so several jobs merge into one report. It always exits 0:
# scripts/qa/informe.py decides pass or fail.
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${QA_OUT:?QA_OUT sin definir}
INFRA=${INFRA_DIR:-$ROOT/agentes-linkedin/infra}
FLOWS="$ROOT/movil/.maestro"
APP=co.projectapp.office
SHARD=${QA_SHARD:-1}
export MAESTRO_CLI_NO_ANALYTICS=1 MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true

mkdir -p "$OUT"/capturas/fallos "$OUT"/videos "$OUT"/junit "$OUT"/maestro "$OUT"/logcat
: > "$OUT/flujos-$SHARD.txt"

log() { echo "[qa] $*"; }

adb wait-for-device
adb shell svc power stayon true
adb shell settings put system screen_off_timeout 1800000
# Same zone as the backend (America/Bogota), so «hoy» and «mañana» match on both sides.
adb root > /dev/null 2>&1 && sleep 2 && adb wait-for-device
adb shell setprop persist.sys.timezone America/Bogota || true
adb shell cmd alarm set-timezone America/Bogota > /dev/null 2>&1 || true
adb shell date
log "pantalla: $(adb shell wm size | tr -d '\r' | tail -n1) · $(adb shell wm density | tr -d '\r' | tail -n1)"

# A cold, software-rendered emulator can leave «Pixel Launcher isn't responding» over the app. System error dialogs
# are hidden (crashes of the app are read from logcat, not from a dialog), and any dialog left is dismissed.
adb shell settings put global hide_error_dialogs 1
adb shell settings put global anr_show_background 0
settle_system() {
  for _ in $(seq 1 12); do
    if adb shell dumpsys window 2> /dev/null | grep -qiE "mCurrentFocus=.*(Application Not Responding|not responding)"; then
      log "diálogo de «no responde» del sistema: se cierra con Esperar"
      adb shell input keyevent KEYCODE_BACK
    fi
    sleep 5
  done
}
settle_system

log "instalando ${QA_APK:?QA_APK sin definir}"
adb install -r -g "$QA_APK"

# CAP-05: a picture in the emulator's gallery for Android's photo picker (one of the PNGs seed_qa generated).
pic=$(find "$INFRA/media/galeria" -name '*.png' 2> /dev/null | head -n1)
if [ -n "$pic" ]; then
  adb push "$pic" /sdcard/Pictures/qa-pizarra.png > /dev/null
  adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Pictures/qa-pizarra.png > /dev/null 2>&1 || true
  adb shell content call --uri content://media --method scan_volume --arg external_primary > /dev/null 2>&1 || true
else
  log "no hay una foto sembrada para el selector de fotos"
fi

adb logcat -c
adb logcat -v threadtime > "$OUT/logcat/logcat-completo-$SHARD.txt" 2>&1 &
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

if [ -n "${QA_FLOWS:-}" ]; then
  selected=$(for name in $QA_FLOWS; do echo "$FLOWS/$name.yaml"; done)
else
  selected=$(ls "$FLOWS"/[0-9][0-9]-*.yaml)
fi
log "emulador $SHARD: $(echo $selected | xargs -n1 basename | tr '\n' ' ')"

for flow in $selected; do
  name=$(basename "$flow" .yaml)
  log "flujo $name: sembrando el mundo de QA"
  (cd "$INFRA" && uv run python manage.py seed_qa >> "$OUT/seed-$SHARD.log" 2>&1) || log "seed_qa falló antes de $name"
  record_start "$name"
  start=$(date +%s)
  # A hard cap per flow: a hung flow fails with its screenshot and the job goes on to the next one.
  timeout --kill-after=30 "${QA_FLOW_TIMEOUT:-480}" maestro test "$flow" \
    --format junit --output "$OUT/junit/$name.xml" \
    --test-output-dir "$OUT/maestro/$name" \
    --debug-output "$OUT/maestro/$name/debug" --flatten-debug-output \
    -e QA_USER=qa -e QA_PASSWORD="${QA_PASSWORD:?}" \
    > "$OUT/maestro/$name.log" 2>&1
  code=$?
  end=$(date +%s)
  if [ "$code" -eq 124 ] || [ "$code" -eq 137 ]; then
    echo "TIMEOUT: el flujo superó ${QA_FLOW_TIMEOUT:-480} s y se cortó" >> "$OUT/maestro/$name.log"
    adb exec-out screencap -p > "$OUT/capturas/fallos/$name--tiempo-agotado.png" 2> /dev/null || true
  fi
  record_stop "$name"
  log "flujo $name: código $code en $((end - start)) s"
  echo "$name $code $((end - start))" >> "$OUT/flujos-$SHARD.txt"
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
adb shell dumpsys activity processes 2> /dev/null | grep -i "$APP" > "$OUT/logcat/procesos-$SHARD.txt" || true
kill "$LOGCAT_PID" 2> /dev/null
wait "$LOGCAT_PID" 2> /dev/null
log "listo"
exit 0
