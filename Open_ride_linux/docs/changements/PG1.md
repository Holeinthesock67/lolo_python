# PG1 : préparation des graphismes au premier lancement

- PR : à venir (empilée sur AC6, #1066) ; cahier : docs/lots/LOT_PG1_preparation_graphismes.md ; version : 6.0
- CHANGELOG (section « Ajouté ») :
  - Premier lancement, ou après une mise à jour du jeu ou du pilote : « Préparation des graphismes : première fois
    seulement » sous le menu, avec une barre. Les shaders de tout le jeu passent une fois, un par image, pour que le
    départ ne fige plus l'écran. Les lancements suivants ne refont rien.
- SUIVI :
  - [ ] PG1 : catalogue des graphismes (graphics_catalog.gd), préparation (graphics_prep.gd), catalogue de départ
    livré (`engine/data/graphismes/`, `engine/tests/catalogue_graphismes.py`).
