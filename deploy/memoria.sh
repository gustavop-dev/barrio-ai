#!/usr/bin/env bash
# Memoria del servidor (cron, cada 5 min): */5 * * * * /ruta/barrio-ai/deploy/memoria.sh
# Avisa en el canal de alertas de Slack (SLACK_WEBHOOK_URL del .env; vacío = solo lo escribe en la salida) cuando:
#  - la memoria disponible del servidor (MemAvailable) queda por debajo de MEMORIA_ALERTA_MB dos lecturas seguidas
#    (diez minutos: un navegador que arranca o la copia de las 4:00 no bastan). Un aviso por episodio, y otro cuando
#    vuelve a MEMORIA_RECUPERADA_MB o más (el hueco entre los dos evita avisos que van y vienen);
#  - el kernel mató un proceso de un contenedor por falta de memoria (evento `oom` de Docker), una vez por contenedor
#    y hora;
#  - Docker reinició solo un contenedor (sube su RestartCount: se cayó y `restart: unless-stopped` lo levantó).
# Un despliegue no cuenta: recrea los contenedores y su cuenta vuelve a cero.
# Lo que ya avisó vive en estado/memoria (fuera de git). Un aviso que no sale se vuelve a intentar en la pasada
# siguiente. Códigos de salida: 0 bien; 1 no se pudo leer la memoria; 2 docker falló; 3 el aviso a Slack no salió.
# Manda el primero que ocurre, y la pasada sigue con lo demás. Pruebas: team_backend/tests/test_memoria_servidor.py.
# Solo para esas pruebas: MEMORIA_MEMINFO (otro /proc/meminfo) y MEMORIA_AHORA (otra hora, en segundos).
set -uo pipefail
cd -- "$(dirname -- "$0")"
umask 077

codigo=0
fallo() { [ "$codigo" -ne 0 ] || codigo=$1; }

# Un valor del .env, sin comillas ni retorno de carro; vacío si no está. Nunca se imprime.
leer_env() {
  local valor=''
  if [ -r .env ]; then
    valor="$(sed -n "s/^$1=//p" .env | tail -n 1 | tr -d '\r')" || valor=''
    valor="${valor%\"}"; valor="${valor#\"}"; valor="${valor%\'}"; valor="${valor#\'}"
  fi
  printf '%s' "$valor"
}

numero() {  # $1 nombre en el .env, $2 por defecto
  local valor
  valor="$(leer_env "$1")"
  if [ -z "$valor" ]; then
    valor=$2
  elif ! [[ $valor =~ ^[0-9]+$ ]]; then
    echo "memoria.sh: $1 no es un número de MiB; se usa $2." >&2
    valor=$2
  fi
  printf '%s' "$valor"
}

webhook="$(leer_env SLACK_WEBHOOK_URL)"
alerta="$(numero MEMORIA_ALERTA_MB 300)"
recuperada="$(numero MEMORIA_RECUPERADA_MB $((alerta + 200)))"
[ "$recuperada" -gt "$alerta" ] || recuperada=$((alerta + 1))
meminfo="${MEMORIA_MEMINFO:-/proc/meminfo}"
ahora="${MEMORIA_AHORA:-}"
[[ $ahora =~ ^[0-9]+$ ]] || ahora="$(date +%s)"
hora="$(date -d "@$ahora" '+%d/%m %H:%M')"
mkdir -p estado
archivo=estado/memoria

# Escribe el texto en la salida (el registro del cron) y lo manda a Slack. 0 = salió o no hay webhook; 1 = no salió.
# La URL va en un archivo de configuración efímero de curl: ni en la línea de órdenes ni en ninguna salida.
avisar() {
  local texto="Barrio · $1"
  printf '%s %s\n' "$(date -d "@$ahora" '+%F %T')" "$texto"
  [ -n "$webhook" ] || return 0
  if printf '{"text":"%s"}' "$texto" |
    curl -fsS -m 10 -o /dev/null -H 'Content-Type: application/json' --data-binary @- \
      --config <(printf 'url = "%s"\n' "$webhook") >/dev/null 2>&1; then
    return 0
  fi
  echo "memoria.sh: el aviso a Slack no salió; se intenta otra vez en la próxima pasada." >&2
  fallo 3
  return 1
}

