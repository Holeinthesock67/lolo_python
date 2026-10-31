# Lot O19 – Aucune roue libre en ERG : consigne minimale de 50 W, test de FTP par la rampe seule

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Aucune roue libre en ERG : consigne minimale de 50 W (FreeRide = palier à 50 W), test de FTP par la rampe seule (20 min retiré) | Python + GDScript | O10, O18 (livrés) | Moyenne | Décision du propriétaire du 29 octobre ; en PR |

## 1. Objectif

Décision du propriétaire du 29 octobre : « aucune roue libre en ERG ». La matrice des boutons (X42) avait trouvé un cas sans règle : un bloc de roue libre au milieu d'un entraînement ERG, où la séance repassait en SIM. Le propriétaire a tranché. Une roue libre n'a pas de sens en ERG. Un bloc FreeRide d'un fichier est un cas de robustesse : il faut une consigne minimale de 50 W. Le test de FTP se fait par paliers croissants jusqu'à ce que le cycliste ne suive plus : c'est la rampe. Le test de 20 minutes, qui imposait 20 min de roue libre, est retiré (choix sur la carte de décision).

## 2. Spécification (validée par le propriétaire le 29 octobre)

| # | Règle |
| --- | --- |
| O19-1 | En ERG, la cible envoyée au trainer ne descend jamais sous 50 W (`ERG_MIN_W`), biais compris. Cela vaut pour un entraînement, l'ERG libre et l'ERG à cadence verrouillée (lot O18), qui partagent la même constante. |
| O19-2 | Un bloc `FreeRide` d'un `.zwo` devient un palier `steady` à 50 W en watts absolus. L'entraînement reste en ERG du premier au dernier bloc : `mode` vaut `ERG`, et le passage de bloc est lissé sur 2 s comme les autres. |
| O19-3 | Les boutons gardent la colonne ERG du §7.1 pendant tout l'entraînement : ± = biais, Z = bloc suivant. La ligne « braquet en roue libre » disparaît du plan des boutons. |
| O19-4 | Le test de FTP est la rampe seule (`ftp_test:ramp`) : paliers d'une minute, +20 W, jusqu'à l'échec, FTP = 75 % de la meilleure minute (lot O10). `ftp_test:20min` est refusé (ligne de commande, plan, commande `start`). Un ancien résultat `20min` du journal est ignoré. |
| O19-5 | Engine : plus de texte « Roue libre », plus de couleur ni de bande de roue libre. La couleur grise reste pour une case sans zone connue (FTP inconnue) sous le nom `NEUTRAL_BLOCK`. Au bilan, un bloc sans cible venu d'un ancien journal s'affiche « sans cible ». |

## 3. Contrat

`docs/contracts/ipc_v1.md` : `block_type` n'a plus la valeur `freeride`, et `target_w` vaut au moins 50 W. Les profils de la liste `workouts` n'ont plus de fraction `null`. `start` n'accepte que `{"ftp_test": "ramp"}`. Les schémas `state.schema.json` et `plans.schema.json`, ainsi que `plan_format_v1.md`, suivent. Ce sont des valeurs retirées : un engine plus ancien les gérait, il ne les recevra simplement plus.

## 4. Fichiers

- Core :
  - `workout.py` : `ERG_MIN_W`, FreeRide en palier, `Block` toujours avec une cible, plus de `is_freeride` ;
  - `free_erg.py`, `session.py`, `ftp_test.py` (le test de 20 min est retiré), `plans.py`, `__main__.py`, `ipc_lists.py`, `workout_formats.py` ;
  - `tools/workouts.py`, `tools/matrice_boutons.py`, `tools/boutons_click.py`.
- Engine :
  - `erg_view.gd`, `erg_view_model.gd`, `hud_view_model.gd`, `hud_view.gd`, `main.gd` ;
  - `workout_chart_model.gd`, `workout_chart_view.gd`, `summary_view*.gd`, `ui_theme.gd` ;
  - `catalog_model.gd`, `menu_flow.gd`.
- Docs : `SPECIFICATION_GENERALE.md` §7.1, `SRS_v1.1.md` §6, `GUIDE_UTILISATION.md`, `README.md`, contrats.
- Tests :
  - core : `test_workout.py`, `test_ftp_test.py`, `test_contract_ipc.py`, `test_free_erg.py`, `test_matrice_boutons.py` ;
  - engine : `test_erg_view_model.gd`, `unit/test_erg_view.gd`, `unit/test_hud_view_model.gd`, `unit/test_menu_flow.gd`, `unit/test_menu_style.gd`, `unit/test_workout_chart_model.gd`, `fake_core.py`, `visual_check.py`, `hud_galerie.py`, `menu_scenarios/plans_ftp.json`.

## 5. Critères d'acceptation

1. `pytest -q` passe dans `core/`, et `run_engine_tests.sh` passe.
2. Un `.zwo` avec un FreeRide : trames `state` toutes en `ERG`, `block_type` `steady`, cible de 50 W (55 W avec un biais de 110 %), ± change le biais et pas le braquet.
3. Biais à 80 % sur un bloc de 50 W, ou en ERG libre à 50 W : la cible reste 50 W.
4. Menu « Test de FTP » : la rampe seule ; `--ftp-test 20min` est refusé.
5. Matrice X42 : la phase « bloc FreeRide » suit la colonne ERG.

## 6. Hors périmètre

Réglage de la consigne minimale (fixe à 50 W) ; réécriture des anciens journaux contenant un test de 20 minutes.
