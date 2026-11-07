# Lot CT16 – Plan de course des bots annoncé au départ

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : plan de course des bots annoncé au départ | Python, GDScript | CT0, CT1, CT3 | Moyenne | Prêt (version 5.0, choisi par le propriétaire le 7 novembre) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`. Idée retenue par le propriétaire le 7 novembre parmi les pistes pour renforcer la tactique et la diversité du jeu, avec une consigne : **ne pas nuire à la compréhension ni à la lisibilité du jeu** (la réputation des bots et la lecture imparfaite de leur réserve ont été écartées pour cette raison).

## 1. Objectif

Rendre chaque course différente, même sur le même circuit : au départ, chaque bot tire un plan de course (« arrivée groupée », « durcir dans la bosse », « échappée matinale », « attendre le sprint ») annoncé au joueur. Le joueur décide qui laisser partir, qui marquer, avec qui rouler.

## 2. À lire

`docs/5.0/PLAN_SERIE_CT.md`, `docs/5.0/CHARTE_CARTOON_CT9.md`, `docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md`, `core/src/openride_core/tools/tactical_sim.py`, `docs/SPECIFICATION_GENERALE.md` §7.1 (boutons), `docs/contracts/ipc_v1.md`.

## 3. Prérequis

CT0, CT1, CT3 livrés.

## 4. Travail demandé

- Plans en données dans `tactical/balance.toml` (5 plans au plus), tirés selon le profil et le circuit avec la graine de la course : un plan règle les paramètres de CT3 (moment des attaques, envie de rouler, intérêt pour les primes de CT15).
- Le bot suit son plan tant que sa réserve le permet ; il peut en changer une fois si la course le rend impossible (échappée reprise), annoncé de la même façon.
- Simulateur : `tactical_sim` tire les plans ; critère : sur un même circuit, au moins trois profils différents gagnent plus de 10 % des courses.
- **Simulateur d'abord** : la règle est ajoutée à `tactical_sim` et le rapport CT0 régénéré avant tout branchement dans la séance.
- **Sécurité** : comme toute la série, rien ne passe par la résistance du trainer ; seuils en % de la FTP ; SIM seulement.

## 5. Lisibilité (consigne du 7 novembre)

Une carte d'une ligne par bot à l'écran de départ (icône du profil, nom, plan), puis un rappel discret dans le bandeau des voisins (T16) ; jamais plus de deux plans affichés pendant la course.
Règles communes : une seule information nouvelle à la fois à l'écran, une explication d'une phrase au premier usage (une fois par profil), et une maquette validée par le propriétaire avant tout code d'affichage, en low, medium et high.

## 6. Modifications de contrat autorisées

Champ `plan` des éléments de `bots` et liste des plans dans `hello_ack.config`, dans la révision de CT1.

## 7. Critères d'acceptation

1. `pytest -q` (et les tests de l'engine pour la partie affichage) passent.
2. Le critère du simulateur décrit au §4 est tenu, et le rapport CT0 régénéré reste dans ses propres critères.
3. Maquettes et captures validées par le propriétaire avant fusion.
4. Recette sur le vélo en étapes de 10 min au plus (CT12).

## 8. Hors périmètre

Ce qui n'est pas décrit au §4 ; la réputation des bots et la lecture imparfaite de leur réserve (écartées le 7 novembre).
