# EN1b : essai d'endurance, manches de la ligue closes après l'arrivée

- PR : à venir ; cahier : docs/lots/LOT_EN1_essai_endurance.md ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Essai d'endurance (`engine/tests/essai_endurance.py`) : depuis RT2 l'arrivée ne ferme plus la séance ; le banc
    demande le bilan (`end_session`) une fois l'issue de la manche connue, ferme une séance restée ouverte avant la
    manche suivante et court chaque manche sur le parcours de son terrain (anneau, vélodrome, ligne finie en côte).
    Essai rJ24D : manche 1 jamais close (91 min, sans place), manches 2 et 3 sans READY.
- SUIVI :
  - [ ] EN1b : saison de l'essai d'endurance courue jusqu'au bout depuis la règle d'arrivée de RT2.
