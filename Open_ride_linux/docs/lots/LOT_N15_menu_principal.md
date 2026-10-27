# Lot N15 – Menu principal : monde, session libre, session ERG, session simulée

## 1. Objectif

Demande du propriétaire du 26 octobre : après l'écran de connexion des appareils (lot N13), arriver sur un menu qui permet de modifier les options, de lancer une vraie session, une vraie session en mode ERG ou une session simulée, et de choisir le monde (la carte). Ce lot réorganise l'accueil du menu du lot N6.

**Lot interne :** aucun ajout au contrat IPC ; un code de sortie de l'engine en plus pour le lanceur `openride`.

## 2. Accueil

Décision D10 du 27 octobre (audit de cohérence) : l'entrée s'appelle « Parcours » (« Monde ouvert » est réservé à la série W) et l'accueil n'affiche que les modes annoncés par `hello_ack.config.modes`.

| Élément | Effet |
| --- | --- |
| « Parcours : … » | Liste des parcours ; le choix (`select_route`) revient à l'accueil, qui affiche le nom du parcours choisi |
| « Session libre » | Mode SIM sans entraînement (`select_workout` à `null`), puis écran « Prêt » ; sans parcours choisi, passe d'abord par la liste des parcours |
| « Session ERG » | Liste des entraînements (sous-menu ERG du lot N16), puis écran « Prêt » ; sans parcours choisi, passe d'abord par la liste des parcours |
| « Session simulée » | Confirmation, puis l'engine sort avec le code 65 : le lanceur relance le core avec le HomeTrainer, le Click et la ceinture simulés (`--trainer sim --input sim --hr sim --sim-scenario nominal`) et l'engine avec `--sim-session` ; l'accueil s'appelle alors « OpenRide — session simulée » et propose « Revenir au matériel réel » (code 64) |
| « Réglages » | Appareils (lot N13) ; réglages (lot O4) |
| « Quitter » | Avec confirmation |

Écran « Prêt » : titre « Prêt : session libre — parcours » ou « Prêt : session ERG — parcours », « Démarrer », « Changer d'entraînement » (ou « Passer en session ERG »), « Changer de parcours ». Après le bilan, « Nouvelle séance » recharge le monde choisi (le core reste en FINISHED jusqu'au prochain `select_route`).

## 3. Livraison (26 octobre 2026)

- `menu_model.gd` : nouvel accueil, monde choisi (`set_world`), mode de la séance, session simulée (`set_sim_session`), retour vers « Prêt » focus sur « Démarrer » ; `menu_flow.gd` : monde repris de la trame d'état et des noms de la liste des parcours, monde rechargé après le bilan ; `menu_view.gd` : quatre éléments visibles quand l'état des appareils est affiché ; `engine_args.gd` : `--sim-session` ; `main.gd` : codes de sortie 64 et 65.
- `launcher.py` : `EXIT_SIM` (65), `sim_core_cmd()`, mode simulé gardé pour les relances après plantage ; tests `test_sim_session_code_relaunches_core_in_simulation_then_back`, `test_sim_core_cmd_replaces_hardware_options`.
- Tests : `test_menu_model.gd` (accueil à six entrées, monde, session libre, ERG, simulée, retour au matériel), `test_menu_flow.gd`, tests graphiques (accueil et liste des mondes), banc des menus `engine/tests/menu_bench.py`, parcours `sessions` (monde, session libre démarrée, pause, bilan, nouvelle séance, session ERG démarrée, « Session simulée » : code 65).
- Modes de l'accueil tirés d'une table `HOME_MODES` filtrée par `modes` (`set_modes`, lu dans `hello_ack.config.modes` quand le core l'annoncera en 2.0 ; absent : session libre et ERG) : un mode de la 2.0 (Cyber-Rogue, lot R13 de la PR #244) n'ajoutera qu'une ligne ; contrat de la 1.0 inchangé.
- Reste (propriétaire) : essai depuis l'icône, au Click réel ; passage en session simulée puis retour au matériel réel par le lanceur.
