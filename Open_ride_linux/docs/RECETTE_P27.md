# Recette du lot P27 – Décor vivant, deuxième vague : oiseaux, animaux, véhicules, cyclistes, ciel, bateaux

Date : 28 octobre 2026  
Code : `main` après la PR du lot P27  
Machine cible : PC du propriétaire (GTX 1060, écran 1 920 × 1 080), HomeTrainer et Click  
Cahier : [LOT_P27_integration_recette_decor_vivant_2.md](lots/LOT_P27_integration_recette_decor_vivant_2.md)  
Recette précédente : [RECETTE_P17.md](RECETTE_P17.md) (première vague : météo, éoliennes, panneaux, foule).

Trois blocs de moins de 10 minutes chacun, puis la mesure en `low` au banc. À cocher par le propriétaire. Les valeurs réelles (FTP, poids, appareils) restent dans `~/OpenRide/config.toml`, jamais dans le dépôt.

---

## 1. Préparation (5 min, sans pédaler)

```bash
cd ~/Games/lolo_python
git switch main && git pull --ff-only
cd Open_ride_linux
engine/tests/run_engine_tests.sh
engine/tests/run_visual_tests.sh          # scène decor_vivant sur le monde de test OSM
```

Parcours : un parcours de campagne compilé avec les couches OSM, `roads` comprise (format `.world` 1.5 : recompiler un parcours plus ancien), avec des prés, des champs, une route voisine, un lac ou un canal et une montée d'au moins 3 km. Un bot à puissance constante dans la séance.

Thème à brume pour le bloc 3 (copie du thème par défaut) :

```bash
mkdir -p ~/OpenRide/Themes/essai-p27
python3 - <<'PY'
import json, pathlib
src = pathlib.Path("engine/themes/default/theme.json")
t = json.loads(src.read_text())
t["name"] = "essai-p27"
t["weather"] = {"kind": "mist", "intensity": 0.7, "morning_mist": True}
pathlib.Path.home().joinpath("OpenRide/Themes/essai-p27/theme.json").write_text(json.dumps(t, indent=2))
PY
```

Dans `~/OpenRide/config.toml`, pour les blocs 1 et 2 :

```toml
[render]
quality = "medium"
theme = "default"
living = true
```

## 2. Blocs sur le vélo

### 2.1 Bloc 1 : campagne en `medium` (8 min, SIM, sur le plat)

À voir :

- [ ] Oiseaux : un rapace qui tourne en cercle, une volée en V, des corneilles qui s'envolent au passage (P23).
- [ ] Animaux selon le terrain : vaches et chevaux dans les prés, moutons sur les prairies en pente, un lièvre qui détale d'un champ (P24). Aucun sur la route, ni enterré, ni en l'air.
- [ ] Véhicules de la route : voitures, utilitaires, camions, autocars ou motos qui croisent et doublent à bonne distance (P25).
- [ ] Véhicules lointains sur les routes voisines, un tracteur qui herse un champ (P25). Aucun sur le parcours.
- [ ] Cyclistes du décor : seuls ou en petits groupes, en face, doublés ou qui doublent ; jamais sur le cycliste ni sur le bot (P28).
- [ ] Bateaux : barque, voilier ou pédalo sur le lac, péniche sur le canal, avec leur sillage (P29).
- [ ] Pause (bouton Y) : tout se fige, y compris le ciel et les bateaux ; reprise sans saut.

À entendre :

- [ ] Meuglements, bêlements ou hennissements près des troupeaux, cris des rapaces et des corneilles.
- [ ] « Salut ! » d'un cycliste qui double ; diesel d'une péniche en passant près du canal.

### 2.2 Bloc 2 : montée avec parapentes (8 min, SIM, montée d'au moins 3 km)

- [ ] Parapentes au-dessus de la montée, qui tournent lentement ; une montgolfière si le vent est faible (P26).
- [ ] Un avion de ligne haut dans le ciel, avec sa traînée qui s'efface vers l'arrière ; le grondement lointain des réacteurs.
- [ ] Plus de cyclistes du décor en montée que sur le plat.
- [ ] Aucune saccade au passage d'un tronçon à l'autre.

### 2.3 Bloc 3 : thème à brume pour les phares (6 min, SIM)

Dans `~/OpenRide/config.toml` : `theme = "essai-p27"`, puis relancer.

- [ ] Phares allumés sur les véhicules de la route et des routes voisines, feux des bateaux allumés.
- [ ] Objets du décor qui sortent de la brume sans apparaître d'un coup.
- [ ] Remettre `theme = "default"` après le bloc.

### 2.4 Avis sur les densités

Une note par ligne (trop peu, bien, trop), à reporter dans les budgets `LIVING` de `engine/scripts/quality_presets.gd` et, pour les cyclistes, dans les taux `RATE_FLAT`, `RATE_CLIMB` et `RATE_VILLAGE` de `engine/scripts/road_cyclists_model.gd` (P28).

| Sorte | `medium` | `low` | Remarque |
|---|---|---|---|
| Cyclistes du décor (plat, montée, village) | | | |
| Véhicules de la route | | | |
| Véhicules lointains et tracteurs | | | |
| Animaux (troupeaux, lièvres) | | | |
| Oiseaux | | | |
| Ciel (avions, parapentes, montgolfières) | | | |
| Bateaux | | | |

## 3. Mesure en `low` au banc (environ 6 min, sans pédaler)

```bash
cd ~/Games/lolo_python/Open_ride_linux
engine/tests/sim_bench.py --scenario decor_vivant_2 --quality low --native --probe
```

Objectif (spécification générale) : 55 images/s ou plus et temps d'image p99 sous 25 ms avec tout le décor vivant. Les chiffres sont dans `~/OpenRide/sim_bench/<date>/decor_vivant_2/sonde/sonde.txt`, avec les captures du banc.

| Mesure | Valeur | Budgets `low` retenus |
|---|---|---|
| images/s médianes | | |
| p99 du temps d'image (ms) | | |
| CPU de la vue (ms) | | |
| appels de dessin | | |

- [ ] Si l'objectif n'est pas tenu : réduire les budgets `low` de `living` (d'abord `boats`, `aircraft`, `cyclists` et `distant_vehicles`, puis `animals` et `birds`), puis ceux de `medium`, et noter ici les valeurs retenues.

## 4. Décor vivant coupé

- [ ] `living = false` dans `[render]` : ni oiseaux, ni animaux, ni véhicules, ni cyclistes du décor, ni engins volants, ni bateaux ; rendu identique à la 1.0.

## 5. Retour

Noter ici les remarques (rendu, son, densités, performance), avec les captures du banc, puis les signaler dans le fil du projet.
