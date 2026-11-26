# BM1 : base qui bouge, contrôle de fraîcheur avant la fusion

- PR : à venir ; rapport : statut/FIABILITE_CI_BANCS_2026-11-26.md (dossier du projet) ; version : 6.0
- CHANGELOG (section « Ajouté ») :
  - `scripts/avant_poussee.py --avant-fusion` : juste avant de fusionner un train, en quelques secondes, refuse la
    fusion si main a changé depuis la base du train un fichier que le train touche aussi, ou un fichier partagé
    (contrat IPC, scène principale de l'engine, garde-fou des tests) : la CI verte ne valait que pour l'ancien main.
- CHANGELOG (section « Corrigé ») :
  - CI : les captures des flancs comparent la PR à sa base au début du run, et non au main du moment (un train
    fusionné pendant le run les déclenchait sur une PR sans rapport, #1088).
- SUIVI :
  - [ ] BM1 : fraîcheur de la base avant la fusion (`avant_poussee.py --avant-fusion`) et étape des flancs sur la base de la PR.
