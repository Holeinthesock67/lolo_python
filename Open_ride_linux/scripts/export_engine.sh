#!/usr/bin/env bash
# Export de l'engine (lot EX2, cadrage J9 : engine exporté en .pck) : binaire « release » de Godot et
# openride.pck à côté, construits depuis engine/export_presets.cfg (préréglage « Linux »).
#
#   GODOT=/chemin/vers/Godot_v4.7.2-stable_linux.x86_64 scripts/export_engine.sh [--pack-only] [--out DOSSIER]
#
# Sortie par défaut : build/engine/ (openride.x86_64 + openride.pck), hors git.
# --pack-only : seulement le .pck (sans modèle d'export), à lancer par « godot --main-pack openride.pck ».
# Le modèle d'export linux_release.x86_64 de la même version que GODOT doit être installé dans
# ~/.local/share/godot/export_templates/<version>/ ; --install-template le télécharge (archive officielle
# de 1,2 Go, seul ce modèle de 73 Mo est gardé) s'il manque.
# Code de sortie : 0 si l'export est fait, 1 s'il échoue, 2 si Godot ou le modèle manquent.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_DIR="$ROOT/engine"
GODOT="${GODOT:-$HOME/Applications/godot/Godot_v4.7.2-stable_linux.x86_64}"
OUT="$ROOT/build/engine"
PACK_ONLY=0
INSTALL_TEMPLATE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --pack-only) PACK_ONLY=1 ;;
    --install-template) INSTALL_TEMPLATE=1 ;;
    --out) OUT="$2"; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "option inconnue : $1"; exit 2 ;;
  esac
  shift
done

if [ ! -x "$GODOT" ]; then
  echo "Godot introuvable : $GODOT (définir GODOT=/chemin/vers/godot)"; exit 2
fi
# « 4.7.2.stable.official.xxxx » : le dossier des modèles s'appelle « 4.7.2.stable ».
VERSION="$("$GODOT" --headless --version 2>/dev/null | tail -n 1 | cut -d. -f1-4)"
TEMPLATE_DIR="$HOME/.local/share/godot/export_templates/$VERSION"
TEMPLATE="$TEMPLATE_DIR/linux_release.x86_64"

if [ "$PACK_ONLY" -eq 0 ] && [ ! -f "$TEMPLATE" ]; then
  if [ "$INSTALL_TEMPLATE" -eq 0 ]; then
    echo "modèle d'export absent : $TEMPLATE (relancer avec --install-template, ou --pack-only)"; exit 2
  fi
  tag="${VERSION%.stable}-stable"
  url="https://github.com/godotengine/godot/releases/download/$tag/Godot_v$tag""_export_templates.tpz"
  tmp="$(mktemp -d -t openride-tpl.XXXXXX)"
  echo "Téléchargement des modèles d'export $tag (1,2 Go)…"
  if ! curl -fsSL -o "$tmp/tpl.tpz" "$url"; then
    rm -rf "$tmp"; echo "téléchargement impossible : $url"; exit 2
  fi
  mkdir -p "$TEMPLATE_DIR"
  unzip -qjo "$tmp/tpl.tpz" templates/linux_release.x86_64 templates/version.txt -d "$TEMPLATE_DIR"
  rm -rf "$tmp"
fi

mkdir -p "$OUT"
rm -f "$OUT/openride.x86_64" "$OUT/openride.pck"
LOG="$OUT/export.log"
if [ "$PACK_ONLY" -eq 1 ]; then
  "$GODOT" --headless --path "$ENGINE_DIR" --export-pack Linux "$OUT/openride.pck" >"$LOG" 2>&1
else
  "$GODOT" --headless --path "$ENGINE_DIR" --export-release Linux "$OUT/openride.x86_64" >"$LOG" 2>&1
fi
code=$?
if [ "$code" -ne 0 ] || [ ! -f "$OUT/openride.pck" ] || { [ "$PACK_ONLY" -eq 0 ] && [ ! -x "$OUT/openride.x86_64" ]; }; then
  tail -n 30 "$LOG"
  echo "export en échec (code $code), journal : $LOG"; exit 1
fi
ls -l "$OUT"
echo "Export fait : $OUT"
