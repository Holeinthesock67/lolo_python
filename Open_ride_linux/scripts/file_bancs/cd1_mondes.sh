#!/usr/bin/env bash
# Banc du lot CD1 (#1179) : copie UNE FOIS les 5 parcours de référence dans un dossier fixe, lu à l'identique par
# les étapes de la branche et de main (périmètre validé par le propriétaire le 28/11 : Alpe d'Huez, Tour du lac
# d'Annecy, démo DB1 « Tour des nouveaux paysages », circuit de la manche 1, Ballon d'Alsace).
# Lecture seule des parcours installés (~/.local/share/openride/routes) ; rien n'est recompilé ; déjà copiés : gardés.
# Le circuit de la manche 1 est le dernier parcours choisi au menu du profil actif (derniers_choix.json, route_id) ;
# son nom est écrit dans circuit.txt et affiché ici : le vérifier dans le journal de la fumée.
set -u
MONDES="${CD1_MONDES:-$HOME/mesures-2026-11-01-auto/mondes-cd1}"
ROUTES="${CD1_ROUTES:-$HOME/.local/share/openride/routes}"
mkdir -p "$MONDES"
if [ ! -s "$MONDES/circuit.txt" ]; then
  PROFIL=$(cat "$HOME/OpenRide/Profils/.profil_actif" 2>/dev/null || echo principal)
  python3 - "$HOME/OpenRide/Profils/$PROFIL/derniers_choix.json" > "$MONDES/circuit.txt" <<'PY'
import json, sys
try:
    print(json.load(open(sys.argv[1], encoding="utf-8")).get("route_id") or "")
except Exception:
    print("")
PY
fi
CIRCUIT=$(tr -d '[:space:]' < "$MONDES/circuit.txt")
echo "Circuit de la manche 1 (dernier parcours du profil) : ${CIRCUIT:-INCONNU}"
manque=0
for id in alpe-d-huez tour-du-lac-d-annecy demo-biomes-paysages ballon-d-alsace "$CIRCUIT"; do
  [ -z "$id" ] && { echo "ABSENT : circuit de la manche 1 (derniers_choix.json sans route_id)"; manque=1; continue; }
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
