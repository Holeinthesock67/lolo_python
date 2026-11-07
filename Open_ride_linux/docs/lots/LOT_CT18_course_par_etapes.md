# Lot CT18 – Course par étapes (trois étapes au temps cumulé)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : course par étapes (trois étapes au temps cumulé) | Python, GDScript | CT0, CT8, CT13 | Moyenne | Prêt (version 5.0, choisi par le propriétaire le 7 novembre) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`. Idée retenue par le propriétaire le 7 novembre parmi les pistes pour renforcer la tactique et la diversité du jeu, avec une consigne : **ne pas nuire à la compréhension ni à la lisibilité du jeu** (la réputation des bots et la lecture imparfaite de leur réserve ont été écartées pour cette raison).

## 1. Objectif

Ajouter une gestion sur plusieurs jours : une course de trois étapes (circuits générés de CT8 : plat, vallonné, col), classement au temps cumulé, avec une réserve qui ne se recharge qu'en partie entre deux étapes.

## 2. À lire

`docs/5.0/PLAN_SERIE_CT.md`, `docs/5.0/CHARTE_CARTOON_CT9.md`, `docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md`, `core/src/openride_core/tools/tactical_sim.py`, `docs/SPECIFICATION_GENERALE.md` §7.1 (boutons), `docs/contracts/ipc_v1.md`.

## 3. Prérequis

CT0, CT8, CT13 livrés.

## 4. Travail demandé

- Fichier d'état de la course par étapes dans le dossier du profil (série MJ) : étape en cours, temps cumulés, réserve de départ de chaque coureur.
- Récupération entre étapes : W′ de départ de l'étape suivante = 100 % moins une part de ce qui a été dépensé au-dessus de la CP (valeur de `balance.toml`, 30 % par défaut, à régler au simulateur), pour le joueur comme pour les bots.
- Bonifications : secondes aux trois premiers de chaque étape (10, 6, 4 s), une seule règle de plus.
- Les étapes se jouent un jour chacune ou d'affilée ; une étape interrompue se reprend (lot de reprise de séance).
- Simulateur : `tactical_sim --etapes` ; critère : le vainqueur du général n'est pas toujours celui qui gagne le plus d'étapes.
- **Simulateur d'abord** : la règle est ajoutée à `tactical_sim` et le rapport CT0 régénéré avant tout branchement dans la séance.
- **Sécurité** : comme toute la série, rien ne passe par la résistance du trainer ; seuils en % de la FTP ; SIM seulement.

## 5. Lisibilité (consigne du 7 novembre)

Écran de l'étape : général en 5 lignes au départ et au bilan ; pendant la course, une seule ligne « Général : 2ᵉ à 12 s ».
Règles communes : une seule information nouvelle à la fois à l'écran, une explication d'une phrase au premier usage (une fois par profil), et une maquette validée par le propriétaire avant tout code d'affichage, en low, medium et high.

## 6. Modifications de contrat autorisées

Aucun pendant la course (le temps cumulé est calculé au bilan) ; menu de la course par étapes par les commandes de menu existantes.

## 7. Critères d'acceptation

1. `pytest -q` (et les tests de l'engine pour la partie affichage) passent.
2. Le critère du simulateur décrit au §4 est tenu, et le rapport CT0 régénéré reste dans ses propres critères.
3. Maquettes et captures validées par le propriétaire avant fusion.
4. Recette sur le vélo en étapes de 10 min au plus (CT12).

## 8. Hors périmètre

Ce qui n'est pas décrit au §4 ; la réputation des bots et la lecture imparfaite de leur réserve (écartées le 7 novembre).
