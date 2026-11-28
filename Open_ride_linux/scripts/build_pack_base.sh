#!/usr/bin/env bash
# Construction des packs de parcours livrés avec le jeu (lots PK1 et AN1) : scripts/build_pack_base.sh [SORTIE]
#
# À lancer une fois sur le PC (réseau : OpenStreetMap par Overpass, MNT Copernicus), avant le paquet J9.
# Pour chaque pack (par défaut tous ceux de compiler/src/openride_compiler/route_packs/ : cols_celebres,
# tours_celebres) :
# 1. construit chaque parcours (`route-pack-build PACK --only ID`), avec son temps ;
# 2. installe le pack dans un dossier de travail (`route-pack-install`), jamais dans ~/OpenRide ;
# 3. compile chaque parcours (`build`) avec les couches du pack (`layers` de son pack.toml, sinon celles par
#    défaut, comme `build-all`), avec son temps ;
# 4. range le tout dans SORTIE/packs/PACK/ (gpx/ et routes/) et écrit manifest.json
#    (liste, poids, empreintes SHA-256, temps, crédits ODbL / Copernicus), puis le contrôle.
#
# SORTIE : par défaut Open_ride_linux/paquet/ (hors git, voir .gitignore), lu par le jeu sans variable ;
# sinon le jeu le lit dans OPENRIDE_PAQUET. Variables : OPENRIDE_COMPILER (commande du compilateur,
# défaut openride-compiler), OPENRIDE_PYTHON (python du core, défaut core/.venv/bin/python),
# PACKS="cols_celebres tours_celebres" (packs construits), ONLY="id1,id2" (quelques parcours seulement, pour un
# essai : un pack sans aucun de ces parcours est sauté), KEEP_WORK=1 (garde le dossier de travail).
# Un parcours refusé (Overpass, contrôle longueur / dénivelé à ± 5 %) n'arrête pas les autres : il est listé
# à la fin et le script sort en code 1. Peut être relancé : chaque pack est remplacé d'un coup à la fin.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_ROOT="${1:-${PROJECT_DIR}/paquet}"
COMPILER="${OPENRIDE_COMPILER:-openride-compiler}"
PYTHON="${OPENRIDE_PYTHON:-${PROJECT_DIR}/core/.venv/bin/python}"
PACKS_DIR="${PROJECT_DIR}/compiler/src/openride_compiler/route_packs"

say() { echo "build_pack_base : $*"; }
die() { echo "build_pack_base : $*" >&2; exit 2; }

command -v "${COMPILER%% *}" >/dev/null 2>&1 || die "compilateur introuvable (${COMPILER}) : scripts/install.sh"
[[ -x "${PYTHON}" ]] || die "python du core introuvable (${PYTHON})"

if [[ -n "${PACKS:-}" ]]; then
    read -r -a PACK_LIST <<< "${PACKS}"
