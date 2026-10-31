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

## 8. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x32`).

- Engine : `_report_quality` dans `main.gd` (ligne toujours écrite, ligne de test, préréglage de la sonde mis à jour quand un réglage change la qualité : avant, la sonde gardait le préréglage du démarrage) ; champ `quality` des captures ; `QualityPresets.applied_name`.
- `engine/tests/quality_guard.py` ; vérifications dans `sim_bench.py`, `visual_check.py` (donc dans `run_engine_tests.sh`, en `low`) et `perf_probe.py --quality`.
- Vitrines : `vitrine_rendu.gd` applique le préréglage (image, ombres, brouillard) et écrit la colonne `qualite_appliquee` ; pour `vitrine_biomes.gd`, la colonne est laissée au fil des biomes, qui retouche le même CSV dans la PR #493 (écart assumé, pour éviter un conflit).
- `menu_bench.py` : l'attente « Qualité graphique : medium » devient « Qualité appliquée : medium » (même événement, nouveau libellé) ; le contrôle complet du banc des menus viendra avec sa réécriture (fil du banc des menus).
- Essai au cloud : `sim_bench.py --quality medium --scenario nominal --probe` passe ; en retirant la ligne `[render]` écrite par #481, il échoue sur « qualité réellement appliquée : qualité demandée medium, appliquée low (3/3 capture(s)) » et « qualité notée par la sonde : mesurée en medium, puis low ».
- Écart : pas de scène dédiée « faux core qui renvoie une autre qualité » dans `run_engine_tests.sh` ; le contrôle de `visual_check.py` et les tests de `core/tests/test_quality_guard.py` (9 tests, cas négatifs compris) couvrent le même défaut.

## 9. Complément Z1 (31 octobre)

Audit de couverture des tests du 28 octobre, lot Z1 accepté par le propriétaire le 31 octobre : les deux écarts de la livraison sont comblés.

- **Garde-fou de régression en CI** : `visual_check.py --garde-qualite` lance la vraie scène face au faux core et vérifie, dans l'ordre : la ligne du démarrage (`source=cli`), une capture dans la qualité demandée, des réglages du core sans `render.quality` puis avec la même valeur (aucune ligne), une autre valeur (appliquée, `source=reglage`), une valeur inconnue (notée, rien ne change), le retour à la qualité demandée et une dernière capture. `run_engine_tests.sh` le lance en `1280x720:medium` et `1280x720:high` (le low est vérifié par les tests graphiques habituels). Cas négatif essayé au cloud : avec `_on_settings` qui n'applique plus la qualité reçue, trois vérifications échouent.
- **Banc des menus** : à chaque départ (et après chaque `relancer`) puis à l'arrêt, `menu_bench.py` vérifie avec `quality_guard` que la qualité appliquée est celle que `config.toml` demande à cet instant : celle du lanceur au départ, celle d'un réglage changé au menu à l'arrêt. Le contrôle du départ n'attend rien (la ligne `source=cli` est écrite avant le `hello_ack`) : une attente laissait passer l'écran « Connexion des appareils » du scénario `connexion_auto`. Nouveau scénario `qualite` (clavier) : `config.toml` en high, vérifié au départ et après une relance.
