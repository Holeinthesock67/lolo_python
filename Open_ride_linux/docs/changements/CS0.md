# CS0 : mesure du style « dessin animé » sur le PC cible

- PR : #1023 (avec CS1) ; cahier : plans/EXPLORATION_CELL_SHADING_2026-11-22.md (dossier du projet), §8.2 ; version : 6.0
- CHANGELOG (section « Ajouté ») :
  - Rien ne change pour le joueur. Outillage : essais de rendu `contours`, `contours_px`, `contours_m`, `paliers` et `saturation` (variable `OPENRIDE_RENDER_DIAG`), variantes `ombres_nettes` et `cs_*` de `engine/tests/cout_rendu.py`, file `scripts/file_bancs/cs0_dessin_anime.toml` (environ 2 h 15 sur le PC, trois qualités).
- SUIVI :
  - [ ] CS0 : coût des contours, des paliers et du style complet mesuré sur la GTX 1060 (tableau `cout.md` et planche), décision B1 / B2 pour les contours du décor.
