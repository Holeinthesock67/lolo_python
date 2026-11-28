# SOL-TUNNELS : contrôle du sol au-dessus de la route dans les tunnels

- PR : à venir (empilée sur #984) ; cahier : aucun (correctif du contrôle) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Contrôle « sol sous la chaussée » (`test_herbe_route.gd`) : dans un tunnel, le terrain n'est pas dessiné
    dans le tube (lot EA5) ; un point de la chaussée dans ce volume n'est plus compté « sol au-dessus », les portails
    et les approches restent contrôlés. Fin des faux échecs du banc multi-zones (Tromsø +63 m, Biarritz +15 m).
- SUIVI :
  - [ ] Contrôle du sol à jour des tunnels : monde d'essai `tunnel-essai.world` dans `run_engine_tests.sh`.
