#!/usr/bin/env bash
# Banc de la pile « routes générées » : compile les 4 parcours de référence avec le compilateur DU CÔTÉ JOUÉ
# (PYTHONPATH du worktree : main ou pile), hors ligne, sur les traces et caches fixes de routes_sources.sh :
#   bash routes_mondes.sh COTE        (COTE : main ou pile ; mondes dans $ROUTES_PILE/mondes-COTE)
# Les couches sont données en toutes lettres et identiques des deux côtés (celles du pack Tours célèbres) : sans elles,
# les couches par défaut (route, terrain, biome, segments) ne montreraient ni l'eau, ni la végétation, ni les maisons
# que #1120 et #1119 changent. DB1 (« Tour des nouveaux paysages ») : générateur des démos, sans réseau.
set -u
COTE="$1"
BASE="${ROUTES_PILE:-$HOME/mesures-2026-11-01-auto/routes-pile}"
export OPENRIDE_OSM_CACHE="$BASE/cache/osm" OPENRIDE_DEM_CACHE="$BASE/cache/dem"
OUT="$BASE/mondes-$COTE"
PY="${PYTHON:-python}"
LAYERS="route,terrain,biome,segments,water,buildings,vegetation,roads,bridges"
rm -rf "$OUT"; mkdir -p "$OUT"
echo "côté $COTE ; tête $(git rev-parse --short HEAD) ; compilateur : $("$PY" -c 'import openride_compiler,sys;print(openride_compiler.__file__)')"
ls "$BASE"/gpx/*.gpx >/dev/null 2>&1 || { echo "ENVIRONNEMENT : traces absentes, lancer la fumée"; exit 2; }
rc=0
for g in "$BASE"/gpx/*.gpx; do
  t=$(date +%s)
  if "$PY" -m openride_compiler build "$g" --out "$OUT" --force --offline --layers "$LAYERS" > "$OUT/$(basename "$g" .gpx).log" 2>&1; then
    echo "compilé : $(basename "$g" .gpx) ($(( $(date +%s) - t )) s)"
  else
    echo "ÉCHEC de compilation : $(basename "$g" .gpx) : $(tail -n 1 "$OUT/$(basename "$g" .gpx).log")"; rc=1
  fi
done
"$PY" -m openride_compiler.demo_biomes --out "$OUT" --paysages > "$OUT/demo-biomes-paysages.log" 2>&1 || { echo "ÉCHEC : démo DB1"; rc=1; }
for w in "$OUT"/*.world; do "$PY" -m openride_compiler verify "$w" > /dev/null 2>&1 || { echo "verify en échec : $w"; rc=1; }; done
ls -d "$OUT"/*.world
exit $rc
