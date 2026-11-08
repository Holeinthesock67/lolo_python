# Lot CO6 – Courses et prochaine course dans le conseil

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : causes de perte des courses disputées (S5) et prochaine course (S6), règles R1, R2 et R7 complètes | Python | CO1, DS2, T4 (livrés sauf CO1) ; CT13 quand il existe | Moyenne | En PR (version 5.0, avec CO3) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Faire entrer les courses dans le conseil : récupérer après une course, s'affûter avant, et travailler ce qui coûte des places.

## 2. Travail demandé

- Lecture des journaux de course existants (lignes `survivor_summary` du Dernier survivant, segments chronométrés T4, courses avec bots) : cause de perte « montée », « sprint », « fin de course » ou aucune, selon les règles du plan §4 ; rien n'est déduit quand le journal ne permet pas de le dire.
- Le journal des courses de la Course tactique (CT13) est lu dès qu'il existe, par la même fonction.
- Prochaine course (CO3) : R2 deux jours avant, R1 le lendemain.

## 3. Critères d'acceptation

`pytest -q` passe ; un cas synthétique par cause, un journal de course sans cause lisible, et une course annoncée dans 2 jours.

## 4. Réalisation (7 novembre, en PR avec CO3)

- `coach.race_of` (pur) : Dernier survivant (lignes `survivor_start`, `survivor`, `survivor_summary`) : éliminé avec une pente moyenne de plus de 3 % sur la minute d'avant → aérobie intense ; éliminé à moins de 2 s → anaérobie ; sinon plus de 10 % de puissance perdue entre le premier et le dernier quart → aérobie léger ; vainqueur ou rien de lisible : aucune cause. Run Cyber-Rogue (`rogue_run`) et course contre les bots hors ERG (relevés avec `draft`) : le journal ne dit pas où le cycliste a perdu, seule la baisse de puissance est lue. Les sprints chronométrés T4 ne gardent pas l'écart au journal : rien n'en est déduit. Seuils dans `[races]` de `coach.toml`.
- Lignes de jeu gardées par `session_summary.load_session` (champ `games`, `journal.GAME_KINDS`) ; faits mis en cache avec une version (`FACTS_VERSION` 2 : les faits d'avant CO6 sont recalculés).
- R1 : course lue hier (avec son TSS), ou course annoncée (CO3) dont le jour était hier. R2 : course annoncée dans 1 à 2 jours (CO3).
- R7 : la cause qui revient au moins 2 fois sur les 3 dernières courses des 4 semaines départage, avant le profil de puissance (« battu au sprint 2 fois sur tes 3 dernières courses »).
- `details.races` dans `--json` et le message `coach` (journal du contrat, révision 1.12). Le journal CT13 sera lu par `race_of` quand il existera.
- Tests : `core/tests/test_coach_courses.py` (un cas par cause, journal sans cause lisible, vainqueur, autres journaux, R1, R7, course annoncée hier et dans 2 jours, lecture d'un journal et version du cache).

