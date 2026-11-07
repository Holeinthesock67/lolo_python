# Lot CT17 – Équipes : deux coéquipiers bots et deux ordres au Click

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : équipes : deux coéquipiers bots et deux ordres au Click | Python, GDScript | CT1, CT3, CT16 | Grande | Prêt (version 5.0, choisi par le propriétaire le 7 novembre) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`. Idée retenue par le propriétaire le 7 novembre parmi les pistes pour renforcer la tactique et la diversité du jeu, avec une consigne : **ne pas nuire à la compréhension ni à la lisibilité du jeu**, la lisibilité étant ici la compréhension tactique de la course (la réputation des bots et la lecture imparfaite de leur réserve ont été écartées pour cette raison).

## 1. Objectif

Ajouter le jeu d'équipe : le joueur court avec deux coéquipiers bots contre une ou deux équipes adverses. Le poisson pilote, le sacrifice pour le leader et le contrôle d'une échappée deviennent possibles.

## 2. À lire

`docs/5.0/PLAN_SERIE_CT.md`, `docs/5.0/CHARTE_CARTOON_CT9.md`, `docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md`, `core/src/openride_core/tools/tactical_sim.py`, `docs/SPECIFICATION_GENERALE.md` §7.1 (boutons), `docs/contracts/ipc_v1.md`.

## 3. Prérequis

CT1, CT3, CT16 livrés.

## 4. Travail demandé

- Équipes de 3 (joueur et deux bots) contre une ou deux équipes de 3 bots, maillots aux couleurs de l'équipe (série MJ, maillots des bots).
- Deux ordres au Click, sans nouveau bouton : Z long (aujourd'hui l'Overdrive) devient, en mode équipes, un choix entre « roulez pour moi » (les coéquipiers prennent la tête et protègent le joueur de l'abri) et « attaquez » (un coéquipier part, les adversaires doivent répondre). Le plan des boutons §7.1 est mis à jour, sans exception par mode.
- Bots coéquipiers (CT3) : ils ne répondent pas aux attaques du joueur, ils relaient pour lui, ils lancent le sprint du leader (poisson pilote) si l'arrivée est groupée.
- Simulateur : équipe du cycliste virtuel avec ses deux ordres ; critère : une équipe bien commandée gagne plus qu'une équipe sans ordres, sans dépasser 45 %.
- **Simulateur d'abord** : la règle est ajoutée à `tactical_sim` et le rapport CT0 régénéré avant tout branchement dans la séance.
- **Sécurité** : comme toute la série, rien ne passe par la résistance du trainer ; seuils en % de la FTP ; SIM seulement.

## 5. Lisibilité tactique (consigne du 7 novembre)

Les coéquipiers ont un liseré de la couleur de l'équipe ; l'ordre en cours s'affiche en une icône près de la jauge de capacités ; pas d'ordre possible pendant 10 s après le précédent.
Ici, lisibilité veut dire **compréhension tactique** (précision du propriétaire du 7 novembre) : le joueur doit comprendre ce qui se passe dans la course, pourquoi un bot agit, et pourquoi il a gagné ou perdu. Règles communes :
- **Cause visible** : chaque décision d'un bot que la règle provoque est annoncée avec sa raison, en une ligne du bandeau des voisins (par exemple « Grimpeur attaque : réserve 80 %, bosse à 5 % »).
- **Conséquence prévisible** : avant de s'engager, le joueur sait ce que coûte un choix (réserve dépensée, points ou secondes en jeu), sans calcul de tête.
- **Bilan qui explique** : le bilan nomme au plus trois moments décisifs de la course (« course perdue au km 6 : 12 s dans la bordure, mal placé à l'entrée ») à partir des événements du core.
- **Simulateur** : chaque victoire du rapport CT0 est rattachée à un moment décisif (attaque, catapulte, bordure, prime…) ; une victoire sans moment décisif identifiable est un défaut de la règle.
- Une seule information nouvelle à la fois à l'écran, une phrase d'explication au premier usage (une fois par profil), et une maquette validée par le propriétaire avant tout code d'affichage, en low, medium et high.

## 6. Modifications de contrat autorisées

Champs `team` des coureurs et `order` de `state.tactical`, commande ou événement de l'ordre, dans la révision de CT1 ou la suivante.

## 7. Critères d'acceptation

1. `pytest -q` (et les tests de l'engine pour la partie affichage) passent.
2. Le critère du simulateur décrit au §4 est tenu, et le rapport CT0 régénéré reste dans ses propres critères.
3. Maquettes et captures validées par le propriétaire avant fusion.
4. Recette sur le vélo en étapes de 10 min au plus (CT12).

## 8. Hors périmètre

Ce qui n'est pas décrit au §4 ; la réputation des bots et la lecture imparfaite de leur réserve (écartées le 7 novembre).
