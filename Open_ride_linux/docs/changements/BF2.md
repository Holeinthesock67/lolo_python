# BF2 : banc des menus à caches de rendu vides jugé à froid

- PR : #1109 ; cahier : docs/lots/LOT_BF2_banc_menus_froid.md ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Banc des menus : un passage parti sans cache de rendu (HOME neuf) est noté « froid », et la sonde juge alors le
    départ à 1 s au lieu de 150 ms, comme le banc simulé.
- SUIVI :
  - [ ] BF2 : marque `shaders.txt` à côté de la sonde (menu_bench), lue par `perf_probe.py report` (`--shaders`).
