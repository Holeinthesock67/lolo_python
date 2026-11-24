# RZ1 : remettre à zéro les statistiques d'un profil

- PR : #991 ; cahier : docs/lots/LOT_RZ1_remise_a_zero_statistiques.md ; version : 2.0
- CHANGELOG (section « Ajouté ») :
  - « Gérer : <profil en cours> › Remettre à zéro mes statistiques » : niveau, expérience, pièces, défis, cartes, records, équipement acheté et cotes des bots repartent de zéro (avant une saison de la ligue, par exemple). Séances et FIT (historique du coach), cote Elo du cycliste, nom, FTP, poids, FC max, réglages, derniers choix et plan gardés.
  - Rien n'est effacé : sauvegarde datée faite avant, dans `~/OpenRide/Profils/.remises_a_zero/` ; « Annuler la remise à zéro » remet les statistiques d'avant. Confirmation aux boutons écrits (« Non, garder mes statistiques » par défaut), exigée aussi par le core ; en ligne de commande : `openride-core profil remise-a-zero | remises | annuler-remise`.
  - Contrat IPC révision 1.31 : `reset_profile_stats`, `undo_profile_reset`, `profiles.resets`.
- SUIVI :
  - [ ] Remise à zéro des statistiques d'un profil (lot RZ1, révision IPC 1.31) : « Gérer : <profil en cours> › Remettre à zéro mes statistiques » ; date de départ des statistiques (`remise_stats.toml`, `progression.recompute(since=…)`), séances, FIT, coach et cote du cycliste gardés ; sauvegarde datée avant tout (`Profils/.remises_a_zero/`), « Annuler la remise à zéro » ; `openride-core profil remise-a-zero | remises | annuler-remise`. Recette : remise à zéro sur le PC avant la ligue d'hiver (28 novembre).
