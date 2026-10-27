#!/usr/bin/env bash
# Change le numéro de version d'OpenRide partout à la fois (lot O2).
# Usage : scripts/bump-version.sh X.Y.Z
#
# Met à jour VERSION, core/pyproject.toml, compiler/pyproject.toml, engine/project.godot et le
# titre de la première section de CHANGELOG.md (« X.Y.Z – AAAA-MM-JJ »). Ne fait ni commit ni
# étiquette Git : la publication reste au lot O8. core/tests/test_version.py vérifie le résultat.

set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
    echo "usage : $0 MAJEUR.MINEUR.CORRECTIF (par exemple 1.0.0)" >&2
    exit 2
fi
NEW="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TODAY="$(date +%F)"

echo "$NEW" > "$ROOT/VERSION"
for f in core/pyproject.toml compiler/pyproject.toml; do
    sed -i -E "0,/^version = \"[^\"]*\"/s//version = \"$NEW\"/" "$ROOT/$f"
done
sed -i -E "s/^config\/version=\"[^\"]*\"/config\/version=\"$NEW\"/" "$ROOT/engine/project.godot"
# Première section « ## … » seulement.
sed -i -E "0,/^## .*/s//## $NEW – $TODAY/" "$ROOT/CHANGELOG.md"

echo "version $NEW : VERSION, pyproject.toml (core, compiler), project.godot et CHANGELOG.md mis à jour"
echo "rappel : réinstaller les paquets (pip install -e) pour que les métadonnées suivent"
