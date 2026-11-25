# OW-CARTE1 : la carte du départ du monde ouvert n'est plus vide dans un lieu jamais visité

- PR : #1076 ; capture du 25 novembre (Sevrier, banc de #1072) ; compilateur (`menu_query map`), core (délai de la requête), engine (texte de la carte)
- CHANGELOG (section « Corrigé ») :
  - Monde ouvert : la carte où l'on choisit le point de départ ne montrait que le curseur quand le lieu n'avait jamais été roulé (routes lues seulement dans les tuiles déjà sur le PC). Les tuiles vectorielles absentes à moins de 3 km du lieu sont maintenant téléchargées à l'ouverture de la carte (réseau permis) et gardées pour le départ ; hors ligne, la carte lit celles déjà sur le PC.
  - Si la carte reste sans route (réseau coupé), elle le dit en mots et rappelle que le départ prendra la route la plus proche.
- SUIVI :
  - [ ] OW-CARTE1 : tuiles de la carte du départ (`menu_query.map_tiles`), tests `compiler/tests/test_menu_query.py` et `engine/tests/unit/test_world_menu_view.gd`.
