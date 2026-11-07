# Lot CO2 – Classement des entraînements par besoin

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : entraînements classés par besoin + 3 séances livrées (récupération, anaérobie, sprints) | Python + .zwo | CO0, O12, O25 (livrés sauf CO0) | Petite | Prêt (version 5.0, après les réponses à CO0) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Savoir, pour chaque entraînement de la bibliothèque (livré, importé, créé au menu), quel besoin il travaille, et combler l'absence de séance d'anaérobie et de récupération.

## 2. Travail demandé

- `workout_need(workout, ftp_w) -> str` dans `coach.py` : besoin qui a le plus de temps au-dessus de Z2 dans les blocs ; récupération si tout est sous 55 % ; même table de bornes que CO1.
- Séances livrées (contenus de départ, lot O25) : `recuperation_40.zwo` (40 min sous 55 %), `anaerobie_8x30s.zwo` (8 × 30 s à 150 %, 3 min de récupération), `sprints_10x10s.zwo` (10 × 10 s à 200 %, 2 min 50 de récupération), noms définitifs selon la réponse Q6.
- Choix de la séance (plan §3) : durée la plus proche du temps disponible, puis la moins faite sur 28 jours ; sinon parcours conseillé (fiches de O15) ou message vers Réglages › Contenus.

## 3. Critères d'acceptation

1. `pytest -q` passe ; chaque séance livrée est classée dans le besoin attendu ; les séances livrées passent les tests de lecture `.zwo` existants.
2. Contenus de départ : les nouvelles séances s'installent sans rien écraser.
