#!/usr/bin/env bash
# Construction du pack « Cols célèbres » livré avec le jeu (lot PK1) : scripts/build_pack_base.sh [SORTIE]
#
# À lancer une fois sur le PC (réseau : OpenStreetMap par Overpass, MNT Copernicus), avant le paquet J9.
# 1. construit chaque col (`route-pack-build cols_celebres --only ID`), avec son temps ;
# 2. installe le pack dans un dossier de travail (`route-pack-install`), jamais dans ~/OpenRide ;
# 3. compile chaque col (`build`, couches par défaut, comme `build-all`), avec son temps ;
# 4. range le tout dans SORTIE/packs/cols_celebres/ (gpx/ et routes/) et écrit manifest.json
#    (liste, poids, empreintes SHA-256, temps, crédits ODbL / Copernicus), puis le contrôle.
#
# SORTIE : par défaut Open_ride_linux/paquet/ (hors git, voir .gitignore), lu par le jeu sans variable ;
# sinon le jeu le lit dans OPENRIDE_PAQUET. Variables : OPENRIDE_COMPILER (commande du compilateur,
# défaut openride-compiler), OPENRIDE_PYTHON (python du core, défaut core/.venv/bin/python),
# ONLY="id1,id2" (quelques cols seulement, pour un essai), KEEP_WORK=1 (garde le dossier de travail).
# Un col refusé (Overpass, contrôle longueur / dénivelé à ± 5 %) n'arrête pas les autres : il est listé
# à la fin et le script sort en code 1. Peut être relancé : la sortie est remplacée d'un coup à la fin.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_ROOT="${1:-${PROJECT_DIR}/paquet}"
PACK="cols_celebres"
COMPILER="${OPENRIDE_COMPILER:-openride-compiler}"
PYTHON="${OPENRIDE_PYTHON:-${PROJECT_DIR}/core/.venv/bin/python}"
RECIPES="${PROJECT_DIR}/compiler/src/openride_compiler/route_packs/${PACK}"

say() { echo "build_pack_base : $*"; }
die() { echo "build_pack_base : $*" >&2; exit 2; }

command -v "${COMPILER%% *}" >/dev/null 2>&1 || die "compilateur introuvable (${COMPILER}) : scripts/install.sh"
[[ -x "${PYTHON}" ]] || die "python du core introuvable (${PYTHON})"
[[ -d "${RECIPES}" ]] || die "recettes introuvables : ${RECIPES}"

if [[ -n "${ONLY:-}" ]]; then
    IFS=',' read -r -a IDS <<< "${ONLY}"
else
    IDS=()
    for f in "${RECIPES}"/*.toml; do
        [[ "$(basename "${f}")" == "pack.toml" ]] || IDS+=("$(basename "${f}" .toml)")
    done
fi
[[ ${#IDS[@]} -gt 0 ]] || die "aucun col à construire"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/openride-pack-base.XXXXXX")"
[[ "${KEEP_WORK:-0}" == "1" ]] || trap 'rm -rf "${WORK}"' EXIT
BUILD="${WORK}/build" GPX="${WORK}/GPX" ROUTES="${WORK}/routes" STAGE="${WORK}/stage/${PACK}"
mkdir -p "${BUILD}" "${GPX}" "${ROUTES}"
TIMES="${WORK}/temps.tsv"
: > "${TIMES}"
REFUSED=()
T0=$(date +%s)

say "${#IDS[@]} col(s) à construire, dossier de travail ${WORK}"
for id in "${IDS[@]}"; do
    t=$(date +%s)
    if ${COMPILER} route-pack-build "${PACK}" --only "${id}" --out "${BUILD}" >"${WORK}/${id}.build.log" 2>&1; then
        echo -e "${id}\tconstruction\t$(( $(date +%s) - t ))" >> "${TIMES}"
        say "construit : ${id} ($(( $(date +%s) - t )) s) $(grep -E "^\s+${id} :" "${WORK}/${id}.build.log" | sed 's/^ *//' || true)"
    else
        REFUSED+=("${id}")
        say "REFUSÉ : ${id} : $(grep -E 'refusé|erreur' "${WORK}/${id}.build.log" | tail -n 1 || true)"
    fi
