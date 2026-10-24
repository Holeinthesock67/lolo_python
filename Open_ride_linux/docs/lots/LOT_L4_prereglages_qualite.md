# Lot L4 – Préréglages de qualité et thème transmis à l'engine

## 1. Objectif

Le SRS §8 prévoit trois préréglages de qualité (bas, moyen, haut) et le choix du thème dans la configuration. `config.toml` a déjà `[render] quality` et `[render] theme` (validés par J3), mais personne ne les transmet à l'engine. Ce lot :
- fait passer ces deux réglages du lanceur `openride` (lot K6) à l'engine, en arguments de ligne de commande ;
- écrit la table des préréglages côté engine, sans affichage, pour qu'E1, E3 et E4 y lisent leurs distances et densités.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_K6_lanceur_unique.md`.
2. `docs/SRS_v1.1.md` §8 (« Performance »), §11 (configuration, section `[render]`).
3. Code : `core/src/openride_core/config.py` (`RenderConfig`, bornes de `quality`), `core/src/openride_core/launcher.py` (`build_supervisor`, `engine_cmd`), `engine/scripts/engine_args.gd`, `scripts/openride-dev.sh`.
4. Tests : `core/tests/test_launcher.py` (ou le fichier de tests de K6), `engine/tests/` (tests d'arguments s'il y en a).

## 3. Prérequis

Lot K1 livré (test engine dans `engine/tests/unit/`). K6 est livré.

## 4. Travail demandé

- **Engine :** `engine_args.gd` accepte `--quality=low|medium|high` (défaut `low`) et `--theme=NOM` (défaut `default`) ; une valeur invalide est signalée sur la sortie d'erreur et remplacée par le défaut, comme pour les ports.
- **Table :** nouveau `engine/scripts/quality_presets.gd` (`extends RefCounted`, sans `class_name`) : `preset(name) -> Dictionary` avec au moins `view_distance_m`, `chunks_ahead`, `chunks_behind`, `vegetation_density_factor`, `ssao`, `fog_volumetric`, `msaa`, `renderer_hint` (`forward_plus` ou `mobile`). Valeurs proposées, à justifier dans le rapport : `low` 3 km, densité 0,3, sans SSAO ni brouillard volumétrique, sans MSAA, `mobile` ; `medium` 5 km, 0,6, SSAO, MSAA 2× ; `high` 8 km, 1,0, SSAO, brouillard volumétrique, MSAA 4×, `forward_plus`.
- **Lanceur :** `launcher.py` lit `render.quality` et `render.theme` de la configuration (même fichier que le core, option `--config` respectée) et ajoute `--quality=…` et `--theme=…` après `--` dans `engine_cmd`. `scripts/openride-dev.sh` fait de même, ou le rapport explique pourquoi il est laissé tel quel.
- Rien n'est encore appliqué au rendu : `main.gd` n'est pas modifié.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/quality_presets.gd`, `engine/tests/unit/test_quality_presets.gd`.
- **Modifiés :** `engine/scripts/engine_args.gd`, `core/src/openride_core/launcher.py`, tests du lanceur, `scripts/openride-dev.sh` (facultatif), `engine/tests/README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, scripts de rendu d'E1, `config.py` (les clés existent déjà).

## 6. Modifications de contrat autorisées

Aucune. Les arguments de l'engine ne font pas partie du contrat IPC.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` ; `engine/tests/run_engine_tests.sh` passe en entier.
2. Test du lanceur : avec un `config.toml` temporaire `quality = "high"`, `theme = "alpes"`, `engine_cmd` contient `--quality=high` et `--theme=alpes` après `--` ; sans configuration, `--quality=low` et `--theme=default`.
3. Test engine : `parse(["--quality=medium", "--theme=x"])` renvoie ces valeurs ; `--quality=ultra` renvoie `low` avec un message ; les arguments existants (ports, `--routes-dir`, `--test-mode`) gardent leur comportement.
4. `preset` : trois préréglages, mêmes clés, distances et densités croissantes de `low` à `high` ; un nom inconnu renvoie `low`.

## 8. Hors périmètre

- Application des préréglages au rendu (E1, E3, E4) et changement de moteur de rendu à chaud.
- Menu de réglages (G).
