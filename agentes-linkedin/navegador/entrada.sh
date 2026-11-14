#!/bin/sh
# Starts the virtual screen the browser draws on and then the command (servir, login, canario…). With NAVEGADOR_VNC=1
# (only for a hand login) it also shows that screen through x11vnc + noVNC on port 6080, with a one-time password
# printed once; compose publishes that port on the server's 127.0.0.1 only, reached through an SSH tunnel.
set -eu

if [ -z "${DISPLAY:-}" ]; then
  export DISPLAY=:99
  Xvfb :99 -screen 0 1366x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -e /tmp/.X11-unix/X99 ] && break
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
