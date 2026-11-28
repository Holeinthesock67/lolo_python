# EC6 : menu du monde ouvert, liste des lieux et carte demandée

- PR : à venir ; revue de code vague 3 (engine), constats E3-01, E3-02, E3-03 ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Recherche d'un lieu : au-delà de 8 lieux trouvés (le core en rend jusqu'à 50), la liste défile avec le choix
    et « 13 / 20 » dit où l'on est ; A ne valide plus un lieu invisible. Pendant la saisie à la grille, les
    3 premiers lieux et « 20 lieux en tout ».
  - Carte : une carte demandée puis quittée par Y pendant « Chargement de la carte… » ne s'affiche plus pour le
    lieu suivant (réponse comparée à la demande par son identifiant, puis par son centre), et le départ n'est
    plus décalé par les routes d'un autre lieu.
  - Noms longs d'OpenStreetMap : un lieu par ligne (nom jusqu'à la deuxième virgule, puis « … » à la largeur
    de la colonne) ; la liste et son explication restent au-dessus du bandeau des boutons. Le core coupe le nom
    à 80 caractères, comme le dit le schéma `places` (il coupait à 120).
- SUIVI :
  - [ ] EC6 : menu du monde ouvert (E3-01 liste au-delà de 8 lieux, E3-02 carte d'un lieu quitté, E3-03 noms longs).
