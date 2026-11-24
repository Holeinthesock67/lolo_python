#!/usr/bin/env bash
# Rappel de la manche de la ligue d'hiver (série CH, lot CH7) : minuteur systemd de l'utilisateur, samedi 18 h et
# dimanche midi, notification bureau si la manche de la semaine n'est pas courue (même OpenRide fermé).
# Usage : scripts/install-rappel-ligue.sh [--uninstall] [--essai]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
NAME="openride-rappel-ligue"
UNINSTALL=0
TRY=0

usage() {
    cat <<'USAGE'
Usage : scripts/install-rappel-ligue.sh [--uninstall] [--essai]

Options :
  --uninstall   Retire le minuteur (plus aucun rappel)
  --essai       Affiche le rappel qui partirait aujourd'hui, sans rien installer
  -h, --help    Affiche cette aide
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --uninstall) UNINSTALL=1 ;;
        --essai) TRY=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "install-rappel-ligue.sh : option inconnue : $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [[ "${UNINSTALL}" -eq 1 ]]; then
    systemctl --user disable --now "${NAME}.timer" >/dev/null 2>&1 || true
    rm -f "${UNIT_DIR}/${NAME}.service" "${UNIT_DIR}/${NAME}.timer"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    echo "Rappel de la ligue retiré."
    exit 0
fi

# Python de l'environnement du core (celui de la commande openride-core).
CORE_BIN="$(command -v openride-core || true)"
[[ -n "${CORE_BIN}" ]] || CORE_BIN="${HOME}/.local/bin/openride-core"
PYTHON="$(dirname "$(readlink -f "${CORE_BIN}")")/python"
if [[ ! -x "${PYTHON}" ]]; then
    echo "install-rappel-ligue.sh : Python du core introuvable (${PYTHON}). Installez d'abord le core." >&2
    exit 1
fi

if [[ "${TRY}" -eq 1 ]]; then
    exec "${PYTHON}" -m openride_core.league_reminder --essai
fi

command -v systemctl >/dev/null 2>&1 || { echo "install-rappel-ligue.sh : systemd introuvable." >&2; exit 1; }
mkdir -p "${UNIT_DIR}"
sed -e "s|@PYTHON@|${PYTHON}|g" "${SCRIPT_DIR}/systemd/${NAME}.service.in" > "${UNIT_DIR}/${NAME}.service"
cp -f "${SCRIPT_DIR}/systemd/${NAME}.timer" "${UNIT_DIR}/${NAME}.timer"
chmod 0644 "${UNIT_DIR}/${NAME}.service" "${UNIT_DIR}/${NAME}.timer"
systemctl --user daemon-reload
systemctl --user enable --now "${NAME}.timer"
echo "Rappel de la ligue installé : samedi 18 h et dimanche midi (${UNIT_DIR})."
systemctl --user list-timers "${NAME}.timer" --no-pager 2>/dev/null | head -n 2 || true
