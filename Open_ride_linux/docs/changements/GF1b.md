# GF1b : banc à vitesse imposée sur la pente du parcours

- PR : à venir ; garde-fou 1 du fil « Fiabiliser les outils de banc » (27 novembre 2026) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Banc simulé `--speed-kmh` : braquet neutre tenu (appuis du Click et changements de watts du scénario retirés) ;
    la vitesse imposée était faussée par les appuis du scénario `demo` (49 km/h pour 40, banc rDPS1, main aussi).
  - Vérification « pente envoyée = pente du parcours » : écart médian au-delà de 0,5 point hors abri = banc faussé,
    code 2 (ENVIRONNEMENT) au lieu d'un échec de la PR.
- SUIVI :
  - [ ] GF1b : sim_bench --speed-kmh à braquet neutre, pente envoyée contrôlée (code 2 si faussée).
