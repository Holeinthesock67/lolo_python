# Lot TT3 – Aspiration +

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série TT : bonus Aspiration + dans `draft.py` (abri × 1,5 plafonné à 0,55, portée 25 m, 35 s) | Python | TT2, AS1 (AS4 souhaitable) | Petite | En revue (version 4.0) |

Série TT (bonus tactiques, version 4.0). Plan de la série : `docs/4.0/PLAN_SERIE_TT.md`, recommandations retenues par le propriétaire le 29 octobre (« ok pour tout », §6 du plan). Cahier rédigé le 8 novembre 2026 (le plan les annonçait, aucun n'existait).

## 1. Objectif

Donner au cycliste un abri plus fort et plus long pendant 40 s, tiré seulement quand il y a des bots.

## 2. À lire

Plan §2 ; `core/src/openride_core/draft.py` (courbe exponentielle P3, zone latérale AS2, plafond du cœur de groupe AS4).

## 3. Travail demandé

- Effet `draft` de la table TT2 : multiplicateur 1,5 sur l'abri calculé, plafond 0,55, portée 15 → 25 m.
- Condition : au moins un bot dans la séance ; sinon refus `no_bots`.
- Le supplément de pente SIM suit l'abri (−1,0 → −1,4 point sur le plat).

## 4. Critères d'acceptation

1. Gain de 1,5 à 2,5 s roue dans la roue sur le plat (test).
2. Plafond 0,55 jamais dépassé, bots compris.

## 5. Fichiers touchés

`core/src/openride_core/draft.py`, `core/src/openride_core/powerups.py`, tests.
