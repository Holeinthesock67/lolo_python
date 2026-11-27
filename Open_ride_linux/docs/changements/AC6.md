# AC6 : premier affichage du monde à froid sans écran figé

- PR : #1066 ; cahier : docs/lots/LOT_AC6_premier_affichage_a_froid.md ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Premier lancement (shaders pas encore en cache) : l'écran ne reste plus figé 5 à 6 s avant le départ ; les
    shaders des tuiles, des arbres, des objets OSM et du décor vivant (cyclistes, voitures, bateaux, foules) sont
    préparés un par un sous le menu.
- SUIVI :
  - [ ] AC6 : premier affichage du monde à froid, une doublure de shader par image avant le départ (shader_warm.gd).
