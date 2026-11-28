# GF5 : test de la circulation coupé en trois fichiers

- PR : à venir ; fil « Fiabiliser les outils de banc » (27 novembre 2026) ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Tests de l'engine : la séance « véhicules et cyclistes du décor ensemble » (16 graines, 80 % du temps de
    `test_traffic_model.gd`, 95 s sur 120 s de délai en CI) passe dans `test_traffic_mixed_a.gd` et
    `test_traffic_mixed_b.gd` (8 graines chacun, séance commune `tests/traffic_test_ride.gd`), mêmes contrôles.
- SUIVI :
  - [ ] GF5 : test_traffic_model coupé en trois (16 s, 48 s, 51 s au cloud au lieu de 122 s).