# --- lo que ya se sabía ------------------------------------------------------------------------------------------------
bajas=0 episodio=0 inicio='' revisado=''
declare -A reinicios=() oom_avisado=()
if [ -r "$archivo" ]; then
  while read -r clave valor _; do
    [[ ${valor:-} =~ ^[0-9]+$ ]] || continue
    case $clave in
      bajas) bajas=$valor ;;
      episodio) episodio=$valor ;;
      inicio) inicio=$valor ;;
      revisado) revisado=$valor ;;
      reinicios:?*) reinicios[${clave#reinicios:}]=$valor ;;
      oom:?*) oom_avisado[${clave#oom:}]=$valor ;;
    esac
  done < "$archivo"
fi

# --- la memoria del servidor -------------------------------------------------------------------------------------------
disp="$(awk '$1 == "MemAvailable:" && $3 == "kB" { print int($2 / 1024); exit }' "$meminfo" 2>/dev/null)" || disp=''
if ! [[ $disp =~ ^[0-9]+$ ]]; then
  echo "memoria.sh: no se pudo leer MemAvailable en $meminfo." >&2
  fallo 1
  disp=''
elif [ "$disp" -lt "$alerta" ]; then
  bajas=$((bajas + 1))
  [ -n "$inicio" ] && [ "$bajas" -gt 1 ] || inicio=$ahora
  if [ "$bajas" -ge 2 ] && [ "$episodio" -eq 0 ]; then
    if avisar "Memoria baja en el servidor: $disp MiB disponibles (aviso por debajo de $alerta) desde las $(date -d "@$inicio" '+%H:%M'). Si sigue bajando, el kernel empieza a matar procesos. Mira qué ocupa con \`docker stats --no-stream\` y la sección «Memoria del servidor» de deploy/README.md."; then
      episodio=1
    fi
  fi
else
  bajas=0
  if [ "$disp" -ge "$recuperada" ]; then
    inicio=''
    if [ "$episodio" -eq 1 ]; then
      avisar "La memoria del servidor se recuperó: $disp MiB disponibles ($hora)." && episodio=0
    fi
  fi
fi

# --- contenedores que el kernel mató o que Docker reinició --------------------------------------------------------------
# El evento `oom` también sale cuando el kernel mata un solo proceso y el contenedor sigue (un renderer de Chromium, un
# worker de gunicorn): por eso se mira además del reinicio. Docker guarda pocos eventos y los pierde al reiniciarse:
# como mucho se mira un día atrás, y la primera pasada diez minutos.
limpio() { tr -cd 'A-Za-z0-9_.-' <<< "$1"; }
desde=$((ahora - 600))
if [[ $revisado =~ ^[0-9]+$ ]] && [ "$revisado" -le "$ahora" ]; then
  desde=$(( revisado > ahora - 86400 ? revisado : ahora - 86400 ))
fi
lineas=() nuevos_oom=() avanzar=1
if eventos="$(timeout 30 docker events --since "$desde" --until "$ahora" --filter type=container --filter event=oom \
                --format '{{.Actor.Attributes.name}}' 2>/dev/null)"; then
  declare -A veces=()
  while read -r nombre; do
    nombre="$(limpio "$nombre")"
    [ -n "$nombre" ] && veces[$nombre]=$(( ${veces[$nombre]:-0} + 1 ))
  done <<< "$eventos"
  for nombre in "${!veces[@]}"; do
    if [ $((ahora - ${oom_avisado[$nombre]:-0})) -ge 3600 ]; then
      lineas+=("$nombre (el kernel lo mató por falta de memoria$([ "${veces[$nombre]}" -gt 1 ] && echo ", ${veces[$nombre]} veces"))")
      nuevos_oom+=("$nombre")
    fi
  done
else
  echo "memoria.sh: docker no respondió al pedir los eventos oom." >&2
  fallo 2
  avanzar=0
fi

declare -A actuales=()
anteriores() { for nombre in "${!reinicios[@]}"; do actuales[$nombre]=${reinicios[$nombre]}; done; }
if ids="$(timeout 30 docker ps -q 2>/dev/null)"; then
  if [ -n "$ids" ]; then
    # shellcheck disable=SC2086  # un id por palabra
    if cuentas="$(timeout 30 docker inspect --format '{{.Name}} {{.RestartCount}}' $ids 2>/dev/null)"; then
      while read -r nombre veces_reinicio; do
        nombre="$(limpio "$nombre")"
        [[ -n $nombre && ${veces_reinicio:-} =~ ^[0-9]+$ ]] || continue
        actuales[$nombre]=$veces_reinicio
        antes=${reinicios[$nombre]:-}
        if [ -n "$antes" ] && [ "$veces_reinicio" -gt "$antes" ]; then
          n=$((veces_reinicio - antes))
          lineas+=("$nombre (Docker lo reinició solo $n $([ "$n" -eq 1 ] && echo vez || echo veces))")
        fi
      done <<< "$cuentas"
    else
      echo "memoria.sh: docker no respondió al pedir los reinicios." >&2
      fallo 2
      anteriores
    fi
  fi
else
  echo "memoria.sh: docker no respondió al listar los contenedores." >&2
  fallo 2
  anteriores
fi

if [ "${#lineas[@]}" -gt 0 ]; then
  detalle="$(printf '%s; ' "${lineas[@]}")"
  if avisar "Contenedores con problemas de memoria o caídas ($hora): ${detalle%; }. Memoria disponible: ${disp:-?} MiB. Revisa \`docker compose ps\` y \`docker compose logs --since 30m\` en deploy/, y la sección «Memoria del servidor» de deploy/README.md."; then
    for nombre in "${nuevos_oom[@]}"; do oom_avisado[$nombre]=$ahora; done
  else
    avanzar=0  # la próxima pasada vuelve a ver lo mismo (eventos y cuentas de antes) y vuelve a intentar
    anteriores
  fi
fi
[ "$avanzar" -eq 1 ] && revisado=$ahora

# --- lo que queda sabido -----------------------------------------------------------------------------------------------
{
  echo "bajas $bajas"
  echo "episodio $episodio"
  [ -z "$inicio" ] || echo "inicio $inicio"
  [ -z "$revisado" ] || echo "revisado $revisado"
  for nombre in "${!actuales[@]}"; do echo "reinicios:$nombre ${actuales[$nombre]}"; done
  for nombre in "${!oom_avisado[@]}"; do
    [ $((ahora - ${oom_avisado[$nombre]})) -ge 86400 ] || echo "oom:$nombre ${oom_avisado[$nombre]}"
  done
} > "$archivo.nuevo" && mv -f -- "$archivo.nuevo" "$archivo" || { echo "memoria.sh: no se pudo guardar $archivo." >&2; fallo 1; }

exit "$codigo"
