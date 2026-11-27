# EC9 : records du parcours et photo d'arrivée

- PR : (à venir) ; revue de code vague 3 engine (E12-01, E12-02) ; engine seul, ni core ni IPC
- CHANGELOG (section « Corrigé ») :
  - « Records du parcours » (écran Prêt) affiche de nouveau les temps : l'écran lit les records du profil en cours (`~/OpenRide/Profils/<profil>/records.json`), là où ils sont écrits depuis les profils, au lieu de l'ancien `~/OpenRide/records.json` supprimé par la migration. Tous les segments affichaient « aucun temps ».
  - Une séance terminée ou abandonnée depuis la pause ne prend plus de « photo d'arrivée » : l'image aurait été celle du menu de pause, et le bilan l'annonçait comme l'arrivée.
- SUIVI :
  - [ ] EC9 : records du profil et photo d'arrivée (E12-01, E12-02), tests `test_records_view_model.gd`, `test_photo_moments_model.gd` et scénario du banc des menus `records_profil`.
