#!/usr/bin/env bash
# Tests graphiques automatiques de la scène principale (visual_check.py) : trois résolutions et
# préréglages de qualité, captures analysées, comparaison aux images de référence et rapport HTML.
#
#   engine/tests/run_visual_tests.sh [--open] [--native] [--update-golden] [--configs 1280x720:low,…]
#
# Les images de référence sont dans ~/.cache/openride/visual_golden (VISUAL_GOLDEN pour un autre
# dossier) : au premier lancement, elles sont créées à partir des captures ; ensuite, chaque lancement
# les compare. Après un changement graphique voulu, relancer avec --update-golden.
# Le rapport (rapport.html et captures) va dans ~/OpenRide/visual_tests/<date> (VISUAL_OUT pour un autre
# dossier) ; --open l'ouvre dans le navigateur à la fin.
# Variables : GODOT (exécutable Godot 4.7), VISUAL_GOLDEN, VISUAL_OUT.
# Code de sortie : 0 si tout passe, 1 si une vérification échoue, 2 si Godot ou xvfb-run manque.
set -u
ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GODOT="${GODOT:-$HOME/Applications/godot/Godot_v4.7.2-stable_linux.x86_64}"
GOLDEN="${VISUAL_GOLDEN:-$HOME/.cache/openride/visual_golden}"
OUT="${VISUAL_OUT:-$HOME/OpenRide/visual_tests/$(date +%Y-%m-%d_%H%M%S)}"

open_report=0
args=()
update=0
for arg in "$@"; do
  case "$arg" in
    --open) open_report=1 ;;
    --update-golden) update=1; args+=("$arg") ;;
    *) args+=("$arg") ;;
  esac
done
# Sans références, le premier lancement les crée.
if [ "$update" -eq 0 ] && [ -z "$(ls -A "$GOLDEN" 2>/dev/null)" ]; then
  echo "Aucune image de référence dans $GOLDEN : elles sont créées par ce lancement."
  args+=(--update-golden)
fi

# --lisibilite : hauteur des chiffres et contraste des textes du HUD (lot X22).
python3 "$ENGINE_DIR/tests/visual_check.py" --godot "$GODOT" --out "$OUT" --golden "$GOLDEN" --lisibilite "${args[@]}"
rc=$?
if [ "$open_report" -eq 1 ] && [ -f "$OUT/rapport.html" ] && command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$OUT/rapport.html" >/dev/null 2>&1 &
fi
exit "$rc"
