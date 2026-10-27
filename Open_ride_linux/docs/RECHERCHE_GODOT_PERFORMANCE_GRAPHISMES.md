# Recherche : Godot, optimisation des performances et des graphismes

Date : 27 octobre 2026. Document de recherche, **sans code** : l'amélioration des graphismes et de l'IA des bots est prévue à la toute fin du projet (décision du propriétaire du 27 octobre), après tous les autres lots, et chaque étape est soumise aux budgets de performance (X2, X13, X16).

Sources : documentation officielle de Godot (dépôt `godot-docs`, branche principale, lue le 27 octobre 2026), référence des classes (dépôt `godot`, `doc/classes`), pages de version 4.4 à 4.7 (dépôt `godot-website`), plus quelques extensions et articles cités au §9. Chaque affirmation renvoie à sa source ; ce qui n'a pas pu être vérifié est marqué **à vérifier**.

## 0. Décisions du propriétaire (27 octobre)

Réponses aux questions posées après la PR #355 :

| Question | Décision |
| --- | --- |
| 1. Série Y | Validée : lots Y1 à Y10 inscrits dans `docs/lots/00_INDEX.md`, issues #357 à #366 (suivi #48). |
| 2. Ordre | Y1, Y2, puis Y4, Y6 et Y3, puis Y5 et Y7, puis Y8, Y9 et Y10. |
| 3. Y1 avancé | Oui : à faire tout de suite, avant S1 (cahier `docs/lots/LOT_Y1_brouillard_distance_prereglage.md`). |
| 4. Brouillard | Opaque à 4 km en `low`, 6 km en `medium` et 9 km en `high`. |
| 5. Godot | Migration directe vers 4.7.x (Y2) au début de la phase finale, avant les autres optimisations. |
| 6. Préréglage | `medium` au quotidien : c'est le préréglage de référence des mesures de la série Y. `low` garde le budget de la spécification (55 images/s, p99 sous 25 ms). |
| 10. Habillage | Priorités validées : toits à pans et façades texturées, puis étalonnage, puis marquages de route. |
| 8. Moteur Mobile | Essai mesuré maintenu (Y7) ; décision après la mesure. |
| 9. Imposteurs | **Notre propre version** (shader et petit outil de capture), sans l'extension externe (Y5). |
| 11. Bots à l'écran | Retard d'affichage d'environ 0,1 s accepté (mémoire de trames et Hermite, Y9). |
| 12. Comportement des bots | Bots réalistes : attaques dans les montées, fatigue, abri, calculés dans le core (Y10). |
| 13. PR #355 | Compléter puis fusionner. |
| 7. Résolution adaptative | ~~Acceptée (75–85 % avec FSR 1.0, Y6)~~ **Remplacée le 27 octobre (19 h 35)** : « utilise seulement la résolution max de mes écrans ». Rendu toujours à la résolution native, sans mise à l'échelle ; Y6 écarté, la marge du GPU sert à la qualité d'image (Y13). |

## 1. En bref

