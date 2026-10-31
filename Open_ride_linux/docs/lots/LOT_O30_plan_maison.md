# Lot O30 – Plan maison depuis le menu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Plan maison depuis le menu : « Plans d'entraînement › Créer un plan » (jours, entraînements de la bibliothèque dans l'ordre choisi, durée), commande `create_plan` | Python + GDScript | O12, O25 | Petite | Audit des options du 31 octobre, accepté par le propriétaire ; en PR (après O29) |

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, §5), accepté par le propriétaire le 31 octobre : composer un plan d'entraînement sans `plan import` ni fichier `.toml` écrit à la main. Le plan se fait avec les entraînements déjà dans la bibliothèque (`~/OpenRide/Workouts/`) ; `plan import DOSSIER` reste la voie pour un dossier d'entraînements venu d'ailleurs.

## 2. Spécification

| # | Règle |
| --- | --- |
| O30-1 | « Plans d'entraînement » finit par **Créer un plan** (une fois la liste reçue). L'écran « Créer un plan » a quatre lignes : **Jours**, **Entraînements**, **Durée**, **Créer le plan** (grisé tant qu'il manque un jour ou un entraînement ; nombre de séances à droite, « 12 séances »). Chaque ligne ouvre son écran ; Y revient. |
| O30-2 | **Jours** : les sept jours, « oui » ou « non », A maintenu bascule. Départ : mardi, jeudi, samedi. Les séances suivent l'ordre de la semaine. |
| O30-3 | **Entraînements** : le test de FTP (rampe) puis la bibliothèque ; un entraînement invalide est grisé. A maintenu ajoute l'entraînement en fin de suite (« n° 3 » à droite) ou le retire (les suivants remontent). 42 au plus. |
| O30-4 | **Durée** : « Automatique » (chaque entraînement une fois, la dernière semaine peut être incomplète), ou de N à 12 semaines, N étant le minimum pour tout placer ; au-delà, la suite recommence. Une durée devenue trop courte (jour retiré, entraînement ajouté) repasse en automatique. |
| O30-5 | La carte de droite montre l'aperçu : nom que le core donnera (« Mon plan », « Mon plan 2 »…), les quatre premières semaines (« S1 : mar Sweet spot, jeu VO2max »), « … jusqu'à la semaine 8 ». |
| O30-6 | **Créer le plan** envoie `create_plan` ; le core écrit `~/OpenRide/Plans/mon-plan.toml` sans rien écraser et répond `plans` avec `created`. L'engine ouvre la page du plan créé (« Plan créé : Mon plan » sur la ligne d'état), d'où **Démarrer ce plan aujourd'hui** le lance : le plan n'est jamais démarré tout seul. Un refus (`plan_invalid`) s'affiche en rouge sur la ligne d'état. Hors séance seulement. |

## 3. Contrat

`docs/contracts/ipc_v1.md`, révision 1.5 : commande `create_plan` `{workouts, days, weeks, name}` (réponse `plans`, erreur `plan_invalid` ou `busy`), champ facultatif `created` `{id, name}` de `plans`. Schémas `cmd` et `plans` mis à jour.

## 4. Fichiers

- Core : `plans.py` (`create_from_library`, `home_plan_name`), `session.py` (commande `create_plan`).
- Engine : `plan_builder.gd` (nouveau, modèle sans nœud des quatre écrans), `menu_flow.gd` (écrans, plan créé ouvert), `ipc_client.gd` et `main.gd` (commande).
- Tests : `core/tests/test_plan_maison.py`, `engine/tests/unit/test_plan_builder.gd`, `test_menu_flow.gd` (ligne « Créer un plan »), scénario `engine/tests/menu_scenarios/plan_maison.json` du banc des menus.
- Docs : contrat, guide d'utilisation (§5, plans), README.
