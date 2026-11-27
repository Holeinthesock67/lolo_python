# EC4 : piste, Grand Prix et WTF (revue de code vague 3, lot E11)

- PR : à venir ; revue de code vague 3 engine (E11-01 à E11-06, `statut/REVUE_CODE_3_ENGINE.md`) ; engine seul, ni core ni IPC
- CHANGELOG (section « Corrigé ») :
  - Piste : avec 7 adversaires ou plus, les noms des coureurs ne clignotent plus avec leur identifiant (« bot7 ») dans la liste, les écarts, la consigne et le tableau de la salle.
  - Piste : avec 8 adversaires ou plus, la liste de gauche et le tableau de la salle gardent toujours ta ligne et celle du dernier menacé d'élimination.
  - Omnium : éliminé dans l'épreuve d'élimination, tu as un bandeau passager « Éliminé · 5e sur 8 » ; la course aux points garde sa consigne, et le résultat final de l'omnium est annoncé.
  - Grand Prix : à la fin de la course, boîtes, objets, averses et halos ne restent plus figés dans le décor derrière le bilan et les menus.
  - Grand Prix : deux usages rapprochés du même objet ont chacun leur mot et leur son ; après une pause, un mot n'est plus rejoué.
  - WTF : une séance arrêtée pendant « Monde à l'envers », une vue imposée ou « Vélo minuscule » ne laisse plus la caméra retournée ni le cycliste minuscule au départ de la séance suivante.
- SUIVI :
  - [ ] EC4 : piste, Grand Prix et WTF (E11-01 à E11-06), tests dans `engine/tests/unit/test_track_hud.gd`, `test_gp_scene.gd` et `test_wtf_scene.gd`.
