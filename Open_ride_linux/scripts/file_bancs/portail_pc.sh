#!/usr/bin/env bash
# Portail de la file des bancs (`[file] avant_etape` de scripts/file_bancs.py) : code 0 = l'étape peut partir.
# Reprend les deux attentes de lance.sh du fil de fusion :
#  1. fenêtre du user : FENETRE (défaut ~/mesures-2026-11-01-auto/fenetre.txt) contient « DEBUT_EPOCH FIN_EPOCH MARQUEUR » ;
#     une étape dont la durée (FILE_DUREE_MIN, donnée par la file) déborderait sur la fenêtre attend sa fin, ou le
#     fichier MARQUEUR (« PC rendu ») posé à côté de fenetre.txt ;
#  2. aucun Godot ni Xvfb en cours (jeu du user ou banc précédent).
# Code 1 avec une ligne de raison : la file réessaie toutes les `attente_s` secondes.
set -u
FENETRE=${FENETRE:-$HOME/mesures-2026-11-01-auto/fenetre.txt}
dur=${FILE_DUREE_MIN:-120}
if [ -f "$FENETRE" ]; then
  FD= FF= FM=
  read -r FD FF FM < "$FENETRE" || true
  # Fichier mal formé (vide, un seul champ, dates non entières) : passage fermé, jamais ouvert par erreur
  # (revue de code vague 5, O2-18).
  case "$FD$FF" in
    *[!0-9]*) ok=0 ;;
    *) ok=1 ;;
  esac
  if [ -z "$FD" ] || [ -z "$FF" ] || [ "$ok" -ne 1 ]; then
    echo "fenêtre du user illisible dans $FENETRE (attendu : DEBUT_EPOCH FIN_EPOCH MARQUEUR)"; exit 1
  fi
  now=$(date +%s)
  if { [ -z "$FM" ] || [ ! -f "$(dirname "$FENETRE")/$FM" ]; } && [ "$now" -lt "$FF" ] && [ $((now + dur * 60)) -ge "$FD" ]; then
    echo "fenêtre du user jusqu'à $(date -d "@$FF" +%H:%M) (étape de $dur min)"; exit 1
  fi
fi
if pgrep -f '^[^ ]*(Godot_v|Xvfb)' >/dev/null; then
  echo "Godot ou Xvfb en cours : $(pgrep -a -f '^[^ ]*(Godot_v|Xvfb)' | head -1 | cut -c1-80)"; exit 1
fi
exit 0
