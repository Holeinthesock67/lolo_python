# Lot EL1 – Élimination plus longue, écarts aux voisins, fin des épreuves de piste et échauffement avant les courses

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Retours de l'essai vélo du 21 novembre au vélodrome : élimination trop courte, pas d'écart aux bots, pas de victoire ; échauffement sur place en ERG avant toutes les courses | Python, GDScript | VD6, VD9, T16, O36 | Moyenne | En revue (captures à valider) |

## 1. Objectif

Essai du 21 novembre (élimination au vélodrome) : « très bien, mais une séance trop courte de 8 minutes », « il manque l'écart en temps par rapport aux bots autour », « il manque un échauffement » (puis : « pour tous les modes difficiles physiquement »), et, premier à l'arrivée, aucun effet de victoire : le jeu continuait.

## 2. Spécification

| # | Règle |
| --- | --- |
| 1 | Élimination : réglage d'épreuve `every_laps` (« Élimination tous les », 2 à 6 tours, 4 par défaut) ; l'omnium garde 2 tours. L'effort des bots suit la longueur : `every_laps` × adversaires tours. |
| 2 | Toutes les épreuves de piste : champs `ahead` et `behind` de l'objet `track` (coureur juste devant et juste derrière, écart en temps de passage signé, règle de `gaps.py` du lot T16, coéquipiers exclus) ; bloc « ÉCARTS » du HUD sous les tours. |
| 3 | Épreuve finie : bandeau du milieu « VICTOIRE ! » (or, arpège `jingle_winner` et public) ou « ARRIVÉE · 3e sur 8 », 6 s, puis on continue à rouler (choix du propriétaire du 21 novembre, fil « retours », lot RT1 : retour au calme, bilan à la demande ; le bandeau permanent est celui de RT1). Cycliste éliminé : `jingle_elim`. |
| 4 | Échauffement (choix du propriétaire : « sur place en ERG, avant le départ ») : une règle pour tous les modes de course (`warmup.RACE_MODES` : Dernier survivant, Grand Prix, épreuves de piste sauf la séance libre, `EventSpec.race`) ; étape `echauffement` du départ (`start_gate.py`) entre le trainer et le pédalage ; profil `warmup.profile` (montée 45→70 % FTP, palier 70 %, deux fois 20 s à 100 % / 40 s à 55 %) passé par `ErgController` ; Z court ou `skip_warmup` le passe, + et − règlent la cible ; Y annule et rend le trainer en SIM ; réglage `depart.echauffement_min` (10 min, 0 : aucun). Rien n'est compté ni enregistré pendant l'échauffement. |
| 5 | Contrat IPC révision 1.33 (ajouts compatibles). |

## 3. Livraison

- Core : `warmup.py`, `start_gate.py`, `session.py`, `track/base.py`, `track/elimination.py`, `track/__init__.py`, `bot_effort.py`, `config.py`, `settings.py`, `ipc_budget.py` ; tests `test_warmup.py`, `test_track_events.py`, `test_track_session.py`, `test_bot_effort.py`.
- Banc : scénario `engine/tests/menu_scenarios/elimination.json` (écran Prêt, étape d'échauffement, `skip_warmup`, épreuve lancée, bilan).
- Engine : `start_wait_model.gd`, `start_screen.gd`, `track/track_hud_model.gd`, `track/track_view.gd`, `track/track_names.gd` ; tests `test_start_wait_model.gd`, `test_track_hud.gd`.
- Captures low, medium et high (trames du vrai core) : dossier du projet `velodrome/elim-ecarts/`.
- Reste : l'échauffement n'est pas dans le FIT (la séance démarre après) ; essai vélo.

## Recette PC
Catégorie : rendu
- Cloud : captures low, medium et high du HUD (fait, `velodrome/elim-ecarts/`), suites core et engine ; scénario `menu_bench` `elimination` joué sur les trois voies (toutes les étapes vertes ; seul échec : Vulkan absent du cloud)
- PC, depuis `/home/utilisateur/Games/lolo_python/Open_ride_linux` (environ 5 min par qualité, trois voies) :
  - fumée : `python3 engine/tests/menu_bench.py --scenario velodrome --qualite medium`
  - `python3 engine/tests/menu_bench.py --scenario elimination --qualite low --captures ecrans --sonde`
  - `python3 engine/tests/menu_bench.py --scenario elimination --qualite high --captures ecrans --sonde`
  - `python3 engine/tests/menu_bench.py --scenario elimination --qualite medium --captures ecrans --sonde`
- `sim_bench` ne connaît pas le vélodrome : rien à y lancer
- Essai vélo : échauffement passé à Z, élimination à 4 tours, victoire
- Versions : révision IPC 1.33 ; WORLDGEN_VERSION et SCHEMA_VERSION inchangés
