#!/usr/bin/env bash
# CI only. The workflow copies this controller outside the checkout before any git reset.
# The supervisor polls every 15 s, including while an iteration is running. Only it mutates Git.
set -euo pipefail

[[ ${GITHUB_ACTIONS:-} == true && ${QA_SESION_CI:-} == 1 ]] || {
  echo 'Este script solo corre dentro de qa-sesion.yml; usa sesion-resultado.sh para leer resultados.' >&2
  exit 2
}
ROOT=${QA_SESION_ROOT:?}
SESSION=${RUNNER_TEMP:?}/qa-sesion
BIN=$(cd "$(dirname "$0")" && pwd)
UTIL="$BIN/sesion-util.py"
APP=co.projectapp.office
API=http://127.0.0.1:8787
export MAESTRO_CLI_NO_ANALYTICS=1 MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true
# disableOnboarding=1: the dev client otherwise opens its menu over the app on first launch (and after clearState).
export QA_DEVCLIENT_URL='oficina0ff1ce://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081&disableOnboarding=1'
export EXPO_PUBLIC_API_URL=http://10.0.2.2:8787 OFFICE_QA_BUILD=1 EXPO_NO_DOTENV=1
cd "$ROOT"

log() { echo "[qa-sesion] $*"; }
animations() {
  for key in window_animation_scale transition_animation_scale animator_duration_scale; do
    adb shell settings put global "$key" "$1" > /dev/null
  done
}

warm_bundle() {
  local until=$((SECONDS + 180)) url status
  python3 "$UTIL" sonda "$ROOT" "$HEAD"
  while (( SECONDS < until )); do
    if curl -fsS --max-time 15 -H 'expo-platform: android' -H 'accept: application/expo+json' \
        http://127.0.0.1:8081/ -o "$OUT/manifest.json"; then
      if url=$(python3 - "$OUT/manifest.json" <<'PY'
import json, sys
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
url = urlsplit(json.load(open(sys.argv[1]))['launchAsset']['url'])
assert url.scheme == 'http' and url.port == 8081
assert url.hostname in ('localhost', '127.0.0.1', '10.0.2.2')
query = dict(parse_qsl(url.query))
query.update(dev='false', minify='true', lazy='false', **{'transform.bytecode': '0'})
print(urlunsplit(('http', '127.0.0.1:8081', url.path, urlencode(query), '')))
PY
      ); then
        status=$(curl -sS --max-time 90 "$url" -o "$OUT/bundle.js" -w '%{http_code}') || status=000
        if [[ $status == 200 ]] && grep -Fq "qa-sesion:$HEAD" "$OUT/bundle.js"; then
          rm -f "$OUT/bundle.js" "$OUT/manifest.json"
          return 0
        fi
      fi
    fi
    sleep 2
  done
  echo 'ERROR: Metro no sirvió un bundle fresco con el SHA esperado.' >&2
  return 1
}

