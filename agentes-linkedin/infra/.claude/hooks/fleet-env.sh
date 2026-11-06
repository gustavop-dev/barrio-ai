#!/usr/bin/env bash
# SessionStart: exporta las variables del fleet a los comandos Bash de la sesión.
# Lee ~/.config/ai-presets/fleet.env si existe; si no, usa los valores por defecto.
set -u
CONFIG="${AI_PRESETS_CONFIG:-$HOME/.config/ai-presets/fleet.env}"
# shellcheck disable=SC1090
[ -f "$CONFIG" ] && . "$CONFIG"

FLEET_PROJECTS_ROOT="${FLEET_PROJECTS_ROOT:-$HOME/webapps}"
OPS_ROOT="${OPS_ROOT:-$FLEET_PROJECTS_ROOT/vps-ops-toolkit}"
FLEET_SSH_USER="${FLEET_SSH_USER:-ryzepeck}"
FLEET_VPS_ROOT="${FLEET_VPS_ROOT:-/home/$FLEET_SSH_USER/webapps}"
FLEET_HOST_ALIASES="${FLEET_HOST_ALIASES:-srv571894=vps-projectapp-staging,srv1681495=vps-projectapp-prod,srv614758=vps-gym}"

[ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0
for v in FLEET_PROJECTS_ROOT OPS_ROOT FLEET_SSH_USER FLEET_VPS_ROOT FLEET_HOST_ALIASES; do
  printf 'export %s=%q\n' "$v" "${!v}"
done >> "$CLAUDE_ENV_FILE"
