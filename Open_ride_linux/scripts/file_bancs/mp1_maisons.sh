#!/usr/bin/env bash
# Lot MP1 (PR #1183) : maisons des villages en pente. Lancé par mp1_maisons.toml, dans le worktree de la branche
# (Open_ride_linux/), PYTHONPATH sur ses sources. Ne touche ni au jeu installé, ni aux profils, ni à
# ~/OpenRide/Cache/monde. Caches MNT et OSM habituels lus (parcours déjà compilés : pas de téléchargement).
#   mp1_maisons.sh compiler SORTIE     # avant (règles MP1 coupées) et après, mondes dans ~/mesures-mp1/routes-*
#   mp1_maisons.sh captures SORTIE     # captures medium avant/après aux villages du rapport, comparaison
# « Avant » = même code, règles MP1 coupées : la comparaison isole l'effet du lot (CD1 est dans les deux).
set -uo pipefail
ETAPE=$1; SORTIE=$2
BASE=~/mesures-mp1
MAX_KM=${MP1_MAX_KM:-6}          # captures sur les 6 premiers km (créneau de 75 min pour 3 parcours × 2)
SPEED=${MP1_SPEED_KMH:-60}
LAYERS=route,terrain,biome,buildings,vegetation,poi,water,coast,roads,bridges,tunnels,segments
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$BASE" "$SORTIE"

traces() {
  local f
  for pat in 'alpe*huez*.gpx' 'ballon*alsace*.gpx' '*annecy*.gpx'; do
    f=$(find ~/OpenRide/GPX -maxdepth 3 -iname "$pat" 2>/dev/null | sort | head -1)
    if [ -z "$f" ] && [ "$pat" = '*annecy*.gpx' ]; then   # pas de trace d'Annecy : Bédoin (Ventoux), village au départ
      f=$(find ~/OpenRide/GPX -maxdepth 3 -iname 'mont*ventoux*.gpx' 2>/dev/null | sort | head -1)
    fi
    [ -n "$f" ] && echo "$f"
  done
}

compiler() {
  rm -rf "$BASE/routes-avant" "$BASE/routes-apres"
  local rc=0
  while IFS= read -r t; do
    echo "trace : $t" | tee -a "$SORTIE/resume.txt"
    python3 -c "import sys; from openride_compiler import cli, building_simplify as B; \
B.simplify_for_compile = lambda *a, **k: B.SimplifyReport(); sys.exit(cli.main(sys.argv[1:]))" \
      build "$t" --layers "$LAYERS" --out "$BASE/routes-avant" --force >>"$SORTIE/compile-avant.log" 2>&1 || rc=1
    python3 -m openride_compiler build "$t" --layers "$LAYERS" --out "$BASE/routes-apres" --force \
      >>"$SORTIE/compile-apres.log" 2>&1 || rc=1
  done < <(traces)
  grep -hE "maisons \(MP1\)|ALERTE|refusé" "$SORTIE/compile-apres.log" | tee -a "$SORTIE/resume.txt"
  mkdir -p "$SORTIE/rapports"
  for w in "$BASE"/routes-apres/*.world; do
    cp "$w/buildings/rapport_maisons.json" "$SORTIE/rapports/$(basename "$w" .world).json" 2>/dev/null || true
  done
  return $rc
}

captures() {
  # Mondes refaits si leur rapport date d'avant le plafond des villages (1er tour de correction, 28/11)
  grep -q plafond_socle_village "$BASE"/routes-apres/*.world/buildings/rapport_maisons.json 2>/dev/null || compiler || return 1
  local rc=0
  for w in "$BASE"/routes-apres/*.world; do
    local name; name=$(basename "$w" .world)
    local at; at=$(python3 -I "$HERE/mp1_points.py" "$w" --max 3 --max-km "$MAX_KM" 2>>"$SORTIE/resume.txt")
    if ! [[ "$at" =~ ^[0-9]+(,[0-9]+)*$ ]]; then   # jamais de captures aux temps par défaut (essai j28a)
      echo "$name : points des villages illisibles, parcours sauté" | tee -a "$SORTIE/resume.txt"; rc=1; continue
    fi
    local last=${at##*,}
    local dur; dur=$(python3 -c "print(round(90 + 1.3 * ($last + 200) / ($SPEED / 3.6)))")
    echo "$name : captures à $at m, $dur s par séance" | tee -a "$SORTIE/resume.txt"
    for side in avant apres; do
      python3 engine/tests/sim_bench.py --native --scenario nominal --world "$BASE/routes-$side/$name.world" \
        --quality medium --speed-kmh "$SPEED" --duration "$dur" --size 1920x1080 --at-m "$at" \
        --out "$SORTIE/captures-$side/$name" >>"$SORTIE/bancs.log" 2>&1 || { rc=1; echo "banc $side $name en échec" | tee -a "$SORTIE/resume.txt"; }
    done
    python3 engine/tests/compare_captures.py "$SORTIE/captures-avant/$name" "$SORTIE/captures-apres/$name" \
      --out "$SORTIE/comparaison/$name" --max-diff 100 >>"$SORTIE/bancs.log" 2>&1 || true
  done
  return $rc
}

case "$ETAPE" in
  compiler) compiler ;;
  captures) captures ;;
  *) echo "étape inconnue : $ETAPE" >&2; exit 2 ;;
esac