done

BUILT_DIR="${BUILD}/${PACK}"
ls "${BUILT_DIR}"/*.gpx >/dev/null 2>&1 || die "aucun col construit"
${COMPILER} route-pack-install "${BUILT_DIR}" --gpx-dir "${GPX}" --force >/dev/null
PACK_FOLDER="$(find "${GPX}" -mindepth 1 -maxdepth 1 -type d ! -name '.*' | head -n 1)"
[[ -n "${PACK_FOLDER}" ]] || die "pack non installé dans ${GPX}"

for gpx in "${PACK_FOLDER}"/*.gpx; do
    id="$(basename "${gpx}" .gpx)"
    t=$(date +%s)
    if ${COMPILER} build "${gpx}" --out "${ROUTES}" --force >"${WORK}/${id}.compile.log" 2>&1; then
        echo -e "${id}\tcompilation\t$(( $(date +%s) - t ))" >> "${TIMES}"
        say "compilé : ${id} ($(( $(date +%s) - t )) s, $(du -sh "${ROUTES}/${id}.world" | cut -f1))"
    else
        REFUSED+=("${id} (compilation)")
        rm -f "${gpx}" "${PACK_FOLDER}/${id}.toml"
        rm -rf "${ROUTES}/${id}.world"
        say "ÉCHEC de compilation : ${id} : $(tail -n 1 "${WORK}/${id}.compile.log")"
    fi
done
ls "${PACK_FOLDER}"/*.gpx >/dev/null 2>&1 || die "aucun col compilé"

# Rangement : gpx/<dossier du pack>/ et routes/<id>.world/ du pack seulement.
mkdir -p "${STAGE}/gpx" "${STAGE}/routes"
cp -a "${PACK_FOLDER}" "${STAGE}/gpx/"
for gpx in "${PACK_FOLDER}"/*.gpx; do
    cp -a "${ROUTES}/$(basename "${gpx}" .gpx).world" "${STAGE}/routes/"
done
"${PYTHON}" - "${TIMES}" "${WORK}/temps.json" <<'EOF'
import json, sys
from openride_core.pack_bundle import route_id
tot = {}
for line in open(sys.argv[1], encoding="utf-8"):
    cid, _step, s = line.rstrip("\n").split("\t")
    rid = route_id(cid + ".gpx")   # recette alpe_d_huez et trace alpe-d-huez : même col
    tot[rid] = tot.get(rid, 0) + int(s)
json.dump(tot, open(sys.argv[2], "w", encoding="utf-8"))
EOF
"${PYTHON}" -m openride_core.pack_bundle manifest "${STAGE}" --times "${WORK}/temps.json"
"${PYTHON}" -m openride_core.pack_bundle verify "${STAGE}" >/dev/null

# Remplacement d'un coup : l'ancien pack n'est effacé qu'une fois le nouveau prêt.
mkdir -p "${OUT_ROOT}/packs"
rm -rf "${OUT_ROOT}/packs/.${PACK}.old"
[[ -d "${OUT_ROOT}/packs/${PACK}" ]] && mv "${OUT_ROOT}/packs/${PACK}" "${OUT_ROOT}/packs/.${PACK}.old"
mv "${STAGE}" "${OUT_ROOT}/packs/${PACK}"
rm -rf "${OUT_ROOT}/packs/.${PACK}.old"

"${PYTHON}" -m openride_core.pack_bundle info "${OUT_ROOT}/packs/${PACK}"
say "durée totale : $(( $(date +%s) - T0 )) s ; pack dans ${OUT_ROOT}/packs/${PACK}"
if [[ ${#REFUSED[@]} -gt 0 ]]; then
    say "${#REFUSED[@]} col(s) refusé(s) : ${REFUSED[*]} (journaux : relancer avec KEEP_WORK=1)"
    exit 1
fi
