# Recette du lot P16 – Vent ressenti et affiché, arbres, nuages, sons

Date : 27 octobre 2026  
Branche : `lot-p16-integration-vent`  
Machine cible : PC du propriétaire (GTX 1060, écran 1 920 × 1 080), HomeTrainer et Click  
Cahier : [LOT_P16_integration_vent_ciel_sons.md](lots/LOT_P16_integration_vent_ciel_sons.md)

À cocher par le propriétaire. Les valeurs réelles (FTP, poids, appareils) restent dans `~/OpenRide/config.toml`, jamais dans le dépôt.

---

## 1. Préparation

```bash
cd ~/Games/lolo_python
git fetch origin lot-p16-integration-vent
git checkout lot-p16-integration-vent
```

Tests sans écran, avant de monter sur le vélo :

```bash
cd Open_ride_linux
(cd core && source .venv/bin/activate && pytest -q)
engine/tests/run_engine_tests.sh
engine/tests/run_visual_tests.sh --update-golden   # le ciel change (nuages) : nouvelles références
engine/tests/run_visual_tests.sh
```

Thème d'essai avec une couverture nuageuse de 0,5 (copie du thème par défaut) :

```bash
mkdir -p ~/OpenRide/Themes/essai-p16
python3 - <<'PY'
import json, pathlib
src = pathlib.Path("Open_ride_linux/engine/themes/default/theme.json")
t = json.loads(src.read_text())
t["name"] = "essai-p16"
t["sky"]["clouds"]["coverage"] = 0.5
pathlib.Path.home().joinpath("OpenRide/Themes/essai-p16/theme.json").write_text(json.dumps(t, indent=2))
PY
```

Dans `~/OpenRide/config.toml` (ou par le menu « Réglages » quand O4 sera livré) :

```toml
[render]
quality = "low"
theme = "essai-p16"
living = true

[wind]
mode = "fixed"
speed_kmh = 25
from_deg = 270          # vent d'ouest ; choisir un parcours qui part vers l'ouest puis revient
max_grade_offset_pct = 4
```

Parcours : un parcours compilé avec forêt et village (couches OSM présentes).

## 2. Essais

### 2.1 Performance (critère 2)

- [ ] 20 min en `low`, tout activé : relever dans le journal du lanceur (`~/run_trainer.log`) les lignes `[perf-rendu]`. Moyenne d'au moins 55 images/s, temps d'image p99 sous 25 ms.
- [ ] Même parcours avec `living = false` : relever l'écart d'images par seconde (objectif : moins de 3 images/s).

| Mesure | `living = true` | `living = false` |
|---|---|---|
| images/s moyennes | | |
| p99 (ms) | | |

### 2.2 Vent en SIM (critère 3)

- [ ] Vent de face : la résistance monte, la vitesse baisse. L'indicateur sous le panneau de gauche montre une flèche vers le bas, « 25 km/h face », le niveau « fort » et la pastille rouge « Vent défavorable ».
- [ ] Demi-tour sur le parcours : « dos », pastille verte « Vent favorable », la vitesse remonte.
- [ ] Route en travers du vent : « travers gauche » ou « travers droit », pastille grise « Vent neutre ».
- [ ] L'indicateur se lit d'un coup d'œil à 2 m de l'écran et ne recouvre ni les chiffres ni le bandeau.
- [ ] `mode = "off"` : l'indicateur est caché.

### 2.3 Arbres, nuages, sons (critères 4 et 5)

- [ ] Les arbres se penchent et les nuages défilent dans le sens de la flèche.
- [ ] Le souffle du vent forcit avec le vent de face. La roue libre ralentit avec la vitesse.
- [ ] L'ambiance change entre forêt (oiseaux), champ (insectes) et village (rumeur), sans clic ni coupure. Les cloches sonnent l'heure près d'une église.
- [ ] En `medium` ou `high` : les touffes d'herbe du bord de route ondulent au vent apparent.

### 2.4 Décor vivant coupé (critère 6)

- [ ] `living = false` : ciel sans nuages, arbres immobiles, pas de fond d'ambiance. Rendu et sons comme en 1.0. Le vent du core, s'il est activé, reste ressenti et affiché.

## 3. Retour

Noter ici les remarques (rendu, son, lisibilité, performance), puis les signaler dans le fil du projet.
