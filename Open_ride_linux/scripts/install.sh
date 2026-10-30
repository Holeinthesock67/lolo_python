#!/usr/bin/env bash
# Installation d'OpenRide en une commande (lot N14) : scripts/install.sh
#
# 1. crée l'environnement Python (core/.venv) et y installe le core et le compilateur ;
# 2. relie `openride` et `openride-core` dans ~/.local/bin ;
# 3. crée ~/OpenRide/config.toml depuis scripts/config.example.toml s'il manque ;
# 4. vérifie Godot 4.7 (chemin demandé une fois, gardé dans [engine] godot de config.toml) ;
# 5. installe les entrées de bureau (scripts/install-desktop.sh).
# Peut être relancé sans dommage. Variables : GODOT (chemin de Godot), OPENRIDE_VENV,
# OPENRIDE_NO_PIP=1 (tests : pas de création du venv ni de pip, OPENRIDE_PYTHON donné).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV="${OPENRIDE_VENV:-${PROJECT_DIR}/core/.venv}"
OPENRIDE_HOME="${HOME}/OpenRide"
CONFIG="${OPENRIDE_HOME}/config.toml"
BIN_DIR="${HOME}/.local/bin"
DEFAULT_GODOT="${HOME}/Applications/godot/Godot_v4.7.2-stable_linux.x86_64"

say() { echo "install.sh : $*"; }
die() { echo "install.sh : $*" >&2; exit 1; }

# 1. Environnement Python
if [[ "${OPENRIDE_NO_PIP:-0}" == "1" ]]; then
    PYTHON="${OPENRIDE_PYTHON:?OPENRIDE_PYTHON requis avec OPENRIDE_NO_PIP=1}"
    BIN_SRC="${OPENRIDE_BIN_SRC:?OPENRIDE_BIN_SRC requis avec OPENRIDE_NO_PIP=1}"
else
    command -v python3 >/dev/null 2>&1 || die "python3 introuvable (sudo apt install python3 python3-venv)."
    if [[ ! -x "${VENV}/bin/python" ]]; then
        say "création de l'environnement Python ${VENV}"
        python3 -m venv "${VENV}" || die "python3 -m venv a échoué (sudo apt install python3-venv)."
    fi
    say "installation du core et du compilateur"
    "${VENV}/bin/pip" install --quiet --upgrade pip
    "${VENV}/bin/pip" install --quiet -c "${PROJECT_DIR}/constraints.txt" \
        -e "${PROJECT_DIR}/core" -e "${PROJECT_DIR}/compiler"
    PYTHON="${VENV}/bin/python"
    BIN_SRC="${VENV}/bin"
fi

# 2. Commandes dans ~/.local/bin
mkdir -p "${BIN_DIR}"
for cmd in openride openride-core openride-compiler; do
    if [[ -x "${BIN_SRC}/${cmd}" ]]; then
        ln -sfn "${BIN_SRC}/${cmd}" "${BIN_DIR}/${cmd}"
    fi
done
[[ -x "${BIN_DIR}/openride" ]] || die "commande openride absente de ${BIN_SRC}."

# 3. Configuration locale et dossiers
mkdir -p "${OPENRIDE_HOME}/GPX" "${OPENRIDE_HOME}/Workouts"
if [[ ! -f "${CONFIG}" ]]; then
    cp "${SCRIPT_DIR}/config.example.toml" "${CONFIG}"
    say "configuration créée : ${CONFIG}"
fi

# 4. Godot 4.7
configured="$("${PYTHON}" -c 'import sys, tomllib
try:
    print(tomllib.load(open(sys.argv[1], "rb")).get("engine", {}).get("godot", ""))
except Exception:
    print("")' "${CONFIG}")"
godot="${GODOT:-${configured:-${DEFAULT_GODOT}}}"
godot="${godot/#\~/${HOME}}"
if [[ ! -x "${godot}" ]]; then
    if [[ -t 0 ]]; then
        read -r -p "Chemin de Godot 4.7 (exécutable) : " godot
        godot="${godot/#\~/${HOME}}"
    fi
    [[ -x "${godot}" ]] || die "Godot 4.7 introuvable (${godot:-aucun chemin}). Téléchargez-le sur godotengine.org puis relancez avec GODOT=/chemin/vers/godot."
fi
version="$("${godot}" --version 2>/dev/null | head -n 1 || true)"
[[ "${version}" == 4.7* ]] || die "Godot 4.7 attendu, trouvé « ${version:-?} » (${godot}). Téléchargez Godot_v4.7.2-stable_linux.x86_64.zip sur https://github.com/godotengine/godot/releases/tag/4.7.2-stable puis relancez avec GODOT=/chemin/vers/godot."
"${PYTHON}" -m openride_core.config_edit "${CONFIG}" engine godot "${godot}" >/dev/null
say "Godot ${version} : ${godot}"

# 5. Entrées de bureau
PATH="${BIN_DIR}:${PATH}" bash "${SCRIPT_DIR}/install-desktop.sh"

say "terminé. Lancez OpenRide depuis le menu des applications, puis configurez vos appareils :"
say "  openride-core devices --save"
