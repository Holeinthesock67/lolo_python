# GF3 : auto-contrôle de l'outil de banc avant la file

- PR : à venir ; garde-fou 3 du fil « Fiabiliser les outils de banc » (27 novembre 2026) ; version : 6.0
- CHANGELOG (section « Ajouté ») :
  - File des bancs : avant toute étape, banc simulé court sur main (scénario demo, 40 km/h imposés, 150 s, low),
    une fois par commit de main. En défaut, rien n'est lancé (code 4, « OUTIL DE BANC EN DÉFAUT » en tête de
    etat.md). `[file] autocontrole = false` le coupe ; une chaîne le remplace.
- SUIVI :
  - [ ] GF3 : file_bancs, auto-contrôle de l'outil avant la file (après GF1b et GF4).
