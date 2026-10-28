# Lot X32 – Garde-fou de la qualité réellement appliquée dans les bancs

## 1. Objectif

Le 28 octobre, on a découvert que `sim_bench.py` passait `--quality` à l'engine sans l'écrire dans la configuration du core : le core renvoyait `[render] quality = "low"` au démarrage et l'engine repassait en `low`. Toutes les mesures « medium » et « high » d'avant la PR #481 mesuraient donc du `low`, sans qu'aucun outil le voie. #481 corrige la cause, pas le risque : un autre chemin (réglage du menu, `config.toml` du PC, nouvel outil) peut refaire la même erreur.

Ce lot rend la qualité **effective** visible et vérifiée par chaque outil qui mesure ou capture le rendu.

## 2. À lire

1. `engine/scripts/main.gd` : `_quality_name`, `_apply_settings` (réglage `render.quality` reçu du core), `RenderQuality.apply_preset`.
2. `engine/scripts/ipc_client.gd` : `test_log` (lignes `[test] …`).
3. Outils : `engine/tests/sim_bench.py`, `visual_check.py`, `menu_bench.py`, `perf_probe.py`, `vitrine_rendu.gd`, `vitrine_biomes.gd` ; PR #481.

## 3. Prérequis

#481 fusionnée (fait le 28 octobre).

## 4. Travail demandé

- **Engine** : à chaque application d'un préréglage (démarrage, réglage reçu du core, changement au menu), une ligne de journal **toujours écrite** (pas seulement en `--test-mode`) : `Qualité appliquée : medium (demandée medium, source config|cli|menu|defaut)`. En `--test-mode`, en plus : `[test] quality applied=medium requested=medium source=config`. Le champ `quality` est ajouté à l'objet de la capture (`[test] screenshot {…}`) et à chaque ligne de la sonde X13 (colonne `qualite` de `moteur.csv`).
- **Module commun** `engine/tests/quality_guard.py` (bibliothèque standard) : lit un journal de l'engine et renvoie la suite des qualités appliquées ; `check(log, wanted)` → `(ok, message)` : la dernière qualité appliquée avant la première capture et toutes celles qui suivent valent `wanted`.
- **Bancs** : `sim_bench.py`, `visual_check.py`, `menu_bench.py` (parcours sans changement de qualité) et `perf_probe.py` appellent `quality_guard.check` ; une différence est un **ÉCHEC** (« qualité demandée medium, appliquée low »). Le rapport HTML et `fps.csv` affichent la qualité appliquée, pas celle demandée. Vitrines : `vitrine_rendu.gd` applique enfin le préréglage demandé (`RenderQuality.apply_preset` et `apply_fog`, comme la scène principale ; aujourd'hui elle n'en applique aucun et ne montre donc pas les effets de Y13) ; `vitrine_rendu.gd` et `vitrine_biomes.gd` écrivent la qualité appliquée dans leur CSV (colonne `qualite_appliquee`).
- **Garde-fou de régression** : un test de `run_engine_tests.sh` lance la vraie scène en `--quality=medium` face au faux core qui renvoie un réglage `render.quality` absent, puis `medium`, puis `high`, et vérifie les lignes `[test] quality`.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/main.gd`, `engine/scripts/perf_probe.gd`, `engine/tests/sim_bench.py`, `visual_check.py`, `menu_bench.py`, `perf_probe.py`, `vitrine_rendu.gd`, `vitrine_biomes.gd`, `run_engine_tests.sh`, `engine/tests/README.md`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/tests/quality_guard.py`, `core/tests/test_quality_guard.py` (lecture du journal, cas positif et négatif).

## 6. Critères d'acceptation

1. Les suites core et engine passent ; les nouveaux tests ont un cas négatif (journal où l'engine repasse en `low` : ÉCHEC).
2. `sim_bench.py --quality medium --scenario nominal --duration 30` sous Xvfb : vérification « qualité appliquée medium » OK ; en retirant la ligne `[render]` écrite par #481, la même commande échoue.
3. Aucune mesure n'est changée ; seule la vérification est ajoutée.

## 7. Hors périmètre

Le contenu des préréglages (Y13), le réglage au menu (O4).
