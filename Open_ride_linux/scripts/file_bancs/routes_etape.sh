#!/usr/bin/env bash
# Banc de la pile « routes générées » : une étape sur UN parcours de référence, même script des deux côtés :
#   bash routes_etape.sh COTE ID SORTIE
# Captures en medium aux points tirés du parcours (tour_visuel.py --auto, mêmes points des deux côtés), puis fluidité
# à chaud en roulant (sim_bench, scénario nominal explicite, 5 min à 30 km/h, sonde ; verdict en paire).
set -u
COTE="$1"; ID="$2"; OUT="$3"
BASE="${ROUTES_PILE:-$HOME/mesures-2026-11-01-auto/routes-pile}"
GODOT="${GODOT:-$HOME/Applications/godot/Godot_v4.7.2-stable_linux.x86_64}"
W=$(ls -d "$BASE/mondes-$COTE"/*.world 2>/dev/null | grep -i -- "$ID" | head -n 1)
if [ -z "$W" ]; then echo "ENVIRONNEMENT : monde $ID absent de $BASE/mondes-$COTE"; exit 2; fi
mkdir -p "$OUT"
echo "Côté : $COTE ; parcours : $ID ($W) ; tête : $(git rev-parse --short HEAD)" | tee "$OUT/parcours.txt"
python engine/tests/tour_visuel.py --godot "$GODOT" --world "$W" --auto --quality medium --native --out "$OUT/captures"
rc1=$?
python engine/tests/sim_bench.py --native --scenario nominal --world "$W" --quality medium --probe \
  --speed-kmh 30 --duration 300 --every 30 --out "$OUT/roule"
rc2=$?
echo "captures : code $rc1 ; roulage : code $rc2" | tee -a "$OUT/parcours.txt"
[ $rc1 -eq 2 ] || [ $rc2 -eq 2 ] && exit 2
[ $rc1 -ne 0 ] || [ $rc2 -ne 0 ] && exit 1
exit 0
