# OW-RECH1 : la recherche de lieu du monde ouvert affiche la réponse au dernier mot tapé

- PR : (à venir) ; bancs du 25 novembre (ea1_lac, rZONES) ; core et engine, IPC inchangé (le champ `request_cmd_id` de `places` existait déjà)
- CHANGELOG (section « Corrigé ») :
  - Monde ouvert : en tapant un nom (« sevrier »), la liste montrait parfois les lieux d'une saisie plus courte arrivés en dernier (« La Sevrie du Moulin », « Sevri, Inde ») et Entrée partait du mauvais endroit. Seule la réponse à la dernière recherche envoyée remplace la liste.
  - Nominatim n'est plus interrogé à chaque lettre : une requête à la fois, et seulement pour la saisie la plus récente (politique de Nominatim : pas d'autocomplétion).
- SUIVI :
  - [ ] OW-RECH1 : réponses de recherche dans le désordre ignorées (`world_menu_model.on_places`, `WorldMenu.new_search`), tests `core/tests/test_world_menu_ipc.py` et `engine/tests/unit/test_world_menu_model.gd`.
