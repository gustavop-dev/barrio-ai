#!/bin/sh
# Starts the virtual screen the browser draws on and then the command (servir, login, canario…). With NAVEGADOR_VNC=1
# (only for a hand login) it also shows that screen through x11vnc + noVNC on port 6080, with a one-time password
# printed once; compose publishes that port on the server's 127.0.0.1 only, reached through an SSH tunnel.
set -eu

if [ -z "${DISPLAY:-}" ]; then
  pantalla="${NAVEGADOR_PANTALLA:-:99}"
  n="${pantalla#:}"
  export DISPLAY="$pantalla"
  # A restarted container keeps its /tmp: the previous run's lock would make Xvfb refuse to start, and its socket file
  # alone looks like a live screen. Nothing else runs yet in this container, so both are stale.
  rm -f "/tmp/.X$n-lock" "/tmp/.X11-unix/X$n"
  Xvfb "$pantalla" -screen 0 1366x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
  xvfb=$!
  # Ready when it accepts a connection (navegador.pagina.display_ready), not when a file appears. If it does not, the
  # container ends with an error so Docker starts it again, instead of serving without a screen.
  intentos=0
  until python -c 'from navegador.pagina import display_ready; raise SystemExit(0 if display_ready() else 1)'; do
    intentos=$((intentos + 1))
    if ! kill -0 "$xvfb" 2>/dev/null || [ "$intentos" -ge 20 ]; then
      echo "La pantalla virtual ($pantalla) no arrancó; el contenedor termina para que Docker lo vuelva a arrancar." >&2
      tail -n 5 /tmp/xvfb.log >&2 || true
      exit 1
    fi
    sleep 0.5
  done
fi

if [ "${NAVEGADOR_VNC:-0}" = "1" ]; then
  # VNC passwords are 8 characters. The file is read and deleted by x11vnc (rm:), so the password is never an argument.
  clave=$(python -c 'import secrets; print(secrets.token_urlsafe(6))')
  archivo=$(mktemp)
  printf '%s\n' "$clave" >"$archivo"
  x11vnc -display "$DISPLAY" -localhost -rfbport 5900 -forever -shared -passwdfile "rm:$archivo" >/tmp/x11vnc.log 2>&1 &
  websockify --web /usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 >/tmp/novnc.log 2>&1 &
  echo "Pantalla del navegador: http://127.0.0.1:6080/vnc.html (por el túnel SSH). Clave de esta sesión: $clave"
fi

exec "$@"
