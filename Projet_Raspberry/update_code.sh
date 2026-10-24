#!/bin/bash
# Met à jour le code des programmes du Raspberry Pi depuis GitHub.
#
#   ~/lolo_python/Projet_Raspberry/update_code.sh check   # montre ce qui changerait, ne modifie rien
#   ~/lolo_python/Projet_Raspberry/update_code.sh         # met à jour (lancé chaque matin par cron)
#
# Seul le CODE est copié. Les données (~/garmin_coach/data, export, ~/podcast-data),
# les environnements Python, le jeton Garmin et rclone ne sont jamais touchés.
# Chaque programme est testé avant d'être remplacé : en cas d'échec, l'ancienne version reste.

set -u
MODE="${1:-run}"
REPO="$HOME/lolo_python"
SRC="$REPO/Projet_Raspberry"
STAMP() { date '+%Y-%m-%d %H:%M:%S'; }

cd "$REPO" || { echo "$(STAMP) dépôt introuvable : $REPO"; exit 1; }
if ! git fetch -q origin main; then
    echo "$(STAMP) GitHub injoignable : aucune mise à jour"; exit 1
fi
git reset -q --hard origin/main        # copie en lecture seule : on suit toujours GitHub
echo "$(STAMP) dépôt à la version $(git log -1 --format='%h %s')"

# deploy NOM DOSSIER_SOURCE DOSSIER_CIBLE COMMANDE_DE_TEST FICHIERS...
deploy() {
    local name="$1" from="$2" to="$3" test="$4"; shift 4
    local changed=()
    for f in "$@"; do
        [ -f "$from/$f" ] || { echo "  $name : $f absent du dépôt, ignoré"; continue; }
        cmp -s "$from/$f" "$to/$f" || changed+=("$f")
    done
    if [ ${#changed[@]} -eq 0 ]; then echo "  $name : à jour"; return 0; fi
    echo "  $name : à mettre à jour → ${changed[*]}"
    [ "$MODE" = "check" ] && return 0

    local tmp; tmp="$(mktemp -d)"
    cp -p "$to"/*.py "$tmp"/ 2>/dev/null
    for f in "$@"; do [ -f "$from/$f" ] && cp "$from/$f" "$tmp/"; done
    if (cd "$tmp" && eval "$test") > "$tmp/test.log" 2>&1; then
        for f in "${changed[@]}"; do cp "$from/$f" "$to/$f"; done
        echo "  $name : mis à jour (test réussi)"
    else
        echo "  $name : TEST ÉCHOUÉ, ancienne version conservée"
        tail -5 "$tmp/test.log" | sed 's/^/    /'
    fi
    rm -rf "$tmp"
}

deploy "Sport" "$SRC/Sport" "$HOME/garmin_coach" \
    "$HOME/garmin_coach/.venv/bin/python test_offline.py" \
    coach.py db.py garmin_source.py report.py training.py integrity.py exercises.py weather_source.py settings_source.py test_offline.py

deploy "Podcast" "$SRC/Podcast" "$HOME/veille" \
    "$HOME/veille-env/bin/python -m py_compile commun.py veille.py && $HOME/piper-env/bin/python -m py_compile podcast.py" \
    commun.py veille.py podcast.py
