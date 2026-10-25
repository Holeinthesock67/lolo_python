#!/usr/bin/env bash
# Mise à jour d'OpenRide depuis le dépôt (entrée de bureau « OpenRide – Mettre à jour », lot N14).
# Usage : scripts/update.sh
#
# git pull --ff-only, puis réinstallation du core et du compilateur dans le venv. Refuse si le
# dépôt a des modifications locales ou ne peut pas avancer en avance rapide. Ne fait jamais de
# reset ni de poussée. Résultat affiché en notification (notify-send) et sur la sortie.
# Variables : OPENRIDE_VENV (défaut : core/.venv), OPENRIDE_NO_PIP=1 (tests : sans pip).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV="${OPENRIDE_VENV:-${PROJECT_DIR}/core/.venv}"

notify() {   # notify ERREUR(0|1) MESSAGE
    local urgency="normal"
    [[ "$1" -eq 1 ]] && urgency="critical"
    echo "$2"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -u "${urgency}" "OpenRide – Mise à jour" "$2" >/dev/null 2>&1 || true
    fi
}

fail() {
    notify 1 "Mise à jour refusée : $1"
    exit 1
}

# Tout le travail est dans une fonction : bash la lit en entier avant que `git pull` ne
# remplace ce fichier.
main() {
    cd "${PROJECT_DIR}" || fail "dossier ${PROJECT_DIR} introuvable."
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "${PROJECT_DIR} n'est pas un dépôt git."
    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
        fail "le dépôt a des modifications locales (git status). Rien n'a été changé."
    fi
    git fetch --quiet || fail "impossible de joindre le dépôt distant (réseau ?)."
    upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" \
        || fail "la branche courante ne suit aucune branche distante."
    if ! git merge-base --is-ancestor HEAD "${upstream}"; then
        fail "le dépôt local a des commits absents de ${upstream} : pas d'avance rapide possible."
    fi
    before="$(git rev-parse --short HEAD)"
    git pull --ff-only --quiet || fail "git pull --ff-only a échoué."
    after="$(git rev-parse --short HEAD)"

    if [[ "${OPENRIDE_NO_PIP:-0}" != "1" ]]; then
        [[ -x "${VENV}/bin/pip" ]] || fail "environnement Python introuvable (${VENV}) : lancez scripts/install.sh."
        "${VENV}/bin/pip" install --quiet -c "${PROJECT_DIR}/constraints.txt" \
            -e "${PROJECT_DIR}/core" -e "${PROJECT_DIR}/compiler" \
            || fail "réinstallation du core ou du compilateur impossible (voir pip)."
    fi

    if [[ "${before}" == "${after}" ]]; then
        notify 0 "OpenRide est déjà à jour (${after})."
    else
        notify 0 "OpenRide mis à jour : ${before} → ${after}."
    fi
}

main "$@"
exit $?
