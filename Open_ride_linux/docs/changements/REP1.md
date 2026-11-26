# REP1 : répétition du samedi 28/11 (sauvegarde, restauration, remise à zéro, saison 1, manche 1)

- PR : à venir (empilée sur SV1, #1018) ; scénario `engine/tests/menu_scenarios/repetition_samedi.json` ; file du PC
  `scripts/file_bancs/repetition_samedi.toml` ; version : 6.0
- CHANGELOG (section « Ajouté ») :
  - Banc des menus : scénario `repetition_samedi`, la procédure du samedi 28/11 jouée de bout en bout sur un profil
    d'essai du HOME temporaire (copie de la semaine au lancement, restauration, remise à zéro, « Commencer la
    saison 1 », manche 1 jusqu'au bilan par Y puis A maintenu) ; `choisir` accepte un motif avec `*`.
- SUIVI :
  - [ ] Répétition du samedi (lot REP1) : scénario `repetition_samedi` OK sur le PC en medium (nuit du 25 au 26/11),
    remplace la fumée du jeudi 26/11.
