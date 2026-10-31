# Lot T3 – Compilateur : couche `segments` du `.world`

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 2.0 série T : compilateur, couche `segments` du `.world`, fichier `<parcours>.segments.toml` | Python | T1, T2 (livrés) | Moyenne | **Livré le 27 octobre** (PR #394 : compilateur, `add-layer … segments`, `verify`, `info`, parcours de démonstration) |

## 1. Objectif

Écrire dans le `.world` la couche facultative `segments` (plan de la série T §3.1 et §3.5) : montées et sprints détectés par T2, plus les segments déclarés à la main dans un fichier posé à côté du GPX (décision du 27 octobre). L'engine lit cette couche lui-même pour dessiner les lignes et les panneaux (T8) ; le core la lit pour chronométrer (T4).

**État : livré le 27 octobre.** Le format de la couche (`segments.json`, version de couche 1.0, entrée `layers.segments` du manifeste) est celui du contrat T1 (format `.world` 1.3, §8 bis, PR #392).

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.1, §3.5 et « Décisions du 27 octobre ».
2. `docs/lots/LOT_T2_detection_segments.md` ; code `core/src/openride_core/segments.py` (`Profile.from_route`, `detect_segments`, `manual_segments`, `merge_manual`, `Segment.to_dict`).
3. `docs/contracts/world_format_v1.md` §2 (manifeste, versions par couche) et §10 (lecture et compatibilité), une fois T1 fusionné.
4. Code du compilateur : `compiler/src/openride_compiler/cli.py` (`build`, `add-layer`, `build-all`), `compiler/src/openride_compiler/writer.py`.

## 3. Prérequis

- T1 (format de la couche) ; T2 (livré, PR #247).
- La détection vit dans le core : le compilateur importe `openride_core.segments` quand le core est installé (cas du PC, où les deux paquets sont dans le même environnement).

## 4. Travail demandé

- **Fichier manuel** `<parcours>.segments.toml`, à côté du GPX (même nom de base), facultatif :

  ```toml
  mode = "add"          # "add" (défaut) : ajoutés aux segments détectés ; "replace" : seuls ceux-ci
  auto_sprints = true   # sprints proposés automatiquement (défaut : true)

  [[segment]]
  type = "sprint"       # "sprint" ou "climb"
  start_km = 12.4
  end_km = 12.8
  name = "Sprint du village"   # facultatif
  ```

  Refus clair (fichier illisible, clé inconnue, type inconnu, segment hors du parcours ou vide) avec le nom du fichier et le numéro du segment.
- **`build`** : couche `segments` produite par défaut quand le core est installé ; sans core, couche omise avec un avertissement (le parcours reste valide, la couche est facultative). `--layers` accepte `segments`.
- **`add-layer <dossier.world> segments [--manual FICHIER]`** : régénère la couche d'un `.world` existant depuis sa couche route, sans réseau et sans projection UTM (les parcours synthétiques sont acceptés) ; par défaut, le fichier manuel cherché est celui du GPX source s'il est connu du manifeste.
- **`build-all`** : prend le fichier `.segments.toml` de chaque GPX du dossier.
- **`info`** : nombre de montées par catégorie et de sprints.
- **`verify`** : segments dans le parcours, `s_start` < `s_end`, identifiants uniques, types et catégories connus.
- **Parcours de démonstration** (`demo_world.py`, `engine/demo`) : segments détectés automatiquement, sans segment manuel (décision du 27 octobre) ; la régénération de `engine/demo` reste identique octet pour octet d'une exécution à l'autre.

## 5. Fichiers concernés

- **Modifiés :** `compiler/src/openride_compiler/cli.py`, `compiler/src/openride_compiler/writer.py`, `compiler/src/openride_compiler/verify.py`, `core/src/openride_core/demo_world.py`, `engine/demo/` (régénéré).
- **Nouveaux :** module de lecture du fichier manuel dans le compilateur, tests du compilateur, vecteurs `.segments.toml`.
- **Interdits :** `segments.py` (sauf correction de bogue), `session.py`, l'engine hors `engine/demo/`.

## 6. Modifications de contrat autorisées

Aucune au-delà de T1 : la couche suit exactement le format fixé par T1.

## 7. Critères d'acceptation

1. `python -m pytest -q` passe en entier dans `core/` et dans `compiler/`.
2. `build` d'un GPX avec montée : couche `segments` présente, conforme au format de T1, segments égaux à ceux de `detect_segments`.
3. Fichier manuel en `add` puis en `replace` : segments attendus ; fichiers invalides refusés avec un message qui nomme le fichier et le segment.
4. `add-layer … segments` sur un parcours synthétique et sur un parcours UTM, sans réseau.
5. Sans core installé : `build` réussit et avertit, `add-layer … segments` échoue avec un message clair.
6. `verify` refuse un segment hors du parcours, un doublon d'identifiant, un type inconnu.
7. Parcours de démonstration : régénération identique deux fois de suite.

## 8. Hors périmètre

- Rendu des lignes, arches et panneaux (T8) ; chronométrage dans la séance (T4 puis branchement).
- Édition des segments dans le menu.

## 9. Livraison (27 octobre 2026)

- Nouveau module `compiler/src/openride_compiler/segments_layer.py` : lecture et validation du fichier manuel, détection par `openride_core.segments`, écriture de `segments.json` (identique octet pour octet pour les mêmes segments), bloc du manifeste et résumé pour `info`.
- `build` : couche `segments` dans les couches par défaut (`route,terrain,segments`) ; sans core, avertissement et couche omise. Fichier manuel invalide : la compilation est refusée, rien n'est écrit.
- `add-layer … segments [--manual FICHIER]` : fichier manuel par défaut, `<trace>.segments.toml` à côté du `.world` puis dans `~/OpenRide/GPX`.
- Choix faits :
  - le manifeste du compilateur porte toujours `layers.segments` (`present` faux quand la couche est absente), comme les autres couches ;
  - le compilateur écrit `format_version` 1.3 ;
  - tout parcours synthétique de `demo_world.py` porte aussi sa couche `segments` (format 1.3), pas seulement celui de démonstration.
- Tests : `compiler/tests/test_segments_layer.py` (19 tests) et `core/tests/test_segments.py` (parcours de démonstration reproductible et conforme aux schémas).
