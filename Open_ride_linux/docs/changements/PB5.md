# PB5 : Cyber-Rogue, tunnels de cadence plus larges et boss plus vivant

- PR : à venir ; retours de jeu du 28 novembre (run Cyber-Rogue, seuil 30 min) ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Salle du Diesel : les tunnels de cadence acceptent 90 ± 8 rpm au lieu de ± 3 (le 28/11, 18 % du temps dans ± 3 : la salle était perdue).
  - Boss : 5 cibles Z en phase 1 au lieu de 4 et une cible Z entre deux ondes de choc en phase 2. Ondes de choc de la phase 3 prêtes mais coupées (`p3_shock_period_s = 0`), à essayer.
- SUIVI :
  - [ ] PB5 : `tunnel_tolerance_rpm` 8, `p1_locks` 5, `p2_strikes` 1, `p3_shock_period_s` (balance.toml, rooms.py) ; trames de référence et filet « à l'identique » régénérés.
