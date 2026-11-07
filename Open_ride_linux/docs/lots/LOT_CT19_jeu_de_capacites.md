# Lot CT19 – Jeu de capacités choisi avant la course (3 parmi 6)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : jeu de capacités choisi avant la course (3 parmi 6) | Python, GDScript | CT6, TT2 à TT5 | Moyenne | Prêt (version 5.0, choisi par le propriétaire le 7 novembre) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`. Idée retenue par le propriétaire le 7 novembre parmi les pistes pour renforcer la tactique et la diversité du jeu, avec une consigne : **ne pas nuire à la compréhension ni à la lisibilité du jeu** (la réputation des bots et la lecture imparfaite de leur réserve ont été écartées pour cette raison).

## 1. Objectif

Diversifier les façons de jouer : avant la course, le joueur choisit 3 capacités parmi 6 du catalogue de la 4.0 (série TT). Chaque choix donne un style (rouleur, attaquant, sprinteur) et il existe des contres.

## 2. À lire

`docs/5.0/PLAN_SERIE_CT.md`, `docs/5.0/CHARTE_CARTOON_CT9.md`, `docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md`, `core/src/openride_core/tools/tactical_sim.py`, `docs/SPECIFICATION_GENERALE.md` §7.1 (boutons), `docs/contracts/ipc_v1.md`.

## 3. Prérequis

CT6, TT2 à TT5 livrés.

## 4. Travail demandé

- Catalogue : les effets de la série TT (`breakaway`, `aero`, plume, enclume…) et le bouclier d'inertie de CT6, sans nouvel effet.
- Choix au menu de départ (écran simple, trois cases) ; les capacités non choisies ne peuvent pas être achetées pendant la course ; Z court et Z long gardent leur sens (CT6), sur les 3 capacités choisies.
- Contres en données : par exemple l'Échappée ne marche pas contre un coureur qui a le Casque aéro actif à moins de 10 m.
- Simulateur : chaque jeu de 3 capacités joué 200 fois ; critère : aucun jeu ne gagne plus de 45 %, et au moins trois jeux différents sont les meilleurs sur un circuit.
- **Simulateur d'abord** : la règle est ajoutée à `tactical_sim` et le rapport CT0 régénéré avant tout branchement dans la séance.
- **Sécurité** : comme toute la série, rien ne passe par la résistance du trainer ; seuils en % de la FTP ; SIM seulement.

## 5. Lisibilité (consigne du 7 novembre)

Trois cases fixes à l'écran, toujours dans le même ordre ; une capacité qu'on ne peut pas encore payer est grisée ; pas de nouvelle jauge.
Règles communes : une seule information nouvelle à la fois à l'écran, une explication d'une phrase au premier usage (une fois par profil), et une maquette validée par le propriétaire avant tout code d'affichage, en low, medium et high.

## 6. Modifications de contrat autorisées

Champ `loadout` de la commande de départ du mode et de `state.tactical`, dans la révision de CT1 ou la suivante.

## 7. Critères d'acceptation

1. `pytest -q` (et les tests de l'engine pour la partie affichage) passent.
2. Le critère du simulateur décrit au §4 est tenu, et le rapport CT0 régénéré reste dans ses propres critères.
3. Maquettes et captures validées par le propriétaire avant fusion.
4. Recette sur le vélo en étapes de 10 min au plus (CT12).

## 8. Hors périmètre

Ce qui n'est pas décrit au §4 ; la réputation des bots et la lecture imparfaite de leur réserve (écartées le 7 novembre).
