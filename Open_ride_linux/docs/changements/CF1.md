# CF1 : PR ouvertes mises en conflit par la dernière fusion

- PR : à venir ; rapport : statut/FIABILITE_CI_BANCS_2026-11-26.md (dossier du projet) ; version : 6.0
- CHANGELOG (section « Ajouté ») :
  - `scripts/conflits_ouverts.py` : juste après une fusion dans main, liste en quelques secondes les PR ouvertes
    dont la fusion avec main ne passe plus (fichiers en conflit) ou dont la révision IPC, `WORLDGEN_VERSION` ou
    `SCHEMA_VERSION` est désormais prise par main (numéro à monter). Assemblage à blanc (`git merge-tree`), aucune
    branche touchée. Le 26/11, les PR mises en conflit par le train de 15h57 n'avaient été vues qu'à 17h28.
- SUIVI :
  - [ ] CF1 : PR ouvertes à prévenir après chaque fusion (`scripts/conflits_ouverts.py`).
