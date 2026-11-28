# SR1 : route qui repasse au même endroit posée sur le sol

- PR : (à venir) ; cahier : aucun (défaut des bancs du monde ouvert du 26/11) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Monde ouvert : là où la balade repasse au même endroit (boucles, allers-retours), la route ne flotte plus
    au-dessus du sol (bancs de Funchal et d'Almería : jusqu'à 10 m de vide sous la route à relief ×1).
- SUIVI :
  - [ ] Règle sol / route (`road_ground.drop_covered_feet`, compilateur et jumelle du core) : un pied de talus qui
    tombe sur la chaussée d'un autre passage, ou tout près, garde sa demande d'appui si aucune chaussée d'une autre
    partie de la route à moins de 15 m ne la contredit (borne du pied 0,5 m sous la sienne, à 30 % de pente près) ;
    une route au-dessus d'une autre perd toujours ses pieds. Balade du monde ouvert (`session_ground.py`) et parcours
    compilés ; carrés du cache inchangés (`keep_compatible=False`, prochaine version du générateur). Tests
    `test_route_that_passes_again_keeps_its_banks`, `test_road_over_another_drops_its_feet`.
