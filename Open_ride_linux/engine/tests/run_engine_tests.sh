#!/usr/bin/env bash
# Tests de l'engine sans écran (lot D6) : vecteurs de route, puis scénarios IPC face au faux core.
#
#   GODOT=/chemin/vers/Godot_v4.3-stable_linux.x86_64 engine/tests/run_engine_tests.sh
#
# Variables : GODOT (exécutable Godot 4.3), STATE_PORT / CMD_PORT (ports de test, défaut 15005 / 15006),
# SCENARIOS (ex. « 1,2,3 »), ENGINE_LOG (journal de l'engine, défaut : fichier temporaire).
# Code de sortie : 0 si tout passe.
set -u
ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GODOT="${GODOT:-$HOME/Applications/godot/Godot_v4.3-stable_linux.x86_64}"
STATE_PORT="${STATE_PORT:-15005}"
CMD_PORT="${CMD_PORT:-15006}"
ENGINE_LOG="${ENGINE_LOG:-$(mktemp -t openride-engine-test.XXXXXX.log)}"
ROUTES_DIR="$(mktemp -d -t openride-routes.XXXXXX)"   # vide : repli sur res://demo/demo.world

if [ ! -x "$GODOT" ]; then
  echo "Godot introuvable : $GODOT (définir GODOT=/chemin/vers/godot)"; exit 2
fi

status=0

echo "== Vecteurs de route =="
if ! "$GODOT" --headless --path "$ENGINE_DIR" --script res://tests/test_route_vectors.gd 2>&1 | grep -v "^Godot Engine"; then
  :
fi
if [ "${PIPESTATUS[0]}" -ne 0 ]; then status=1; fi

echo "== ERG (lot I6) =="
python3 "$ENGINE_DIR/tests/fake_core.py" --erg-workout --state-port "$STATE_PORT" --cmd-port "$CMD_PORT" &
ERG_FAKE_PID=$!
sleep 0.2
ERG_OUT="$("$GODOT" --headless --path "$ENGINE_DIR" --script res://tests/test_erg_view_model.gd -- --ipc-state-port="$STATE_PORT" --ipc-cmd-port="$CMD_PORT" 2>&1)"
erg_rc=$?
wait "$ERG_FAKE_PID"
erg_fake_rc=$?
echo "$ERG_OUT" | grep -v "^Godot Engine" || true
if [ "$erg_rc" -ne 0 ] || [ "$erg_fake_rc" -ne 0 ]; then status=1; fi
erg_issues="$(echo "$ERG_OUT" | grep -E "SCRIPT ERROR|ERROR:|WARNING:" \
  | grep -v -E "ObjectDB instances leaked|resources still in use at exit|[Mm]esh.*(null|nul)" || true)"
if [ -n "$erg_issues" ]; then echo "$erg_issues"; status=1; fi

echo "== Scénarios IPC (journal de l'engine : $ENGINE_LOG) =="
: >"$ENGINE_LOG"
FAKE_ARGS=(--state-port "$STATE_PORT" --cmd-port "$CMD_PORT" --engine-log "$ENGINE_LOG")
if [ -n "${SCENARIOS:-}" ]; then FAKE_ARGS+=(--scenarios "$SCENARIOS"); fi
python3 "$ENGINE_DIR/tests/fake_core.py" "${FAKE_ARGS[@]}" &
FAKE_PID=$!
sleep 0.3
"$GODOT" --headless --path "$ENGINE_DIR" -- --ipc-state-port="$STATE_PORT" --ipc-cmd-port="$CMD_PORT" \
  --routes-dir="$ROUTES_DIR" --test-mode >"$ENGINE_LOG" 2>&1 &
GODOT_PID=$!

wait "$FAKE_PID"
fake_status=$?
if ! kill -0 "$GODOT_PID" 2>/dev/null; then
  echo "L'engine s'est arrêté pendant les scénarios :"; tail -20 "$ENGINE_LOG"; fake_status=1
fi
kill -TERM "$GODOT_PID" 2>/dev/null
for _ in $(seq 50); do kill -0 "$GODOT_PID" 2>/dev/null || break; sleep 0.1; done
kill -KILL "$GODOT_PID" 2>/dev/null
wait "$GODOT_PID" 2>/dev/null
rmdir "$ROUTES_DIR" 2>/dev/null
if [ "$fake_status" -ne 0 ]; then status=1; fi

echo "== Erreurs et avertissements de Godot =="
# Tolérés : avertissements connus du mode sans écran (objets non libérés à la sortie, mesh nul).
issues="$(grep -E "SCRIPT ERROR|ERROR:|WARNING:" "$ENGINE_LOG" \
  | grep -v -E "ObjectDB instances leaked|resources still in use at exit|[Mm]esh.*(null|nul)" || true)"
if [ -n "$issues" ]; then
  echo "$issues"; status=1
else
  echo "aucun"
fi

if [ "$status" -eq 0 ]; then echo "RÉSULTAT : tous les tests de l'engine passent"; else echo "RÉSULTAT : ÉCHEC"; fi
exit "$status"
