# Étude du rendu invisible (lot S1)

Rapport du lot S1 (`docs/lots/LOT_S1_rendu_invisible.md`, issue #190) : ce qui est chargé, construit ou dessiné sans être vu, et les pistes essayées pour ne plus le calculer. Contraintes du propriétaire : résolution native uniquement (ni FSR ni échelle dynamique), budgets X2, X13 et X16 comme garde-fous, mesures sur la GTX 1060 hors séance vélo, captures et chiffres avant / après.

## 1. État de départ (main du 28 octobre)

| Catégorie | Chargé | Dessiné | Part invisible |
|---|---|---|---|
| Tuiles lointaines (5 km) | à moins de la fin du brouillard plus une tuile (Y1 : 9 / 11 / 12 km) | tri de Godot sur le cadre de la caméra | derrière la caméra, environ la moitié ; peu coûteuses (maille de 50 m) |
| Tuiles proches (1 km) | toutes à moins de 1 500 m de la caméra et du point visé 10 s plus loin, **derrière comprises** | tri de Godot sur le cadre | environ la moitié derrière la caméra, construites quand même (sommets, arbres, bâtiments exclus) |
| Arbres | 16 cases de 250 m par tuile proche | LOD 0 jusqu'à 300 m (ombres), LOD 1 jusqu'à 1 500 m | ceux des tuiles derrière ; le budget retirait les cases les plus éloignées, **même devant** |
| Tronçons de route et OSM (bâtiments, eau) | de 1 tronçon derrière à 3 / 5 / 8 devant | bâtiments jusqu'à 1,5 / 2,5 / 4 km | un tronçon derrière |
| Relief et bâtiments qui masquent | – | rien n'est masqué (pas d'occulteurs) | tout ce qui est derrière une colline ou un village |
| Décor vivant, bots | mis à jour à chaque image | sélection des plus proches, derrière compris | ceux derrière la caméra |
| Ombres | 150 / 300 / 600 m | – | à revoir avec Y4 |

## 2. Pistes

| Piste du cahier | Lot | État |
|---|---|---|
| 1. Au-delà du brouillard | Y1 (#381) | fusionnée le 27 octobre ; banc sans gain ni perte (mondes trop petits) |
| 2. Hors du champ de la caméra active (tuiles proches) | S1a | dans cette PR, interrupteur `--culling` |
| 6. Ne pas construire ce qui sera invisible | S1a | même tri : une tuile écartée n'est ni calculée (WorkerThreadPool) ni garnie d'arbres |
| Budget d'arbres dépensé dans le champ | S1a | cases hors du champ retirées en premier |
| 4. Masqué par le relief et les bâtiments | S1b | à faire : occulteurs simples tirés des tuiles (crêtes) et boîtes des bâtiments |
| 3. Distances de visibilité (eau, petits objets) | S1b | à faire |
| Décor vivant et bots hors vue en veille | S1c | à faire |
| 5. Ombres | Y4 | après la migration Y2 |

## 3. Piste 2 et 6 : tri des tuiles proches (S1a)

`engine/scripts/view_culling.gd` voit le monde de dessus. La caméra active (`get_viewport().get_camera_3d()`, donc aussi les vues de V12) donne un secteur : sommet à la caméra, axe du regard, demi-angle du champ horizontal plus 15°. Une tuile proche est voulue si :

- elle est à moins du rayon gardé de la caméra, quelle que soit la direction : distance des ombres du préréglage plus une case d'arbres (400 / 550 / 850 m), pour que les ombres du relief et des arbres juste derrière restent justes et qu'un demi-tour ne découvre rien ;
- ou elle est à moins de 1 500 m d'une des vues et dans son secteur. Les vues sont celle de maintenant et celles que la même caméra aura le long de la route sur les 400 prochains mètres au moins (10 s à la vitesse du moment), avec le même écart entre le regard et la route. Dans une épingle, la tuile du retour est donc demandée avant le virage.

Une tuile déjà chargée garde 10° de marge en plus, pour ne pas être libérée puis reconstruite au moindre balancement. Les tuiles lointaines restent toutes chargées : si la vue change, elles servent de fond pendant que les tuiles proches se construisent (moins d'une seconde). Tant que la caméra n'est pas placée sur la position donnée au streamer (chargement d'un parcours), rien n'est écarté.

Tests : `engine/tests/unit/test_culling.gd` (critère 2 du cahier).

## 4. Mesures sur la GTX 1060

Commandes (PC cible, hors séance vélo, environ 25 min) :

```bash
cd ~/Games/lolo_python/Open_ride_linux
for q in low medium; do for c in off on; do
  python3 engine/tests/sim_bench.py --native --probe --scenario rendu_invisible \
    --quality $q --culling $c --out ~/OpenRide/sim_bench/S1_${q}_${c}
done; done
```

`--culling off` est la mesure « avant ». La sonde (X13) écrit `moteur.csv` : images/s, temps d'image p50 / p99, objets et primitives dessinés, mémoire vidéo, tuiles proches et lointaines, arbres. Les captures du banc, prises toutes les 20 s à la même position dans les deux essais, servent à vérifier qu'aucune différence n'est visible.

| Préréglage | Tri | Images/s moy. | p99 (ms) | Objets | Primitives | Mémoire vidéo (Mo) | Tuiles proches | Arbres |
|---|---|---|---|---|---|---|---|---|
| low | off | à mesurer | | | | | | |
| low | on | à mesurer | | | | | | |
| medium | off | à mesurer | | | | | | |
| medium | on | à mesurer | | | | | | |

Règle de décision (cahier, §4 étape 3) : piste gardée si elle gagne au moins 3 % d'images/s en moyenne ou 1 ms de p99, sans changement visible ni apparition d'objet. Sinon, `culling` repasse à faux par défaut et le résultat est consigné ici.
