# Lot O25 – Contenus de départ sans terminal : premier lancement et « Réglages › Contenus »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Contenus de départ sans terminal : entraînements, deux plans et parcours de démonstration installés au premier lancement, écran « Réglages › Contenus », message de bienvenue réécrit (contrat 1.5 : `list_contents`, `install_content`, `contents`) | Python + GDScript | O11, O16, U19 (livrés) | Petite | Livré le 31 octobre (PR #651) |

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, §6.2), accepté par le propriétaire le 31 octobre : le joueur ne tape plus aucune commande pour avoir des entraînements, des plans et des parcours. Au premier lancement, tout ce qui est livré avec OpenRide et ne demande aucun téléchargement s'installe seul ; sur une installation existante, la même action est dans le menu. Le message de bienvenue ne renvoie plus vers `openride-core devices --save`.

## 2. Spécification

| # | Règle |
| --- | --- |
| O25-1 | « Contenus de départ » = les entraînements livrés (`core/workouts/`), les deux plans de départ (`core/plans/`) et les quatre parcours de démonstration des biomes (`openride-core demo-biomes`, lot U19). Rien n'est téléchargé. |
| O25-2 | Une installation ne remplace jamais un fichier du joueur : un entraînement, un plan ou un parcours du même nom est gardé tel quel. |
| O25-3 | Premier lancement (`config.toml` absent, le lanceur passe `--first-run` au core) : le core installe les contenus de départ de lui-même, en tâche de fond. Le joueur voit l'avancement dans « Réglages › Contenus ». |
| O25-4 | « Réglages › Contenus » : une ligne par contenu, avec son état (« à installer », « en partie installé », « installé », « installation : 40 % ») et ce qu'il contient. A maintenu installe ce qui manque ; une ligne installée n'est pas choisissable. La ligne d'état donne le compte rendu (« Ajouté : 6 entraînement(s), 2 plan(s), 4 parcours. ») ou l'échec en rouge. Une seule installation à la fois, hors séance. |
| O25-5 | À la fin d'une installation, l'engine redemande les listes des parcours, des entraînements, des réglages et des plans : les nouveaux contenus apparaissent sans relancer. |
| O25-6 | Message de bienvenue : « Au premier écran, « Rechercher et appairer » relie le home trainer, le Zwift Click et la ceinture cardio. Les entraînements, deux plans et des parcours de démonstration s'installent pendant ce temps (Réglages › Contenus). » |
| O25-7 | Un contenu qui télécharge (`network` vrai, packs du lot O29) passe par une confirmation, « Non » par défaut ; jamais d'installation silencieuse qui télécharge (lot O16). |
| O25-8 | Sans compilateur, les parcours de démonstration sont sautés avec une remarque ; les entraînements et les plans s'installent quand même (contenu « en partie installé »). |

Le pack « cols célèbres » (lot O16) se construit depuis OpenStreetMap : il demande le réseau, il n'est donc pas dans les contenus de départ et arrive dans le même écran avec le lot O29 (O25-7).

## 3. Contrat

`docs/contracts/ipc_v1.md`, révision 1.5 : commandes `list_contents` (requête, réponse à chaque copie) et `install_content` `{id}`, message `contents` (`busy`, `message`, `items` de `{id, kind, label, detail, state, network, size_mb, progress_pct}`), rangé parmi les messages de 60 000 octets au plus ; codes d'erreur `content_invalid` et `content_failed`. Schéma `docs/contracts/ipc/contents.schema.json`.

## 4. Fichiers

- Core : `contents.py` (nouveau : catalogue, état, installation dans un fil), `session.py` (commandes, avancement une fois par seconde, `first_run`), `__main__.py`, `launcher.py` (message de bienvenue), `demo_world.py` (`biome_demo_names`), `tools/workouts.py` (`install_builtin_workouts`, partagé avec la commande), `ipc_server.py`.
- Engine : `contents_view_model.gd` (nouveau), `menu_flow.gd`, `main.gd`, `ipc_client.gd`.
- Tests : `core/tests/test_contenus.py`, `engine/tests/unit/test_contents_view_model.gd`, scénario du banc des menus `engine/tests/menu_scenarios/contenus.json` (Click, clavier, souris) ; `test_menu_flow.gd`, `reglages.json`, `test_launch_no_terminal.py` suivent la nouvelle ligne et le nouveau message.
- Docs : contrat, schémas, spécification générale §6.1, guide d'utilisation (les commandes `tools.workouts install` et `plan install` y sont remplacées par le menu), README.

## 5. Critères d'acceptation

1. `pytest -q` dans `core/` : contenus installés une fois, fichier du joueur gardé, sans compilateur, une seule installation, contenu inconnu, refus pendant une séance, premier lancement, schéma.
2. Tests Godot : modèle et déroulé de l'écran (ouverture, installation, confirmation d'un téléchargement, listes redemandées, échec).
3. Banc des menus `contenus` sur les trois voies : fichiers présents dans le HOME temporaire, parcours de démonstration dans la liste.
4. Captures de l'écran avant et après installation montrées au propriétaire avant la fusion.

**Sur le PC (via le fil de fusion) :** banc des menus `contenus` (HOME temporaire, rien n'est écrit dans le vrai `~/OpenRide`).

## Livraison

PR #651, fusionnée le 31 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Audit des options du 31 octobre, accepté par le propriétaire ; en PR ».
