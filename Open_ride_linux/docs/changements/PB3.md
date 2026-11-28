# PB3 : puissance du HUD lissée comme en Cyber-Rogue

- PR : à venir ; retours de jeu du 28 novembre (manche 1, Course en tours) ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Le grand chiffre de la puissance en haut à gauche (et sa couleur de zone) est lissé sur environ 8 s, comme la puissance affichée en Cyber-Rogue : il ne saute plus à chaque coup de pédale. Mesure perdue : « — » tout de suite, comme avant.
- SUIVI :
  - [ ] PB3 : moyenne de `power_3s` sur 5 s dans hud_view_model.gd (`POWER_DISPLAY_S`, `shown_power_w`) ; ligne de diagnostic inchangée.
