#!/usr/bin/env bash
# Mise à jour d'OpenRide depuis le dépôt (entrée de bureau « OpenRide – Mettre à jour », lot N14).
# Usage : scripts/update.sh
#
# git pull --ff-only, puis réinstallation du core et du compilateur dans le venv. Refuse si le
# dépôt a des modifications locales ou ne peut pas avancer en avance rapide, et dit alors quoi
# faire. Ne fait jamais de reset ni de poussée.
# Jeu ouvert (lanceur, core ou Godot de cette installation) : rien n'est touché ; une fenêtre
# propose « Fermer le jeu » (arrêt propre par SIGTERM), « Réessayer » ou « Annuler ». Pendant la
# mise à jour, le verrou ~/OpenRide/.update.lock empêche le lanceur de démarrer.
# Sans terminal, le résultat s'affiche dans une fenêtre (zenity, sinon kdialog, sinon
# notify-send) ; dans un terminal, sur la sortie. Journal : ~/OpenRide/Logs/update.log.
# Variables : OPENRIDE_VENV (défaut : core/.venv), OPENRIDE_NO_PIP=1 (tests : sans pip),
# OPENRIDE_NO_GUI=1 (ni fenêtre ni notification), OPENRIDE_CLOSE_TIMEOUT (secondes, défaut 30).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV="${OPENRIDE_VENV:-${PROJECT_DIR}/core/.venv}"
OPENRIDE_DIR="${HOME}/OpenRide"
LOG="${OPENRIDE_DIR}/Logs/update.log"
LOCK="${OPENRIDE_DIR}/.update.lock"
TITLE="OpenRide – Mise à jour"
CLOSE_TIMEOUT="${OPENRIDE_CLOSE_TIMEOUT:-30}"

log() {
    mkdir -p "$(dirname "${LOG}")" 2>/dev/null || return 0
    printf '%s %s\n' "$(date '+%F %T')" "$*" >>"${LOG}" 2>/dev/null || true
}

# Fenêtres seulement sans terminal, avec un affichage, et hors tests.
gui() {
    [[ "${OPENRIDE_NO_GUI:-0}" != "1" && ! -t 0 && ( -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ) ]]
}

notify() {   # notify ERREUR(0|1) MESSAGE
    echo "$2"
    log "$2"
    gui || return 0
    local text="$2"
    [[ "$1" -eq 1 ]] && text="${text}"$'\n\n'"Journal : ${LOG}"
    if command -v zenity >/dev/null 2>&1; then
        zenity "$([[ "$1" -eq 1 ]] && echo --error || echo --info)" --no-wrap --title="${TITLE}" \
            --text="${text}" >/dev/null 2>&1 || true
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --title "${TITLE}" "$([[ "$1" -eq 1 ]] && echo --error || echo --msgbox)" "${text}" \
            >/dev/null 2>&1 || true
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send -u "$([[ "$1" -eq 1 ]] && echo critical || echo normal)" "${TITLE}" "$2" \
            >/dev/null 2>&1 || true
    fi
}

fail() {
    notify 1 "Mise à jour refusée : $1"
    exit 1
}

# --- jeu ouvert --------------------------------------------------------------------------

# Processus de cette installation : Python du venv (lanceur `openride`, core, compilateur) ou
# Godot lancé sur le projet `engine` de ce dépôt. Les autres copies d'OpenRide sont ignorées.
is_game() {
    local prev="" a
    [[ "$1" == "${VENV}/"* ]] && return 0
    for a in "$@"; do
        [[ "${prev}" == "--path" && "${a}" == "${PROJECT_DIR}/engine" ]] && return 0
        prev="${a}"
    done
    return 1
}

is_launcher() {   # lanceur `openride` : il arrête lui-même core et engine sur SIGTERM
    local a
    [[ "$1" == "${VENV}/"* ]] || return 1
    for a in "${@:2}"; do
        [[ "${a}" == */openride ]] && return 0
    done
    return 1
}

game_pids() {   # game_pids [launcher] : PID du jeu (ou de ses lanceurs seulement), un par ligne
    local d pid args
    for d in /proc/[0-9]*; do
        pid="${d#/proc/}"
        [[ "${pid}" == "$$" || "${pid}" == "${BASHPID}" ]] && continue
        [[ -O "${d}" ]] || continue
        mapfile -d '' -t args <"${d}/cmdline" 2>/dev/null || continue
        ((${#args[@]})) || continue
        if [[ "${1:-}" == "launcher" ]]; then
            is_launcher "${args[@]}" && echo "${pid}"
        else
            is_game "${args[@]}" && echo "${pid}"
        fi
    done
    return 0
}

ask_game_open() {   # affiche le choix ; sortie : close, retry ou cancel
    local text="OpenRide est ouvert : la mise à jour ne peut pas remplacer ses fichiers pendant qu'il tourne. Rien n'a été changé."
    if [[ -t 0 && "${OPENRIDE_NO_GUI:-0}" != "1" ]]; then
        local answer
        echo "${text}" >&2
        read -r -p "[F]ermer le jeu (une séance en cours est arrêtée proprement), [R]éessayer, [A]nnuler ? " answer
        case "${answer}" in
            [fF]*) echo close ;;
            [rR]*) echo retry ;;
            *) echo cancel ;;
        esac
        return 0
    fi
    if gui && command -v zenity >/dev/null 2>&1; then
        local out rc
        out="$(zenity --question --no-wrap --title="${TITLE}" --ok-label="Fermer le jeu" \
            --cancel-label="Annuler" --extra-button="Réessayer" \
            --text="${text}"$'\n\n'"« Fermer le jeu » arrête proprement une séance en cours, puis met à jour."$'\n'"« Réessayer » : fermez OpenRide vous-même d'abord." 2>/dev/null)"
        rc=$?
        if [[ ${rc} -eq 0 ]]; then echo close
        elif [[ "${out}" == *"Réessayer"* ]]; then echo retry
        else echo cancel
        fi
        return 0
    fi
    if gui && command -v kdialog >/dev/null 2>&1; then
        kdialog --title "${TITLE}" --yes-label "Fermer le jeu" --no-label "Réessayer" \
            --cancel-label "Annuler" --yesnocancel "${text}" >/dev/null 2>&1
        case $? in
            0) echo close ;;
            1) echo retry ;;
            *) echo cancel ;;
        esac
        return 0
    fi
    echo cancel
}

