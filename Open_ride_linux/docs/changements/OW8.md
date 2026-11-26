# OW8 : monde ouvert, révisions de route en rafale

- PR : #1105 ; cahier : docs/lots/LOT_OW8_revisions_en_rafale.md ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Monde ouvert : quand la route s'arrête (sens unique au bout d'une impasse), le générateur ne republie plus la
    même route deux fois par seconde ; l'écran ne se fige plus et le décor n'est plus refait en boucle (Tromsø).
  - Monde ouvert : une révision qui ne change pas la route (tuiles arrivées) ne reconstruit ni la route ni le
    décor, et l'image n'attend plus les tronçons de bâtiments de l'ancienne route.
- SUIVI :
  - [ ] OW8 : révisions identiques supprimées (`_extend`), `same_route` dans `live_world.gd`, travaux orphelins
    dans les streamers. À rejouer : `ow_zone_tromso` en medium.
