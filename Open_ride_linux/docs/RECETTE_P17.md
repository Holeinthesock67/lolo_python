# Recette du lot P17 – Décor complet : météo, animaux, éoliennes, véhicules, bord de route, foule, abri

Date : 27 octobre 2026  
Code : `main` (PR #321, fusionnée le 27 octobre)  
Machine cible : PC du propriétaire (GTX 1060, écran 1 920 × 1 080), HomeTrainer et Click  
Cahier : [LOT_P17_integration_decor_complet.md](lots/LOT_P17_integration_decor_complet.md)  
Recette précédente : [RECETTE_P16.md](RECETTE_P16.md) (vent, nuages, sons), à faire d'abord.

À cocher par le propriétaire. Les valeurs réelles (FTP, poids, appareils) restent dans `~/OpenRide/config.toml`, jamais dans le dépôt.

---

## 1. Préparation

```bash
cd ~/Games/lolo_python
git switch main && git pull --ff-only
```

Tests sans écran, avant de monter sur le vélo :

```bash
cd Open_ride_linux
(cd core && source .venv/bin/activate && pytest -q)
engine/tests/run_engine_tests.sh
engine/tests/run_e2e.sh
engine/tests/run_visual_tests.sh --update-golden   # route marquée, panneaux, foule : nouvelles références
engine/tests/run_visual_tests.sh
```

Thème d'essai avec une pluie légère et la brume du matin (copie du thème par défaut) :

```bash
mkdir -p ~/OpenRide/Themes/essai-p17
python3 - <<'PY'
import json, pathlib
src = pathlib.Path("Open_ride_linux/engine/themes/default/theme.json")
t = json.loads(src.read_text())
t["name"] = "essai-p17"
t["weather"] = {"kind": "rain", "intensity": 0.3, "morning_mist": True}
t["fauna"] = {"birds": 0.8, "livestock": 0.8, "deer": 0.5}
pathlib.Path.home().joinpath("OpenRide/Themes/essai-p17/theme.json").write_text(json.dumps(t, indent=2))
PY
```

Dans `~/OpenRide/config.toml` :

```toml
[render]
quality = "low"
theme = "essai-p17"
living = true

[wind]
mode = "fixed"
speed_kmh = 20
from_deg = 270
```

Parcours : un parcours compilé avec un col (montée de plus de 3 km), un village, des prés, une forêt et si possible des éoliennes (couches OSM présentes). Deux bots à puissance constante dans la séance.

## 2. Essais

### 2.1 Performance (critère 2)

- [ ] 30 min en `low`, tout activé (col, village, éoliennes, prés, forêt, deux bots, pluie légère) : relever les lignes `[perf-rendu]` du journal du lanceur (`~/run_trainer.log`). Moyenne d'au moins 55 images/s, temps d'image p99 sous 25 ms, aucune saccade à l'arrivée des tronçons.
- [ ] Si l'objectif n'est pas tenu : réduire les budgets `low` de `living` dans `engine/scripts/quality_presets.gd` (d'abord `weather_particles`, `spectators`, `passersby`, puis `animals` et `birds`) et noter ici les valeurs retenues.

| Mesure | Valeur | Budgets `low` retenus |
|---|---|---|
| images/s moyennes | | |
| p99 (ms) | | |
| saccades à l'arrivée des tronçons | | |

### 2.2 Abri derrière un bot (critère 3)

- [ ] Rouler dans la roue d'un bot : « Abri 30 % » (ou la valeur du moment) apparaît en bleu sous l'indicateur du vent, la résistance baisse en SIM.
- [ ] En sortant de la roue, l'abri baisse progressivement puis la pastille disparaît.

### 2.3 Décor (critère 4)

- [ ] Pluie fine autour de la caméra, poussée par le vent ; chaussée plus sombre et brillante ; bruit de pluie dans l'ambiance.
- [ ] Brume dans le fond de vallée, qui se dissipe en montant.
- [ ] Animaux : oiseaux au-dessus des forêts, troupeaux dans les prés, chevreuil qui s'enfuit. Aucun sur le cycliste, ni enterré, ni en l'air.
- [ ] Éoliennes qui tournent face au vent, drapeaux qui flottent dans le sens de la flèche du vent, eau qui scintille.
- [ ] Véhicules : en face ou qui doublent à bonne distance, jamais sur le cycliste ; figés en pause.
- [ ] Bord de route : marquages au sol, bornes kilométriques, panneaux « Sommet à 3 km », panneau du col lisible à l'approche, chiffres des derniers kilomètres peints sur la chaussée.
- [ ] Spectateurs dans le dernier kilomètre du col, qui encouragent au passage ; clameur plus forte en appuyant et après avoir doublé un bot.
- [ ] Passants dans le village et le long de la route, qui saluent ; jamais pendant un bip du Click.

### 2.4 Endurance (critère 5)

- [ ] Une heure de séance sans plantage. Relever la mémoire de l'engine à la 10e et à la 60e minute (`ps -o rss= -C Godot_v4.3-stable_linux.x86_64` ou la ligne du moniteur système) : écart de moins de 10 %.

| Mesure | 10e minute | 60e minute | Écart |
|---|---|---|---|
| mémoire de l'engine (Mo) | | | |

### 2.5 Décor vivant coupé

- [ ] `living = false` : ni pluie, ni brume, ni animaux, ni véhicules, ni panneaux, ni foule ; route et eau comme en 1.0. L'abri et le vent du core restent affichés.

## 3. Retour

Noter ici les remarques (rendu, son, lisibilité, performance), puis les signaler dans le fil du projet.
