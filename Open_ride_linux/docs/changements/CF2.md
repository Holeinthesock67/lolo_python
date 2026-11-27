# CF2 : révision IPC calculée, les PR de protocole ne se bloquent plus

- PR : à venir ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Révision du contrat IPC tenue dans un registre (`core/src/openride_core/revisions_ipc/`) : `CONTRACT_REV` vaut la
    dernière révision numérotée, plus une par révision en attente (un fichier par lot dans `a_numeroter/`). Une PR
    qui change le contrat n'écrit plus la ligne `CONTRACT_REV` ni son assertion : deux PR de protocole ne se
    gênent plus et passent dans le même train. Valeur annoncée et contrat inchangés (1.36 sur main).
- CHANGELOG (section « Ajouté ») :
  - `scripts/numeroter_revisions.py` : donne leur numéro aux révisions en attente sur la branche du train
    (`--ecrire`), met le journal d'`ipc_v1.md` à jour ; `--migrer LOT` passe une PR ouverte au registre.
  - `avant_poussee.py` : échec si une branche de lot réécrit `CONTRACT_REV` à la main ou change `historique.txt`.
- SUIVI :
  - [ ] CF2 : révision IPC calculée (registre `revisions_ipc/`, `scripts/numeroter_revisions.py`).