else
    PACK_LIST=()
    for d in "${PACKS_DIR}"/*/; do
        [[ -f "${d}pack.toml" ]] && PACK_LIST+=("$(basename "${d}")")
    done
fi
[[ ${#PACK_LIST[@]} -gt 0 ]] || die "aucun pack à construire dans ${PACKS_DIR}"

WORK_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/openride-pack-base.XXXXXX")"
[[ "${KEEP_WORK:-0}" == "1" ]] || trap 'rm -rf "${WORK_ROOT}"' EXIT
REFUSED=()
BUILT=0
T0=$(date +%s)

# build_one PACK : construit, compile et range un pack ; ajoute ses refus à REFUSED.
build_one() {
    local PACK="$1"
    local RECIPES="${PACKS_DIR}/${PACK}"
    [[ -f "${RECIPES}/pack.toml" ]] || die "recettes introuvables : ${RECIPES}"
    local IDS=() id f t
    for f in "${RECIPES}"/*.toml; do
        id="$(basename "${f}" .toml)"
        [[ "${id}" == "pack" ]] && continue
        if [[ -z "${ONLY:-}" || ",${ONLY}," == *",${id},"* ]]; then
            IDS+=("${id}")
        fi
    done
    if [[ ${#IDS[@]} -eq 0 ]]; then
        say "${PACK} : aucun parcours demandé, pack sauté"
        return 0
    fi

    local WORK="${WORK_ROOT}/${PACK}"
    local BUILD="${WORK}/build" GPX="${WORK}/GPX" ROUTES="${WORK}/routes" STAGE="${WORK}/stage/${PACK}"
    mkdir -p "${BUILD}" "${GPX}" "${ROUTES}"
    local TIMES="${WORK}/temps.tsv"
    : > "${TIMES}"
    local before=${#REFUSED[@]}

    say "${PACK} : ${#IDS[@]} parcours à construire, dossier de travail ${WORK}"
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

    # route-pack-build écrit dans BUILD/<nom normalisé du pack> (cols-celebres) : on prend le seul dossier écrit.
    local BUILT_DIR
    BUILT_DIR="$(find "${BUILD}" -mindepth 1 -maxdepth 1 -type d ! -name '.*' | head -n 1)"
    if [[ -z "${BUILT_DIR}" ]] || ! ls "${BUILT_DIR}"/*.gpx >/dev/null 2>&1; then
        say "${PACK} : aucun parcours construit, pack non rangé"
        return 0
    fi
    ${COMPILER} route-pack-install "${BUILT_DIR}" --gpx-dir "${GPX}" --force >/dev/null
    local PACK_FOLDER
    PACK_FOLDER="$(find "${GPX}" -mindepth 1 -maxdepth 1 -type d ! -name '.*' | head -n 1)"
    [[ -n "${PACK_FOLDER}" ]] || die "pack ${PACK} non installé dans ${GPX}"

    local gpx
    for gpx in "${PACK_FOLDER}"/*.gpx; do
        id="$(basename "${gpx}" .gpx)"
        t=$(date +%s)
        # Sans --layers : `build` prend les couches du pack.toml posé à côté de la trace (eau et maisons d'un tour de lac).
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
    if ! ls "${PACK_FOLDER}"/*.gpx >/dev/null 2>&1; then
        say "${PACK} : aucun parcours compilé, pack non rangé"
        return 0
    fi

    # Rangement : gpx/<dossier du pack>/ et routes/<id>.world/ du pack seulement.
    mkdir -p "${STAGE}/gpx" "${STAGE}/routes"
    cp -a "${PACK_FOLDER}" "${STAGE}/gpx/"
    for gpx in "${PACK_FOLDER}"/*.gpx; do
        cp -a "${ROUTES}/$(basename "${gpx}" .gpx).world" "${STAGE}/routes/"
    done
    "${PYTHON}" - "${TIMES}" "${WORK}/temps.json" <<'EOF_PY'
import json, sys
from openride_core.pack_bundle import route_id
tot = {}
for line in open(sys.argv[1], encoding="utf-8"):
    cid, _step, s = line.rstrip("\n").split("\t")
    rid = route_id(cid + ".gpx")   # recette alpe_d_huez et trace alpe-d-huez : même parcours
    tot[rid] = tot.get(rid, 0) + int(s)
json.dump(tot, open(sys.argv[2], "w", encoding="utf-8"))
EOF_PY
    "${PYTHON}" -m openride_core.pack_bundle manifest "${STAGE}" --times "${WORK}/temps.json"
    "${PYTHON}" -m openride_core.pack_bundle verify "${STAGE}" >/dev/null

    # Remplacement d'un coup : l'ancien pack n'est effacé qu'une fois le nouveau prêt.
    mkdir -p "${OUT_ROOT}/packs"
    rm -rf "${OUT_ROOT}/packs/.${PACK}.old"
    [[ -d "${OUT_ROOT}/packs/${PACK}" ]] && mv "${OUT_ROOT}/packs/${PACK}" "${OUT_ROOT}/packs/.${PACK}.old"
    mv "${STAGE}" "${OUT_ROOT}/packs/${PACK}"
    rm -rf "${OUT_ROOT}/packs/.${PACK}.old"
    "${PYTHON}" -m openride_core.pack_bundle info "${OUT_ROOT}/packs/${PACK}"
    BUILT=$(( BUILT + 1 ))
    say "${PACK} : rangé dans ${OUT_ROOT}/packs/${PACK} ($(( ${#REFUSED[@]} - before )) refus)"
}

for p in "${PACK_LIST[@]}"; do
    build_one "${p}"
done

say "durée totale : $(( $(date +%s) - T0 )) s ; ${BUILT} pack(s) dans ${OUT_ROOT}/packs"
[[ ${BUILT} -gt 0 ]] || die "aucun pack construit"
if [[ ${#REFUSED[@]} -gt 0 ]]; then
    say "${#REFUSED[@]} parcours refusé(s) : ${REFUSED[*]} (journaux : relancer avec KEEP_WORK=1)"
    exit 1
fi
