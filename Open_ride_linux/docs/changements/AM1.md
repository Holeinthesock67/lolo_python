# AM1 : pas d'herbe ni de rochers sur les amorces de chaussée

- PR : (à venir) ; cahier : aucun (défaut des bancs du monde ouvert du 26/11) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Plus de touffes d'herbe ni de rochers sur le bout de route dessiné avant le départ et après l'arrivée d'une
    balade (bancs d'Almería et de Funchal : 308 et 2 252 touffes sur la chaussée).
- SUIVI :
  - [ ] Garde-fou de la chaussée (road_clearance.gd) : les amorces de road_builder.gd (100 m avant le départ, 200 m
    après l'arrivée, routes ouvertes) font partie de l'axe tenu dégagé, pour les touffes d'herbe (grass_tufts.gd),
    les détails de sol (ground_details.gd) et volcano_fx.gd ; test `_test_lead_tufts` de test_road_clearance.gd.
