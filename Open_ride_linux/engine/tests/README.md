# Tests de l'engine sans écran

Tous les tests se lancent depuis `Open_ride_linux/`, avec Godot 4.3 officiel
(`godotengine/godot`, version `4.3-stable`) dont le chemin est donné par `GODOT` :

```bash
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_engine_tests.sh
```

Le script renvoie 0 si tout passe et finit par un résumé (une ligne par test et son résultat).

## Tests de rendu hors écran (`engine/tests/render/`, lot E2)

En mode `--headless`, le serveur de rendu de Godot est factice : aucun shader n'est compilé. Les tests de `engine/tests/render/` rendent donc une vraie image, sous Xvfb avec l'OpenGL logiciel de Mesa (moteur Compatibility), et lisent la couleur des pixels. Même contrat que les tests unitaires (lignes `[OK]`, ligne finale, code de sortie). Paquets : `xvfb`, `xauth`, `libgl1-mesa-dri`. Sans `xvfb-run`, `run_engine_tests.sh` saute cette étape, sauf avec `REQUIRE_RENDER=1` (intégration continue), qui la fait échouer.

| Fichier | Lot | Vérifie |
| --- | --- | --- |
| `test_terrain_render.gd` | E2, Y11 | Shader triplanaire compilé et rendu : herbe, roche, neige et trois mélanges égaux à `blend_weights` (L3) à 3/255 près, seuil de pente du thème, texture utilisée à la place de la couleur ; lot Y11 : relief de l'herbe visible, vert moyen à ± 20 % du thème |
| `test_ground_details_render.gd` | U8 | Relief du sable (`terrain_biomes.gdshader`), éclairé sous un soleil rasant : prairie tempérée identique au pixel près avec et sans le relief, désert de sable changé par les rides et les dunes |
| `test_terrain_biomes_render.gd` | U6 | Shader multi-biome (`terrain_biomes.gdshader`) compilé : deux biomes en bandes sur deux tuiles voisines (teinte de chaque bande à moins de 5 % du thème, pas de marche au bord commun, limite modulée par le bruit), `low` sans le 4e biome (couleur témoin sans effet) et `medium` avec, couche texturée lue dans le tableau `ground_a` |
| `test_fauna_render.gd` | P11, Y14 | Shader des animaux (`fauna.gdshader`) compilé : une vache vue de côté à la couleur de sa robe (ou d'une tache claire), un oiseau vu de dessus, rien sans animal |
| `test_water_shimmer_render.gd` | P12 | Shader de l'eau qui scintille (`water_shimmer.gdshader`) compilé : couleur de base de l'eau d'E4, deux images identiques sans défilement (aucun clignotement) |
| `test_crowd_render.gd` | P15, P21, Y14 | Shader des spectateurs (`crowd.gdshader`) compilé : buste à la couleur d'instance du haut, visage et jambes aux couleurs de peau et de pantalon de la tenue (`people_mesh.gd`) ; lot P21 : chien des passants à la couleur de sa robe |
| `test_sky_clouds_render.gd` | P6 | Ciel nuageux (`sky_clouds.gdshader`) : couverture 0, ciel identique au ciel procédural actuel à 3/255 près ; couverture 0,6, au moins 30 % de pixels clairs au-dessus de l'horizon ; avec vent, motif décalé dans le sens du vent (corrélation) ; deux couches |
| `test_tree_sway_render.gd` | P5 | Arbre seul au vent (`tree_sway.gdshader`) : vent nul, deux images identiques ; vent fort, pied immobile à 2/255 près, cime qui bouge |
| `test_road_markings_render.gd` | P14 | Marquages (`road_markings.gdshader`) sur un vrai ruban de `road_builder.gd` : ligne médiane claire au centre, motif de 13 m (3 m peints), bandes de rive aux deux bords, chiffre « 1 » peint sur la voie de droite |
| `test_vehicle_render.gd` | P25 | Shader des véhicules (`vehicle.gdshader`) compilé : berline proche (peinture du matériau) et en MultiMesh (couleur d'instance) à la même peinture, vitres sombres ; dans le noir, phares éteints puis allumés |
| `test_sky_render.gd` | P26 | Shaders du ciel (`vehicle_far.gdshader`, `contrail.gdshader`) compilés : dans un brouillard épais, avion lointain qui garde sa couleur, le même avec `vehicle.gdshader` noyé ; traînée opaque au réacteur, effacée vers son bout et sur ses bords |
| `test_boat_render.gd` | P29 | Bateaux (`vehicle.gdshader`, `wake.gdshader`) : coque du voilier à la couleur de sa palette, plancher de la barque en bois, sillage marqué à la poupe et effacé vers son bout |

## Tests graphiques de la scène principale (`visual_check.py`)

```bash
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_visual_tests.sh --open
```

Sans action manuelle : `visual_check.py` lance la vraie scène (`main.tscn`) sous Xvfb (OpenGL logiciel de Mesa, moteur Compatibility), face au faux core (`VisualCore`, dérivé de `fake_core.py`), pour chaque configuration `résolution:qualité` (défaut `1280x720:low,1920x1080:high,1024x600:medium`). Le parcours est la démo avec terrain synthétique. À chaque scène, le script envoie le message de test `{"type": "_test", "action": "screenshot", "path": …, "tag": …}` : l'engine enregistre l'image affichée en PNG et écrit une ligne `[test] screenshot {…}` (textes, visibilité et rectangles en pixels des éléments du HUD, images par seconde, maillages visibles, position de la caméra, `ticks_ms`). PNG lus et écrits avec la bibliothèque standard de Python.

| Scène | Vérifications |
| --- | --- |
| `attente` | Aucun core : ligne d'état « en attente du core… », valeurs `--`, éléments dans l'écran |
| `vue_fixe` | Séance à l'arrêt à s = 1 500 m : les sept lignes du HUD exactes, ligne ERG cachée, bandeau caché, éléments dans l'écran sans chevauchement, texte dessiné (pixels clairs), image ni noire ni uniforme, ciel en haut, sol en bas, maillages affichés |
| `nuages` | Lot P16 : ciel de P6 du thème par défaut, pixels de nuage au-dessus de l'horizon, entre les panneaux du HUD |
| `mouvement_1`, `mouvement_2` | 8 m/s : vitesse 28.8 km/h, distance qui avance, caméra à 8 m/s ± 25 % (temps de l'engine), sol qui défile |
| `vent` | Lot P16 : vent de face de 26 km/h dans la trame : indicateur visible sous la colonne de gauche, « km/h face », « fort », pastille rouge « Vent défavorable », mise en page sans chevauchement |
| `abri` | Lot P17 : aspiration de 13,5 % dans la trame : pastille « Abri 30 % » sous l'indicateur du vent, mise en page sans chevauchement |
| `pluie` | Lot P17 : pluie imposée par le message de test `weather` : particules actives, chaussée mouillée, ciel en haut et sol en bas |
| `col` | Lots P17 et T8 : arrêt à 25 m du panneau du sommet de la démo (sommet de `climb1` de la couche `segments`, à 1 500 m) : panneau « Sommet » devant la caméra, lettres d'au moins 6 px en 720p, aucun spectateur (montée de moins de 3 km) |
| `erg` | Ligne ERG visible, cible dans la ligne de puissance, pente « trainer en ERG », mise en page |
| `pause` | « PAUSED (trainer_lost) » et « RECONNECTING » dans la ligne d'état |
| `core_muet_1`, `core_muet_2` | Core muet : `core_lost`, bandeau « Core non joignable » rouge et sans recouvrir le HUD, caméra et image figées |
| `reprise` | Bandeau disparu, image normale |
| `erreur` | Trame `error` : code `route_invalid` dans le bandeau rouge, sans recouvrir le HUD |
| `decor_vivant` | Lot P27 : monde de test OSM (`make_osm_world.py`, copié à côté de la démo), 8 m/s à partir de 1 480 m (un utilitaire double à 1 500 m avec la graine 0) ; captures toutes les 2 s, 30 s au plus, jusqu'à avoir vu un troupeau, des oiseaux, un véhicule croisé, un véhicule lointain et un objet du ciel (`decor` de la ligne `screenshot` : `animals`, `birds`, `vehicles`, `distant_vehicles`, `aircraft`) ; vérifié par la présence des objets, sans image de référence (le décor bouge) ; lot P30 : captures `decor_pause_1` et `decor_pause_2` à 2 s d'écart en pause, `frozen_sig` du décor identique |
| `pente_0pct`, `pente_4pct` | Pentes de 0,6 % et 4,5 % du parcours demo (lot Q2) : inclinaison de la caméra ; avec `--visual-grade=1.5` ou `1.8`, exagération du relief (captures suffixées `_k1.5`, `_k1.8`) |
| `journal` | Aucune erreur ni avertissement Godot (mêmes tolérances que ci-dessous), rendu actif |

Images de référence : avec `--golden DOSSIER`, les scènes reproductibles (`attente`, `vue_fixe`, `pause`, `erreur` : s fixé, rien ne bouge) sont comparées aux références ; échec si l'écart moyen dépasse 6 niveaux sur 255 ou si plus de 1 % des pixels changent de plus de 40 niveaux (un défaut localisé, comme une ligne du HUD disparue, ne pèse que quelques niveaux en moyenne). Le rapport montre alors les écarts en rouge. `--update-golden` enregistre les captures comme références. `run_visual_tests.sh` garde les références dans `~/.cache/openride/visual_golden` (`VISUAL_GOLDEN`) et les crée au premier lancement ; après un changement graphique voulu, le relancer avec `--update-golden`.

Sortie : une ligne `[OK]` ou `[ÉCHEC]` par vérification, `rapport.html` (captures, textes du HUD, mesures, tableau des vérifications) et les PNG dans le dossier `--out` (`run_visual_tests.sh` : `~/OpenRide/visual_tests/<date>`, ou `VISUAL_OUT`). Code de sortie 0 si tout passe, 1 sinon, 2 si Godot ou `xvfb-run` manque. `--native` lance l'engine sur l'écran réel avec son rendu habituel (Forward+, GTX 1060) au lieu de Xvfb : la fenêtre s'ouvre environ une minute par configuration, sans rien à faire (références distinctes à prévoir, le rendu n'étant pas celui de Mesa).

`run_engine_tests.sh` lance la même vérification sur `VISUAL_CONFIGS` (défaut `1280x720:low`, environ 40 s, sans références ; `none` pour la sauter), donc aussi en intégration continue.

Premier défaut trouvé : le bandeau d'alerte (placé à 360 px du bord) recouvrait le HUD dès que celui-ci s'élargissait (ligne d'état, ligne ERG). Il se place désormais à droite du HUD s'il reste 360 px, sinon dessous (`banner.gd`, `layout_for`, test `unit/test_banner_layout.gd`).

## Banc des menus (`menu_bench.py`)

Tous les menus joués de bout en bout au Click V2 simulé, au clavier et à la souris, face au vrai core sur Bluetooth simulé : scénarios déclaratifs de `menu_scenarios/*.json` (un écran ou un parcours de menus chacun), vérifiés par identifiants d'écran et d'élément, `config.toml`, journaux et code de sortie ; voir [docs/OUTILS_DE_TEST.md](../../docs/OUTILS_DE_TEST.md) §3. Messages de test de l'engine qu'il utilise, réutilisables par d'autres bancs (aussi en séance) : `key` (`key`, `shift`, `hold_ms` : touche appuyée puis relâchée par `Input.parse_input_event`), `mouse` (`kind` click, right, wheel_up, wheel_down ou move ; `item` ou `at`) et `menu_state` (`req` : état des menus en une ligne `[test] menu_state {…}`). Ajouter un écran au banc : un fichier JSON, sans toucher au script.

## Banc d'essai simulé (`sim_bench.py`)

Vrai core sur Bluetooth simulé et vraie scène, captures et rapport HTML, sur le parcours `demo` ou le « village simulé » de `make_sim_world.py` (178 bâtiments, montée et descente) : voir [docs/OUTILS_DE_TEST.md](../../docs/OUTILS_DE_TEST.md) §3. Hors de `run_engine_tests.sh` (plusieurs minutes par scénario).

**Sonde de performance du moteur (lot X13).** `sim_bench.py --probe` (ou, avec le vrai jeu, `OPENRIDE_PERF_PROBE=~/OpenRide/sonde/moteur.csv openride` puis `engine/tests/perf_probe.py watch` dans un second terminal) mesure où part le temps, une ligne par seconde. L'engine, lancé avec `--perf-probe=FICHIER.csv` (`engine/scripts/perf_probe.gd`), écrit le temps d'image p50, p99 et max, les temps CPU et GPU de la vue relevés par le RenderingServer, les appels de dessin, objets et primitives dessinés, la mémoire vidéo et statique, les nœuds, les tuiles proches et lointaines, les tronçons OSM et les arbres. `perf_probe.py` y ajoute nvidia-smi (charge, mémoire vidéo, température et fréquence du GPU) et le CPU et la mémoire de chaque processus (core, Godot, lus dans `/proc`), recale les deux séries sur l'heure et écrit `sonde.csv`, `sonde.txt` (médiane, p99 et max de chaque mesure, dérive entre la première et la dernière minute) et `rapport.html` (courbes). `perf_probe.py report DOSSIER` refait le rapport. La mesure de référence se fait sur le PC cible, en fenêtre réelle (`--native`) : sous Xvfb, le rendu logiciel est environ dix fois plus lent. `--display borderless` ou `--display fullscreen` (avec `--native`) mesure les pleins écrans à la définition native de l'écran ; sans cette option, le banc garde la fenêtre de `--size`.

**Lisibilité et débordements (lot X22).** `--lisibilite` ajoute, sur chaque capture, la hauteur des chiffres principaux ramenée à 1080 lignes (au moins 28 px) et le contraste WCAG mesuré dans l'image (4,5:1 pour les valeurs, 3:1 pour les libellés et les textes des encarts) ; `check_layout` vérifie en plus, toujours, que les panneaux (colonnes, vent, abri, blocs segment et bonus, encart des bots, profil) tiennent dans l'écran sans se chevaucher. Scène `bots_segment_bonus` : 4 bots à profil, deux voisins, un segment en cours et un bonus en réserve. Calculs dans `hud_lisibilite.py` (testé par `core/tests/test_hud_lisibilite.py`).

**Qualité réellement appliquée (lot X32).** À chaque application d'un préréglage (démarrage, réglage reçu du core, menu), l'engine écrit `Qualité appliquée : medium (demandée medium, source cli|defaut|reglage)` et, en `--test-mode`, `[test] quality applied=… requested=… source=…` ; chaque capture porte le champ `quality` et la sonde (X13) note le préréglage appliqué seconde par seconde. `quality_guard.py` lit le journal de l'engine : `sim_bench.py` (vérifications « qualité réellement appliquée » et « qualité notée par la sonde »), `visual_check.py` et `perf_probe.py watch|report --quality Q` échouent si la qualité appliquée diffère de la qualité demandée (défaut corrigé par la PR #481 : un banc « medium » rendait du low). La qualité appliquée est affichée dans le rapport du banc et dans `fps.csv` ; `vitrine_rendu.gd` applique le préréglage comme la scène principale et son CSV a une colonne `qualite_appliquee`.

**Endurance d'une heure (lot X16).** `sim_bench.py --native --scenario endurance` (recette 1.0, lignes 17 et 18) roule une heure sur le village simulé (`--duration 5400` pour 90 min) : effort changé toutes les 5 min, un appui Click à chaque changement, parcours rechargé et relancé à chaque fin (« tours du parcours »), sonde de performance active. En plus des vérifications du banc (engine vivant jusqu'à la fin, aucune erreur Godot, aucune exception du core), après 5 min de mise en route : médiane des images/s d'au moins 30, baisse de moins de 10 % entre les 10 premières et les 10 dernières minutes, au plus 6 saccades par heure (seconde dont la pire image dépasse 100 ms), et croissance de la mémoire (pente des moindres carrés) sous 100 Mo/h pour Godot, 20 Mo/h pour le core, 50 Mo/h pour la mémoire vidéo de Godot et 100 Mo/h pour nvidia-smi. Seuils dans `perf_probe.ENDURANCE_LIMITS`. Sous Xvfb (sans `--native`), les images/s et les saccades sont données à titre indicatif (INFO).

## Tests unitaires (`engine/tests/unit/`, lot K1)

Pour ajouter un test, il suffit de déposer un fichier dans `engine/tests/unit/` : le script le découvre, sans modification. Contrat d'un test unitaire :

- un script `test_*.gd` qui `extends SceneTree` et se lance par `godot --headless --path engine --script res://tests/unit/test_x.gd` ;
- il écrit une ligne `[OK] …` ou `[ÉCHEC] …` par vérification, puis une ligne finale `<nom> : N vérifications, M échecs` (`<nom>` : nom du fichier sans `.gd`) ;
- il quitte avec le code 0 si tout passe, 1 sinon ; il ne dépend d'aucun port réseau ni d'aucun fichier hors de `res://` et `user://`.

Les fichiers sont lancés par ordre alphabétique. Un test échoue si son code de sortie n'est pas 0, si sa ligne finale manque, s'il écrit une erreur ou un avertissement Godot (`SCRIPT ERROR`, `ERROR:`, `WARNING:`, hors avertissements connus du mode sans écran) ou s'il dépasse `UNIT_TIMEOUT` secondes (120 par défaut : une erreur de script dans `_init` laisse Godot tourner sans quitter).

**Budgets de temps (lot X2).** Un test unitaire vérifie un résultat, pas une durée : la durée dépend de la machine (le PC cible est plus lent que les machines de GitHub pour la préparation des arbres). Une mesure de temps passe par `tests/perf_budget.gd` : `PerfBudget.measure_ms(fn, runs, warmup)` (médiane après chauffe) puis `PerfBudget.check(nom, ms)`, qui écrit une ligne `[PERF] nom : x ms, budget y ms` et ajoute `(DÉPASSÉ)` au-delà du budget. Budgets dans `tests/perf_budgets.json` (`budget_ms` du cahier pour le PC cible, `ci_ms` quand la variable `CI` existe), remplaçables par machine dans `~/OpenRide/perf_budgets.json` (`{"tree_tile_high": 230}`) ou le fichier nommé par `OPENRIDE_PERF_BUDGETS`. Mode `OPENRIDE_PERF` : `report` (défaut) n'échoue jamais sur un temps, `strict` compte un dépassement comme un échec, `off` ne mesure qu'une fois. `run_engine_tests.sh` résume toutes les mesures avant son résumé final et les ajoute au fichier `PERF_CSV` s'il est donné. Les coûts par image du décor vivant (série P : météo, faune, éoliennes, circulation, foule, ambiance, herbe, branchement) passent aussi par ces budgets (`weather_evaluate`, `fauna_frame_200`, `crowd_frame_200`…).

```bash
OPENRIDE_PERF=strict PERF_CSV=~/OpenRide/perf/tests.csv engine/tests/run_engine_tests.sh   # passage dédié aux temps
```

`UNIT=test_route_vectors engine/tests/run_engine_tests.sh` ne lance que ce test et saute les autres étapes (rendu, ERG, scénarios à faux core).

| Fichier | Lot | Vérifie |
| --- | --- | --- |
| `test_route_vectors.gd` | A | `route_data.gd` contre `docs/contracts/world/route_test_vectors.json` (42 vecteurs) |
| `test_theme_loader.gd` | I5, U5 | Validation, fusion avec le thème `default` et chargement de textures dans `theme_loader.gd` (52 vérifications, dont la lecture d'un thème 1.0 après le passage du défaut en 1.2, et le thème 2.0 en pack de biomes : accepté, erreurs du pack refusées) |
| `test_biome_model.gd` | U5 | Couche biome (`biome_layer.gd`) et modèle de biome (`biome_model.gd`) : validation des tuiles, exemple du contrat lu sur disque, dégradé continu à travers un bord de tuile, `top_biomes` en `low`, forçage et `--biome=`, thème 1.x identique pour les 16 biomes, thème 2.0 de l'exemple, `blend`, coût de `weights_at` |
| `test_ground_details.gd` | U8 | Détails de sol (`ground_details.gd`) : rien sans modèle de biome, budgets de `living(preset)` et décor vivant coupé, savane (herbes hautes, termitières), montagne (rochers), prairie (rien), aucun objet à moins de 3 m du bord sur un parcours de 5 km à épingle, coût par image, placement déterministe, teinte de la variante régionale, maillages (80 faces, normales sortantes) |
| `test_biome_textures.gd` | U6 | Sols des biomes (`biome_textures.gd`) : estimation de la mémoire vidéo et niveau retenu (2 048 px, 1 024 au-delà de 1 Go, couleurs unies), couches de sol des 16 biomes sans doublon, biomes en usage (forçage, parts du manifeste), poids d'une tuile (ordre des parts, 3 biomes en `low`, tuile absente, forçage), matériau de tuile et ombre des nuages recopiée |
| `test_vegetation_biomes.gd` | U7 | Espèces construites par code (`tree_species.gd`, moins de 300 triangles, dimensions) et végétation par biome (`tree_renderer.gd`, `vegetation_placer.assign_species`) : modèle inactif identique, tuile méditerranéenne à plus de 80 % d'espèces méditerranéennes, oasis, polaire sans arbre, limite des arbres, groupes par espèce, budget |
| `test_fauna_biomes.gd` | U12, U17 | Faune par biome (`fauna_placer.gd` BIOME_SPECIES et BIOME_GROUPS, `fauna_renderer.gd`) : prairie tempérée identique à P11, zèbres et girafes de la savane à plus de 150 m de la route, espèces de la montagne, de la toundra, de la jungle, du littoral et de la zone humide, dromadaires près de l'eau, aucun animal sur la chaussée, densités mélangées, mouettes sans croassement, budgets de `low`, branchement du modèle de biome dans `world_streamer.gd` (`--biome=savanna`, `auto`) |
| `test_menu_model.gd` | K5 | Navigation des menus (`menu_model.gd`) : 12 scénarios d'événements du Click (focus, éléments désactivés, boucle, retour, confirmation, liste vide), événements inconnus, aucun nœud créé |
| `test_key_map.gd` | O17 | Clavier = Click (`key_map.gd`) : chaque ligne du tableau du clavier de la spécification générale §7.1 (touches, synonymes de l'appui long, Échap = Y), seuils de 0,5 s et 0,9 s, zone floue (± ambigus, rien pour A et Z), Maj lue à l'appui, relâchement sans appui, perte du focus, touches sans rôle (P, Espace, Tab, Retour arrière) |
| `test_menu_style.gd` | menus, étape 1 | Thème commun des menus (`ui_theme.gd`) : contrastes (texte 7:1, couleurs de rôle 4,5:1 sur les cartes), aucune police sous 16 px, hiérarchie des tailles ; aide des boutons (`button_help.gd`) : A maintenu pour valider en tête, seulement A, +, B et Y (§7.1), rôle de Y selon l'écran ; pictogrammes (`ui_icons.gd`) de toutes les entrées de l'accueil, de Prêt, de la pause et de la confirmation ; menu en plein écran avec l'accueil entier, sélection encadrée, désactivé atténué, détail à droite, fiche dans la carte de Prêt ; raison de la pause sous le titre ; table des couleurs de données (couleurs en dur : `test_theme_colors.gd`) ; étape 2 : chiffres clés et lignes des fiches de parcours et d'entraînement (`catalog_model.gd`), carte selon l'écran et le focus (`menu_flow.card`), aperçu de la création, graphique choisi par `detail_card.gd` (profil, blocs, aucun) ; étape 3a : rangées des réglages (valeur à droite, curseur, modification en place), carte d'un réglage, aide « Enregistrer » en modification ; étape 3b : fiches du test de FTP (blocs de la rampe et des 20 minutes comme le core), des plans et de la séance du jour, de l'appairage (barres de signal, enregistré, erreur) |
| `test_theme_colors.gd` | X38 | Couleurs du thème : aucune couleur écrite en dur hors de `ui_theme.gd` dans les scripts d'interface (ceux qui chargent `ui_theme.gd`, plus `banner.gd`, `bots_view_model.gd`, `ui_icons.gd`) ; détecteur vérifié sur une source fabriquée (`Color(1, 0, 0)`, `Color.BLACK`, `Color8`, `Color.html` trouvés ; `Color(UiTheme.X, alpha)`, `Color.TRANSPARENT` et commentaires permis) ; message avec fichier, ligne et couleur du thème la plus proche |
| `test_vegetation_placer.gd` | K3 | Placement des arbres (`vegetation_placer.gd`) : déterminisme et empreinte figée, densité par `kind`, bruit sans zone, exclusions (route, limite des arbres, pente, trous), temps d'une tuile |
| `test_hud_view_model.gd` | K2 | Modèle de vue du HUD (`hud_view_model.gd`) : textes et valeurs limites, profil d'altitude (ouvert et boucle), prochaine montée, temps de `profile` |
| `test_building_mesh.gd` | L1 | Maillage 3D des bâtiments extrudés (`building_mesh.gd`) : murs à arêtes vives, toit plat avec cour intérieure, sens des anneaux, couleurs déterministes par `id`, cas invalides et temps de 500 bâtiments |
| `test_water_mesh.gd` | L2 | Maillage de l'eau (`water_mesh.gd`) : cours d'eau en ruban (droits et en coude), plans d'eau avec îles, largeur par défaut, cas invalides et déterminisme ; lot P12 : matériau sans `shimmer` identique à celui d'E4, ondes du matériau `shimmer` poussées dans le sens du vent |
| `test_theme_render_params.gd` | L3 | Paramètres de rendu tirés du thème (`theme_render_params.gd`) : uniforms terrain, fonction de référence du mélange herbe/roche/neige, poids triplanaires, route et direction du soleil ; nuages du thème 1.2 (`cloud_params`, lot P6 : valeurs par défaut et bornes) |
| `test_terrain_material.gd` | E2 | Instanciation et configuration du shader triplanaire (`terrain_material.gd` et `terrain.gdshader`) : uniforms du thème et constantes de L3, textures (avec mipmaps), ligne médiane de la route sur une texture de thème, tuiles sans couleur de sommet (le rendu réel est vérifié dans `tests/render/`) |
| `test_render_quality.gd` | E1 | Brouillard de limite (`render_quality.gd`, `main.tscn`) : mode profondeur à pleine opacité (`fog_density` = 1), début et fin avec et sans terrain |
| `test_quality_presets.gd` | L4, P4, P16, P25, P26, P28, P29, S1 | Préréglages de qualité (`quality_presets.gd`), budgets du décor vivant `living()` (coupure comprise) et arguments `--quality` / `--theme` de `engine_args.gd` ; arguments `--living=on|off` (lot P16) et `--culling=on|off` (lot S1) ; véhicules lointains 6, 12 et 24 (lot P25) ; engins volants 4, 8 et 12 (lot P26) ; bateaux 4, 8 et 16 (lot P29) ; cyclistes 4, 8 et 16 (lot P28) |
| `test_audio_mix.gd` | volumes du menu | Volumes par catégorie (`audio_mix.gd`, docs/AUDIO.md) : bus `Ride`, `Ambience` et `Events` créés une fois et envoyés à `Master`, courbe (100 % = 0 dB, 50 % ≈ −12 dB, 0 % = coupé), `apply_settings` limité aux réglages `audio.*`, chaque lecteur sur le bus de sa catégorie (sound_player, véhicules, foule, passants), volumes affichés en curseur dans Réglages |
| `test_fps_counter.gd` | Réglages | Compteur d'images/s du HUD (`fps_counter.gd`, réglage `render.fps`) : caché par défaut et pour une valeur inconnue, texte « N images/s · p99 M ms » une fois par seconde, saccades visibles dans le p99, police d'au moins 16 px, choix affiché « oui » / « non » |
| `test_display_mode.gd` | – | Mode d'affichage (`display_mode.gd`) : trois modes vers `DisplayServer` (fenêtré, plein écran sans bordure, exclusif), taille de fenêtre de `project.godot`, rien d'appliqué sans écran, souris masquée en séance et visible dans les menus, argument `--display` de `engine_args.gd` (fenêtre par défaut, repli avec message) et textes du réglage `render.display` |
| `test_banner_layout.gd` | – | Placement du bandeau d'alerte (`banner.gd`, `layout_for`) : à droite du HUD s'il reste 360 px, sinon dessous, jamais par-dessus, de 800 à 3 840 px de large |
| `test_sound_model.gd` | L5, P10 | Modèle sonore sans affichage (`sound_model.gd`) : vent, roue libre (délai 0,5 s et arrêt à > 10 W), hystérésis des points d'intérêt, lissage 12 dB/s et déterminisme ; lot P10 : vent selon la vitesse dans l'air (vent de face et de dos, rafales), roue libre à la cadence, 171 coups/s à 36 km/h, un « clac » par reprise, silence immédiat en pause |
| `test_render_quality.gd` | E3, P17, S1 | Application des préréglages de qualité (`render_quality.gd` et `quality_presets.gd`) : caméra, ombres, SSAO, MSAA, brouillard en profondeur et volumétrique, rayon gardé du tri du visible (lot S1) ; brume de la météo (`weather_fog_range`) |
| `test_tree_renderer.gd` | E3 | Rendu et gestion des arbres (`tree_renderer.gd`) : LOD0 (0-300 m avec ombres) et LOD1 (300-1500 m sans ombre), déterminisme, exclusions (route, pente, limite des arbres), budget d'instances |
| `test_culling.gd` | S1 | Tri de ce que la caméra voit (`view_culling.gd`) : secteur du champ (devant, derrière, de biais, caméra dans la tuile), caméra active passée au tri (vue subjective, caméra 6 m derrière et 3 m au-dessus, caméra latérale), rayon gardé selon les ombres du préréglage, marge de maintien des tuiles chargées, épingle : chaque tuile visible est demandée au moins 100 m avant d'être vue ; jointures des tuiles proches (`seam_gap` du mode test) dans les quatre directions et marche de 1 m détectée |
| `test_hud_view.gd` | E3 | Affichage du HUD (`hud_view.gd`) : valeurs principales (>= 48 px), libellés (>= 24 px), profil d'altitude (120 colonnes), prochaine montée, mise en page sans chevauchement à 1280x720 et 1920x1080 |
| `test_free_erg_menu.gd` | O18 | ERG d'une session libre : lignes de l'écran de pause (mode SIM / ERG / ERG cadence, puissance et cadence cibles, modification en place, Y annule, `set_ride_mode`), aucune ligne pendant un entraînement, bandeau « ERG libre » et « ERG cadence » (plage, trop vite, trop lent) sans temps restant, ligne ERG du HUD, rappel des commandes selon le mode |
| `test_erg_view.gd` | N7 | Bandeau et histogramme ERG (`erg_view.gd`) : textes du bandeau (bloc i/n, type, cible biais compris, temps restant, cible suivante, pause), zones de Coggan aux seuils de `openride-core summary`, largeurs des blocs selon le profil v1.1, curseur juste à la seconde, repli en cases égales sans profil, caché en SIM, mise en page à 1280x720 et 1920x1080 |
| `test_workout_chart_view.gd` | O14 | Vue des courbes (`workout_chart_view.gd`) : légende par taille, tiret pour une valeur absente, mode inconnu ramené à la taille réduite, courbes à la place de l'histogramme ERG sauf en `hidden`, profil retrouvé par nom |
| `test_summary_view_model.gd` | N4 | Modèle de l'écran de fin de séance (`summary_view_model.gd`) : 10 lignes du bilan enrichi dans l'ordre fixé, 3 lignes en v1, blocs ERG avec déviations et couleurs, fichier FIT seul, écran de menu avec confirmation de quitter, aucun nœud créé |
| `test_devices_view_model.gd` | N5 | Modèle d'état des appareils (`devices_view_model.gd`) : lignes d'état en v1.1 et repli v1, alertes de perte/reconnexion et batterie sous 20 % / 10 %, `ready_to_ride`, aucun nœud créé |
| `test_catalog_model.gd` | N3 | Modèle de catalogue (`catalog_model.gd`) : conversion des parcours et entraînements au format de menu, labels, tri, focus sautant les éléments désactivés, aucun nœud créé |
| `test_cue_model.gd` | essai | Consignes d'essai (`cue_model.gd`) : lecture et tri du fichier `~/OpenRide/Essais/<parcours>.consignes.json`, consignes invalides ignorées, chaque consigne donnée une seule fois à sa distance, réarmement après un nouveau départ, aucun nœud créé |
| `test_osm_decor_route.gd` | – | Décor OSM et route : aucun arbre dans un bâtiment ni à moins de 3 m de ses murs (`tree_renderer.gd`, `exclude_buildings`), cours d'eau coupés au passage de la chaussée et ruisseau sur le bas-côté retiré (`osm_streamer.gd`, `cut_lines_at_road`) |
| `test_far_terrain_carve.gd` | – | Terrain lointain abaissé sous la route (`terrain_tiles.gd`, `carve_under_route`) : vallée en V à 30 % et route en S à 7 %, dépassement de 8 m sans correctif, au moins 2 m sous la chaussée après, aucun sommet relevé, bord commun de deux tuiles identique |
| `test_sound_player.gd` | E4, P26, P29 | Lecteurs et sons procéduraux du parcours (`sound_player.gd`) : synthèse au démarrage (< 500 ms), vent, roue libre, limitation à 4 lecteurs 3D actifs, volumes à 0,5 dB de `sound_model.gd` ; fonds d'ambiance du lot P9 (6 boucles, lecteurs non spatialisés, `.ogg` de remplacement lu dans `~/OpenRide/Sounds/` avec `tests/data/sounds/rain.ogg`, cloches de l'heure pleine) ; lot P10 : boucle du vent sans clic, `pitch_scale` du cliquetis calé sur le modèle, un « clac » par reprise ; lot P13 : sons `vehicle_pass` et `tractor_engine` ; lot P15 : son `crowd_cheer` ; lot P21 : quatre sons brefs de passants ; lot P26 : sons `helicopter_rotor` et `airliner_rumble` ; lot P29 : `barge_engine` en boucle et `ship_horn` joué une fois |
| `test_ambience_model.gd` | P9 | Fonds d'ambiance (`ambience_model.gd`) : oiseaux en forêt, insectes au champ, eau à 20 m, oiseaux 24 dB plus bas la nuit, pluie, altitude, pause, au plus `ambience_voices` fonds audibles, au plus 3 dB en 0,5 s, cloches (3 coups à 15 h), voisinage tiré des couches, coût de `evaluate` |
| `test_anim_clock.gd` | correctif « image figée » | Horloge des animations (`anim_clock.gd`) : personnages (`crowd.gdshader`) et animaux (`fauna.gdshader`) animés par l'uniforme global `anim_time` et non par `TIME`, déclaré dans `project.godot`, horloge qui avance sans reculer, `main.gd` qui la fige quand le core ne répond plus |
| `test_grass_tufts.gd` | P5, Y11 | Touffes d'herbe (`grass_tufts.gd`) : gerbe de brins, quatre teintes tirées, fondu au loin avant la fin de la fenêtre (Y11) ; 0 décor vivant coupé, budget, déterminisme, bande de 2 à 15 m hors route, bâtiments, eau et pentes, coût par image ; matériaux de balancement de `tree_renderer.gd` (d'origine quand le décor vivant est coupé) |
| `test_sky_clouds.gd` | P6 | Ciel nuageux (`sky_clouds.gd`) : `off`, couverture nulle ou décor vivant coupé rendent le matériau actuel, une couche en `low`, deux en `high`, ombre des nuages seulement en `high` (uniform faux par défaut dans `terrain.gdshader`), défilement vers où souffle le vent, coût de `update` |
| `test_weather_model.gd` | P8 | Météo légère (`weather_model.gd`) : brume de vallée plus forte sous `valley_alt_m`, constante sans heure solaire, maximale à 6 h et nulle à 11 h avec, pluie et neige jamais ensemble, neige au-dessus de `snow_line_m`, thème sans `weather` sans effet, coût de `evaluate` |
| `test_weather_particles.gd` | P8 | Pluie et neige (`weather_particles.gd`) : budget de `living(preset)`, nœud vide à budget nul, boîte de 40 m centrée sur la caméra après 500 m, repère du monde, vent du nord qui pousse vers le sud, aucun effet sans `weather`, coût de `update` |
| `test_wind_model.gd` | P4 | Modèle du vent (`wind_model.gd`) : repère, lissage (90 % en 1,2 s sans dépassement), phase continue, expiration du vent du core et vent du thème, vent apparent, coût de `evaluate` |
| `test_fauna_placer.gd` | P11, P23, P24 | Placement des animaux (`fauna_placer.gd`) : déterminisme, troupeaux de 3 à 12 bêtes autour des points `livestock`, aucune bête à moins de 4 m de l'axe, dans l'eau ou un bâtiment, ni sur une pente au-dessus de 25 %, oiseaux jamais sous 15 m du sol, pas de bétail sans point `livestock`, pas de chevreuil avec `fauna.deer = 0`, au plus un chevreuil tous les 3 km ; P23 : rapaces, volées en V et corneilles par tronçon (fréquence, hauteur, distance à la route, jamais au-dessus d'une forêt ni sur une pente de 50 %, déterministes par parcours, comptés dans le budget des oiseaux) ; P24 : vaches et chevaux dans les prés, moutons sur les prairies en pente de 30 %, aucun troupeau de plus dans un pré à point `livestock`, lièvres de 15 à 60 m de la route, au plus 2 par kilomètre |
| `test_fauna_behaviour.gd` | P11, P23, P24 | Comportement et affichage des animaux (`fauna_behaviour.gd`, `fauna_renderer.gd`) : chevreuil en fuite à 59,5 m, loin de la route, disparu en moins de 6 s ; écart des oiseaux ; budget de `living(preset)` avec 200 candidats (les plus proches gardés), aucun nœud créé ; P23 : corneilles qui s'envolent à 35 m en croassant et se reposent plus loin, volée en V (vitesse, forme, fin de trajectoire), rapace sur son cercle et ses cris toutes les 30 s à moins de 250 m, ailes repliées au sol ; P24 : un meuglement par période de 40 s à 100 m, hennissements, lièvre qui file en zigzag à 24 m et disparaît, chevaux et lièvres affichés ; mise à jour de 177 animaux de toutes les sortes sous 0,45 ms par image |
| `test_wind_turbines.gd` | P12 | Éoliennes (`wind_turbines.gd`) : rotor arrêté sous 10 km/h puis de 5 à 17 tr/min, nacelle face au vent en 38 s après un changement de 90°, au plus 3 °/s, 20 éoliennes au plus (les plus proches), aucun nœud créé ; 20 éoliennes et 30 drapeaux mis à jour sous 0,2 ms par image |
| `test_flags.gd` | P12 | Drapeaux (`flags.gd`) : tissu orienté vers où souffle le vent à 15° près, un drapeau par village sans mât OSM à 150 m, au même endroit à chaque chargement, 30 drapeaux au plus |
| `test_crowd_model.gd` | P15 | Spectateurs (`crowd_model.gd`, `crowd_renderer.gd`) : seulement dans le dernier kilomètre d'un col de 8 km, plus nombreux près du sommet, aucun sur une montée de 2 km (sauf `crowd_all_climbs`), à 0,3 m au moins du bord, des deux côtés, aucun dans l'eau, déterministe ; « encourage » à 10 m, « calme » à 100 m ; clameur nulle hors des zones, croissante, plus forte après un dépassement de bot ; budget du préréglage, les plus proches gardés ; 200 spectateurs mis à jour sous 0,2 ms |
| `test_fauna_mesh.gd` | Y14, P24 | Maillages des animaux (`fauna_renderer.gd` `build_mesh`) : au plus 1 500 triangles, robe et parties sombres ; oiseau de 0,9 m d'envergure le long de x, poids de l'aile 0 sur le corps et 1 au bout, tête vers +z ; bêtes (dont cheval et lièvre de P24) aux pieds à y = 0, tête qui broute à l'avant, pattes immobiles |
| `test_people_mesh.gd` | Y14 | Personnages construits par code (`people_mesh.gd`) : tenues relues telles quelles et variées, zones de couleur, pieds au sol et 1,76 m, tibias, porte-drapeau, au plus 1 000 triangles ; chien qui trotte en diagonale, banc ; palettes et articulations passées au shader |
| `test_passersby_model.gd` | P21 | Passants (`passersby_model.gd`, `crowd_renderer.gd` en mode « passants ») : 10 à 30 personnes dans un village de 500 m, 6 à 17 sur 5 km de campagne, rôles selon le lieu, déterministe ; jamais à moins de 1 m du bord ni dans l'eau, ni dans la zone des spectateurs d'un col ; marcheurs sur leur segment et tournés dans leur sens de marche ; une partie salue au passage, une seule fois ; sons espacés d'au moins 20 s, à moins de 30 m, aucun pendant un bip ; budget, plus proches, chiens et bancs ; 80 passants : modèle sous 0,1 ms, avec la sélection sous 0,2 ms |
| `test_traffic_model.gd` | P13, P25 | Circulation (`traffic_model.gd`, `traffic_renderer.gd`) : séance de 30 km à 30 km/h (3 à 15 véhicules, au moins un dépassement, rien au-dessus de la limite de neige ni sur la pente de 10 %), jamais deux véhicules au même endroit ni à moins de 1,5 m du cycliste, jamais de dépassement face à un véhicule, 12 graines de plus, déterminisme, budget (0 : aucun), pause, affichage à la place du modèle sans nœud créé, mise à jour sous 0,1 ms ; lot P25 : sept sortes tirées d'après leurs parts, vitesses dans la plage de chaque sorte, phares (brume, pluie, soleil bas), chaque sorte habillée (caisse, roues, peinture), son à la hauteur de la sorte |
| `test_vehicle_mesh.gd` | P25 | Maillages des véhicules (`vehicle_mesh.gd`) : huit sortes de 2 000 triangles au plus, à la taille hors tout de `traffic_model.gd`, posées sur le sol, phares devant et feux derrière, toutes les zones de couleur, faces dans le sens de leurs normales, roues à leur place, déterminisme, palettes |
| `test_road_traffic_model.gd` | P25 | Circulation des routes voisines et tracteurs des champs (`road_traffic_model.gd`, `road_traffic_renderer.gd`) : chemins des routes (rue trop courte et chemin piéton écartés), sens unique, piste à tracteurs, une vitesse par voie ; champs cultivés et leurs rangs en zigzag posés sur le sol ; deux minutes de circulation (budget, voie de droite, pente, jamais deux véhicules au même endroit, tri des plus proches), déterminisme, pause, retrait, affichage en MultiMesh, phares, coût par image |
| `test_road_cyclists_model.gd` | P28 | Cyclistes du décor (`road_cyclists_model.gd`, `road_cyclists_renderer.gd`) : 20 km de plaine (15 à 30 groupes) et 10 km de montée (20 à 40), jamais à moins de 1,2 m du cycliste ni d'un bot, groupes doublés et qui doublent, budget, déterminisme, « Salut ! », pas de groupe en face pendant qu'un véhicule passe, vitesse à puissance constante en pente, cadence, pause, affichage et coût par image |
| `test_sky_traffic_model.gd` | P26 | Ciel (`sky_mesh.gd`, `sky_traffic_model.gd`, `sky_traffic_renderer.gd`) : maillages à leur taille et faces orientées ; deux heures de ciel clair (avions de ligne, hélicoptère, montgolfières, au plus `MAX_AT_ONCE` de chaque sorte), avions lointains dessinés à 2 500 m dans leur vraie direction, hélicoptère à 120–250 m ; parapentes au-dessus des montées, montgolfières qui dérivent avec le vent ; rien sous la pluie, dans la brume ni par grand vent, pas d'avion par ciel couvert ; budget et priorité, pause, déterminisme ; affichage, traînées, rotor, sons, coût par image |
| `test_boat_model.gd` | P29 | Bateaux (`boat_mesh.gd`, `boat_model.gd`, `boat_renderer.gd`) : maillages à leur taille, flottaison et faces ; lac avec une île (voiliers, barques, pédalos près du bord, toujours sur l'eau et écartés, loin de la route), étangs, ruisseau, canal (péniches sur leur moitié droite), rivière (canoës plus rapides dans le sens du courant), mer (voiliers près de la côte, ferry et porte-conteneurs au large) ; gîte et bôme sous le vent, petits bateaux rentrés par grand vent ou sous la pluie ; budget, plan d'eau compté une fois, déterminisme, pause, tronçons ; affichage, sillages, voile, sons, coût par image |
| `test_climb_detector.gd` | P14 | Montées (`climb_detector.gd`) : col de 8 km à 7 % et bosse de 400 m à 5 % (une montée, sommet à ± 20 m, pente 7,0 % ± 0,2), rampes séparées par 200 m fusionnées, 1 km à 9 % gardé, parcours vallonné sans montée |
| `test_records_view_model.gd` | T10 | Écran « Records » (`records_view_model.gd`, `menu_flow.gd`) : fichier absent (segments listés, désactivés), version inconnue et fichier illisible (« Aucun record lisible »), meilleur temps par segment, tables « sans bonus » et « avec bonus » séparées (temps au dixième, date, W et W/kg), segment sans record, entrée « Records du parcours » de l'écran Prêt, A court bascule la table, Y revient, option « Bonus » affichée oui / non |
| `test_roadside_model.gd` | P14 | Bord de route (`roadside_model.gd`, `roadside_props.gd`) : nombres au format français, panneaux d'approche à 5, 3, 2 et 1 km (« Sommet à 3 km », « Pente moyenne 7 % »), panneau du sommet (nom OSM ou « Sommet », altitude au mètre), une borne par kilomètre sans doublon sur une boucle, rien dans l'eau ni sur un pont, côté droit à 1,5 m du bord, panneaux lisibles à 30 m et face au cycliste, tronçons posés et retirés |
| `test_wind_view_model.gd` | P4 | Indicateur du vent et de l'abri (`wind_view_model.gd`) : secteurs et hystérésis, verdict favorable ou non, niveaux d'intensité et rafale isolée, abri, indicateur caché sans vent |
| `test_camera_pitch.gd` | Q2 | Inclinaison de la caméra selon la pente (`camera_follow.gd`) : 0° sur le plat, atan(pente) à 8 %, lissage temporel (saut < 1° par image), bornes ±12° |
| `test_visual_grade_scale.gd` | Q2 | Facteur d'exagération visuelle (`road_builder.gd`, `terrain_tiles.gd`, `world_streamer.gd`, `osm_streamer.gd`) : élévations k=1.0 et k=1.5, terrain sous la route, hauteur des bâtiments inchangée et base au sol, HUD inchangé, surcoût < 5% |
| `test_living_decor.gd` | P17, P25 à P29 | Décor vivant, deuxième vague (`living_decor.gd`, `osm_streamer.gd`, `world_streamer.gd`, `hud_view.gd`) sur un parcours OSM de synthèse avec col et village : montée, chiffres peints et panneaux, éolienne et drapeau, spectateurs et passants, pluie, chaussée mouillée, brume de vallée, véhicules jamais sur le cycliste et figés en pause, troupeau au sol hors de la route, panneaux retirés avec les tronçons, « Abri 30 % », coupure avec `living = false`, routes voisines et tracteurs des champs jamais sur le parcours, phares sous la pluie, circulation lointaine figée en pause, ciel figé en pause et coupé avec `living = false` (lot P26), barque et péniches jamais sur le parcours, feux sous la pluie, figées en pause (lot P29), cyclistes du décor croisés (lot P28), coût par image ; lot P27 : aucun nœud de la deuxième vague créé en route (toutes les sortes activées), enveloppe de P23 à P26, P28 et P29 en `medium` (`decor_vivant_2_frame`, 0,8 ms) |
| `test_living_world.gd` | P16 | Branchement du décor vivant (`living_world.gd`, `hud_view.gd`) : ciel de P6 à la place du ciel actuel, vent du core vers le décor, nuages dans le sens du vent, indicateur « face » / « dos » / neutre, voisinage sonore au plus 2 fois par seconde à partir des contours chargés, exclusions de l'herbe, panneau du vent sous la colonne de gauche et caché sans vent, `living = false` : ciel, herbe et ambiance de la 1.0 ; coût par image |
| `test_segment_markers_model.gd` | T8 | Segments et arches de bonus (`route_data.gd`, `segment_markers_model.gd`, `segment_markers.gd`) : couche `segments` lue, champ inconnu ignoré, couche invalide ignorée ; portiques de départ et d'arrivée, panneaux « Sprint dans 1 km, 500 m, 200 m », pied de montée (catégorie, longueur, pente) et « Sommet dans 1 km, 500 m » sur le parcours de démonstration ; boucle ; arches et lecture de `powerups.toml` identiques au core (vecteurs `tests/data/arch_schedule_vectors.json`) ; montées du décor prises dans la couche ; fenêtre autour de la caméra, arches cachées sans bonus, moins de 50 nœuds actifs |
| `test_segment_hud_model.gd` | T9 | Blocs segment et bonus du HUD (`segment_hud_model.gd`, `hud_view.gd`) : approche « Montée 2 · cat. 3 dans 1,2 km », chrono, écart au record négatif en vert et positif en rouge, rien sans record, nom lu dans la couche `segments`, résultat (temps, « Record ! » et ancien record, place, points) affiché 8 s, `segment_result` répété 3 fois affiché une fois, bonus en réserve « Z : Aéro », bonus actif et barre de temps, bloc bonus caché sans champ `powerup` (ERG), blocs sous le panneau de droite sans chevauchement |
| `test_bot_hud_model.gd` | T15 | Encart des bots du HUD (`bot_hud_model.gd`, `hud_view.gd`) : voisins devant et derrière avec l'écart « +1,2 s » / « −3,1 s », ligne qui disparaît à `null`, ligne par bot (nom et profil traduit, FTP en W et en W/kg, réserve W′, maillot), porteurs des maillots (« toi »), bot sans champ de profil, lignes qui tiennent, colonne de droite empilée sans chevauchement au-dessus du profil d'altitude |
| `test_route_parts.gd` | W10 | Route d'un monde vivant lue par parties (vecteurs de référence découpés en parties de 30 m, route de 5 400 m en parties de 1 km) : mêmes valeurs à 1e-6 près, remplacement depuis la partie 3 (parties 0 à 2 : mêmes objets), trou entre parties et dossier non vivant refusés |
| `test_live_world.gd` | W10 | `live_world.gd` : révision lue en tâche de fond et route échangée, révisions manquées (relecture complète), révision en avance sur le disque, partie illisible (route gardée), amorces des branches non suivies à moins de 1 500 m, recentrage (multiple de 1 000 m, erreur sous 1 mm à 60 km), carrés de couches à coordonnées relatives au coin de tuile, ruban fondu des amorces |
| `test_live_streamer.gd` | W10 | `world_streamer.gd` sur un monde vivant : tronçons gardés et refaits après `swap_route`, amorces créées et libérées |
| `test_junction_view_model.gd` | W12 | Panneau du carrefour : invisible à 301 m, visible à 300 m, disparu après le carrefour, branches de gauche à droite, flèches à 15°, libellés, pentes à 1 %, verrouillage, flèches ← et → (deux `choose_branch` vers les bonnes branches, rien si verrouillé), placement sans recouvrement en 1 920 × 1 080 et 1 280 × 720, attribution |
| `test_world_menu_model.gd` | W11 | Menu du monde ouvert sans affichage : rotation et inclinaison du globe, recherche « Ventoux » → carte → cap 90° → `start_open_world` avec les bons arguments, curseur accroché à la route la plus proche, boucle et destination, retours, épinglage des régions, texte et barre de préchargement |
| `test_world_menu_view.gd` | W11 | Entrée « Monde ouvert » de l'accueil, affichage du globe, de la recherche, de la carte et du préchargement avec attributions, parties de `world_map` et `places` réunies (copie renvoyée ignorée), `open_world` gardé entre deux trames |

## Étapes du script

1. **Tests unitaires** : tous les fichiers de `engine/tests/unit/` (ci-dessus).
2. **Couches OSM** (`test_osm_layers.gd`, lot K4 et `test_osm_streamer.gd`, lot E4) : `make_osm_world.py` produit avec le vrai compilateur (installé : `pip install -e compiler`), sans réseau, un `.world` à cinq couches (dont, depuis P22, `roads` et les prés et champs de `vegetation`) à partir des réponses Overpass enregistrées (`compiler/tests/data/osm/`) et écrit les nombres attendus (`expected.json`) ; le test vérifie que `osm_layers.gd` lit autant d'éléments que le compilateur en a écrits, tronçon par tronçon, puis les fichiers corrompus (JSON invalide, anneau de 2 points, `density` 1,5, `kind` inconnu, version `2.0`, terrains ouverts acceptés, routes voisines invalides ignorées), `chunks_for_window` et le temps de lecture de 200 bâtiments.
3. **Rendu par tronçons** (`test_world_streamer.gd`, lot E1) : le script écrit d'abord la démo avec terrain synthétique (`python -m openride_core.tools.fake_world --demo --terrain`, lancé avec `PYTHONPATH=core/src`, bibliothèque standard seulement) dans un dossier temporaire, puis vérifie le ruban, les tuiles et la fenêtre de chargement (tableau ci-dessous). Ce test ne doit écrire aucune erreur ni aucun avertissement.
4. **Coutures du sol multi-biome** (`test_biome_seams.gd`, série U, sous Xvfb) : la même démo, copiée avec une couche biome qui passe de la prairie tempérée au désert de sable d'ouest en est, est chargée par `world_streamer.gd` comme en séance ; vue de dessus sans éclairage du bord commun de deux tuiles proches loin de la route : pas de marche de couleur au bord (au plus 3 fois l'écart entre colonnes voisines et 3 %), puis contrôle du test avec une tuile volontairement fausse.
5. **ERG** (`test_erg_view_model.gd`, lot I6) : modèle de vue ERG (`erg_view_model.gd`), histogramme `profile_bars` et scénario des 10 blocs face à `fake_core.py --erg-workout` (bips à T − 3 s ± 0,1 s).
6. **Scénarios IPC** : `fake_core.py` (Python 3, bibliothèque standard) joue le rôle du core ; l'engine tourne sans écran avec `--test-mode` et charge la démo avec terrain du même dossier temporaire.
7. **Contrôle de la sortie de Godot** : aucune erreur ni aucun avertissement de script, hors avertissements connus du mode sans écran (objets non libérés à la sortie, mesh nul).

Thème d'essai pour le PC cible (hors du script) : `make_texture_theme.py` écrit un thème à trois textures 2 048² dans `~/OpenRide/Themes/essai_textures` ; procédure dans [docs/ESSAI_GRAPHIQUE_E2.md](../../docs/ESSAI_GRAPHIQUE_E2.md).

Lancement seul du test de rendu :

```bash
PYTHONPATH=core/src python3 -m openride_core.tools.fake_world --demo --terrain --out /tmp/routes
"$GODOT" --headless --path engine --script res://tests/test_world_streamer.gd -- /tmp/routes/demo.world
```

## Rendu par tronçons (lot E1)

| N° | Test | Vérification |
| --- | --- | --- |
| 1 | Raccord route-terrain | À s = 0 puis 2 500 m : objets chargés = fenêtre attendue (calculée à part) ; centre du ruban = `sample_point(s).y` à 1 cm ; à 3 m du bord, terrain affiché sous la route de 0 à 20 cm ; tuile lointaine abaissée de 2 m |
| 2 | Durée sans fuite | De 0 à la fin à 20 m/s simulés (60 images/s, sans attente réelle) : `MeshInstance3D` bornés, aucun tronçon manquant sous la caméra ni 10 s plus loin, `Performance.OBJECT_COUNT` en fin à ± 5 % du premier tiers |
| 3 | Jointures | Dernière coupe d'un tronçon = première du suivant, sommet par sommet (démo avec et sans terrain) |
| 4 | Terrain absent | `res://demo/demo.world` : sol plat 5 m sous l'altitude minimale, ruban affiché |
| – | Compléments | `NaN` (moyenne des voisins, puis replis), faces tournées vers le haut ; temps de construction d'un tronçon et d'une tuile |

Variables facultatives : `UNIT` et `UNIT_TIMEOUT` (tests unitaires, ci-dessus), `STATE_PORT` et `CMD_PORT` (ports de test, 15005 et 15006 par défaut, pour ne pas gêner un core réel), `SCENARIOS` (par exemple `1,2,3` ; le 1 doit venir en premier car il exige un engine qui vient de démarrer), `ENGINE_LOG` (fichier où garder le journal de l'engine).

## Scénarios

| N° | Scénario | Vérification |
| --- | --- | --- |
| 1 | `hello` jusqu'au `hello_ack` | `hello` espacés d'1 s ± 0,3 s ; aucun `hello` après le `hello_ack` ; configuration reçue journalisée |
| 2 | Commande ignorée trois fois | 4 envois du même `cmd_id`, espacés de 200 ms environ, puis accusé et fin des renvois |
| 3 | Commande jamais acquittée | Abandon entre 2,7 et 3,3 s, signal `command_failed`, message dans le bandeau, plus de renvoi |
| 4 | Core muet 1,5 s | Bandeau « core non joignable » ; la caméra avance pendant la première seconde (extrapolation), ne bouge plus au-delà de 1,1 s, ne recule jamais ; à la reprise le bandeau disparaît |
| 5 | `shutdown` | Bandeau « Le core s'est arrêté » ; l'engine reste en vie (heartbeats) et renvoie des `hello` ; un nouveau core dont `seq` repart de 1 est accepté |
| 6 | Trames `state` en désordre | La trame arrivée en retard est ignorée et comptée ; la plus récente est appliquée |
| 7 | Trame `error` | Le bandeau contient le code (`route_invalid`) |
| 8 | Heartbeats | 2 Hz ± 20 % pendant 10 s |

## Arguments de l'engine

Ils se donnent après `--` (lecture par `OS.get_cmdline_user_args()`, voir `engine/scripts/engine_args.gd`). Ils ne font pas partie du contrat IPC.

| Argument | Défaut | Rôle |
| --- | --- | --- |
| `--ipc-state-port=N` | 5005 | Port d'écoute des trames du core. S'il est occupé, l'engine affiche un message et quitte avec le code 1 |
| `--ipc-cmd-port=N` | 5006 | Port du core vers lequel partent `hello`, `heartbeat`, `cmd`, `bye` |
| `--routes-dir=CHEMIN` | `~/.local/share/openride/routes` | Dossier des parcours : l'engine charge `<dossier>/<route_id>.world` ; pour `demo`, repli sur `res://demo/demo.world` (sans terrain) si le dossier manque |
| `--test-mode` | absent | Journal de test et messages de test (ci-dessous) ; limite le rendu à 60 images par seconde |

## Ce que l'engine expose aux tests

Avec `--test-mode`, l'engine écrit sur la sortie standard des lignes `[test] clé=valeur`, lues au fil de l'eau par `fake_core.py` dans le fichier où le script redirige la sortie :

| Ligne | Moment |
| --- | --- |
| `hello_ack config={…}` | `hello_ack` reçu (configuration en JSON) |
| `state seq=N s=… session=…` | Trame `state` appliquée |
| `state_late seq=N late=K` | Trame en retard ignorée (K : total) |
| `cmd_sent name=… id=N` | Nouvelle commande |
| `cmd_acked name=… id=N sends=K` | Commande acquittée après K envois |
| `cmd_failed name=… id=N after_ms=… sends=K` | Commande abandonnée |
| `core_lost age_ms=…` / `core_returned` | Core injoignable depuis 1 s / trames reprises |
| `shutdown` | Message `shutdown` reçu |
| `banner text=…` | Texte du bandeau à chaque changement (lignes séparées par ` \| `, vide quand il disparaît) |
| `screenshot {…}` | Capture demandée par le message de test `screenshot` (tests graphiques, ci-dessus) |
| `route_loaded id=… length_m=… path=…` / `route_missing id=…` | Parcours chargé / introuvable (la ligne d'information qui précède dit si le terrain est présent) |
| `cam s=… age_ms=… frozen=0\|1 moved=0\|1` | Position affichée de la caméra, à 20 Hz ; `age_ms` : âge de la dernière trame |

Le faux core déclenche une commande par un message de test `{"type": "_test", "action": "send_command", "name": …, "args": {…}}` envoyé sur le port d'état, et une capture d'écran par `{"type": "_test", "action": "screenshot", "path": …, "tag": …}`. Hors `--test-mode`, ce type est inconnu et donc ignoré (contrat §1).

## Bout en bout (lot J8)

```bash
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_e2e.sh [--keep]
```

`run_e2e.sh` appelle `e2e_check.py`, qui lance le vrai core (`openride-core run --trainer mock --input none --autostart`) puis l'engine en `--test-mode`, tous deux avec un `HOME` temporaire et deux ports UDP libres. Chaque vérification imprime une ligne `[OK]` ou `[ÉCHEC]` avec sa mesure :

| Vérification | Attendu |
| --- | --- |
| hello puis hello_ack | moins de 3 s entre `Reçu 'hello'` (core) et `hello_ack reçu` (engine) |
| trames state | au moins 25 par seconde sur 5 s (lignes `[test] state`), `seq` croissant |
| input_event relayé | commande `input_event` `PLUS_SHORT` (`cmd_id` 10 000) envoyée par le script : traitée par le core, `Bip : PLUS_SHORT` dans la sortie de l'engine |
| perte de l'engine | engine arrêté : le script écoute le port d'état, `PAUSED` (`engine_lost`) en moins de 3 s |
| braquet | `gear` passé de 12 à 13 dans les trames du core |
| même parcours demo | `route_length_m` du core égal (à 0,05 m près) à la longueur de `route_loaded` de l'engine, qui lit le même dossier de parcours que le core |
| end_session | `FINISHED`, résumé présent, trame conforme à `docs/contracts/ipc/state.schema.json` |
| fichier FIT | écrit dans le dossier temporaire |
| Godot, core, HOME | aucune erreur ni avertissement de Godot (mêmes tolérances que `run_engine_tests.sh`), core arrêté avec le code 0, `~/OpenRide` et `~/run_trainer.log` du vrai `HOME` inchangés, moins de 60 s au total |

Le script renvoie 0 si tout passe. En cas d'échec, ou avec `--keep`, `core.log` et `engine.log` restent dans le dossier temporaire indiqué. `e2e_check.py --engine-routes-dir DOSSIER` donne à l'engine un autre dossier de parcours que le core (sert à vérifier que la comparaison des longueurs échoue).

## Essai avec le vrai core (critère 3 du lot D)

```bash
source core/.venv/bin/activate
openride-core run --trainer mock --input none --autostart > /tmp/core.log 2>&1 &
"$GODOT" --headless --path engine > /tmp/engine.log 2>&1 &
sleep 60; kill %2; sleep 1; kill -INT %1; wait
grep -c "Heartbeat engine perdu" /tmp/core.log    # attendu : 0
```
