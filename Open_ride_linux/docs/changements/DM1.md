# DM1 : délais des bancs tirés des passages précédents, départ du monde ouvert sur événement

- PR : à venir ; rapport : statut/FIABILITE_CI_BANCS_2026-11-26.md (dossier du projet) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - File des bancs du PC : le délai d'une étape n'est plus un chiffre fixe. Il vaut au moins 1,5 fois la plus
    longue des 5 dernières durées de la même mesure (toutes files confondues), et il double après un arrêt sur
    délai sans durée connue (plafond : 4 fois le délai écrit). `verifier` signale une sous-commande dont le délai
    interne n'est pas sous celui de l'étape. Les 25 et 26/11, ces délais fixes ont coûté environ 7 h 30 de PC
    (rZONES26, endurance #1067).
  - Bancs du monde ouvert : la fermeture du menu s'attend après « Monde ouvert prêt » (événement, jusqu'à 15 min),
    et non plus 300 s fixes avant lui (échec de Grenoble, génération plus longue en montagne).
- SUIVI :
  - [ ] DM1 : délais mesurés dans `file_bancs.py` et départ du monde ouvert sur événement (`menu_bench.py`).
