# Lot GP5 – Équilibrage au banc simulé

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : simulateur de courses (cycliste virtuel X27 et bots), rapport et valeurs de `grandprix.toml` | Python | GP1, GP3 | Moyenne | Livré le 8 novembre (PR #779, version 4.0), cibles tenues |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Régler forces, poids et fréquences pour que le mode soit amusant sans être une loterie.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §3 et §4.2 ; `core/src/openride_core/sim_rider.py` (X27) ; `core/src/openride_core/sim_scenarios.py`.

## 3. Travail demandé

- Outil `grandprix_sim` : N courses simulées par configuration (adversaires, chaos, niveau du joueur), rapport Markdown.
- Cibles (course juste, choix du propriétaire le 8 novembre) : à niveau égal, le joueur gagne sa part, entre 0,5/(N + 1) et 1,5/(N + 1) des courses ; plus faible que les bots, aucune cible de victoires (pas de rattrapage fort, la course reste juste) ; aucun objet ne représente plus de 35 % du temps total gagné ou perdu.
- Valeurs retenues écrites dans les valeurs par défaut de `grandprix.toml`.

## 4. Critères d'acceptation

1. Rapport joint à la PR, avec les trois niveaux de chaos et 2, 4 et 11 bots.
2. Les cibles sont tenues, ou l'écart est expliqué et soumis au propriétaire.

## 5. Livraison (8 novembre 2026)

- Outil `python -m openride_core.tools.grandprix_sim` (`core/src/openride_core/tools/grandprix_sim.py`) : courses de 10 km en ligne, physique du core, abri en une dimension sur la voie, règles du mode et bots du lot GP3 ; cycliste virtuel à puissance constante, mené par le même cerveau que les bots (`GrandPrixMode(bots=...)` accepte le cycliste pour ce banc) ; forme du jour ± 3 % ; rejouable à l'octet près quel que soit `--jobs` ; `--values` essaie un fichier au format de `grandprix.toml`.
- Rapport : `docs/4.0/RAPPORT_EQUILIBRAGE_GP5.md` (200 courses par configuration, 2, 4 et 11 bots, trois chaos, niveaux 100 et 90 %).
- Correctif : le temps gagné des objets pour soi à durée (super-forme, voiture d'équipe) n'était pas compté au bilan (`summary.gp.gained_s`), seul le coup de fouet l'était.
- Valeurs : celles du lot GP1, gardées. Écarts : à niveau égal, part juste (1/(N + 1)) aux variations près, la borne basse n'est donc tenue qu'à moitié ; à 10 % sous les bots, 0 à 2 % de victoires au lieu de 10 %. Les compenser demanderait des objets de rattrapage qui font une loterie. Le propriétaire a choisi le 8 novembre de garder une course juste : cibles du §3 réécrites en ce sens, toutes tenues.
- Furtif : aucun gain de temps compté (l'effet `breakaway` agit sur l'abri de TT2, pas sur la vitesse) ; il sert à voler l'objet du coureur devant.
