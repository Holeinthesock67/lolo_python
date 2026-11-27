# EC1 : retour au menu après une séance

- PR : à venir ; revue de code vague 3 (E2-01, E2-02, E2-03, E2-04, E2-05) ; engine seul (menus), ni core ni IPC
- CHANGELOG (section « Corrigé ») :
  - Monde ouvert : après une balade, le menu garde le parcours choisi avant elle. Il n'y a plus de bandeau d'erreur au retour au menu, ni de ligne « Parcours : ow:… » à l'accueil, ni de « Session libre › Démarrer » sans effet.
  - Cyber-Rogue : une run préparée puis quittée avant le départ ne laisse plus la séance suivante partir sans parcours (pente nulle, pas d'arrivée). L'écran « Composition de la run… » a une sortie : Y revient à l'écran de départ, et sans réponse du core le menu y revient seul avec un message.
  - Liste des parcours : le filtre « Étiquette » fait défiler les étiquettes de la liste affichée ; toutes sont atteignables, y compris dans la liste d'un mode.
  - Séance arrêtée par une erreur (contrôle du trainer refusé) : le bilan de la séance enregistrée s'affiche, au lieu d'un écran « Pause » ou « Prêt » aux actions sans effet.
- SUIVI :
  - [ ] EC1 : retour au menu après une séance (E2-01 à E2-05), tests `engine/tests/unit/test_revue_code_ec1.gd`.
