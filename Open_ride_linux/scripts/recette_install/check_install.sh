#!/usr/bin/env bash
# Vérification d'une installation neuve d'OpenRide (lot X29, recette 1.0 lignes 1 et 2).
#
# À lancer dans un compte vierge : un conteneur Ubuntu 24.04 neuf ou un HOME temporaire
# (scripts/recette_install.py s'en charge). Enchaîne, avec les vrais scripts du dépôt :
#   1. clone du dépôt (REPO_URL) dans ~/Games/lolo_python, comme un nouvel utilisateur ;
#   2. scripts/install.sh, sans terminal, avec GODOT ;
#   3. commandes, configuration, raccourcis de bureau et icône ;
#   4. premier démarrage : compilation des parcours (openride --compile-only), core 8 s sur le
#      trainer simulé (« Core démarré »), libération du trainer ;
#   5. données de l'utilisateur (parcours, séance, configuration modifiée), nouveau commit sur le
#      dépôt d'origine, scripts/update.sh, puis install.sh relancé : le code avance, les données
#      restent identiques octet pour octet.
# Une ligne « [OK] … » ou « [ÉCHEC] … » par vérification, puis « RÉSULTAT : … ».
# Variables : REPO_URL (dépôt à cloner, requis, inscriptible pour l'étape 5), GODOT (Godot 4.7, requis),
# OPENRIDE_NO_PIP=1 avec OPENRIDE_PYTHON et OPENRIDE_BIN_SRC (essai rapide sans pip, comme les tests).
# Code de sortie : 0 si tout passe, 1 sinon.

set -uo pipefail

: "${REPO_URL:?REPO_URL requis}"
: "${GODOT:?GODOT requis}"
DEST="${HOME}/Games/lolo_python"
PROJECT="${DEST}/Open_ride_linux"
failures=0
checks=0

check() {   # check <0 si réussi> <libellé> [mesure]
    checks=$((checks + 1))
    if [[ "$1" -eq 0 ]]; then
        echo "[OK] $2${3:+ : $3}"
    else
        failures=$((failures + 1))
        echo "[ÉCHEC] $2${3:+ : $3}"
    fi
}

step() { echo; echo "== $*"; }

fingerprint() {   # empreinte des données de l'utilisateur (hors journaux et caches)
    (cd "${HOME}/OpenRide" && find . -type f ! -path './Logs/*' ! -name '*.log' ! -name '.update.lock' -print0 | sort -z \
        | xargs -0 sha256sum)
}

step "1. Clone du dépôt"
git clone --quiet "${REPO_URL}" "${DEST}" 2>&1
check $? "clone du dépôt" "${DEST}"
git -C "${DEST}" config user.email "recette@example.invalid"
git -C "${DEST}" config user.name "Recette"

step "2. Installation (scripts/install.sh)"
start=$(date +%s)
bash "${PROJECT}/scripts/install.sh" </dev/null > "${HOME}/install.log" 2>&1
rc=$?
tail -n 5 "${HOME}/install.log"
check ${rc} "install.sh sans terminal" "code ${rc} en $(( $(date +%s) - start )) s (journal ~/install.log)"

step "3. Commandes, configuration, bureau"
for cmd in openride openride-core openride-compiler; do
    [[ -x "${HOME}/.local/bin/${cmd}" ]]
    check $? "commande ${cmd} dans ~/.local/bin"
done
PATH="${HOME}/.local/bin:${PATH}"
out="$(openride-core --help 2>&1)"
check $? "openride-core --help" "$(echo "${out}" | head -n 1 | cut -c1-60)"
[[ -f "${HOME}/OpenRide/config.toml" ]]
check $? "configuration créée" "~/OpenRide/config.toml"
grep -q "^godot = \"${GODOT}\"" "${HOME}/OpenRide/config.toml"
check $? "chemin de Godot gardé dans [engine] godot"
for d in GPX Workouts; do
    [[ -d "${HOME}/OpenRide/${d}" ]]
    check $? "dossier ~/OpenRide/${d}"
done
apps="${HOME}/.local/share/applications"
for entry in openride openride-release openride-update; do
    f="${apps}/${entry}.desktop"
    [[ -f "${f}" ]] && grep -q "^Exec=" "${f}"
    check $? "raccourci ${entry}.desktop"
