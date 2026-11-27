# Lot IM0 – Filet « à l'identique » des modes de jeu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série IM (interface commune des modes) : séances scriptées par mode, empreintes de référence comparées octet pour octet | Python | — | Moyenne | En revue |

Série IM, premier lot du cadrage « une interface commune pour les modes de jeu » (22 novembre 2026, dossier du projet :
`plans/CADRAGE_INTERFACE_MODES_2026-11-22.md`, §4 et §5.2). Tests seulement : aucune ligne du jeu ne change, ni l'IPC,
ni l'engine, ni l'écran.

## 1. Objectif

Avant de ranger la colle des modes de `session.py` dans des adaptateurs (IM1 à IM9), poser un filet qui dit si une
refonte change quoi que ce soit : pour chaque mode, une séance scriptée et déterministe, dont on relève le journal,
une trame `state` sur dix pas, le bilan, la suite des consignes envoyées au trainer, les messages envoyés à l'engine et
les fichiers écrits. Chaque relevé est réduit à une empreinte SHA-256, gardée dans le dépôt.

## 2. Séances

`core/tests/identique_scenarios.py`, une fonction par cas du cadrage :

| Cas du cadrage | Séances |
| --- | --- |
| 1. Session libre | `libre` : 3 bots, braquets, Z, pause, bots changés, demi-tour à l'arrêt et en roulant |
| 2. Course | `course` : boucle de 1 km, 3 tours, 7 adversaires, arrivée, cote Elo |
| 3. Grand Prix | `grandprix` : objets (Z), voies (A, flèches), voitures d'équipe, pause de 3 s, arrivée |
| 4. Dernier survivant | `survivant_continuer`, `survivant_terminer` : cycliste éliminé, réglage `after_out` ride et end |
| 5. WTF | `wtf` : cinq règles jouées, plat du chef refusé, refus de l'ERG |
| 6. Piste | `piste_scratch`, `piste_poursuite`, `piste_americaine` (relais), `piste_libre_erg` |
| 7. Cyber-Rogue | `rogue_gagnee` (boss battu), `rogue_perdue` (trois défaites), `rogue_reprise` (core relancé) |
| 8. Ligue | **reportée au lot IM8**, qui sort la ligue de `session.py` (rien ne touche à la ligue avant la saison 1) |
| 9. Refus | `refus` : chaque refus de `start`, `set_ride_mode`, `set_bots` et `u_turn`, par mode, avec son texte |
| 10. Fin forcée | `fin_sans_enregistrer`, `fin_arret_du_core`, `fin_trainer_refuse` |

## 3. Déterminisme

`core/tests/identique.py` fige, le temps d'une séance : l'horloge murale (`time.time`, `strftime`, `localtime`,
`datetime.now` et `date.today` de la séance et du mode classique, fuseau UTC), les `random.Random()` créés sans graine
(graine 1234 : bonus en réserve du mode classique), et pose un profil de joueur neuf dans le dossier temporaire.
Le code du jeu n'est pas touché. Vérifié : mêmes octets d'un passage à l'autre, avec un autre `PYTHONHASHSEED`, en
3.13 et en 3.14. En 3.11, l'instantané `pickle` du Cyber-Rogue et l'arrondi d'une trame diffèrent : la comparaison
y est sautée.

Constats relevés en écrivant le filet (rien de corrigé ici, comportement figé tel quel) :

- la graine des bonus du mode classique n'est pas tirée de l'horloge comme les autres : `ClassicRace` crée ses bonus
  avec `random.Random()` sans graine (à reprendre avec RC1 et IM3, même classement après reprise) ;
- en Course, les refus de `set_ride_mode` disent « Le Grand Prix des objets se joue en SIM seulement. » (texte du
  Grand Prix ; la Course est un `GrandPrixMode(mode="race")`). Le cadrage garde les textes mot pour mot : à corriger
  dans un lot à part, puis `--maj`.

## 4. Lancement

```bash
(cd core && pytest -q tests/test_modes_identique.py)    # ~1 min 30, marque slow
python3 scripts/modes_identique.py                      # rejoue et dit ce qui a changé
python3 scripts/modes_identique.py --maj                # référence réécrite (changement voulu, à dire dans la PR)
python3 scripts/modes_identique.py --releve A           # relevés complets, pour comparer deux versions
```

## 5. Livraison (26 novembre 2026)

- Tests : `core/tests/identique.py`, `core/tests/identique_scenarios.py`, `core/tests/test_modes_identique.py`,
  référence `core/tests/data/modes_identique.json` ; outil `scripts/modes_identique.py`.
- Docs : `docs/OUTILS_DE_TEST.md` §1, `docs/PLAN_DE_TESTS.md` §3.1 ; durée du fichier dans `scripts/durees_tests.json`.
- Bancs : aucun (tests du core seulement, CI et cloud).
