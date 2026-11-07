# Lot CT15 – Primes en course : sprints et sommets à points

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : primes en course : sprints et sommets à points | Python, GDScript | CT0, CT1, T2, T14 | Moyenne | Prêt (version 5.0, choisi par le propriétaire le 7 novembre) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`. Idée retenue par le propriétaire le 7 novembre parmi les pistes pour renforcer la tactique et la diversité du jeu, avec une consigne : **ne pas nuire à la compréhension ni à la lisibilité du jeu** (la réputation des bots et la lecture imparfaite de leur réserve ont été écartées pour cette raison).

## 1. Objectif

Donner un choix tactique pendant la course : les sprints intermédiaires et les sommets rapportent des points (classement par points du mode), mais les disputer vide la réserve W′. Le joueur choisit entre les points et la victoire finale.

## 2. À lire

`docs/5.0/PLAN_SERIE_CT.md`, `docs/5.0/CHARTE_CARTOON_CT9.md`, `docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md`, `core/src/openride_core/tools/tactical_sim.py`, `docs/SPECIFICATION_GENERALE.md` §7.1 (boutons), `docs/contracts/ipc_v1.md`.

## 3. Prérequis

CT0, CT1, T2, T14 livrés.

## 4. Travail demandé

- Segments `sprint` et `climb` de la série T (`segments.py`, `segment_timing.py`) et barème des maillots du lot T14 (`jerseys.py`), sans nouveau barème : sprints 15/10/6/4/2, sommets selon la catégorie.
- Classement par points de la Course tactique (vainqueur du maillot vert du mode), en plus du classement à l'arrivée ; le bilan donne les deux.
- Bots (CT3) : chaque profil a son intérêt pour les primes (sprinteur pour les sprints, grimpeur pour les sommets, baroudeur pour tout ce qui passe pendant son échappée), réglé dans `tactical/balance.toml`.
- Simulateur : `tactical_sim` compte les points ; nouveau critère du rapport : aucune stratégie ne gagne à la fois la course et les points dans plus de 30 % des courses (sinon les primes ne coûtent rien).
- **Simulateur d'abord** : la règle est ajoutée à `tactical_sim` et le rapport CT0 régénéré avant tout branchement dans la séance.
- **Sécurité** : comme toute la série, rien ne passe par la résistance du trainer ; seuils en % de la FTP ; SIM seulement.

## 5. Lisibilité (consigne du 7 novembre)

Rien de plus à l'écran que l'annonce de la prime à 1 km (déjà faite par la série T) et le classement par points au bilan ; pendant la course, une seule ligne « Points : 2ᵉ à 4 pts ».
Règles communes : une seule information nouvelle à la fois à l'écran, une explication d'une phrase au premier usage (une fois par profil), et une maquette validée par le propriétaire avant tout code d'affichage, en low, medium et high.

## 6. Modifications de contrat autorisées

Champ `points` de `state.tactical` (rang, écart), dans la révision de CT1.

## 7. Critères d'acceptation

1. `pytest -q` (et les tests de l'engine pour la partie affichage) passent.
2. Le critère du simulateur décrit au §4 est tenu, et le rapport CT0 régénéré reste dans ses propres critères.
3. Maquettes et captures validées par le propriétaire avant fusion.
4. Recette sur le vélo en étapes de 10 min au plus (CT12).

## 8. Hors périmètre

Ce qui n'est pas décrit au §4 ; la réputation des bots et la lecture imparfaite de leur réserve (écartées le 7 novembre).
