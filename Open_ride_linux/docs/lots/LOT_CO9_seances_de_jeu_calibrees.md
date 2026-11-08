# Lot CO9 – Séances de jeu calibrées au besoin

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : course contre bots, Cyber-Rogue, Dernier survivant… avec bots et circuit calibrés au besoin, vérifiés au simulateur | Python | CO1, CO2, T13, O15, X27 (CT8 pour les circuits générés) | Moyenne | Prêt (version 5.0) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Demande du propriétaire du 7 novembre : la séance conseillée peut être une course contre les bots, une run Cyber-Rogue ou un autre mode, avec la difficulté et le circuit réglés pour travailler le besoin du jour (plan §4 ter).

## 2. Travail demandé

- Table des formats par besoin dans `coach.toml` (plan §4 ter) : mode, tactique des bots (Y10), force des bots en % de la FTP, forme du circuit (longueur des montées, bosses courtes, sprints), durée.
- Choix du circuit : fiches des parcours (O15 : montée principale, dénivelé, durée estimée) ; circuit généré de CT8 quand il existe.
- Vérification : séance simulée en temps accéléré avec le cycliste virtuel aux valeurs du joueur (`sim_rider.py`, `tools/bots_race.py`, `tools/rogue_sim.py`, `tools/tactical_sim.py`) ; proposée seulement si le temps prédit dans les zones du besoin atteint 70 % de l'entraînement équivalent, sinon format suivant, sinon entraînement ERG seul.
- Lancement : mêmes réglages que le menu du mode (bots, parcours, difficulté de la pente laissée au joueur) ; ligne « Besoin du jour » ajoutée au bilan, calculée avec les zones de `session_summary`.

## 3. Tests

Un cas synthétique par besoin (format retenu, réglages, temps prédit) ; format écarté quand la simulation n'atteint pas 70 % ; aucun format possible → entraînement ERG.

## 4. Critères d'acceptation

`pytest -q` passe ; le calcul d'un conseil avec simulation reste sous 2 s sur le PC (à mesurer via le fil de fusion, pas de lancement direct).