close_game() {   # SIGTERM au lanceur (ou, sans lanceur, au core et à l'engine) puis attente
    local pids waited=0
    pids="$(game_pids launcher)"
    [[ -n "${pids}" ]] || pids="$(game_pids)"
    log "fermeture du jeu : SIGTERM à ${pids//$'\n'/ }"
    # shellcheck disable=SC2086
    kill -TERM ${pids} 2>/dev/null || true
    while [[ -n "$(game_pids)" && ${waited} -lt ${CLOSE_TIMEOUT} ]]; do
        sleep 1
        waited=$((waited + 1))
    done
    [[ -z "$(game_pids)" ]]
}

wait_game_closed() {
    local choice
    while [[ -n "$(game_pids)" ]]; do
        log "jeu ouvert : $(game_pids | tr '\n' ' ')"
        choice="$(ask_game_open)"
        log "choix : ${choice}"
        case "${choice}" in
            close)
                close_game || fail "OpenRide ne s'est pas fermé en ${CLOSE_TIMEOUT} s. Fermez-le, puis relancez « Mettre à jour ». Rien n'a été changé."
                ;;
            retry) ;;
            *) fail "OpenRide est ouvert. Fermez-le, puis relancez « Mettre à jour ». Rien n'a été changé." ;;
        esac
    done
}

# --- mise à jour -------------------------------------------------------------------------

# Tout le travail est dans une fonction : bash la lit en entier avant que `git pull` ne
# remplace ce fichier.
main() {
    log "--- mise à jour de ${PROJECT_DIR}"
    mkdir -p "${OPENRIDE_DIR}" 2>/dev/null || true
    if command -v flock >/dev/null 2>&1 && exec 9>>"${LOCK}"; then
        flock -n 9 || fail "une autre mise à jour est déjà en cours."
    fi
    cd "${PROJECT_DIR}" || fail "dossier ${PROJECT_DIR} introuvable."
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "${PROJECT_DIR} n'est pas un dépôt git."
    wait_game_closed

    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
        log "$(git status --short --untracked-files=no)"
        fail "le dépôt a des modifications locales (voir « git status » dans ${PROJECT_DIR}). Rien n'a été changé."
    fi
    local err
    err="$(git fetch --quiet 2>&1)" || { log "${err}"; fail "impossible de joindre le dépôt distant (réseau ?). Rien n'a été changé."; }
    upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" \
        || fail "la branche courante ($(git branch --show-current 2>/dev/null || echo 'aucune')) ne suit aucune branche distante. Revenez sur main : « git switch main » dans ${PROJECT_DIR}."
    git merge-base --is-ancestor HEAD "${upstream}"
    case $? in
        0) ;;
        1)
            local n
            n="$(git rev-list --count "${upstream}..HEAD")"
            log "commits locaux absents de ${upstream} :"$'\n'"$(git log --oneline "${upstream}..HEAD")"
            fail "le dépôt local a ${n} commit(s) absent(s) de ${upstream} (liste dans le journal) : pas d'avance rapide possible. Rien n'a été changé. Pour revenir à la version publiée en gardant ces commits dans une branche de sauvegarde, dans ${PROJECT_DIR} : « git branch sauvegarde-$(date +%F) && git reset --hard ${upstream} », puis relancez « Mettre à jour »."
            ;;
        *) fail "vérification de l'historique git impossible (voir le journal). Rien n'a été changé." ;;
    esac

    wait_game_closed   # le jeu a pu être lancé pendant le fetch
    before="$(git rev-parse --short HEAD)"
    err="$(git pull --ff-only --quiet 2>&1)" || { log "${err}"; fail "git pull --ff-only a échoué (voir le journal)."; }
    after="$(git rev-parse --short HEAD)"
    log "git : ${before} → ${after}"

    if [[ "${OPENRIDE_NO_PIP:-0}" != "1" ]]; then
        [[ -x "${VENV}/bin/pip" ]] || fail "environnement Python introuvable (${VENV}) : lancez scripts/install.sh."
        "${VENV}/bin/pip" install --quiet -c "${PROJECT_DIR}/constraints.txt" \
            -e "${PROJECT_DIR}/core" -e "${PROJECT_DIR}/compiler" >>"${LOG}" 2>&1 \
            || fail "le code est à jour (${after}) mais la réinstallation du core ou du compilateur a échoué. Relancez « Mettre à jour » : elle reprendra cette étape."
    fi

    if [[ "${before}" == "${after}" ]]; then
        notify 0 "OpenRide est déjà à jour (${after})."
    else
        notify 0 "OpenRide mis à jour : ${before} → ${after}."
    fi
}

main "$@"
exit $?
