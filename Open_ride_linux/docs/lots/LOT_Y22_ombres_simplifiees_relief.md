# Lot Y22 – Ombres simplifiées du relief (faux relief dans les ombres)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Ombres du relief portées par un faux relief simplifié (maille 40 m) au lieu des tuiles dessinées ; tuiles lointaines sans ombre | GDScript | Y4, Y13 | Petite | En PR (mesures PC et captures à faire) |

## 1. Objectif

Étude d'optimisation du 5 novembre (`docs/ETUDE_OPTIMISATION_RENDU_2026-11-05.md` §4 point 6 et §6.1 point 6), lancée par le propriétaire le 6 novembre à 0 h 24 (« Lance les 6 et fais des mesures pour vérifier les gains individuels »). Les ombres font la moitié des primitives dessinées (1,32 million avec, 0,69 million sans, en medium) pour 1,9 à 2,3 ms de GPU.

Avec les cascades du soleil (PSSM, 2 en low, 4 en medium et high), chaque objet qui touche une cascade y est dessiné en entier. Une tuile proche (1 km, maille de 10 m) fait 21 600 triangles avec ses jupes ; une tuile lointaine (5 km, maille de 50 m) 20 000 et se trouve toujours sous la caméra, enfoncée sous le relief proche. Les deux étaient dessinées dans chaque cascade qu'elles touchent, alors que le relief ne s'ombre lui-même que par ses formes de plus de quelques dizaines de mètres (l'éclairage par la normale fait déjà le reste).

## 2. Ce qui est fait

- `TerrainTiles.shadow_proxy_arrays` : faux relief d'une tuile proche, un sommet sur 4 (maille de 40 m, 1 450 triangles avec ses jupes, 15 fois moins), calculé dans la tâche de fond de la tuile à partir des sommets dessinés (relief exagéré et raccord au lointain compris).
  - Toujours sous le vrai relief : sur chaque maille grossière, plus fort dépassement de l'interpolation grossière au-dessus des sommets fins, puis chaque sommet descend du plus fort dépassement de ses mailles voisines, plus une marge de 0,5 m. Pas d'acné d'ombre (le relief n'est jamais dans l'ombre de son propre faux relief) ; sur une pente régulière, le faux relief est exactement 0,5 m sous le vrai ; une colline garde son sommet.
  - Jupes de 20 m aux bords : deux tuiles voisines peuvent abaisser différemment leur bord commun, la jupe bouche la fente (sinon un trait de lumière traverserait l'ombre d'une crête).
- `WorldStreamer.relief_shadow` : `full` (rendu d'avant), `proxy` (seul le faux relief des tuiles proches porte l'ombre, en `SHADOWS_ONLY` ; tuiles dessinées, lointaines, plates et sol plat sans ombre) ou `off` (le relief ne porte aucune ombre). Le relief reçoit toujours les ombres (arbres, bâtiments, cyclistes) ; la route garde la sienne. Le faux relief n'est calculé qu'en `proxy` (environ 4 ms par tuile, dans la tâche de fond) : en `full`, rien ne change par rapport à avant ; passer à `proxy` en séance refait les tuiles proches.
- Clé `relief_shadow` de `QualityPresets.IMAGE`, posée par `RenderQuality.apply_preset` ; **reste `full` dans les trois préréglages** tant que les mesures et les captures ne sont pas validées.
- Essai au banc : `OPENRIDE_RENDER_DIAG=ombres_terrain=proxy|off|full` ; variantes `ombres_terrain_proxy` et `sans_ombres_terrain` de `engine/tests/cout_rendu.py`.
- Test : `engine/tests/unit/test_relief_shadow.gd` (faux relief sous le vrai, relief ×1 et ×2,5, pente exacte, colline gardée, nombre de triangles, trois modes, tuile refaite au passage à `proxy`, clé des préréglages et essai).

## 3. Mesures à faire sur le PC (fil « Fusionner les PR et séquencer les mesures »)

Règles : low, medium **et** high (budgets GPU 6, 12, 14 ms) ; gain de ce lot seul, sur le socle proposé le 6 novembre ; captures avant et après validées par le propriétaire avant toute fusion.

```bash
cd ~/Games/lolo_python && git fetch origin claude/project-thread-sbdk0q && git checkout claude/project-thread-sbdk0q
cd Open_ride_linux
python3 engine/tests/cout_rendu.py lancer --socle propose --repetitions 2 \
  --variantes base,ombres_terrain_proxy,sans_ombres_terrain \
  --out ~/OpenRide/mesures/2026-11-06/ombres_relief
python3 engine/tests/cout_rendu.py analyser ~/OpenRide/mesures/2026-11-06/ombres_relief
```

Environ 3 variantes × 3 qualités × 2 répétitions × 70 s, soit 25 min. Résultat attendu : `cout.md` (gain GPU médian de chaque variante par rapport à `base`, même qualité) et `planche/` (capture de chaque variante). Pour les captures d'un relief marqué, refaire la même chose avec `--biome alpine`.

## 4. Décision attendue

- Gain d'au moins 0,3 ms (au-dessus du bruit de ±0,6 ms sur deux répétitions, on regarde la médiane) et captures sans différence gênante : `relief_shadow = "proxy"` dans les préréglages concernés.
- `off` sert de borne (coût total des ombres du relief) ; il ne serait retenu que si les captures ne montrent aucune ombre de relief manquante.
