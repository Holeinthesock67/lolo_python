# PA1 : profils abîmés protégés (revue de code S5-01 et S5-05)

- PR : à venir ; cahier : aucun (constats S5-01 et S5-05 de la revue de code vague 1, `statut/revue-code-vague1/S5.md`) ; version : 6.0
- Contrat IPC : inchangé (aucune révision prise). Les messages passent par les fenêtres du lanceur.
- CHANGELOG (section « Corrigé ») :
  - Un `profile.json` abîmé (équipement, achats, vies, avatar) est repris de sa copie et la copie est remise en place : le lancement suivant ne repart plus des valeurs par défaut. Trois copies tournent (`.bak`, `.bak.2`, `.bak.3`), le fichier abîmé est gardé sous `profile.json.corrompu-…`, une fenêtre le dit au joueur.
  - Un `profil.toml` illisible ne fait plus démarrer le jeu sur l'autre joueur ni sur un profil `principal` neuf : le lanceur propose de le réparer (ancien fichier gardé sous `profil.toml.illisible-…`, nom, FTP, poids et tables encore lisibles repris) ; sur refus, il s'arrête avec un message.
- SUIVI :
  - [ ] PA1 : profils abîmés (S5-01 copie remise en place et rotation de trois copies ; S5-05 profil illisible jamais remplacé, réparation proposée par le lanceur, rien d'effacé). Remise à zéro (RZ1) et sauvegardes (SV1) inchangées : la remise déplace le profil avec ses copies.
