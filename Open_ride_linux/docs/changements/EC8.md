# EC8 : décor vivant, véhicules retenus, bots en pause et cyclistes proches

- PR : à venir ; revue de code vague 3 engine (E6-01, E6-02, E6-03, `statut/REVUE_CODE_3_ENGINE.md`) ; core `traffic.py` et engine, sans changement d'IPC (le champ `v` de `vehicles` garde son sens : la vitesse du véhicule)
- CHANGELOG (section « Corrigé ») :
  - Circulation : une voiture retenue derrière un bot ou un cycliste du décor ne tremble plus d'avant en arrière et ses roues tournent à sa vraie vitesse : le core envoie la vitesse réellement tenue, plus sa vitesse de croisière.
  - Pause : les bots ne glissent plus vers l'avant (jusqu'à 1,7 m à 40 km/h) et ne se posent plus dans le vélo du cycliste.
  - Qualité basse et moyenne : les cyclistes du décor et les véhicules à moins de 60 m sont toujours dessinés ; ils n'apparaissent et ne disparaissent plus à quelques mètres du joueur (le budget du préréglage ne coupe qu'au-delà).
- SUIVI :
  - [ ] EC8 : décor vivant (E6-01, E6-02, E6-03), tests `core/tests/test_traffic.py` (véhicule retenu), `engine/tests/unit/test_bots_view_model.gd` (pause) et `engine/tests/unit/test_drawn_budget.gd` ; à voir au banc : cyclistes du décor en `low`.
