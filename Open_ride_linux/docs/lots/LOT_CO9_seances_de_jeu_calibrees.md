# Lot CO9 – Séances de jeu calibrées au besoin

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : course contre bots, Cyber-Rogue, Dernier survivant… avec bots et circuit calibrés au besoin, vérifiés au simulateur | Python | CO1, CO2, T13, O15, X27 (CT8 pour les circuits générés) | Moyenne | En PR (version 5.0, avec CO3 et CO6) |

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

## 5. Réalisation (7 novembre, en PR avec CO3 et CO6)

- `core/src/openride_core/coach_game.py` et table `[game]` de `coach.toml` : un format par besoin, dans l'ordre (récupération : balade seule sur un parcours sans pente de plus de 2 % ; aérobie léger : sortie avec 4 bots à 65 % de la FTP, sans attaque, montées de moins de 2 min ; aérobie intense : course contre 4 bots à 95 %, tactique complète, montée principale de 4 à 10 min ; anaérobie : Dernier survivant, 4 adversaires, une arche par kilomètre). D'autres formats (Cyber-Rogue, Course tactique, vélodrome) s'ajoutent par une ligne de la table quand leur simulation existera.
- Parcours : les parcours prêts du catalogue et leurs fiches O15 ; le circuit généré de CT8 entrera par le même catalogue.
- Vérification : cycliste virtuel aux valeurs du joueur (stratégie `pente` de `sim_rider.py`, puissance de montée fixée par le format, sprints aux arches), tronçon de 100 m par tronçon à la vitesse d'équilibre des fiches, tours jusqu'au temps disponible ; format proposé si le temps prédit dans les zones du besoin atteint 70 % de celui de l'entraînement conseillé (sinon d'une part de la durée, `reference_pct`), sinon format suivant, sinon `route` reste `null` (entraînement ERG seul). Un tour complet de la vraie séance à 50 Hz (`tools/bots_race.py`) dépasse le budget de 2 s : il sert à la recette sur le PC (CO7).
- Sortie : objet `route` du message `coach` et de `--json` (mode, parcours, tours, durée, bots, réglages du survivant, temps prédit, temps de référence, part en %), à côté de l'entraînement (Q10) ; option `--routes` de `openride-core coach`.
- Reste à faire avec l'écran (CO5) : lancement par l'engine (`select_route` puis `start` avec les réglages du mode) et ligne « Besoin du jour » du bilan.
- Tests : `core/tests/test_coach_jeu.py` (format retenu et réglages de chaque besoin, temps prédit par le cycliste virtuel, format écarté sous 70 %, aucun format possible, conseil avec la séance de jeu, parcours du catalogue et budget de 2 s dans le conteneur).

