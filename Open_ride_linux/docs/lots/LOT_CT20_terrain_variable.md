# Lot CT20 – Terrain qui change : bordures, pluie et pavés

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : terrain qui change : bordures, pluie et pavés | Python, GDScript | CT7, CT8, AS3, U (surfaces) | Moyenne | Prêt (version 5.0, choisi par le propriétaire le 7 novembre) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`. Idée retenue par le propriétaire le 7 novembre parmi les pistes pour renforcer la tactique et la diversité du jeu, avec une consigne : **ne pas nuire à la compréhension ni à la lisibilité du jeu**, la lisibilité étant ici la compréhension tactique de la course (la réputation des bots et la lecture imparfaite de leur réserve ont été écartées pour cette raison).

## 1. Objectif

Faire compter le placement autant que les watts : des sections de vent de travers où l'éventail se forme (bordures, série AS3), une pluie qui baisse l'adhérence en virage (vitesse critique de CT7) et des secteurs pavés (surfaces de la série U, résistance au roulement plus forte).

## 2. À lire

`docs/5.0/PLAN_SERIE_CT.md`, `docs/5.0/CHARTE_CARTOON_CT9.md`, `docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md`, `core/src/openride_core/tools/tactical_sim.py`, `docs/SPECIFICATION_GENERALE.md` §7.1 (boutons), `docs/contracts/ipc_v1.md`.

## 3. Prérequis

CT7, CT8, AS3, U (surfaces) livrés.

## 4. Travail demandé

- Circuits générés (CT8) avec des sections marquées « vent de travers », « pavés » et une météo de la course (sec ou pluie), tirées avec la graine.
- Vent de travers : le modèle d'abri d'AS3 tel quel (zone abritée décalée, bordure) ; pluie : μ plus bas dans `√(μ g R)` (CT7) ; pavés : Crr de la série U, sous le même plafond de pente envoyée que le vent.
- Bots (CT3) : se placer avant une section annoncée (ils remontent le groupe 500 m avant), et lever le pied en virage sous la pluie.
- Simulateur : critère : sur un circuit avec bordure, un coureur mal placé à l'entrée perd en moyenne plus de 10 s.
- **Terrain du rouleur** (choix recommandé le 7 novembre) : les sections de bordure sont le terrain du rouleur (le faux plat revient au baroudeur) ; ce lot retire le rouleur de `PENDING_TERRAIN` dans `tactical_sim.py`, et le rapport CT0 doit le montrer premier bot d'au moins un circuit à bordure.
- **Simulateur d'abord** : la règle est ajoutée à `tactical_sim` et le rapport CT0 régénéré avant tout branchement dans la séance.
- **Sécurité** : comme toute la série, rien ne passe par la résistance du trainer ; seuils en % de la FTP ; SIM seulement.

## 5. Lisibilité tactique (consigne du 7 novembre)

Chaque section est annoncée 1 km avant par un panneau et une icône (vent, goutte, pavé) ; une seule annonce à la fois ; les effets au sol suivent la charte cartoon (CT9).
Ici, lisibilité veut dire **compréhension tactique** (précision du propriétaire du 7 novembre) : le joueur doit comprendre ce qui se passe dans la course, pourquoi un bot agit, et pourquoi il a gagné ou perdu. Règles communes :
- **Cause visible** : chaque décision d'un bot que la règle provoque est annoncée avec sa raison, en une ligne du bandeau des voisins (par exemple « Grimpeur attaque : réserve 80 %, bosse à 5 % »).
- **Conséquence prévisible** : avant de s'engager, le joueur sait ce que coûte un choix (réserve dépensée, points ou secondes en jeu), sans calcul de tête.
- **Bilan qui explique** : le bilan nomme au plus trois moments décisifs de la course (« course perdue au km 6 : 12 s dans la bordure, mal placé à l'entrée ») à partir des événements du core.
- **Simulateur** : chaque victoire du rapport CT0 est rattachée à un moment décisif (attaque, catapulte, bordure, prime…) ; une victoire sans moment décisif identifiable est un défaut de la règle.
- Une seule information nouvelle à la fois à l'écran, une phrase d'explication au premier usage (une fois par profil), et une maquette validée par le propriétaire avant tout code d'affichage, en low, medium et high.

## 6. Modifications de contrat autorisées

Champs `section` (type, distance) et `weather` de `state.tactical`, dans la révision de CT1 ou la suivante.

## 7. Critères d'acceptation

1. `pytest -q` (et les tests de l'engine pour la partie affichage) passent.
2. Le critère du simulateur décrit au §4 est tenu, et le rapport CT0 régénéré reste dans ses propres critères.
3. Maquettes et captures validées par le propriétaire avant fusion.
4. Recette sur le vélo en étapes de 10 min au plus (CT12).

## 8. Hors périmètre

Ce qui n'est pas décrit au §4 ; la réputation des bots et la lecture imparfaite de leur réserve (écartées le 7 novembre).
