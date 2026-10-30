#!/usr/bin/env bash
# Essai de bout en bout sans écran (lot J8) : vrai core (trainer simulé) et vrai engine Godot 4.7.
#
#   GODOT=/chemin/vers/Godot_v4.7.2-stable_linux.x86_64 engine/tests/run_e2e.sh [--keep]
#
# Le core et l'engine tournent avec un HOME temporaire et des ports UDP libres : rien n'est écrit
# dans le vrai dossier personnel. Le détail des vérifications est dans e2e_check.py.
# Code de sortie : 0 si tout passe, 1 si une vérification échoue, 2 si Godot est introuvable.
set -u
ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GODOT="${GODOT:-$HOME/Applications/godot/Godot_v4.7.2-stable_linux.x86_64}"
PYTHON="${PYTHON:-python3}"

echo "== Bout en bout : vrai core et vrai engine =="
exec "$PYTHON" "$ENGINE_DIR/tests/e2e_check.py" --godot "$GODOT" "$@"