done
icon="$(find "${HOME}/.local/share/icons" -name 'openride.svg' 2>/dev/null | head -n 1)"
[[ -n "${icon}" ]]
check $? "icône installée" "${icon#"${HOME}"/}"
if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "${apps}/openride.desktop"
    check $? "desktop-file-validate openride.desktop"
fi

step "4. Premier démarrage"
openride --compile-only > "${HOME}/compile.log" 2>&1
check $? "openride --compile-only" "$(tail -n 1 "${HOME}/compile.log" | cut -c1-80)"
timeout -s INT 8 openride-core run --trainer sim --input sim --hr sim --autostart > "${HOME}/core.log" 2>&1
rc=$?
grep -q "Core démarré" "${HOME}/core.log"
check $? "core lancé sur le trainer simulé" "« Core démarré » lu, code ${rc} après SIGINT"
! grep -q "Traceback" "${HOME}/core.log"
check $? "aucune exception du core"
openride-core release-trainer --help > /dev/null 2>&1
check $? "openride-core release-trainer disponible"

step "5. Mise à jour qui garde les données"
mkdir -p "${HOME}/OpenRide/GPX" "${HOME}/OpenRide/Activities"
printf '<?xml version="1.0"?><gpx version="1.1"><trk><trkseg><trkpt lat="45.0" lon="6.0"/><trkpt lat="45.01" lon="6.0"/></trkseg></trk></gpx>\n' \
    > "${HOME}/OpenRide/GPX/essai.gpx"   # trace fictive
printf 'séance factice de la recette\n' > "${HOME}/OpenRide/Activities/2026-01-01_essai.fit"
sed -i 's/^difficulty_pct = [0-9]*/difficulty_pct = 37/' "${HOME}/OpenRide/config.toml"   # réglage à la main
grep -q "^difficulty_pct = 37" "${HOME}/OpenRide/config.toml"
check $? "configuration modifiée par l'utilisateur" "difficulty_pct = 37"
before_fp="$(fingerprint)"
before_head="$(git -C "${DEST}" rev-parse --short HEAD)"
# Nouveau commit sur le dépôt d'origine (clone de travail à côté, puis poussée vers l'origine).
work="$(mktemp -d)"
git clone --quiet "${REPO_URL}" "${work}/up" && (
    cd "${work}/up" && git config user.email "recette@example.invalid" && git config user.name "Recette" \
        && echo "Ligne ajoutée par la recette d'installation." >> Open_ride_linux/docs/RECETTE_INSTALL_TEMOIN.md \
        && git add -A && git commit --quiet -m "Témoin de mise à jour" && git push --quiet origin HEAD
) > /dev/null 2>&1
check $? "nouveau commit publié sur le dépôt d'origine"
bash "${PROJECT}/scripts/update.sh" > "${HOME}/update.log" 2>&1
rc=$?
check ${rc} "scripts/update.sh" "$(tail -n 1 "${HOME}/update.log")"
after_head="$(git -C "${DEST}" rev-parse --short HEAD)"
[[ "${before_head}" != "${after_head}" && -f "${PROJECT}/docs/RECETTE_INSTALL_TEMOIN.md" ]]
check $? "code mis à jour" "${before_head} → ${after_head}"
bash "${PROJECT}/scripts/install.sh" </dev/null > "${HOME}/install2.log" 2>&1
check $? "install.sh relancé sur une installation existante"
after_fp="$(fingerprint)"
[[ "${before_fp}" == "${after_fp}" ]]
check $? "parcours, séances et config.toml inchangés" "$(echo "${after_fp}" | wc -l) fichier(s) comparé(s)"
if [[ "${before_fp}" != "${after_fp}" ]]; then
    diff <(echo "${before_fp}") <(echo "${after_fp}") | head -n 10
fi
grep -q "^difficulty_pct = 37" "${HOME}/OpenRide/config.toml"
check $? "réglage de l'utilisateur gardé" "difficulty_pct = 37"
rm -rf "${work}"

echo
echo "${checks} vérifications, ${failures} échec(s)"
if [[ ${failures} -eq 0 ]]; then
    echo "RÉSULTAT : installation neuve OK"
    exit 0
fi
echo "RÉSULTAT : ÉCHEC"
exit 1