iteration() {
  HEAD=$1
  OUT=$2
  local name start code scale pic
  # The parent prepared the immutable list for this SHA before starting the worker.
  # timeout --foreground keeps child commands in this worker group, so a new push kills them all.
  refresh_backend "$(cat "$SESSION/backend-head")" "$HEAD"
  warm_bundle
  adb reverse tcp:8081 tcp:8081
  adb shell am force-stop "$APP"
  # Quoted for the device shell: an unquoted & in the link split the command there.
  adb shell "am start -W -a android.intent.action.VIEW -d '$QA_DEVCLIENT_URL' $APP"
  python3 "$UTIL" preparar "$ROOT" "$OUT/flujos" "$BIN/sesion-abrir.yaml"
  timeout --foreground --kill-after=10 90 maestro test "$ROOT/scripts/qa/autoprueba-fallos.yaml" \
    > "$OUT/autoprueba-fallos.log" 2>&1
  curl -fsS --max-time 10 -X DELETE "$API/api/v1/qa/fallos" > /dev/null
  for name in $(cat "$OUT/seleccion.txt"); do
    start=$(date +%s)
    code=0
    mkdir -p "$OUT/maestro/$name"
    # A failed seed/switch reset fails this flow; never run against leftovers and call it a pass.
    if ! (cd "$INFRA_DIR" && timeout --foreground --kill-after=10 90 uv run python manage.py seed_qa >> "$OUT/seed.log" 2>&1); then
      echo 'ERROR: seed_qa falló antes del flujo.' > "$OUT/maestro/$name.log"
      code=1
    elif ! curl -fsS --max-time 10 -X DELETE "$API/api/v1/qa/fallos" > /dev/null; then
      echo 'ERROR: no se pudo limpiar el interruptor de fallos.' > "$OUT/maestro/$name.log"
      code=1
    else
      # Re-seeding generates the gallery fixture; keep Android's photo picker usable after every seed.
      pic=$(find "$INFRA_DIR/media/galeria" -name '*.png' -print -quit)
      if [[ -n $pic ]]; then
        adb push "$pic" /sdcard/Pictures/qa-pizarra.png > /dev/null
        adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE \
          -d file:///sdcard/Pictures/qa-pizarra.png > /dev/null 2>&1 || true
        adb shell content call --uri content://media --method scan_volume --arg external_primary > /dev/null 2>&1 || true
      fi
      scale=0
      for animated in ${QA_FLUJOS_ANIMADOS:-01-entrada 02-navegacion 03-oficina}; do
        [[ $animated != "$name" ]] || scale=1
      done
      animations "$scale"
      # A killed previous flow may not have executed its onFlowComplete hook.
      adb shell cmd connectivity airplane-mode disable
      adb reverse tcp:8081 tcp:8081
      timeout --foreground --kill-after=15 "${QA_FLOW_TIMEOUT:-480}" maestro test "$OUT/flujos/$name.yaml" \
        --format junit --output "$OUT/junit/$name.xml" \
        --test-output-dir "$OUT/maestro/$name" \
        --debug-output "$OUT/maestro/$name/debug" --flatten-debug-output \
        -e QA_USER=qa -e QA_PASSWORD="${QA_PASSWORD:?}" -e QA_DEVCLIENT_URL="$QA_DEVCLIENT_URL" \
        > "$OUT/maestro/$name.log" 2>&1 || code=$?
    fi
    if (( code != 0 )); then
      [[ $code != 124 && $code != 137 ]] || echo 'TIMEOUT: se agotó el límite del flujo.' >> "$OUT/maestro/$name.log"
      timeout --foreground 10 adb exec-out screencap -p > "$OUT/capturas/$name.png" 2> /dev/null || true
    fi
    echo "$name $code $(($(date +%s) - start))" >> "$OUT/flujos.txt"
    log "$name: código $code"
  done
}

