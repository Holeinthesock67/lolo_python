# PB1 : conseil « Passe dans une boîte » seulement en Grand Prix, et seulement quand utile

- PR : à venir ; retours de jeu du 28 novembre (manche 1, Course en tours) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - En Course (sans boîte ni objet), Z n'affiche plus « Z refusé : aucun objet · Passe dans une boîte « + BONUS » » et la zone de consigne n'en parle plus.
  - En Grand Prix, la consigne « Passe dans une boîte « + BONUS » » n'apparaît plus en permanence : seulement quand une boîte libre est en vue sur ta voie (150 m devant).
- SUIVI :
  - [ ] PB1 : conseil des boîtes limité au Grand Prix et aux boîtes en vue (refusal_model.gd, gp_hud_model.gd).
