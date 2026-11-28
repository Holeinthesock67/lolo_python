#!/usr/bin/env bash
# Banc de la pile « routes générées » (#984, #1026, #1120, #1073, #1119) : sources communes, préparées UNE FOIS par la
# fumée, puis lues à l'identique par main et par la pile.
#   - traces GPX d'Alpe d'Huez et du Ballon d'Alsace (pack Cols célèbres) et du Tour du lac d'Annecy (recette de #943,
#     reprise de main si #943 y est, sinon de sa branche) : route-pack-build, réseau (Overpass, relief) ;
#   - caches OSM et relief dans un dossier FIXE (OPENRIDE_OSM_CACHE, OPENRIDE_DEM_CACHE) : les compilations des deux
#     côtés tournent ensuite en --offline sur exactement les mêmes données.
# Rien n'est écrit dans ~/OpenRide ni dans ~/OpenRide/Cache/monde. Déjà préparé : gardé.
set -u
BASE="${ROUTES_PILE:-$HOME/mesures-2026-11-01-auto/routes-pile}"
export OPENRIDE_OSM_CACHE="$BASE/cache/osm" OPENRIDE_DEM_CACHE="$BASE/cache/dem"
mkdir -p "$BASE/gpx" "$OPENRIDE_OSM_CACHE" "$OPENRIDE_DEM_CACHE"
PY="${PYTHON:-python}"
rc=0
if ls "$BASE"/gpx/*.gpx >/dev/null 2>&1 && [ "$(ls "$BASE"/gpx/*.gpx | wc -l)" -ge 3 ]; then
  echo "traces déjà prêtes : $(ls "$BASE"/gpx | tr '\n' ' ')"; exit 0
fi
# Cols célèbres : Alpe d'Huez et Ballon d'Alsace
"$PY" -m openride_compiler route-pack-build cols_celebres --only alpe_d_huez,ballon_d_alsace --out "$BASE/build/cols" || rc=2
# Tours célèbres (#943) : recette de main si présente, sinon de la branche de #943
REC="$BASE/recettes/tours_celebres"
mkdir -p "$REC"
SRC=compiler/src/openride_compiler/route_packs/tours_celebres
if [ -f "$SRC/tour_du_lac_d_annecy.toml" ]; then
  cp "$SRC/pack.toml" "$SRC/tour_du_lac_d_annecy.toml" "$REC/"
else
  for f in pack.toml tour_du_lac_d_annecy.toml; do
    git show "origin/claude/project-thread-jyojdk:Open_ride_linux/$SRC/$f" > "$REC/$f" || rc=2
  done
fi
"$PY" -m openride_compiler route-pack-build "$REC" --out "$BASE/build/tours" || rc=2
find "$BASE/build" -name '*.gpx' -exec cp {} "$BASE/gpx/" \;
echo "traces : $(ls "$BASE"/gpx 2>/dev/null | tr '\n' ' ')"
[ "$(ls "$BASE"/gpx/*.gpx 2>/dev/null | wc -l)" -ge 3 ] || { echo "ENVIRONNEMENT : moins de 3 traces construites"; exit 2; }
exit $rc
