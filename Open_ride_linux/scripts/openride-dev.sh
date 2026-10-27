#!/usr/bin/env bash
# Lanceur de développement : core en arrière-plan + moteur Godot au premier plan, un seul terminal.
# Fermer la fenêtre Godot, Ctrl+C ou fermer le terminal arrête le core proprement : consigne
# annulée, contrôle FTMS rendu au trainer, déconnexion BLE, FIT écrit.
# Remplacement en Python, avec supervision (relance de Godot s'il plante) : `openride` (lot K6).
#
#   scripts/openride-dev.sh                              # HomeTrainer + Click, démarrage automatique
#   scripts/openride-dev.sh --trainer mock --input keyboard --autostart
#   scripts/openride-dev.sh --trainer sim --input sim --hr sim --autostart   # Bluetooth simulé
#   scripts/openride-dev.sh --trainer sim --input sim --hr sim --sim-scenario coupures --autostart
#   scripts/openride-dev.sh --trainer ftms --input click --gear 6 --autostart
#   scripts/openride-dev.sh --trainer ftms --input click --autostart --workout sweet_spot_3x10
#   scripts/openride-dev.sh --trainer mock --input keyboard --autostart --route <parcours compilé>
#
# Tous les arguments sont transmis tels quels à « openride-core run » (--route et --workout
# demandent --autostart).
#
# Variables : GODOT (chemin de l'exécutable), OPENRIDE_LOG (journal du core), GODOT_ARGS,
# QUALITY et THEME (préréglage et thème, à la place de ceux de config.toml), OPENRIDE_PERF_PROBE
# (fichier CSV de la sonde de performance du moteur, lot X13).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GODOT="${GODOT:-$HOME/Applications/godot/Godot_v4.3-stable_linux.x86_64}"
LOG="${OPENRIDE_LOG:-$HOME/run_trainer.log}"

CORE_ARGS=("$@")
if [ ${#CORE_ARGS[@]} -eq 0 ]; then
  CORE_ARGS=(--trainer ftms --input click --autostart)
fi
# --config éventuel, transmis aussi à « openride-core release-trainer » en cas d'arrêt forcé.
# --trainer sim : rien à libérer (pas de vrai trainer) en cas d'arrêt forcé.
CONFIG_ARG=""
SIM_TRAINER=0
for ((i = 0; i < ${#CORE_ARGS[@]}; i++)); do
  case "${CORE_ARGS[$i]}" in
    --config=*) CONFIG_ARG="${CORE_ARGS[$i]#--config=}" ;;
    --config) CONFIG_ARG="${CORE_ARGS[$((i + 1))]:-}" ;;
    --trainer=sim) SIM_TRAINER=1 ;;
    --trainer) [ "${CORE_ARGS[$((i + 1))]:-}" = sim ] && SIM_TRAINER=1 ;;
  esac
done
CONFIG_ARG_LIST=()
[ -n "$CONFIG_ARG" ] && CONFIG_ARG_LIST=(--config "$CONFIG_ARG")

if [ ! -x "$GODOT" ]; then
  echo "Godot introuvable : $GODOT (définir GODOT=/chemin/vers/godot)"; exit 1
fi
# shellcheck disable=SC1091
source "$ROOT/core/.venv/bin/activate" || { echo "Environnement Python absent : voir core/.venv"; exit 1; }

openride-core run "${CORE_ARGS[@]}" </dev/null >"$LOG" 2>&1 &
CORE_PID=$!

cleanup() {
  trap - EXIT INT TERM HUP
  kill -INT "$CORE_PID" 2>/dev/null
  # Le core relâche le trainer (pente 0 %, contrôle FTMS rendu) puis se déconnecte : jusqu'à 10 s.
  for _ in $(seq 100); do kill -0 "$CORE_PID" 2>/dev/null || break; sleep 0.1; done
  if kill -0 "$CORE_PID" 2>/dev/null; then
    echo "Le core ne s'arrête pas : arrêt forcé puis libération du trainer."
    kill -KILL "$CORE_PID" 2>/dev/null
    wait "$CORE_PID" 2>/dev/null
    [ "$SIM_TRAINER" = 1 ] || openride-core release-trainer "${CONFIG_ARG_LIST[@]}" >>"$LOG" 2>&1 || true
  fi
  wait "$CORE_PID" 2>/dev/null
  echo
  echo "Core arrêté. Journal complet : $LOG"
  echo "--- Avertissements ---"
  grep -E "WARNING|ERROR" "$LOG" | tail -15 || true
}
trap cleanup EXIT INT TERM HUP   # HUP : terminal fermé

sleep 2
if ! kill -0 "$CORE_PID" 2>/dev/null; then
  echo "Le core s'est arrêté au démarrage :"; tail -20 "$LOG"; exit 1
fi
# Ports IPC et réglages de rendu lus dans config.toml (sections ipc et render), le même fichier que le core.
# QUALITY, THEME et OPENRIDE_DISPLAY, s'ils sont définis, l'emportent sur config.toml (essais graphiques ;
# OPENRIDE_DISPLAY=windowed garde une fenêtre, comme avec le lanceur).
read -r STATE_PORT CMD_PORT CFG_QUALITY CFG_THEME CFG_DISPLAY < <(python3 - "$CONFIG_ARG" <<'PY' 2>/dev/null || echo "5005 5006 low default fullscreen"
import sys
from pathlib import Path
from openride_core.config import load
cfg = load(Path(sys.argv[1]) if sys.argv[1] else None)
print(cfg.ipc.port_state, cfg.ipc.port_commands, cfg.render.quality, cfg.render.theme, cfg.render.display)
PY
)
QUALITY="${QUALITY:-$CFG_QUALITY}"
THEME="${THEME:-$CFG_THEME}"
DISPLAY_MODE="${OPENRIDE_DISPLAY:-$CFG_DISPLAY}"
# shellcheck disable=SC2086
"$GODOT" --path "$ROOT/engine" ${GODOT_ARGS:-} -- --ipc-state-port="${STATE_PORT:-5005}" --ipc-cmd-port="${CMD_PORT:-5006}" --quality="${QUALITY:-low}" --theme="${THEME:-default}" --display="${DISPLAY_MODE:-fullscreen}" ${OPENRIDE_PERF_PROBE:+--perf-probe="$OPENRIDE_PERF_PROBE"}
