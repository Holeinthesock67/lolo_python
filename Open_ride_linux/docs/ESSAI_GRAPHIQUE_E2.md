# Essai graphique du lot E2 sur le PC cible (GTX 1060)

Procédure des critères 5 à 7 du cahier [LOT_E2_shader_triplanaire_theme.md](lots/LOT_E2_shader_triplanaire_theme.md) : shader compilé sans erreur, images par seconde avec et sans textures, limite du terrain lointain, changement de thème. Elle reprend aussi l'essai d'E1 resté ouvert (à-coups, trous). Environ 30 minutes, sans le vélo.

Ce qui n'existe pas encore et ne doit pas être noté comme défaut : ciel physique, arbres, HUD final avec profil d'altitude, grain de l'herbe et facettes de la roche (lot E3) ; bâtiments, forêts, eau et sons (lot E4).

## 1. Préparer

```bash
cd ~/Games/lolo_python && git pull
cd Open_ride_linux
python3 engine/tests/make_texture_theme.py      # thème ~/OpenRide/Themes/essai_textures, 3 textures 2 048²
openride-compiler theme-check ~/OpenRide/Themes/essai_textures
```

## 2. Mesurer les images par seconde

La synchronisation verticale bride l'affichage à la fréquence de l'écran (60 Hz) : les « environ 60 images/s » d'E1 sont peut-être ce plafond. Pour voir la marge réelle, elle est coupée pendant la mesure (`--disable-vsync`) et Godot écrit sa cadence chaque seconde (`--print-fps`). Le préréglage est `low`.

Trois minutes par essai, sans toucher à la souris, puis fermer la fenêtre :

```bash
export GODOT_ARGS="--disable-vsync --print-fps"
THEME=default        scripts/openride-dev.sh --trainer mock --input keyboard --autostart | tee ~/essai_e2_uni.log
THEME=essai_textures scripts/openride-dev.sh --trainer mock --input keyboard --autostart | tee ~/essai_e2_textures.log
```

Puis la même paire sur un vrai parcours compilé, de préférence en montagne et au-dessus de 2 200 m pour voir la neige (ajouter `--route <parcours>`, journaux `~/essai_e2_route_uni.log` et `~/essai_e2_route_textures.log`).

Moyenne d'un journal, sans les 20 premières secondes de chargement :

```bash
grep -o "Project FPS: [0-9]*" ~/essai_e2_uni.log | awk 'NR>20 {s+=$3; n++} END {printf "%.0f images/s sur %d s\n", s/n, n}'
```

Si la cadence reste collée à 60 malgré `--disable-vsync`, c'est le pilote NVIDIA qui impose la synchronisation : la couper dans `nvidia-settings` le temps de la mesure.

**Attendu :** moyenne ≥ 55 images/s dans les quatre cas ; perte ≤ 10 % entre `default` (couleurs unies) et `essai_textures`.

## 3. Regarder

À faire sans `GODOT_ARGS` (synchronisation verticale normale), sur la démo puis sur le parcours réel.

| N° | Point | Attendu |
| --- | --- | --- |
| V1 | Terminal au lancement | Aucune ligne `SHADER ERROR`, `ERROR` ou `WARNING` de Godot (critère 5). |
| V2 | Herbe, roche, neige | Herbe sur le plat et les pentes douces, roche sur les pentes fortes (plus de 22°), neige au-dessus de 2 200 m sauf sur les falaises. Transitions courtes, sans bande dure. |
| V3 | Horizon | Les montagnes lointaines se fondent dans le brouillard : aucun bord de terrain coupé net, aucune tuile qui apparaît d'un coup au loin. Une bande gris bleu à l'horizon est normale (sa couleur sera alignée sur le ciel dans E3). |
| V4 | Textures au loin (`essai_textures`) | Pas de scintillement ni de moiré sur les pentes lointaines ; le grain reste net sous la caméra. |
| V5 | Route | Couleur du thème, ligne médiane visible, pas de terrain qui traverse la route. |
| V6 | Déplacement | Pas d'à-coups au chargement des tuiles, pas de trou dans le sol (essai d'E1). |
| V7 | Changement de thème | `THEME=essai_textures` puis `THEME=default` changent l'aspect du terrain sans recompiler le parcours (critère 7). |
| V8 | Soleil | Ombres cohérentes avec un soleil à 40° de hauteur. |

## 4. Rapporter

- Les quatre moyennes d'images par seconde (et la cadence avec la synchronisation verticale, pour comparaison).
- Pour chaque point V1 à V8 : OK, ou une capture d'écran (touche Impr. écran) avec ce qui ne va pas.
- Les journaux `~/essai_e2_*.log` si un point échoue.

Si la perte avec textures dépasse 10 %, refaire la mesure avec des textures 1 024² (`make_texture_theme.py --size 1024`) : cela dit si le coût vient de la taille des images ou du nombre de lectures.
