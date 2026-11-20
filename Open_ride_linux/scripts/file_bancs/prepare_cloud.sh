#!/usr/bin/env bash
# Préparation d'un conteneur cloud (sans GPU) pour les étapes `lieu = "cloud"` de scripts/file_bancs.py
# (plan du 20 novembre : captures et contrôles sans mesure GPU en cloud, le PC garde la mesure GPU et la planche).
# Comme la CI : Godot 4.7.2 dans ~/.cache/godot-4.7.2, Xvfb et Vulkan logiciel (lavapipe), core/.venv du dépôt avec
# le core et le compilateur. Idempotent. Usage, depuis la racine du dépôt :
#   bash Open_ride_linux/scripts/file_bancs/prepare_cloud.sh
#   python3 Open_ride_linux/scripts/file_bancs.py lancer FILE.toml --lieu cloud
# Les commandes des étapes cloud trouvent Godot dans $GODOT (exporté par ce script dans ~/.cache/godot-4.7.2/env).
set -eu
VERSION=4.7.2
DOSSIER=$HOME/.cache/godot-$VERSION
BIN=$DOSSIER/Godot_v${VERSION}-stable_linux.x86_64
racine=$(git rev-parse --show-toplevel)
if [ ! -x "$BIN" ]; then
  mkdir -p "$DOSSIER"
  curl -fsSL -o "$DOSSIER/godot.zip" \
    "https://github.com/godotengine/godot/releases/download/${VERSION}-stable/Godot_v${VERSION}-stable_linux.x86_64.zip"
  (cd "$DOSSIER" && python3 -m zipfile -e godot.zip . && rm godot.zip)
  chmod +x "$BIN"
fi
if ! command -v xvfb-run >/dev/null || [ ! -e /usr/share/vulkan/icd.d/lvp_icd.x86_64.json ]; then
  if [ "$(id -u)" = 0 ] && command -v apt-get >/dev/null; then
    apt-get update -q && apt-get install -y -q --no-install-recommends xvfb xauth mesa-vulkan-drivers
  else
    echo "xvfb-run ou Vulkan logiciel absent : installer xvfb xauth mesa-vulkan-drivers" >&2
  fi
fi
venv=$racine/Open_ride_linux/core/.venv
if [ ! -x "$venv/bin/python" ]; then
  python3 -m venv "$venv"
fi
(cd "$racine/Open_ride_linux" && "$venv/bin/pip" install -q -c constraints.txt -e "core[dev]" -e compiler)
echo "GODOT=$BIN" > "$DOSSIER/env"
echo "Prêt : GODOT=$BIN, environnement $venv"
