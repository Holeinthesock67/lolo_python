# Lot Y6 – Anticrénelage SMAA en `low` et garde-fou de charge, à résolution native

## 1. Objectif

Le lot Y6 prévu le 27 octobre (`docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §8 : résolution 3D par préréglage, résolution adaptative avec FSR 1.0, FXAA ou SMAA en `low`) a été rattrapé le même soir par une consigne du propriétaire (27 octobre, 19 h 35, cahier Y13 de la PR #446 §1) : **la résolution reste la résolution maximale de l'écran**, sans mise à l'échelle 3D, sans FSR ni résolution adaptative. Le FXAA de `low` est déjà fait par l'étape 1 de Y13.

Ce cahier réécrit donc Y6 sur ce qui reste utile, sans toucher à la résolution :

1. **SMAA 1×** (Godot 4.5) à la place du FXAA en `low`, s'il coûte moins de 0,3 ms et donne des bords plus nets ;
2. un **garde-fou de charge** : quand la carte graphique sature plusieurs secondes (scène chargée, pluie, village, foule), couper un à un les effets les plus chers du préréglage, puis les rendre quand la charge redescend, au lieu de baisser la résolution.

**Décision du propriétaire du 28 octobre :** Y6 est gardé sous cette forme.

## 2. À lire

1. Le cahier Y13 (PR #446) : §1 (consigne de résolution), §5 (table `IMAGE`), §8 (liens avec Y6) ; `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §4 (T6, T12) et §5.
2. Code : `engine/scripts/quality_presets.gd`, `render_quality.gd`, `perf_probe.gd` (temps GPU mesuré), `fps_counter.gd`, `main.gd` (ligne `[perf-rendu]`).

## 3. Prérequis

Y2 (SMAA 1× existe depuis Godot 4.5) et X13 livrés ; étape 1 de Y13 fusionnée.

## 4. Travail demandé

- **SMAA** : en `low`, essai de `screen_space_aa` SMAA à la place du FXAA ; mesure du temps GPU et captures des bords (route, arbres, fils de clôture) ; garder celui qui gagne en netteté pour moins de 0,3 ms, sinon garder le FXAA.
- **Garde-fou** (nouveau `engine/scripts/load_guard.gd`, sans nœud) : moyenne glissante sur 3 s du temps GPU de la vue (`RenderingServer.viewport_get_measured_render_time_gpu`, déjà lu par la sonde X13) ; au-dessus de `GPU_HIGH_MS` (proposition : 13 ms, soit 80 % d'une image à 60 Hz) pendant 3 s, couper l'effet suivant de la liste `SHED_ORDER` du préréglage : SSIL, puis SSAO, puis glow, puis MSAA 4× → 2× ; sous `GPU_LOW_MS` (proposition : 9 ms) pendant 10 s, rendre le dernier effet coupé. Jamais plus d'un changement par 3 s ; jamais la résolution ; jamais un réglage qui recompile un shader en séance (qualité des ombres : saccade immédiate, §5 de la recherche).
- **Visibilité** : une ligne dans le journal de l'engine à chaque changement, et l'effet coupé affiché à côté des images/s quand l'option « Afficher les images/s » est active.
- **Réglage** : aucun réglage de plus dans le menu ; le garde-fou se coupe dans `config.toml` (`[render] load_guard = false`) pour les mesures.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/quality_presets.gd`, `render_quality.gd`, `main.gd` (une ligne d'appel par image), `fps_counter.gd` ; `engine/tests/unit/test_quality_presets.gd`, `test_render_quality.gd`, `test_fps_counter.gd` ; `docs/SRS_v1.1.md` (configuration `[render]`, comparée au code par `core/tests/test_docs_coherence.py`), `core/src/openride_core/config.py` (clé `load_guard`), `scripts/config.example.toml` ; ce cahier, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/scripts/load_guard.gd`, `engine/tests/unit/test_load_guard.gd`.
- **Interdits :** `scaling_3d_scale` (reste à 1), le compilateur, le contrat IPC.

## 6. Modifications de contrat autorisées

Configuration : clé facultative `[render] load_guard` (booléen, vrai par défaut), transmise à l'engine comme les autres clés `[render]` ; ajout compatible.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier ; `pytest -q` du core passe.
2. Garde-fou, sur une suite de temps GPU simulés : 3 s à 15 ms coupent le SSIL, 3 s de plus coupent le SSAO, 10 s à 8 ms rendent le SSAO ; jamais deux changements en moins de 3 s ; jamais de changement de résolution.
3. SMAA ou FXAA en `low` choisi sur mesure et captures, noté dans ce cahier.

**Sur le PC cible (le propriétaire) :** séance de 20 min en `medium` sur un parcours avec villages et pluie : aucune saccade visible au moment d'un changement ; lire dans le journal combien de fois le garde-fou a coupé un effet.

## 8. Hors périmètre

- Baisse de résolution, FSR, rendu à débit variable (VRS : exclu, la GTX 1060 ne le gère pas).
- Choix des effets de chaque préréglage : Y13.

## 9. Réalisation, étape 1 : SMAA en `low` (30 octobre)

Le propriétaire a donné son accord le 30 octobre, après la migration Y2 vers Godot 4.7.2.

- `QualityPresets.IMAGE` remplace le booléen `fxaa` par la clé `screen_aa` (`off`, `fxaa` ou `smaa`). `low` passe à `smaa`, `medium` et `high` restent à `off` (ils ont le MSAA 4×). `RenderQuality.SCREEN_AA` fait le lien avec `Viewport.SCREEN_SPACE_AA_*`. L'anticrénelage d'écran ne s'applique qu'en Forward+, comme avant.
- Tests : `test_quality_presets` vérifie la clé et sa valeur, et qu'il y a toujours un anticrénelage (41 vérifications). `test_render_quality` vérifie l'anticrénelage appliqué au viewport (72 vérifications).
- Captures dans le cloud (Forward+ lavapipe, 1280×720, `low`, vitrine `route`, `village`, `arbres_temperes`, `eolienne` et `panneaux`), FXAA de main contre SMAA. Le SMAA garde le texte des panneaux, les fenêtres et les écorces nets, là où le FXAA les floute. Les bords des pales, des troncs et de la route restent lissés.
- Reste à faire :
  - mesure sur le PC (GTX 1060, 1680×1011) en `low`, `medium` et `high`, pour le critère d'au plus +0,3 ms en `low` ;
  - captures montrées au propriétaire ;
  - le garde-fou de charge, qui fera l'étape 2 avec sa propre PR.

## 10. Réalisation, étape 2 : garde-fou de charge (30 octobre)

- `engine/scripts/load_guard.gd`, sans nœud. Il lit à chaque image le temps GPU de la vue et en fait une moyenne glissante sur 3 s, pondérée par la durée des images.
  - **Coupe** : sur une fenêtre pleine dont la moyenne dépasse 13 ms, il coupe l'effet suivant de `SHED_ORDER` : SSIL, puis SSAO, puis glow, puis MSAA ramené à 2×.
  - **Retour** : la première fenêtre pleine après une coupe mesure ce que l'effet coûtait. Le dernier effet coupé revient quand la moyenne plus ce coût reste sous 12,5 ms pendant 10 s, ce qui garantit qu'il ne refera pas dépasser 13 ms. Il revient aussi après 10 s sous 9 ms, si la scène s'est allégée depuis la coupe.
  - **Correction du 30 octobre (essai 7bc)** : la première version ne rendait les effets qu'après 10 s sous 9 ms. Sur le village en medium, le GPU est monté à 15 ms pendant 6 s, puis s'est stabilisé à 10,7 ms. Le SSIL et le SSAO sont restés coupés toute la séance, alors que le SSAO, qui fait gagner 1,5 ms, pouvait revenir.
  - **Garde-fous** : jamais deux changements à moins de 3 s, et la fenêtre repart de zéro après chaque changement. Seuls les effets allumés par le préréglage peuvent être coupés. En Compatibility, le SSAO et le SSIL n'existent pas et ne sont donc jamais coupés. Une mesure nulle est ignorée. La résolution et la qualité des ombres ne sont jamais touchées.
- `main.gd` fait un appel par image. À chaque changement, le garde-fou réapplique son état par-dessus le préréglage et écrit une ligne `[charge] t=40.2 s coupé : SSIL (GPU 15.0 ms en moyenne sur 3 s)` dans le journal, horodatée en secondes depuis le lancement. Il repart de zéro quand le préréglage change et reste en pause pendant le Cyber-Rogue, qui a son propre `Environment`.
- `fps_counter.gd` : quand le compteur d'images/s est affiché, la ligne finit par « · allégé : SSIL, SSAO ». La mesure du temps GPU reste active (`measure_kept`, ancien `probe_active`).
- Configuration : `[render] load_guard` (vrai par défaut) dans `config.py`, le lanceur (`--load-guard=on|off`), `SRS_v1.1.md` et `config.example.toml`. Avec `--test-mode`, l'engine coupe le garde-fou sauf `--load-guard=on`, pour que les outils de test mesurent les préréglages tels quels. `sim_bench.py --load-guard on` sert aux essais.
- Tests :
  - `test_load_guard.gd` (19 vérifications) couvre les critères du §7 :
    - 3 s à 15 ms coupent le SSIL, 3 s de plus coupent le SSAO ;
    - 10 s à 8 ms rendent le SSAO ;
    - cas du village : après le pic, à 10,7 ms, le SSAO revient et le SSIL reste coupé, sans oscillation ;
    - écart d'au moins 3 s entre deux changements ;
    - rien ne change entre les deux seuils, ni sur un pic court ;
    - préréglage low, Compatibility, garde-fou coupé ;
    - effets appliqués, résolution intacte.
  - `test_quality_presets` vérifie les arguments, `test_fps_counter` la fin de ligne, `test_launcher` les arguments du lanceur.
- Reste : la séance sur le PC du §7, en medium sur un parcours chargé, pour vérifier qu'aucune saccade n'est visible à un changement. Le changement de MSAA et le glow passent par les « ubershaders » de Godot 4.4 et suivants, ce qui devrait éviter toute saccade de compilation, mais cela reste à confirmer.
