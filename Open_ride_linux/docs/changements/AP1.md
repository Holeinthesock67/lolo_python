# AP1 : contrôle avant poussée, banc multi-zones sans délai dépassé

- PR : à venir ; rapport : statut/FIABILITE_CI_BANCS_2026-11-26.md (dossier du projet) ; version : 6.0
- CHANGELOG (section « Ajouté ») :
  - `scripts/avant_poussee.py` : avant chaque poussée, en 1 à 3 minutes, les fautes qui faisaient le plus souvent
    rougir la CI et les trains (fichier `.uid` oublié, numéro IPC ou WORLDGEN déjà pris, conflit avec main, lot en
    double, test qui écrit hors de son dossier temporaire) ; `--corriger` écrit les `.uid` manquants.
- CHANGELOG (section « Corrigé ») :
  - Banc multi-zones du monde ouvert : le contrôle sol / route ne passe plus que sur la balade de la zone
    (`controle_sol_route.py --balades-seules`) ; il contrôlait aussi les 40 parcours installés et les 7 étapes
    finissaient sur leur délai de 30 min (26/11).
- SUIVI :
  - [ ] AP1 : contrôle avant poussée (`scripts/avant_poussee.py`) et banc multi-zones à la balade seule.
