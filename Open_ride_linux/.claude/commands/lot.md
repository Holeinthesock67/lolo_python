---
description: Réalise un lot de travail de docs/lots/ de bout en bout (branche, code, tests, docs, fusion)
argument-hint: <identifiant du lot, ex. F, B2, E1>
---

Réalise le lot $ARGUMENTS d'OpenRide.

1. Lis `docs/lots/00_INDEX.md` (règles communes et statut), puis `docs/lots/LOT_$ARGUMENTS_*.md` et les documents de sa section « À lire ».
   - Si le lot est déjà livré, ou si une dépendance n'est pas livrée, arrête-toi et dis-le.
2. Crée la branche `lot-<id>-<sujet>` depuis `main` à jour.
   - Ne touche qu'aux fichiers autorisés par le lot, et jamais hors de `Open_ride_linux/`.
3. Fais le travail. Chaque critère d'acceptation vérifiable par machine doit avoir son test.
4. Fais passer toutes les suites (voir `/tests`). Coche chaque critère avec la commande qui le prouve.
5. Mets à jour la documentation :
   - section « Livraison » à la fin du lot (date, critères tenus, écarts assumés) ;
   - statut dans `00_INDEX.md` ;
   - `docs/SUIVI_AVANCEMENT.md` ;
   - `README.md` si les commandes changent ;
   - suivi de l'audit si un constat est corrigé.
6. Avant toute fusion dans `main`, demande confirmation à Laurent. Fusion en `--no-ff`, avec un message en français.
   - Après la fusion, donne-lui la commande pour récupérer : `cd /home/depret/Games/lolo_python && git checkout main && git pull`.
7. Termine par un résumé court en français :
   - ce qui est fait ;
   - les écarts ;
   - les essais à faire sur le matériel.

Si un contrat paraît faux ou incomplet, arrête-toi et pose la question plutôt que de l'interpréter.
