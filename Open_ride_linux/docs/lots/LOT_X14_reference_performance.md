# Lot X14 – Référence de performance, comparaison avant/après et verdict de budget

## 1. Objectif

Aucune référence de performance n'existe : une PR peut faire perdre 10 images/s sans que personne ne le voie. Les comparaisons avant/après de la file des mesures (main contre branche, préréglage par préréglage, captures à l'appui) se font à la main, et les budgets de chaque préréglage (cahier Y13 §3) se vérifient en recalculant les médianes. Propositions des fils (28 octobre) : fusions et mesures (comparateur de bancs avec verdict), qualité d'image Y13 (verdict de budget, page de comparaison), bâtiments (comparateur des vitrines), biomes (banc par biome).

## 2. À lire

`engine/tests/sim_bench.py`, `perf_probe.py` (`sonde.csv`, `write_report`, `endurance_checks`), `vitrine_rendu.gd`, `vitrine_biomes.gd` (CSV), cahier Y13 §3 (budgets par préréglage), `plans/FILE_MESURES_PC.md`.

## 3. Travail demandé

- **Budgets** : `engine/tests/perf_targets.json` : par préréglage, `fps_median_min`, `p99_ms_max`, `gpu_ms_median_max`, `gpu_busy95_pct_max`, `warmup_s` (20 s ignorées) ; valeurs du cahier Y13 §3 (low : GPU ≤ 6 ms depuis le 31/10, 4 ms avant, ≥ 55 i/s, p99 < 25 ms ; medium : ≥ 58 i/s, p99 < 25 ms, GPU ≤ 12 ms ; high : ≥ 55 i/s, GPU ≤ 14 ms). `perf_probe.py report` et `sim_bench --probe` ajoutent une vérification OK/ÉCHEC par budget (préréglage lu dans la sonde, pas dans la ligne de commande : X32). Sous Xvfb, les budgets sont en INFO.
- **Comparateur** `engine/tests/compare_bench.py AVANT APRÈS [--seuil-bruit 3]` : deux dossiers de banc ou de vitrine ; verdict par mesure (images/s, p99, GPU médian, appels de dessin, triangles) : « mieux », « pareil » (dans le bruit), « moins bien » ; page HTML avec les captures au même nom côte à côte (curseur glissant), le tableau des écarts et le préréglage appliqué de chaque côté ; CSV des écarts par vue pour les vitrines.
- **Référence** `engine/tests/perf_reference.py run|compare|update` : parcours fixes (village simulé, circuit d'essai, un parcours par biome de démonstration U19 quand il existe), 5 min par préréglage, sonde active ; résultat comparé à `~/OpenRide/perf/reference.json` ; alerte au-delà de −5 % d'images/s ou +1 ms de p99.

## 4. Fichiers

- **Nouveaux :** `engine/tests/perf_targets.json`, `compare_bench.py`, `perf_reference.py`, `core/tests/test_compare_bench.py`, `core/tests/test_perf_targets.py`.
- **Modifiés :** `perf_probe.py`, `sim_bench.py`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Verdict de budget sur des sondes fabriquées : dans le budget, hors budget, chauffe ignorée.
2. Comparateur sur deux dossiers fabriqués : écart dans le bruit = « pareil », −10 % = « moins bien » ; captures appariées par nom.
3. `perf_reference.py run --duree 30 --qualite low` tourne sous Xvfb (mesures en INFO).

## 6. Hors périmètre

Les mesures sur la GTX 1060 (file des mesures du PC).

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x14`, sur X35 et X32).

- `engine/tests/perf_targets.json` (budgets du §3 de Y13, `gpu_busy95_pct_max` fixé à 5 % : `high` passait 17 s sur 300 au-dessus de 95 % le 28 octobre) ; `perf_probe.budget_checks` juge le préréglage lu dans la sonde, refuse une mesure qui change de préréglage, met en INFO sous Xvfb et sans nvidia-smi ; lignes dans `sonde.txt`, vérifications dans `sim_bench.py --probe`, `perf_probe.py report|watch --budgets` (code 1) et `report --xvfb`.
- Le p99 jugé est la médiane des p99 de chaque seconde (la valeur que donnent les tableaux de Y13) ; les pics des captures en sont déjà retirés (X35).
- `engine/tests/compare_bench.py` : bancs (sonde, à défaut `fps.csv`) et vitrines (`vitrine.csv`, `vitrine_biomes.csv`) ; HTML avec curseur glissant, `ecarts.csv`.
- `engine/tests/perf_reference.py run|compare|update` : mondes `village` et `demo` par défaut (`osm` en option) ; le parcours par biome U19 s'ajoutera à `DEFAULT_WORLDS` quand il existera.
- Tests : `core/tests/test_perf_targets.py` (6), `core/tests/test_compare_bench.py` (8).