1. **La piste la plus rentable est déjà sous nos yeux :** quel que soit le préréglage, la caméra voit jusqu'à 12 km et le brouillard ne se ferme qu'à 12 km (`render_quality.gd` : `camera.far` et `FOG_TERRAIN.end` valent `WorldStreamer.FAR_RADIUS_M`), alors que le préréglage `low` annonce 3 km de vue. Fermer le brouillard et la caméra selon le préréglage réduit tout le reste (tuiles lointaines, sommets, ombres) et répond à la remarque du propriétaire du 25 octobre (« brouillard trop loin »). Coût faible, risque faible.
2. **Monter de Godot 4.3 à 4.7** (dernière version stable trouvée, juin 2026) apporte sans travail : ubershaders et précompilation des pipelines (moins de saccades à la première apparition d'un objet, 4.4), interpolation physique en 3D (4.4), génération des LOD qui garde mieux la forme (4.6), sondes de réflexion moins chères et SSR plus rapide (4.6), un tampon de constantes par passe qui accélère le rendu (4.7). C'est un lot à part, mesuré avant et après au banc.
3. **Ne pas dessiner l'invisible** (lot S1) : Godot fait déjà le tri par champ de vue et, en Forward+, une pré-passe de profondeur qui évite de colorier deux fois un pixel opaque. L'occlusion par le relief existe (`OccluderInstance3D`) mais coûte du processeur et rapporte surtout sur un relief en « pyramide » : à mesurer, pas à supposer.
4. **Niveaux de détail :** les `visibility_range` (déjà sur les arbres et les bâtiments) gagnent à passer en HLOD (un bloc simplifié par village au loin, `visibility_parent`) et en mode de fondu « Disabled » (hystérésis) plutôt que « Self », qui force la transparence pendant le fondu.
5. **Arbres lointains :** des imposteurs (un plan qui imite l'arbre sous plusieurs angles) au-delà de 1 500 m permettraient de garder une forêt visible jusqu'au brouillard pour quelques sommets par arbre.
6. **Résolution :** `scaling_3d_scale` à 0,75–0,85 avec FSR 1.0 (Forward+ seulement) est le levier le plus direct si le rendu est limité par la carte graphique ; une résolution adaptative se construit en GDScript avec le temps GPU mesuré (déjà relevé par la sonde X13). Le rendu à débit variable (VRS) est **exclu** : la GTX 1060 (Pascal) ne le gère pas.
7. **Bots :** le lissage passe par une petite mémoire de trames (2 à 3 trames de retard, environ 70–100 ms) et une interpolation d'Hermite qui respecte la vitesse ; l'écart latéral et les dépassements se traitent par des comportements de pilotage simples (Reynolds). Rien de cela n'est coûteux en rendu ; le coût est dans le nombre de bots animés, qui se règle par niveaux de détail.

## 2. Ce que fait le moteur aujourd'hui (lu dans le code du 27 octobre)

| Sujet | État actuel | Fichier |
| --- | --- | --- |
| Moteur de rendu | Forward+ pour tous les préréglages (`project.godot`). La clé `renderer_hint: "mobile"` du préréglage `low` n'est lue nulle part : `low` tourne en Forward+. | `project.godot`, `quality_presets.gd` |
| Distance de vue | `view_distance_m` 3 / 5 / 8 km par préréglage, mais `camera.far` = 12 km et brouillard de profondeur de 3 km à 12 km avec relief (300 m à 3 km sans relief), identiques pour tous les préréglages. | `render_quality.gd`, `world_streamer.gd` |
| Ombres | Soleil avec ombres, distance 150 / 300 / 600 m ; atlas des ombres directionnelles 2048. Mode et cascades par défaut (PSSM 4). | `render_quality.gd`, `project.godot` |
| Arbres | `MultiMeshInstance3D` par case de 250 m, deux niveaux : LOD0 jusqu'à 300 m avec ombres, LOD1 de 300 à 1 500 m sans ombres. Budgets 20 000 / 50 000 / 100 000. | `tree_renderer.gd` |
| Bâtiments | `visibility_range_end` 1 500 / 2 500 / 4 000 m ; ombres seulement de près. | `osm_streamer.gd`, `quality_presets.gd` |
| Effets | SSAO (qualité 0) en `medium` et `high`, brouillard volumétrique en `high`, MSAA 0 / 2× / 4×. | `quality_presets.gd`, `project.godot` |
| Mesure | Ligne `[perf-rendu]` (images/s, p50, p99, arbres, appels de dessin) et sonde X13 (`perf_probe.gd`, temps CPU et GPU de la vue, objets, primitives, VRAM, tuiles). | `main.gd`, `perf_probe.gd` |

**Budgets à respecter** (`docs/SPECIFICATION_GENERALE.md`, série P, R14, U18) : en `low` sur la GTX 1060, 55 images/s en moyenne et temps d'image p99 sous 25 ms avec tout le décor vivant ; 60 images/s dans le Cyber-Rogue (R14) ; 55 images/s avec les biomes (U18) ; 1 h sans fuite ni saccade (X16). Référence mesurée : essai du 25 octobre, 59,4 images/s et p99 22 ms en `low` (lot S1).

## 3. Ce que les versions récentes de Godot apportent

| Version | Apport utile à OpenRide | Effet attendu | Source |
| --- | --- | --- | --- |
| 4.4 (mars 2025) | **Ubershaders et précompilation des pipelines** : le moteur prépare les pipelines au chargement d'un maillage et compile les variantes optimisées en arrière-plan. | Moins de saccades à la première apparition d'un objet ou d'un effet (p99). | [Pipeline compilations](https://docs.godotengine.org/en/stable/tutorials/performance/pipeline_compilations.html) |
| 4.4 | **Interpolation physique en 3D** (et dans `MultiMesh`) : affichage lissé entre deux pas physiques. | Utile pour la caméra et les bots si on les fait avancer par pas fixes. | [Release 4.4](https://godotengine.org/releases/4.4/), [Physics interpolation](https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/physics_interpolation_introduction.html) |
| 4.4 | Tonalité **AgX** (scènes très lumineuses mieux rendues), compression des textures **Betsy** sur la carte graphique, Jolt intégré (facultatif). | Qualité de l'image ; imports plus rapides. | [Release 4.4](https://godotengine.org/releases/4.4/), [Phoronix 4.4-dev1](https://phoronix.com/news/Godot-4.4-Dev-1-Engine) |
| 4.5 (sept. 2025) | **Shader baker** à l'export : shaders précompilés pour le pilote cible. | Démarrage plus rapide ; ne corrige pas les saccades existantes. | [Release 4.5](https://godotengine.org/releases/4.5/), [Pipeline compilations](https://docs.godotengine.org/en/stable/tutorials/performance/pipeline_compilations.html) |
| 4.5 | **Stencil buffer**, **SMAA 1×**, **occlusion spéculaire** tirée de l'occlusion ambiante, cartes de normales « bent ». | Meilleur anticrénelage bon marché ; reflets plus justes dans les creux. | [Release 4.5](https://godotengine.org/releases/4.5/), [CG Channel](https://www.cgchannel.com/tag/bent-normal-map/) |
| 4.6 (janv. 2026) | **SSR refait** (Hi-Z, demi-résolution possible), **sondes de réflexion en cartes octaédriques** (moins de GPU et de mémoire), LOD générés qui gardent la forme des objets en plusieurs morceaux, désaturation et précision HDR améliorées dans le moteur Mobile, Jolt par défaut pour les **nouveaux** projets seulement. | Eau et surfaces mouillées plus belles à coût réduit ; LOD plus propres. | [Release 4.6](https://godotengine.org/releases/4.6/), [Digital Production](https://digitalproduction.com/2026/01/28/godot-4-6-arrives-with-major-cg-friendly-updates/) |
| 4.6 | **Changement visible** : le glow est mélangé avant la tonalité et le mode « Screen » devient le défaut ; l'ancien rendu ne se retrouve pas par un simple réglage. | À recetter à l'œil lors de la migration. | [Release 4.6](https://godotengine.org/releases/4.6/) |
| 4.7 (juin 2026) | **Un tampon de constantes d'environnement par passe** (moins de dépendances de copie entre passes), sortie HDR (Linux sous Wayland), `AreaLight3D`, mise à l'échelle 3D au plus proche voisin. | Gain de rendu général sans travail ; le reste est peu utile ici. | [Release 4.7](https://godotengine.org/releases/4.7/), [PR #115177](https://github.com/godotengine/godot/pull/115177), [GameDev.net](https://gamedev.net/news/godot-47-released-r4011/) |

**Recommandation :** une migration directe 4.3 → 4.7.x en un seul lot, au début de la phase finale et **avant** toute autre optimisation, pour que les mesures suivantes partent de la bonne base. Points de vigilance : fichiers `.uid` créés par l'éditeur depuis 4.4 (à versionner), glow modifié en 4.6, comportement des `MultiMesh` et des shaders du terrain (E2) à revérifier, scripts de test (`run_engine_tests.sh`, `sim_bench.py`) à relancer sur le PC cible. Jolt n'est pas imposé aux projets existants. La version exacte à retenir est **à vérifier** le jour du lot (dernier correctif 4.7.x).

## 4. Techniques classées par gain attendu, coût et risque

Gain : estimation qualitative pour notre scène (route, relief, villages, forêts, caméra basse qui regarde devant), à confirmer au banc. Coût : travail de développement. Risque : changement visible ou régression.

| # | Technique | Gain | Coût | Risque | Lot lié |
| --- | --- | --- | --- | --- | --- |
| T1 | **Brouillard et `camera.far` par préréglage** (par exemple `low` : brouillard opaque vers 3,5–4 km, caméra et tuiles lointaines coupées juste après) | Fort | Faible | Faible (horizon plus proche, voulu par le propriétaire) | S1 piste 1, nouveau Y1 |
| T2 | Migration vers Godot 4.7 (ubershaders, interpolation 3D, LOD, SSR, tampons par passe) | Moyen, surtout sur le p99 | Moyen | Moyen (changements visibles, tests à revoir) | nouveau Y2 |
| T3 | **Visibility ranges en HLOD** : maisons séparées de près, un bloc simplifié par village au loin (`visibility_parent`), fondu « Disabled » avec marge plutôt que « Self » | Fort dans les villages | Moyen | Faible | S1 piste 3, nouveau Y3 |
| T4 | **Ombres** : distance par préréglage (déjà), PSSM 2 cascades en `low`, pas d'ombres pour les LOD lointains ni les petits objets, filtre « Soft Low », profondeur 16 bits (défaut), « Blend Splits » coupé | Moyen | Faible | Faible | S1 piste 5, nouveau Y4 |
| T5 | **Arbres : imposteurs** au-delà de 1 500 m (ou panneaux simples), `visible_instance_count` pour régler la densité sans reconstruire le `MultiMesh`, `custom_aabb` correct | Fort pour la qualité à coût égal | Moyen | Moyen (extension en cours de développement, aspect à recetter) | O1, nouveau Y5 |
| T6 | **Résolution 3D** : `scaling_3d_scale` 0,75–0,85 + FSR 1.0 ; résolution adaptative pilotée par le temps GPU | Fort si limité par le GPU, nul sinon | Faible à moyen | Moyen (image plus douce) | nouveau Y6 |
| T7 | **Étaler la construction** des tuiles sur plusieurs images (budget de temps par image, `WorkerThreadPool`) et ne pas construire ce qui sera invisible | Fort sur le p99 et les 15 premières secondes | Moyen | Faible | S1 piste 6, O1 |
| T8 | **Occlusion par le relief** : `ArrayOccluder3D` tiré des crêtes des tuiles, jamais déplacé | Faible à moyen (Forward+ a déjà sa pré-passe) | Moyen | Moyen (coût processeur, faux masquages) | S1 piste 4 |
| T9 | **LOD automatique des maillages** : seuil `mesh_lod_threshold` par préréglage, `lod_bias` par objet ; pour les maillages générés, `ImporterMesh.generate_lods()` | Moyen sur les bâtiments | Moyen | Faible ; disponibilité de `generate_lods()` dans un jeu exporté **à vérifier** | nouveau Y3 |
| T10 | **Transparence** : feuillage en `alpha scissor` (ou `alpha hash`) plutôt qu'en mélange ; éviter les grandes surfaces transparentes superposées | Moyen (taux de remplissage) | Faible | Faible | P5, Y5 |
| T11 | **Textures** : compression VRAM, mipmaps, filtrage anisotrope modéré, packs par préréglage | Moyen sur la VRAM et la bande passante | Faible | Faible | P20 |
| T12 | **Anticrénelage** : FXAA ou SMAA (4.5) en `low` plutôt que rien ; MSAA seulement en `medium`/`high` ; TAA ou FSR 2.2 trop chers pour la GTX 1060 à vérifier | Qualité à coût faible | Faible | Faible | Y2, Y6 |
| T13 | **Moteur Mobile pour `low`** (lancer Godot avec `--rendering-method mobile`) : pas de pré-passe de profondeur, plus rapide sur les scènes simples, mais sans SSAO, brouillard volumétrique, TAA ni FSR | Incertain | Faible pour l'essai | Moyen (image différente, shaders à revérifier) | nouveau Y7 (essai seulement) |
| T14 | Rendu à débit variable (VRS) | — | — | **Exclu** : la GTX 1060 (Pascal) ne le gère pas | — |

Détails et sources par technique :

- **T1 – brouillard et distance.** La documentation recommande de régler la distance maximale des ombres et de l'affichage selon ce que la scène montre vraiment ; tout ce qui est au-delà du brouillard opaque est du travail perdu. Le brouillard de profondeur existe dans les trois moteurs ; le brouillard volumétrique seulement en Forward+. [Optimizing 3D performance](https://docs.godotengine.org/en/stable/tutorials/performance/optimizing_3d_performance.html), [Environment and post-processing](https://docs.godotengine.org/en/stable/tutorials/3d/environment_and_post_processing.html), [Renderers](https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html).
- **T3 – HLOD.** Les `visibility_range` fonctionnent sur tout `GeometryInstance3D` (`MeshInstance3D`, `MultiMeshInstance3D`, `Sprite3D`, particules). L'exemple de la documentation est exactement notre cas : un groupe de maisons séparées de près, un seul maillage moins détaillé au loin, avec `visibility_parent` pour ne régler qu'une distance. Le mode « Self » ou « Dependencies » force le rendu transparent pendant la transition ; « Disabled » avec une marge (hystérésis) est le plus rapide. [Visibility ranges (HLOD)](https://docs.godotengine.org/en/stable/tutorials/3d/visibility_ranges.html), [GeometryInstance3D](https://docs.godotengine.org/en/stable/classes/class_geometryinstance3d.html).
- **T4 – ombres.** Par défaut le soleil utilise PSSM à 4 cascades : un grand objet présent dans les quatre est dessiné quatre fois pour les ombres plus une fois pour l'image. La documentation conseille une taille 4096, ou 2048 sur un GPU modeste (notre réglage), le filtre « Soft Low », la profondeur 16 bits, et une distance maximale ajustée à la scène ; « Blend Splits » coûte du détail et du temps. [Lights and shadows](https://docs.godotengine.org/en/stable/tutorials/3d/lights_and_shadows.html).
- **T5 – arbres.** Les instances d'un `MultiMesh` éloignées les unes des autres doivent être réparties dans plusieurs nœuds pour que le tri par champ de vue et l'occlusion fonctionnent (c'est ce que font nos cases de 250 m). `visible_instance_count` limite le nombre d'instances dessinées sans reconstruire le tampon ; `custom_aabb` évite un calcul de boîte. L'extension *Godot Octahedral Impostors* (licence MIT, en cours de développement) capture l'objet sous plusieurs angles dans une texture et n'affiche qu'un plan (12 à 36 sommets). [Mesh LOD](https://docs.godotengine.org/en/stable/tutorials/3d/mesh_lod.html), [MultiMesh](https://docs.godotengine.org/en/stable/classes/class_multimesh.html), [Using MultiMesh](https://docs.godotengine.org/en/stable/tutorials/performance/using_multimesh.html), [Octahedral Impostors](https://github.com/SIsilicon/Godot-Octahedral-Impostors).
- **T6 – résolution.** L'échelle est par axe : 0,75 en 1080p donne 1440×810, soit 1,17 Mpix au lieu de 2,07 (environ −44 % de pixels). FSR 1.0 et FSR 2.2 n'existent qu'en Forward+ ; FSR 1.0 gagne à être combiné au MSAA, FSR 2.2 apporte son propre anticrénelage temporel mais peut coûter trop cher sur un GPU lent. `Viewport.scaling_3d_scale` se change à chaud. Godot n'a pas de résolution adaptative toute faite : un petit régulateur (moyenne glissante du temps GPU, paliers de 0,05, hystérésis de quelques secondes) suffit. [Resolution scaling](https://docs.godotengine.org/en/stable/tutorials/3d/resolution_scaling.html), [RenderingServer](https://docs.godotengine.org/en/stable/classes/class_renderingserver.html) (`viewport_get_measured_render_time_gpu`).
- **T8 – occlusion.** Godot pixellise les occulteurs sur le processeur dans un petit tampon (bibliothèque Embree) ; un objet n'est retiré que si sa boîte englobante est entièrement cachée. Les occulteurs ne se « cuisent » qu'à partir de `MeshInstance3D` ; pour un monde généré, `ArrayOccluder3D` se remplit par script. Ne jamais déplacer un occulteur (reconstruction de l'arbre BVH). En Forward+, la pré-passe de profondeur limite déjà le surcoût du coloriage ; le gain vient surtout des appels de dessin et des sommets. La documentation cite le relief en pyramide comme le plus favorable en plein air. [Occlusion culling](https://docs.godotengine.org/en/stable/tutorials/3d/occlusion_culling.html).
- **T9 – LOD automatique.** Seuil par défaut d'un pixel, « perceptuellement sans perte » ; `mesh_lod_threshold` du viewport se change à chaud, `lod_bias` par objet. [Mesh LOD](https://docs.godotengine.org/en/stable/tutorials/3d/mesh_lod.html), [ImporterMesh](https://docs.godotengine.org/en/stable/classes/class_importermesh.html).
- **T10 et T11.** Les objets transparents sont triés d'arrière en avant et coûtent en taux de remplissage, surtout superposés ; la compression des textures réduit d'abord la bande passante. [GPU optimization](https://docs.godotengine.org/en/stable/tutorials/performance/gpu_optimization.html).
- **T13 – Mobile.** Tableau des fonctions par moteur : Mobile n'a ni SSAO, ni brouillard volumétrique, ni TAA, ni FSR 2.2 ; occlusion plus rentable en Mobile faute de pré-passe. [Renderers](https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html), [Occlusion culling](https://docs.godotengine.org/en/stable/tutorials/3d/occlusion_culling.html).
- **T14 – VRS.** Réservé aux NVIDIA Turing et plus récentes (y compris GTX 1600) ; sans effet sur une carte non compatible. [Variable rate shading](https://docs.godotengine.org/en/stable/tutorials/3d/variable_rate_shading.html).

## 5. Saccades et temps d'image p99

Le budget p99 (25 ms) est plus fragile que la moyenne. Causes connues et remèdes :

- **Compilation de shaders à la première apparition** : réglée en grande partie par les ubershaders de 4.4 ; ne pas changer en cours de séance un réglage qui modifie une constante de spécialisation (qualité des ombres, par exemple) : c'est une saccade immédiate. Le moniteur « pipelines compilés » du profileur montre la cause. [Pipeline compilations](https://docs.godotengine.org/en/stable/tutorials/performance/pipeline_compilations.html).
- **Construction des tuiles et des tronçons** sur le fil principal : découper l'instanciation (`MultiMesh`, `ArrayMesh`) en tranches limitées en temps par image (lots O1, S1).
- **Ralentissement des 15 premières secondes** (1 à 3 images/s relevé au banc le 25 octobre) : construire la scène derrière l'écran de chargement avant le départ.
- **Ramasse-miettes et allocations** : réutiliser les tableaux (`PackedFloat32Array`) plutôt que d'en créer à chaque image. [General optimization](https://docs.godotengine.org/en/stable/tutorials/performance/general_optimization.html).

## 6. Graphismes : plus beau à coût maîtrisé

Retours du propriétaire (25 octobre) : bâtiments sans texture et tous à toit plat, graphismes pauvres. Pistes, de la moins chère à la plus chère :

1. **Tonalité et étalonnage** : AgX (4.4) et ses réglages (4.6), ajustements de luminosité, contraste et saturation de l'`Environment`. Coût nul ou presque. [Environment and post-processing](https://docs.godotengine.org/en/stable/tutorials/3d/environment_and_post_processing.html).
2. **Bâtiments** : toits à deux ou quatre pans générés, textures de façade par thème en atlas (une seule texture par village, peu de changements de matériau), fenêtres par shader plutôt que par géométrie. C'est le « lot habillage » déjà évoqué.
3. **Chaussée et herbe** (demande du 27 octobre, lot Y11) : cartes de normales et rugosité variable, détail à deux échelles, décalques (`Decal`, coût par pixel couvert, limités en distance), route mouillée, parallaxe en `high` ; pour l'herbe, normale par le dessus, vagues de vent, touffes raccordées au sol, coquilles en essai. [Using decals](https://docs.godotengine.org/en/stable/tutorials/3d/using_decals.html), [Standard Material 3D](https://docs.godotengine.org/en/stable/tutorials/3d/standard_material_3d.html). Cahier : `docs/lots/LOT_Y11_chaussee_herbe_relief.md`.
8. **Lumière et particules** (demande du 27 octobre, lot Y12) : glow léger, rayons de soleil, ombre des nuages en `medium`, reflets SSR, poussière, pollen, feuilles, éclaboussures, kit d'étincelles du Cyber-Rogue ; budgets par préréglage et échelle commune avec R17. [Particle systems (3D)](https://docs.godotengine.org/en/stable/tutorials/3d/particles/index.html), [Volumetric fog](https://docs.godotengine.org/en/stable/tutorials/3d/volumetric_fog.html). Cahier : `docs/lots/LOT_Y12_lumieres_particules.md`.
4. **Eau** : SSR refait en 4.6 (demi-résolution) et sondes de réflexion octaédriques ; seulement en `medium` et `high`.
5. **Occlusion ambiante** : SSAO en demi-résolution en `medium` ; occlusion spéculaire automatique (4.5).
6. **Foule et passants** (P15, P21) : animation dans le shader de sommets à partir d'une texture, comme l'exemple « des milliers de poissons » de la documentation, avec `MultiMesh` et données par instance. [Animating thousands of fish](https://docs.godotengine.org/en/stable/tutorials/performance/vertex_animation/animating_thousands_of_fish.html).
7. **Terrain** : l'extension Terrain3D (GDExtension, carte de géométrie en « clipmap », jusqu'à 10 niveaux de détail, licence MIT) montre la technique de référence pour un relief étendu ; notre terrain est généré par tuiles depuis le `.world`, donc on retiendrait l'idée (anneaux de détail autour de la caméra) plutôt que l'extension. [Terrain3D](https://github.com/outobugi/Terrain3D/wiki), [GameFromScratch](https://gamefromscratch.com/terrain3d-a-new-terrain-engine-for-godot/).

## 7. IA des bots : lissage et comportement

Le core calcule les bots à 50 Hz et envoie l'état à 30 Hz ; l'engine affiche à la cadence de l'écran. La caméra utilise déjà une extrapolation bornée à 1 s avec rattrapage en 150 ms (`camera_follow.gd`). Pour les bots (O7, puis T et R) :

- **Mémoire de trames et interpolation** : afficher les bots avec un léger retard (2 à 3 trames, soit 70 à 100 ms à 30 Hz) et interpoler entre deux trames connues plutôt qu'extrapoler ; une **interpolation d'Hermite** qui utilise aussi la vitesse de chaque trame passe par les points et respecte les vitesses, donc pas de cassure. Règle de Glenn Fiedler : un retard qui survit à la perte de deux trames d'affilée. [Snapshot interpolation](https://gafferongames.com/post/snapshot_interpolation/), [geckos.io snapshot-interpolation](https://www.skypack.dev/view/@geckos.io/snapshot-interpolation).
- **Position latérale et dépassements** : comportements de pilotage simples (suivre une ligne, éviter, se ranger, se mettre dans la roue), lissés par une accélération latérale bornée, plutôt que des sauts de file. [Reynolds, Steering Behaviors](https://www.red3d.com/cwr/steer/).
- **Interpolation physique de Godot 4.4** : utile si les bots sont avancés par pas fixes dans l'engine ; elle couvre aussi les instances de `MultiMesh` (`physics_interpolation_quality`, `reset_instance_physics_interpolation`). [Physics interpolation](https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/physics_interpolation_introduction.html), [MultiMesh](https://docs.godotengine.org/en/stable/classes/class_multimesh.html).
- **Coût de rendu** : niveaux de détail des bots (modèle animé de près, silhouette ou imposteur au loin, rien au-delà du brouillard), cadence de pédalage animée dans le shader à partir de la cadence envoyée par le core.
- **Comportement** (réalisme de la course, plus que du rendu) : profils de puissance qui varient avec la pente et la fatigue, attaques dans les montées (séries T et R) ; tout reste dans le core, qui est le maître de l'état.

## 8. Propositions de lots (série Y, « rendu et IA, fin de projet »)

Validée par le propriétaire le 27 octobre (§0). Toute la série vient **après** les autres lots, sauf Y1, avancé à la demande du propriétaire (il répond à son retour du 25 octobre). Les mesures se font en `medium`, le préréglage du propriétaire, puis en `low`. Chaque lot mesure avant et après au banc simulé avec la sonde X13, garde les seuils d'X2, et ne retient une piste que si elle respecte la règle de S1 (au moins 3 % d'images/s ou 1 ms de p99 gagnés, sans changement visible non voulu). Endurance X16 à la fin de la série.

| Lot | Contenu | Dépend de | Taille | Délégable |
| --- | --- | --- | --- | --- |
| Y1 | Brouillard opaque à 4 / 6 / 9 km, `camera.far` et rayon des tuiles lointaines par préréglage (T1) ; retrait de la clé `renderer_hint` inutilisée | X13 (livré) ; avant S1 | Petite | Oui (essai sur le PC par le propriétaire) |
| Y2 | Migration vers Godot 4.7.x : moteur, scripts, tests, banc, lanceur ; recette visuelle (glow 4.6) | Y1, X2, X13 | Moyenne | Non : interne (PC cible) |
| Y3 | HLOD des villages et LOD des bâtiments (T3, T9), fondus sans transparence | Y2, S1 | Moyenne | Oui |
| Y4 | Ombres par préréglage : cascades, distances, objets sans ombres (T4) | Y2 | Petite | Oui |
| Y5 | Arbres lointains en imposteurs écrits par nous (décision du 27 octobre, sans extension externe), feuillage en `alpha scissor`, densité par `visible_instance_count` (T5, T10) | O1, Y2 | Moyenne | Oui (aspect validé par le propriétaire) |
| Y6 | Résolution 3D par préréglage et résolution adaptative (FSR 1.0, temps GPU), anticrénelage FXAA/SMAA en `low` (T6, T12) | Y2, X13 | Petite | Oui |
| Y7 | Essai du moteur Mobile pour `low` (T13) : mesure seule, décision du propriétaire | Y2 | Petite | Oui (mesure) |
| Y8 | Habillage, dans l'ordre validé : toits à pans et textures de façade en atlas, puis étalonnage AgX (§6) ; les décalques de route passent dans Y11 (décision du 27 octobre) | Y3, P20 | Grande | En partie |
| Y9 | Lissage des bots : mémoire de trames, Hermite, déplacements latéraux, LOD des bots (§7) | O7 | Moyenne | Oui |
| Y10 | Comportement des bots (profils, attaques, abri) côté core | Y9, séries T et R | Moyenne | Oui |
| Y11 (#385) | Chaussée réaliste (normales, rugosité variable, deux échelles, décalques, route mouillée, parallaxe en `high`) et faux relief de l'herbe (normale, teinte, vagues de vent, touffes, coquilles en essai) ; enveloppe +1,0 ms GPU en `medium` | Y2, P20, P14/P17, Y1 | Moyenne à grande | En partie |
| Y12 (#386) | Lumière (glow, rayons, ombre des nuages, SSR, halo) et particules (poussière, pollen, feuilles, éclaboussures, foules, kit Cyber-Rogue) ; enveloppe +1,5 ms GPU en `medium` | Y2, Y1, P17, R17, Y11 | Moyenne | Oui |
| Y13 | Qualité d'image par préréglage à résolution native (rendu des tons, étalonnage, anticrénelage, SSAO/SSIL, glow, ombres, filtrage, puis densités et brume) : cahier `docs/lots/LOT_Y13_qualite_image_prereglages.md` | Y1 | Moyenne | Interne |

**Y1 réalisé (27 octobre, code) :** clé `fog_end_m` dans `quality_presets.gd` (4 000 / 6 000 / 9 000 m), début du brouillard à 40 % de la fin (1,6 / 2,4 / 3,6 km), `camera.far` = fin + 3 %, tuiles lointaines chargées jusqu'à la fin + une tuile lointaine (9 / 11 / 12 km, plafond 12 km), sol plat de même rayon ; sans relief, brouillard inchangé (300 m à 3 km) ; clé `renderer_hint` retirée. Mesures du 27 octobre sur le PC cible (GTX 1060, banc simulé `montee_descente` avec la sonde X13, fenêtre 1857 × 1011, PC au calme, avant = base commune sans Y1, après = branche Y1) :

| Préréglage, monde | Images/s médianes avant → après | p99 du temps d'image | Appels de dessin | Tuiles lointaines | VRAM Godot |
| --- | --- | --- | --- | --- | --- |
| `medium`, village et demo | 60 → 60 | ~145 ms → ~145 ms (pics de chargement) | ~443, inchangés | 12 → 12 | 221 Mo, inchangée |
| `low`, village et demo | 60 → 60 | ~145 ms → ~145 ms (pics de chargement) | ~430, inchangés | 12 → 12 | 133 Mo, inchangée |

Aucun gain ni perte mesurable : la synchronisation verticale plafonne à 60 images/s et les mondes de test (village, demo) n'ont que 12 tuiles lointaines de 5 km, toutes dans le nouveau rayon ; le gain du rayon réduit n'apparaîtra que sur un grand parcours réel. Captures avant et après au même instant quasi identiques (écart RGB ≤ 0,4), aucune tuile ne surgit au bord du brouillard. `recette_pc` sur la branche : core et compilateur OK (seul échec, `test_require_denylist`, connu et présent aussi sur `main`), engine OK avec un budget de temps X2 dépassé, bout en bout en échec à cause d'un ancien script de suivi qui écrivait dans `~/OpenRide` (sans lien avec Y1). Reste à faire par le propriétaire : `essai-69` en `medium` puis en `low` pour valider l'horizon plus proche.

Ordre conseillé : Y1, Y2, puis Y4, Y6 et Y3 (les plus rentables), Y5, Y7, et enfin Y8, Y11, Y12, Y9, Y10 (Y11 et Y12 validés le 27 octobre : les gains de performance d'abord, ils paient l'habillage). Essai de rendu mesuré avec les outils de la série X : `docs/ESSAI_RENDU_Y11_Y12.md`. Ce qui relève de « ne pas dessiner l'invisible » (tuiles derrière, construction inutile, occlusion par le relief) reste dans S1, pour ne pas faire deux fois le même travail.

## 10. Chaussée, herbe, lumière et particules : décisions du propriétaire (27 octobre)

Cahiers `LOT_Y11_chaussee_herbe_relief.md` (issue #385), `LOT_Y12_lumieres_particules.md` (issue #386), essai `docs/ESSAI_RENDU_Y11_Y12.md`. Réponse du propriétaire : « OK pour tout » (recommandations retenues).

| Question | Décision |
| --- | --- |
| 1. Lots | Y11 et Y12 validés, après Y8 : ordre Y8, Y11, Y12, puis Y9, Y10. |
| 2. Enveloppe | Au plus +2,5 ms de GPU en `medium` pour Y11 et Y12 ensemble (+1,0 et +1,5), p99 au plus +1 ms ; `low` garde 55 images/s et p99 sous 25 ms. |
| 3. Essai, étape 0 | Référence sans code (environ 35 min sur le PC), après Y1. |
| 4. Essai, étape 1 | Maquette de mesure après Y2 (Godot 4.7), le glow et le SSR changeant en 4.6. |
| 5. Textures de sol | Packs CC0 seulement ; Gemini réservé aux décalques fictifs (inscriptions dans les cols). |
| 6. Décalques de route | Déplacés d'Y8 vers Y11. |
| 7. Herbe | Touffes 1 500 / 8 000 / 20 000 sous réserve de la mesure ; coquilles en essai `high` ; parallaxe de l'herbe écartée. |
| 8. Halo du soleil | `high` seulement. |
| 9. Lucioles | Version 2.0, avec le jour et la nuit. |

## 9. Sources

Documentation officielle de Godot (version « stable » ; textes lus dans le dépôt [godot-docs](https://github.com/godotengine/godot-docs)) :

- [Optimizing 3D performance](https://docs.godotengine.org/en/stable/tutorials/performance/optimizing_3d_performance.html)
- [Occlusion culling](https://docs.godotengine.org/en/stable/tutorials/3d/occlusion_culling.html)
- [Visibility ranges (HLOD)](https://docs.godotengine.org/en/stable/tutorials/3d/visibility_ranges.html)
- [Mesh level of detail (LOD)](https://docs.godotengine.org/en/stable/tutorials/3d/mesh_lod.html)
- [Resolution scaling](https://docs.godotengine.org/en/stable/tutorials/3d/resolution_scaling.html)
- [Lights and shadows](https://docs.godotengine.org/en/stable/tutorials/3d/lights_and_shadows.html)
- [Environment and post-processing](https://docs.godotengine.org/en/stable/tutorials/3d/environment_and_post_processing.html)
- [Volumetric fog](https://docs.godotengine.org/en/stable/tutorials/3d/volumetric_fog.html)
- [3D antialiasing](https://docs.godotengine.org/en/stable/tutorials/3d/3d_antialiasing.html)
- [Variable rate shading](https://docs.godotengine.org/en/stable/tutorials/3d/variable_rate_shading.html)
- [Overview of renderers](https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html)
- [GPU optimization](https://docs.godotengine.org/en/stable/tutorials/performance/gpu_optimization.html), [General optimization](https://docs.godotengine.org/en/stable/tutorials/performance/general_optimization.html)
- [Reducing stutter from shader (pipeline) compilations](https://docs.godotengine.org/en/stable/tutorials/performance/pipeline_compilations.html)
- [Using MultiMesh](https://docs.godotengine.org/en/stable/tutorials/performance/using_multimesh.html), [Animating thousands of fish](https://docs.godotengine.org/en/stable/tutorials/performance/vertex_animation/animating_thousands_of_fish.html)
- [Physics interpolation](https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/physics_interpolation_introduction.html)
- [Using decals](https://docs.godotengine.org/en/stable/tutorials/3d/using_decals.html)
- Référence des classes : [GeometryInstance3D](https://docs.godotengine.org/en/stable/classes/class_geometryinstance3d.html), [MultiMesh](https://docs.godotengine.org/en/stable/classes/class_multimesh.html), [ImporterMesh](https://docs.godotengine.org/en/stable/classes/class_importermesh.html), [RenderingServer](https://docs.godotengine.org/en/stable/classes/class_renderingserver.html), [Viewport](https://docs.godotengine.org/en/stable/classes/class_viewport.html)

Versions :

- [Godot 4.4](https://godotengine.org/releases/4.4/), [Godot 4.5](https://godotengine.org/releases/4.5/), [Godot 4.6](https://godotengine.org/releases/4.6/), [Godot 4.7](https://godotengine.org/releases/4.7/) (textes lus dans le dépôt [godot-website](https://github.com/godotengine/godot-website))
- [PR #115177 (tampons par passe, 4.7)](https://github.com/godotengine/godot/pull/115177), [PR #111210 (SSR, 4.6)](https://github.com/godotengine/godot/pull/111210), [PR #107902 (sondes octaédriques, 4.6)](https://github.com/godotengine/godot/pull/107902), [PR #110028 (LOD, 4.6)](https://github.com/godotengine/godot/pull/110028)
- Articles : [Phoronix, 4.4-dev1](https://phoronix.com/news/Godot-4.4-Dev-1-Engine), [GameFromScratch, 4.4](https://gamefromscratch.com/godot-4-4-released/), [It's FOSS, 4.5](https://itsfoss.com/news/godot-4-5-release/), [CG Channel, 4.5](https://www.cgchannel.com/tag/bent-normal-map/), [Digital Production, 4.6](https://digitalproduction.com/2026/01/28/godot-4-6-arrives-with-major-cg-friendly-updates/), [GameDev.net, 4.7](https://gamedev.net/news/godot-47-released-r4011/)

Extensions et techniques :

- [Terrain3D](https://github.com/outobugi/Terrain3D/wiki) ; [Godot Octahedral Impostors](https://github.com/SIsilicon/Godot-Octahedral-Impostors)
- [Glenn Fiedler, Snapshot Interpolation](https://gafferongames.com/post/snapshot_interpolation/) ; [Craig Reynolds, Steering Behaviors For Autonomous Characters](https://www.red3d.com/cwr/steer/)
