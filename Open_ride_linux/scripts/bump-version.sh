#!/usr/bin/env bash
# Change le numéro de version d'OpenRide partout à la fois (lot O2).
# Usage : scripts/bump-version.sh X.Y.Z
#
# Met à jour VERSION, core/pyproject.toml, compiler/pyproject.toml, engine/project.godot et le
# CHANGELOG.md : la section « ## Non publié » (ou « ## X.Y.Z – Non publiée ») en tête prend le titre « X.Y.Z – AAAA-MM-JJ » ; sans section
# « Non publié » en tête, une nouvelle section vide est insérée avant la première, et les notes de la
# version précédente gardent leur titre (revue de code vague 5, O1-08). Ne fait ni commit ni
# étiquette Git : la publication reste au lot O8. core/tests/test_version.py vérifie le résultat.
# Le numéro et la date écrits à la main dans README.md (racine du dépôt) restent à changer à la main.

set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
    echo "usage : $0 MAJEUR.MINEUR.CORRECTIF (par exemple 1.0.0)" >&2
    exit 2
fi
NEW="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TODAY="$(date +%F)"
CHANGELOG="$ROOT/CHANGELOG.md"
FIRST="$(grep -m1 -E '^## ' "$CHANGELOG" || true)"
if [[ "$FIRST" =~ ^"## $NEW – "[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
    echo "$0 : CHANGELOG.md a déjà une section $NEW en tête ; rien n'est changé" >&2
    exit 2
fi

echo "$NEW" > "$ROOT/VERSION"
for f in core/pyproject.toml compiler/pyproject.toml; do
    sed -i -E "0,/^version = \"[^\"]*\"/s//version = \"$NEW\"/" "$ROOT/$f"
done
sed -i -E "s/^config\/version=\"[^\"]*\"/config\/version=\"$NEW\"/" "$ROOT/engine/project.godot"
if [[ "$FIRST" == *"Non publi"* ]]; then
    # La section « Non publié » (ou « X.Y.Z – Non publiée ») devient la nouvelle version.
    sed -i -E "0,/^## .*Non publi.*/s//## $NEW – $TODAY/" "$CHANGELOG"
else
    # Pas de « Non publié » : nouvelle section avant la première, la précédente garde son titre.
    sed -i -E "0,/^## /s//## $NEW – $TODAY\n\n## /" "$CHANGELOG"
fi

echo "version $NEW : VERSION, pyproject.toml (core, compiler), project.godot et CHANGELOG.md mis à jour"
echo "rappel : réinstaller les paquets (pip install -e) pour que les métadonnées suivent"