: "${QA_RAMA:?}" "${QA_DEADLINE:?}" "${QA_NATIVE_FINGERPRINT:?}" "${GH_TOKEN:?}"
git check-ref-format "refs/heads/$QA_RAMA"
[[ $QA_RAMA != qa-sesion/* ]] || { echo 'Una rama de resultados no puede ser la rama de código.' >&2; exit 2; }
[[ ${QA_MODE:-} == true && ${LIVE_PROVIDERS:-} == false && ${LIVE_LINKEDIN:-} == false \
   && ${LIVE_LINKEDIN_OFFICIAL:-} == false && ${OPERATOR_ALLOW_FAKE:-} == true \
   && ${DATABASE_URL:-} == postgresql://knowledge:qa-only-ci-password@127.0.0.1:5432/knowledge ]] || exit 2
mkdir -p "$SESSION"
WORKER=''
METRO_PID=''
HEAD=$(git rev-parse HEAD)
OUT=''
PR=''
START=$(date +%s)

stop_worker() {
  if [[ -n $WORKER ]]; then
    kill -TERM -- "-$WORKER" 2> /dev/null || true
    sleep 2
    kill -KILL -- "-$WORKER" 2> /dev/null || true
    wait "$WORKER" 2> /dev/null || true
    WORKER=''
  fi
}
cleanup() {
  stop_worker
  [[ -z $METRO_PID ]] || kill -TERM -- "-$METRO_PID" 2> /dev/null || true
}
new_output() {
  # Retain only one iteration on disk too, so a long session cannot fill the runner.
  [[ -z $OUT ]] || rm -rf "$OUT"
  OUT=$(mktemp -d "$SESSION/iteracion.XXXXXX")
  mkdir -p "$OUT"/{junit,maestro,capturas}
  : > "$OUT/flujos.txt"
  START=$(date +%s)
}

publish() {
  local state=$1 message=$2 result index tree commit comment gitdir
  result=$(mktemp -d "$SESSION/publicar.XXXXXX")
  rmdir "$result"
  tail -c 262144 "$SESSION/metro.log" > "$OUT/metro.log" 2> /dev/null || true
  python3 "$UTIL" resumen "$OUT" "$result" "$QA_RAMA" "$HEAD" "$state" "$message" "$START"
  # Separate index/work tree; commit-tree with NO parent makes every publication an orphan.
  # Only refs/heads/qa-sesion/<rama> is force-pushed. The checked-out source index is untouched.
  index=$(mktemp "$SESSION/index.XXXXXX")
  rm "$index"
  gitdir=$(git rev-parse --absolute-git-dir)
  tree=$(
    export GIT_INDEX_FILE="$index" GIT_WORK_TREE="$result" GIT_DIR="$gitdir"
    cd "$result"
    git read-tree --empty
    git add -f --all .
    git write-tree
  )
  commit=$(git -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
    commit-tree "$tree" -m "QA sesión: $HEAD")
  timeout 60 git push --force origin "$commit:refs/heads/qa-sesion/$QA_RAMA"
  rm -f "$index"
  if [[ -n $PR ]]; then
    # Match both marker and bot author; never edit a human's last comment or qa-movil's comment.
    comment=$(timeout 30 gh api --paginate "repos/$GITHUB_REPOSITORY/issues/$PR/comments" \
      --jq '.[] | select(.user.login == "github-actions[bot]" and (.body | startswith("<!-- qa-sesion -->"))) | .id' | tail -n1)
    if [[ -n $comment ]]; then
      timeout 30 gh api --method PATCH "repos/$GITHUB_REPOSITORY/issues/comments/$comment" \
        -F "body=@$result/resumen.md" > /dev/null
    else
      timeout 30 gh pr comment "$PR" --repo "$GITHUB_REPOSITORY" --body-file "$result/resumen.md" > /dev/null
    fi
  fi
  cat "$result/resumen.md"
  rm -rf "$result"
}

refresh_backend() {
  # JS-only pushes keep gunicorn alive. Backend edits must not silently use old Python modules.
  # Reconcile dependencies/schema and restart only gunicorn when backend sources changed.
  local old=$1 new=$2 pid
  if ! git diff --quiet "$old" "$new" -- agentes-linkedin || [[ -f $SESSION/backend-pendiente ]]; then
    log 'Cambió el backend: actualizando el backend local de QA.'
    touch "$SESSION/backend-pendiente"
    if [[ -s $SESSION/gunicorn.pid ]]; then
      pid=$(cat "$SESSION/gunicorn.pid")
      kill -TERM "$pid" 2> /dev/null || true
      for _ in $(seq 1 30); do kill -0 "$pid" 2> /dev/null || break; sleep 1; done
      # Do not start a second API if the old master failed to shut down.
      if kill -0 "$pid" 2> /dev/null; then echo 'ERROR: gunicorn no se detuvo.' >&2; return 1; fi
    fi
    (
      cd "$INFRA_DIR"
      timeout --foreground --kill-after=10 120 uv sync --frozen
      timeout --foreground --kill-after=10 90 uv run python manage.py migrate --noinput
      timeout --foreground --kill-after=10 90 uv run python manage.py bootstrap_local
      timeout --foreground --kill-after=10 90 uv run python manage.py collectstatic --noinput --verbosity 0
      DJANGO_SETTINGS_MODULE=linkedin_backend.settings_qa \
        nohup setsid uv run gunicorn linkedin_backend.wsgi:application --bind 0.0.0.0:8787 --workers 3 --timeout 120 \
        --pid "$SESSION/gunicorn.pid" --access-logfile - --error-logfile - --capture-output \
        >> "$QA_OUT/api-$QA_SHARD.log" 2>&1 &
    )
  fi
  for _ in $(seq 1 60); do
    # A superseded autoprueba/flow may have left /health returning a simulated 503.
    if curl -fsS --max-time 3 -X DELETE "$API/api/v1/qa/fallos" > /dev/null \
        && curl -fsS --max-time 2 "$API/health" > /dev/null; then
      printf '%s\n' "$new" > "$SESSION/backend-head"
      rm -f "$SESSION/backend-pendiente"
      return 0
    fi
    sleep 1
  done
  echo 'ERROR: el backend local no responde.' >&2
  return 1
}

if [[ ${1:-} == --iteracion ]]; then
  iteration "$2" "$3"
  exit 0
fi

trap cleanup EXIT
trap 'exit 130' INT TERM
printf '%s\n' "$HEAD" > "$SESSION/backend-head"
adb wait-for-device
adb root > /dev/null 2>&1 || true
sleep 2
adb wait-for-device
adb shell svc power stayon true
adb shell settings put system screen_off_timeout 1800000
adb shell setprop persist.sys.timezone America/Bogota || true
adb shell cmd alarm set-timezone America/Bogota > /dev/null 2>&1 || true
adb shell settings put global hide_error_dialogs 1
adb shell settings put global anr_show_background 0
adb install -r -g "${QA_APK:?}"
adb shell mkdir -p /sdcard/Pictures
adb reverse tcp:8081 tcp:8081
python3 "$UTIL" sonda "$ROOT" "$HEAD"
# Host advertised in Expo's manifest must be reachable through adb reverse, not the runner's LAN IP.
(
  cd "$ROOT/movil"
  # CI=false: with CI=true (GitHub's default) Metro disables file watching, and the pushes reset by the loop would
  # never reach the bundle (run 42510134236: «reloads are disabled»).
  export CI=false EXPO_OFFLINE=1 REACT_NATIVE_PACKAGER_HOSTNAME=localhost
  exec setsid npx expo start --dev-client --no-dev --minify --port 8081
) > "$SESSION/metro.log" 2>&1 &
METRO_PID=$!

seen=''
initial=${QA_SELECCION:-}
errors=0
while true; do
  if (( $(date +%s) >= QA_DEADLINE )); then
    stop_worker
    [[ -n $OUT ]] || new_output
    publish caducada 'Se agotó la duración de la sesión. Inicia otra con workflow_dispatch.'
    exit 0
  fi
  # gh pr view returns the closed/merged PR too; if there is no PR, branch-only sessions are allowed.
  pr_json=$(timeout 20 gh pr view "$QA_RAMA" --repo "$GITHUB_REPOSITORY" --json number,state 2> "$SESSION/pr-error.log") || pr_json=''
  if [[ -n $pr_json ]]; then
    PR=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("number",""))' <<< "$pr_json")
    state=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("state",""))' <<< "$pr_json")
    if [[ $state == MERGED || $state == CLOSED ]]; then
      stop_worker
      [[ -n $OUT ]] || new_output
      publish cerrada "El PR #$PR está $state; la sesión terminó."
      exit 0
    fi
  elif ! grep -qi 'no pull requests found' "$SESSION/pr-error.log"; then
    log 'No se pudo consultar el PR; se reintentará en el próximo sondeo.'
  fi
  if ! timeout 25 git fetch --no-tags origin "+refs/heads/$QA_RAMA:refs/remotes/origin/qa-sesion-vigilada"; then
    errors=$((errors + 1))
    if (( errors >= 3 )); then
      stop_worker
      [[ -n $OUT ]] || new_output
      publish error 'No se pudo leer la rama en tres intentos; revisa si fue eliminada o falló GitHub.'
      exit 1
    fi
    sleep 15
    continue
  fi
  errors=0
  next=$(git rev-parse refs/remotes/origin/qa-sesion-vigilada)
  if [[ $next != "$seen" ]]; then
    stop_worker
    HEAD=$next
    new_output
    if [[ $(python3 "$UTIL" huella "$ROOT" "$HEAD") != "$QA_NATIVE_FINGERPRINT" ]]; then
      publish nativo 'Cambió lo nativo: corre qa-movil (APK nuevo)'
      exit 0
    fi
    git reset --hard "$HEAD"
    if ! python3 "$UTIL" seleccionar "$ROOT" "$HEAD" --initial "$initial" > "$OUT/seleccion.txt" 2> "$OUT/iteracion.log"; then
      publish error 'Selección de flujos inválida; revisa el tag [qa: ...] y el log.'
    else
      if [[ ! -s $OUT/seleccion.txt || -z $(cat "$OUT/seleccion.txt") ]]; then
        publish idle 'Sin tag [qa: ...] ni selección inicial: esperando un push con flujos.'
      else
        setsid bash "$BIN/sesion.sh" --iteracion "$HEAD" "$OUT" > "$OUT/iteracion.log" 2>&1 &
        WORKER=$!
      fi
    fi
    initial=''
    seen=$HEAD
  fi
  if [[ -n $WORKER ]] && ! kill -0 "$WORKER" 2> /dev/null; then
    code=0
    wait "$WORKER" || code=$?
    WORKER=''
    if (( code == 0 )); then
      publish terminado 'Flujos ejecutados con Metro --no-dev --minify y el backend local de QA.'
    else
      publish error 'Falló la preparación de la iteración; revisa maestro/iteracion.log y metro.log.'
    fi
  fi
  sleep 15
done
