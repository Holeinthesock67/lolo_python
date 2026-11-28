#!/usr/bin/env bash
# Banc du lot CD1 (#1179) : copie UNE FOIS les 4 parcours de référence dans un dossier fixe, lu à l'identique par
# les étapes de la branche et de main (périmètre validé par le propriétaire le 28/11 : Alpe d'Huez, Tour du lac
# d'Annecy, démo DB1 « Tour des nouveaux paysages », Ballon d'Alsace ; circuit de la manche 1 retiré à 14h00).
# Lecture seule des parcours installés (~/.local/share/openride/routes) ; rien n'est recompilé ; déjà copiés : gardés.
set -u
MONDES="${CD1_MONDES:-$HOME/mesures-2026-11-01-auto/mondes-cd1}"
ROUTES="${CD1_ROUTES:-$HOME/.local/share/openride/routes}"
mkdir -p "$MONDES"
manque=0
for id in alpe-d-huez tour-du-lac-d-annecy demo-biomes-paysages ballon-d-alsace; do
  if [ -d "$MONDES/$id.world" ]; then
    echo "déjà copié : $id"
  elif [ -d "$ROUTES/$id.world" ]; then
    cp -a "$ROUTES/$id.world" "$MONDES/$id.world" && echo "copié : $id"
  else
    echo "ABSENT : $id ($ROUTES/$id.world) : son étape sortira en ENVIRONNEMENT"
    [ "$id" = "tour-du-lac-d-annecy" ] || manque=1
  fi
done
# Annecy (#943) peut manquer tant que #943 n'est pas fusionnée : seule son étape est touchée.
exit $manque
