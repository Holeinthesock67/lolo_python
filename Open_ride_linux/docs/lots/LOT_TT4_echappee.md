# Lot TT4 – Échappée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série TT : bonus Échappée (les suiveurs perdent ton abri et ne répondent pas à ton attaque pendant 20 s) | Python | TT2, AS1, Y10 | Moyenne | Prêt (version 4.0) |

Série TT (bonus tactiques, version 4.0). Plan de la série : `docs/4.0/PLAN_SERIE_TT.md`, recommandations retenues par le propriétaire le 29 octobre (« ok pour tout », §6 du plan). Cahier rédigé le 8 novembre 2026 (le plan les annonçait, aucun n'existait).

## 1. Objectif

Fusion du Burrito et du Fantôme (décision du 29 octobre) : pendant 20 s, les bots derrière le cycliste ne reçoivent plus son abri et ne suivent pas son attaque.

## 2. À lire

Plan §2 ; `core/src/openride_core/draft.py` (abri donné aux suiveurs, zone 2D d'AS2) ; `docs/lots/LOT_Y10_comportement_bots_core.md` (règle de réponse aux attaques) ; `core/src/openride_core/bot_tactics.py`.

## 3. Travail demandé

- Effet `breakaway` : abri donné aux suiveurs annulé (en 1D, puis dans le cône de la zone 2D d'AS2) ; bots aveugles à l'attaque dans la règle de réponse de Y10.
- Conditions : au moins un bot ; refus à moins de 400 m de l'arrivée ou de la fin d'un sprint (`near_finish`).
- Marque `breakaway` déjà utilisée par le Furtif du Grand Prix (GP4) : même ligne de table.

## 4. Critères d'acceptation

1. Un suiveur collé perd environ 14 m (1,4 s) sur 20 s (test sur une course simulée).
2. Aucun effet sur l'abri que reçoit le cycliste.

## 5. Fichiers touchés

`core/src/openride_core/draft.py`, `core/src/openride_core/bot_tactics.py`, `core/src/openride_core/powerups.py`, tests.
