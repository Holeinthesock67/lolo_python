# GF7 : sonde de performance bornée au roulage (écran de bilan, dérive, préparation)

- PR : à venir ; fil « Fiabiliser les outils de banc » (27 novembre 2026), constats du fil « Bilan des à-coups »
  (statut/BILAN_ACOUPS_2026-11-28.md, §3) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Banc simulé avec `--probe` : budgets et à-coups jugés du chargement à l'ordre `end_session` ; l'écran de bilan
    qui suit (29 à 37 images « menu affichage summary », fausse périodicité de 595 m, pire image en échec) est
    relevé à part, non jugé (« à-coups : écran de bilan »).
  - Dérive de la sonde : première minute prise après le premier mètre (le chargement à froid n'y est plus),
    dernière minute avant `end_session`.
  - Saccades par cause : totaux et pires du roulage seul ; la barre de préparation (avant le premier mètre) et
    l'écran de bilan ont chacun leur ligne « hors roulage ». `sonde.csv` et `saccades.csv` restent entiers.
  - Fenêtre lue au journal de séance (premier enregistrement à 1 m) et à l'heure de `end_session`, annoncée en
    INFO « fenêtre jugée par la sonde ». `perf_probe.py` seul (sans fenêtre) juge comme avant.
- SUIVI :
  - [ ] GF7 : perf_probe et sim_bench, fenêtre du roulage pour les à-coups, la dérive et les totaux par cause.
