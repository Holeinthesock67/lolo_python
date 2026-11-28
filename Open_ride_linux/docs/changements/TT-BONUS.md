# TT-BONUS : bonus plus longs et plus forts, temps gagné affiché

- PR : #1093 ; cahier : docs/lots/LOT_TTBONUS_bonus_plus_forts.md ; version : 4.0 ; contrat IPC : révision numérotée à la fusion
- CHANGELOG (section « Modifié ») :
  - Bonus : la Plume, le Casque aéro et la Puissance durent 30 s et sont plus forts (masse × 0,8, CdA × 0,6, puissance × 1,20) : 4 à 5 s gagnées sur leur terrain au lieu de 1 s, enfin sensibles sur le vélo.
  - À la fin d'un bonus, le HUD dit le temps qu'il a fait gagner (« Casque aéro : +4,2 s ») pendant 6 s.
- SUIVI :
  - [ ] TT-BONUS : bonus plus forts et temps gagné affiché (`powerup.gain`, révision IPC du lot), tests `core/tests/test_tt_bonus_gain.py`, recette vélo du propriétaire.
