# Lot Y15 – Pente encore plus marquée à l'écran

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Pente encore plus marquée à l'écran : relief affiché ×2,5 par défaut porté par la route (tout le décor suit), regard qui ne suit que la moitié de la pente, champ de vision qui respire avec elle ; décor décidé sur le vrai relief | GDScript + shader | Q2, V12 | Petite | **Livré le 28 octobre**, séance sur le PC à faire (demande du 28 octobre) |

**Statut : livré le 28 octobre (branche `claude/project-thread-mo1aek`)**, en attente de la séance sur le PC (montée de 8 % et descente, quatre vues de caméra, images par seconde).

## 1. Objectif

Demande du propriétaire du 28 octobre : « il faut encore amplifier et exagérer l'impression visuelle de pente ». Le lot Q2 avait ajouté le tangage de la caméra et un facteur de relief réglable, mais ce facteur était resté à 1,0 (aucune exagération) et la caméra suivait toute la pente : la route paraissait plate dans l'image, seul l'horizon bougeait. La physique, la pente envoyée au trainer, la valeur de pente du HUD et le profil d'altitude ne changent pas. Pas de nouveau réglage dans les menus (refusé le 27 octobre) : seule la valeur par défaut change.

## 2. Règles communes (pas d'exception)

- **Le relief affiché est porté par la route** (`route_data.gd`) : `relief_k` et `display_y(alt) = alt_m[0] + (alt − alt_m[0]) × relief_k`. `sample()["y"]` et `sample_point()` rendent la hauteur affichée ; `alt_m` et `grade_pct` restent réels. Route, caméra, avatar, bots, banderoles des segments, passants, véhicules, ciel, bateaux, animaux et terrain suivent tous la même formule, au même endroit. Les copies de la formule dans `main.gd`, `road_builder.gd`, `segment_markers.gd`, `bots_view.gd`, `camera_follow.gd`, `world_streamer.gd` et `osm_streamer.gd` sont retirées. `main.gd` règle `relief_k` sur la route au chargement ; une route du monde ouvert révisée le garde (`revised_from`).
- **Le décor se décide sur le vrai relief, seule la géométrie est étirée** : roche et neige du shader du terrain jugées sur la pente et l'altitude réelles (`relief_k`, `relief_origin_m`), arbres placés sur les hauteurs réelles (pente, limite des arbres, biomes) puis posés à la hauteur affichée. Une montagne garde sa neige à la même altitude réelle, un pré en pente ne devient pas un éboulis.
- **Le même effet dans les quatre vues** (lot V12) : subjective, suivi proche, suivi éloigné, latérale.

## 3. Contenu

| Réglage | Avant | Après |
| --- | --- | --- |
| Relief affiché (`[render] visual_grade_scale`, `--visual-grade`) | 1,0 par défaut, borne 2,0 | **2,5** par défaut, borne 3,0 (une montée de 8 % se voit comme 20 %) |
| Regard de la caméra | suit toute l'inclinaison de la route | suit la moitié (`CameraViews.CAMERA_PITCH_FOLLOW`) : la rampe monte dans l'image en montée, plonge en descente, et l'horizon bouge quand même |
| Borne du tangage de la route (`PITCH_MAX_DEG`) | ±12° | ±18° (avec le relief ×2,5, 13 % réels restent suivis) |
| Champ de vision | 65° fixe | respire avec la pente (`CameraViews.fov_deg`) : jusqu'à −5° en montée (effet de téléobjectif, la rampe paraît plus raide), +6° en descente (vitesse) ; tiré du tangage déjà lissé (0,5 s) |

Non retenu : faire défiler la route plus vite ou plus lentement que la vitesse réelle. La distance affichée, les bots, les arches et les segments ne colleraient plus à la position du core.

## 4. Coût

Aucun sommet ni appel de dessin en plus : mêmes maillages, hauteurs multipliées à la construction (déjà le cas avec Q2), quatre opérations de plus par pixel du terrain. Vitrine `engine/tests/vitrine_pente.gd` : mêmes triangles avant et après dans les seize captures.

## 5. Livraison et vérification

- Tests : `test_visual_grade_scale.gd` (relief porté par la route, terrain creusé sous la route affichée, tangage sur 8 % avec k = 2, champ de vision), `test_camera_pitch.gd` (bornes ±18°), `test_camera_views.gd` (regard à la moitié de la pente), `test_route_vectors.gd` (k = 1 inchangé), `core/tests/test_launcher.py`.
- Vitrine : `xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility --audio-driver Dummy --script res://tests/vitrine_pente.gd -- --out DOSSIER [--k 2.5]` (avant / après, montée et descente de 8 %, quatre vues, CSV des angles et du champ de vision).
- Sur le PC (file des mesures) : `--native`, une montée d'environ 8 % et une descente en `medium`, les quatre vues, captures et `[perf-rendu]` avant / après (main contre la branche). Si `~/OpenRide/config.toml` contient déjà `visual_grade_scale`, l'enlever pour prendre la nouvelle valeur par défaut.
- Les captures de référence `pente_0pct` et `pente_4pct` de `visual_check.py` (lancées avec `--visual-grade=1.0`) changent un peu à 4,5 % : regard à mi-pente et champ de vision resserré ; à régénérer sur le PC.
