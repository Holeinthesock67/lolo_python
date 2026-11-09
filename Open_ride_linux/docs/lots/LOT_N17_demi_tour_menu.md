# Lot N17 – Demi-tour sur la route depuis l'écran de pause

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série N : demi-tour sur la route depuis l'écran de pause | Python + GDScript | 1.0 publiée | Moyenne | En PR : contrat IPC 1.9, core, écran de pause, caméra et HUD (8 novembre), **version 1.x** |

## 1. Objectif

Faire demi-tour sur le parcours en cours, sans quitter la séance : le cycliste met en pause (Y), choisit « Faire demi-tour » dans l'écran de pause, et repart dans l'autre sens au même endroit. Demande du propriétaire du 27 octobre (décision D11 de l'audit de cohérence) : le demi-tour se fait **dans les menus**, pas par un geste du Click, pour ne pas entamer le plan de boutons commun (spécification générale §7.1). Version 1.x.

## 2. À lire

1. `docs/SPECIFICATION_GENERALE.md` §5.1 (exigence 1.x-UI-1) et §7.1 ; `docs/SRS_v1.1.md` §5 (physique) et §14 ; `docs/contracts/ipc_v1.md` (commandes, `state`) ; `docs/lots/LOT_N6_affichage_menus.md` (écran de pause).
2. Code : `core/src/openride_core/session.py`, `core/src/openride_core/route.py` (interpolation à `s`), `core/src/openride_core/physics.py`, `engine/scripts/main.gd`, `engine/scripts/route_data.gd`, le modèle de l'écran de pause.

## 3. Prérequis

La 1.0 publiée (étiquette `v1.0.0`) ; lot de contrat suivant la règle du §6.1 de la spécification générale (première révision libre à la fusion, sauf fusion avant `v1.0.0` : révision 1.3).

## 4. Travail demandé

- **Contrat :** commande `u_turn` (acceptée en `PAUSED` seulement ; sinon `error` `busy`) ; champ facultatif `dir` de `state` (`1` dans le sens du parcours, `-1` à rebours, absent vaut `1`).
- **Core :** le sens inverse fait décroître `s` ; la pente envoyée au trainer et celle de la physique changent de signe ; arrivée au départ du parcours = fin du parcours comme à l'arrivée normale ; journal : événement `u_turn` avec `s` ; le FIT garde la distance parcourue croissante.
- **Bots et fantôme :** ils continuent dans leur sens ; l'aspiration ne s'applique qu'entre cyclistes de même sens.
- **Segments (série T, si présents) :** un passage à rebours ne compte pas.
- **Engine :** entrée « Faire demi-tour » dans l'écran de pause, avec confirmation (A long valide, Y revient, §7.1) ; caméra et HUD (profil, distance restante) dans le nouveau sens.

## 5. Fichiers concernés

- **Modifiés :** `session.py`, `ipc_server.py`, schémas `cmd` et `state`, `ipc_v1.md`, `main.gd`, `route_data.gd`, modèle et vue de l'écran de pause, tests du core et de l'engine, spécification générale, index, suivi.

## 6. Modifications de contrat autorisées

Commande `u_turn`, champ `dir` de `state` (ajouts compatibles).

## 7. Critères d'acceptation

1. Tests du core et de l'engine au vert.
2. Parcours de démonstration en simulé : demi-tour à 3 km, retour au départ, la séance se termine au km 0 avec 6 km parcourus dans le FIT.
3. Pente du trainer de signe opposé sur le même tronçon, à 0,1 point près.
4. Écran de pause : l'entrée se choisit et se valide au Click selon le §7.1 et au clavier.

## 8. Hors périmètre

Demi-tour automatique au bout d'un parcours aller simple, demi-tour en monde ouvert (la série W choisit déjà les branches).

## 9. Livraison (8 novembre 2026, une PR)

- **Contrat, révision 1.9** (la 1.8 est réservée à la collection de cartes, lot BC2) : commande `u_turn` acceptée en `PAUSED` seulement ; champ `dir` de `state` écrit à `-1` à rebours, absent dans le sens du parcours ; `grade` donné dans le sens roulé ; `lane_m` reste dans le repère de la route. Refus `busy` aussi pendant une run Cyber-Rogue, en monde ouvert (hors périmètre, §8), en Dernier survivant et en Grand Prix des objets (courses à arches ou à distance fixée), et au départ d'un parcours en ligne.
- **Core :** `RiderPhysics` porte le sens (`direction`) et la distance parcourue (`distance`, toujours croissante) ; `s` décroît à rebours. Pente du terrain, anticipation de la latence, pente envoyée et cap du vent retournés ; départ du parcours = arrivée. Journal : événement `u_turn` (`s`, `distance`, `dir`), relevés avec `distance` croissante et, après un demi-tour, la position `pos` ; le FIT garde la distance croissante. Reprise après un plantage : position, distance et sens repris du journal.
- **Bots et fantôme :** ils gardent leur sens. À rebours, le cycliste n'est plus dans les groupes des bots ni dans leur abri, et il n'a lui-même ni abri ni aspiration (personne dans son sens) ; la circulation l'évite sur l'autre moitié de la route.
- **Segments :** un passage en cours est annulé au demi-tour ; à rebours rien ne compte (en direct et à la relecture du journal, qui lit `pos`) ; `segment`, `bot_ahead` et `bot_behind` ne sont plus remplis.
- **Engine :** entrée « Faire demi-tour » de l'écran de pause après « Abandonner », avec confirmation (focus sur « Non », A long valide, Y revient), montrée sur un parcours seulement ; caméra, avatar, tronçons et tuiles, inclinaison, vent ressenti, profil d'altitude, prochaine montée et repères des bots dans le nouveau sens ; distance du HUD et de la fiche de la pause croissante (`ridden_distance.gd`).
- **Tests :** `core/tests/test_u_turn.py` (critère 2 : demi-tour à 3 km, fin au km 0, 6 km au FIT ; critère 3 : pente envoyée opposée à 0,1 point près au braquet neutre ; refus, double demi-tour, segments, bots, reprise) ; engine : `test_menu_model.gd` et `test_menu_flow.gd` (critère 4), `test_camera_follow_lag.gd`, `test_hud_view_model.gd`.
- **Reste :** captures des trois qualités (low, medium, high) à valider par le propriétaire avant la fusion ; mesures sur le PC par le fil de fusion.
