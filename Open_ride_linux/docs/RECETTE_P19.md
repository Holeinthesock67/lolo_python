# Recette du lot P19 – Jour, nuit et saisons dans le jeu (version 2.0)

Date de préparation : 8 novembre 2026  
Code : branche du lot P19 (après P7 et P18, PR #781)  
Machine cible : PC du propriétaire (GTX 1060, écran 1 920 × 1 080), **sans le vélo**  
Cahier : [LOT_P19_integration_jour_nuit_saisons.md](lots/LOT_P19_integration_jour_nuit_saisons.md)

Deux réglages séparés de **Réglages › Graphisme**, coupés par défaut : **Jour et nuit** (`render.day_night` : `off`, `theme`, `real`, `accelerated`) et **Saisons** (`render.seasons` : `off`, `theme`, `date`, `spring`, `summer`, `autumn`, `winter`). Coupés, l'image et le coût GPU sont ceux d'avant. Le défaut ne change qu'après les bancs aux trois qualités et la validation des captures. À cocher : « fait », ou « à corriger » avec une remarque.

---

## 1. Tests (sans écran, environ 15 minutes)

```bash
cd ~/Games/lolo_python/Open_ride_linux
(cd core && source .venv/bin/activate && pytest -q)
engine/tests/run_engine_tests.sh
```

- [ ] Tests du core verts (dont les réglages `render.day_night` et `render.seasons`, garde des options du menu).
- [ ] Tests Godot verts, dont `test_daylight_model`, `test_season_model`, `test_sky_cycle`, `test_tree_faces` et `test_season_render`.

## 2. Captures (fil des mesures du PC, environ 10 minutes par qualité)

```bash
python3 engine/tests/visual_check.py --native --jour-nuit --configs 1920x1080:low --out ~/mesures-p19/low
python3 engine/tests/visual_check.py --native --jour-nuit --configs 1920x1080:medium --out ~/mesures-p19/medium
python3 engine/tests/visual_check.py --native --jour-nuit --configs 1920x1080:high --out ~/mesures-p19/high
```

- [ ] Contrôles verts : image de plus en plus sombre du midi à la nuit, nuit jamais noire, retour à l'image d'avant une fois les réglages recoupés.
- [ ] Captures validées par le propriétaire : midi, crépuscule orangé, heure bleue, nuit étoilée (route lisible), automne, hiver (arbres avec charpente), printemps.

## 3. Bancs GPU aux trois qualités

Budgets : low 8 ms, medium 13 ms, high 16 ms. Bancs `sim_bench.py` en low, medium et high, réglages coupés (doit égaler `main`), puis `day_night = "theme"` + `seasons = "winter"` dans `~/OpenRide/config.toml` (le cas le plus chargé : étoiles, lune, feuilles qui tombent), puis remise à `off`.

- [ ] Réglages coupés : aucun écart avec `main` au-delà du bruit.
- [ ] Réglages actifs : sous les budgets, ou écart noté pour décision.

## 4. Au menu (sans le vélo, 5 minutes)

- [ ] **Réglages › Graphisme › Jour et nuit** sur « journée accélérée », séance libre sur `demo` : le soleil bouge sans saut de lumière ni d'ombre ; le HUD ne change pas.
- [ ] **Saisons** sur « hiver » puis « coupées » en séance : le paysage change tout de suite, puis revient à l'été.
- [ ] Les deux réglages sont gardés dans `config.toml` après relance.

## Reste hors de cette recette

Brume du matin (P8) et cloches (P9) liées à l'heure, floraison des vergers, nuages plus bas l'hiver, date qui avance en journée accélérée.
