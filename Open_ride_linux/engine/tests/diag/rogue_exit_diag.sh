#!/usr/bin/env bash
# Diagnostic temporaire : quelles parties de la planche rogue bloquent la sortie de Godot (Forward+, Xvfb) ?
# Usage : GODOT=/chemin/godot tests/diag/rogue_exit_diag.sh   (≈ 5 min au pire, sans vélo)
ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LIMIT="${LIMIT:-30}"
run() {
  local t0 t1 rc
  t0=$(date +%s.%N)
  timeout -k 5 "$LIMIT" xvfb-run -a "$GODOT" --path "$ENGINE_DIR" --rendering-driver vulkan --rendering-method forward_plus \
    --audio-driver Dummy --script res://tests/diag/rogue_exit_diag.gd -- "$@" > /tmp/rogue_diag.log 2>&1
  rc=$?
  t1=$(date +%s.%N)
  printf '%-28s rc=%-3s %5.1f s  %s\n' "${*:-complet}" "$rc" "$(echo "$t1 - $t0" | bc)" \
    "$(grep -E 'quit demandé|ERROR|WARNING' /tmp/rogue_diag.log | tr '\n' ' ' | cut -c1-120)"
}
run
run waitfree
run noeffect
run nolabels
run noglow
run nofog
run nopresets
run nolabels noglow nofog noeffect
# Pile des fils au moment du blocage (gdb parent du processus : pas besoin de sudo).
if command -v gdb >/dev/null && command -v Xvfb >/dev/null; then
  Xvfb :97 -screen 0 1280x720x24 >/dev/null 2>&1 & xpid=$!
  sleep 1
  DISPLAY=:97 timeout -s INT 40 gdb -q -batch -ex run -ex "info threads" -ex "thread apply all bt 12" --args \
    "$GODOT" --path "$ENGINE_DIR" --rendering-driver vulkan --rendering-method forward_plus --audio-driver Dummy \
    --script res://tests/diag/rogue_exit_diag.gd > /tmp/rogue_diag_gdb.log 2>&1
  kill "$xpid" 2>/dev/null
  echo "Pile gdb : /tmp/rogue_diag_gdb.log ($(wc -l < /tmp/rogue_diag_gdb.log) lignes)"
else
  echo "gdb ou Xvfb absent : pas de pile"
fi
