# IM1 et IM2 : interface commune des modes, trame puis fin de séance

- PR : #1113 (IM1), IM2 ; cadrage : plans/CADRAGE_INTERFACE_MODES_2026-11-22.md (série IM) ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Aucun changement à l'écran ni sur le vélo : rangement interne du core. Chaque mode de jeu a son adaptateur
    (`core/src/openride_core/game_modes/`) ; la trame (IM1), la fin de séance et le classement lu par la cote Elo
    et la ligue (IM2) passent par la table des modes. Journal, trames, bilan et consignes du trainer identiques
    (filet « à l'identique », 17 séances).
- SUIVI :
  - [ ] Série IM : IM1 (trame des modes) et IM2 (fin de séance, `ranking` pour la cote Elo et la ligue) fusionnés.
