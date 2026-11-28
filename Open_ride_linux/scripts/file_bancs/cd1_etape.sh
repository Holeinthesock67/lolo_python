#!/usr/bin/env bash
# Une étape du banc CD1 (#1179) sur UN parcours de référence, jouée telle quelle sur la branche et sur main :
#   bash cd1_etape.sh ID SORTIE
# ID : alpe-d-huez, tour-du-lac-d-annecy, demo-biomes-paysages, ballon-d-alsace.
# 1. Captures en medium aux points tirés du parcours (tour_visuel.py --auto : départ, arrivée, plat, montées à 5 et
#    10 %, village le plus dense, forêt et eau les plus proches, frontières de biome) : mêmes points sur main et sur la
#    branche, planche.html à valider par le propriétaire.
# 2. Fluidité à chaud en roulant : sim_bench, scénario nominal explicite, 7 min à 30 km/h en medium, sonde.
# Monde absent (Annecy avant la fusion de #943) : code 2, ENVIRONNEMENT pour cette étape seule.
set -u
ID="$1"
OUT="$2"
MONDES="${CD1_MONDES:-$HOME/mesures-2026-11-01-auto/mondes-cd1}"
GODOT="${GODOT:-$HOME/Applications/godot/Godot_v4.7.2-stable_linux.x86_64}"
W="$MONDES/$ID.world"
if [ -z "$ID" ] || [ ! -d "$W" ]; then
  echo "ENVIRONNEMENT : monde absent ($W) ; lancer d'abord la fumée (cd1_mondes.sh)"
  exit 2
fi
mkdir -p "$OUT"
echo "Parcours : $ID ($W) ; tête : $(git rev-parse --short HEAD)" | tee "$OUT/parcours.txt"
python engine/tests/tour_visuel.py --godot "$GODOT" --world "$W" --auto --quality medium --native --out "$OUT/captures"
rc1=$?
python engine/tests/sim_bench.py --native --scenario nominal --world "$W" --quality medium --probe \
  --speed-kmh 30 --duration 420 --every 30 --out "$OUT/roule"
rc2=$?
echo "captures : code $rc1 ; roulage : code $rc2" | tee -a "$OUT/parcours.txt"
[ $rc1 -eq 2 ] || [ $rc2 -eq 2 ] && exit 2
[ $rc1 -ne 0 ] || [ $rc2 -ne 0 ] && exit 1
exit 0
