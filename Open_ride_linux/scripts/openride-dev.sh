#!/usr/bin/env bash
# Lanceur de développement : core en arrière-plan + moteur Godot au premier plan, un seul terminal.
# Fermer la fenêtre Godot (ou Ctrl+C) arrête le core proprement (résistance relâchée, FIT écrit).
#
#   scripts/openride-dev.sh                              # Victory + Click, démarrage automatique
#   scripts/openride-dev.sh --trainer mock --input keyboard --autostart
#   scripts/openride-dev.sh --trainer ftms --input click --gear 6 --autostart
#
# Variables : GODOT (chemin de l'exécutable), OPENRIDE_LOG (journal du core), GODOT_ARGS.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GODOT="${GODOT:-$HOME/Applications/godot/Godot_v4.3-stable_linux.x86_64}"
LOG="${OPENRIDE_LOG:-$HOME/run_victory.log}"

CORE_ARGS=("$@")
if [ ${#CORE_ARGS[@]} -eq 0 ]; then
  CORE_ARGS=(--trainer ftms --input click --autostart)
fi

if [ ! -x "$GODOT" ]; then
  echo "Godot introuvable : $GODOT (définir GODOT=/chemin/vers/godot)"; exit 1
fi
# shellcheck disable=SC1091
source "$ROOT/core/.venv/bin/activate" || { echo "Environnement Python absent : voir core/.venv"; exit 1; }

openride-core run "${CORE_ARGS[@]}" </dev/null >"$LOG" 2>&1 &
CORE_PID=$!

cleanup() {
  trap - EXIT INT TERM
  kill -INT "$CORE_PID" 2>/dev/null
  wait "$CORE_PID" 2>/dev/null
  echo
  echo "Core arrêté. Journal complet : $LOG"
  echo "--- Avertissements ---"
  grep -E "WARNING|ERROR" "$LOG" | tail -15 || true
}
trap cleanup EXIT INT TERM

sleep 2
if ! kill -0 "$CORE_PID" 2>/dev/null; then
  echo "Le core s'est arrêté au démarrage :"; tail -20 "$LOG"; exit 1
fi
# shellcheck disable=SC2086
"$GODOT" --path "$ROOT/engine" ${GODOT_ARGS:-}
