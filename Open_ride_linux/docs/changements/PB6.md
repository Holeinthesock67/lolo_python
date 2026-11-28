# PB6 : bilan protégé du second appui de « Terminer et enregistrer »

- PR : à venir ; retours de jeu du 28 novembre (run Cyber-Rogue, retour au calme écourté) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Terminer une séance par A maintenu ne fait plus sauter le bilan : le Click renvoyait parfois un second A maintenu 0,8 s plus tard, qui validait « Menu principal » sur le bilan à peine ouvert (séance pourtant enregistrée). Pendant 1,5 s après « Terminer et enregistrer », A, Y et Z sont ignorés sur le bilan ; + et − naviguent toujours.
- SUIVI :
  - [ ] PB6 : garde du bilan dans menu_flow.gd (`SUMMARY_GUARD_S`), journal du 28/11 11h13 : end_session 11:13:25,625, FINISHED 11:13:26,412, second A_LONG 11:13:26,414, puis retour à l'accueil.
