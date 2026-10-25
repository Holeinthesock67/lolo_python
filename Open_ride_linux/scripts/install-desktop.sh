#!/usr/bin/env bash
# Installation (ou désinstallation) des raccourcis de bureau OpenRide pour l'utilisateur :
# OpenRide, OpenRide – Libérer le trainer et OpenRide – Mettre à jour (lots L8 et N14).
# Usage : scripts/install-desktop.sh [--uninstall] [--prefix DOSSIER]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR_IN="${SCRIPT_DIR}/desktop"
UPDATE_SH="${SCRIPT_DIR}/update.sh"
ENTRIES=(openride openride-release openride-update)
ICON_SRC="${SCRIPT_DIR}/desktop/openride.svg"

PREFIX="${HOME}/.local/share"
UNINSTALL=0

usage() {
    cat <<'EOF'
Usage : scripts/install-desktop.sh [--uninstall] [--prefix DOSSIER]

Options :
  --prefix DOSSIER   Dossier cible (défaut : ~/.local/share)
  --uninstall        Supprime les fichiers .desktop et l'icône installés
  -h, --help         Affiche cette aide
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --uninstall)
            UNINSTALL=1
            shift
            ;;
        --prefix)
            if [[ $# -lt 2 || -z "$2" ]]; then
                echo "install-desktop.sh : --prefix attend un dossier." >&2
                exit 1
            fi
            PREFIX="$2"
            shift 2
            ;;
        --prefix=*)
            PREFIX="${1#--prefix=}"
            if [[ -z "${PREFIX}" ]]; then
                echo "install-desktop.sh : --prefix attend un dossier." >&2
                exit 1
            fi
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "install-desktop.sh : option inconnue : $1" >&2
            exit 1
            ;;
    esac
done

APP_DIR="${PREFIX}/applications"
ICON_DIR="${PREFIX}/icons/hicolor/scalable/apps"
ICON_DEST="${ICON_DIR}/openride.svg"

refresh_caches() {
    if command -v update-desktop-database >/dev/null 2>&1 && [[ -d "${APP_DIR}" ]]; then
        update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1 && [[ -d "${PREFIX}/icons/hicolor" ]]; then
        gtk-update-icon-cache -f -t "${PREFIX}/icons/hicolor" >/dev/null 2>&1 || true
    fi
}

if [[ "${UNINSTALL}" -eq 1 ]]; then
    for entry in "${ENTRIES[@]}"; do
        rm -f "${APP_DIR}/${entry}.desktop"
    done
    rm -f "${ICON_DEST}"
    refresh_caches
    echo "Raccourcis OpenRide désinstallés de ${PREFIX}."
    exit 0
fi

OPENRIDE_BIN=""
if command -v openride >/dev/null 2>&1; then
    OPENRIDE_BIN="$(command -v openride)"
elif [[ -x "${HOME}/.local/bin/openride" ]]; then
    OPENRIDE_BIN="${HOME}/.local/bin/openride"
else
    echo "install-desktop.sh : commande « openride » introuvable dans le PATH ni dans ~/.local/bin/openride." >&2
    echo "Installez d'abord le core (pip install -e core) ou ajoutez son environnement au PATH." >&2
    exit 1
fi

# Résolution en chemin absolu si nécessaire.
if [[ "${OPENRIDE_BIN}" != /* ]]; then
    OPENRIDE_BIN="$(cd "$(dirname "${OPENRIDE_BIN}")" && pwd)/$(basename "${OPENRIDE_BIN}")"
fi

mkdir -p "${APP_DIR}" "${ICON_DIR}"
for entry in "${ENTRIES[@]}"; do
    sed -e "s|@OPENRIDE@|${OPENRIDE_BIN}|g" -e "s|@UPDATE@|${UPDATE_SH}|g" \
        "${DESKTOP_DIR_IN}/${entry}.desktop.in" > "${APP_DIR}/${entry}.desktop"
    chmod 0644 "${APP_DIR}/${entry}.desktop"
done
cp -f "${ICON_SRC}" "${ICON_DEST}"
chmod 0644 "${ICON_DEST}"

refresh_caches
echo "Raccourcis OpenRide installés dans ${APP_DIR} (Exec=${OPENRIDE_BIN})."
