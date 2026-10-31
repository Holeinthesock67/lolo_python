# Lot P23 – Oiseaux de la campagne : rapaces, volées en V, corneilles qui s'envolent

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Oiseaux de la campagne : rapace en cercle, volées en V, corneilles qui s'envolent au passage, cris | GDScript + shader | P11, P17, P21 | Moyenne | **Livré le 27 octobre**, séance sur le PC à faire (deuxième vague du décor vivant, demandée le 27 octobre) |

## 1. Objectif

Demande du propriétaire du 27 octobre (« ça manque de vie : animaux, oiseaux, véhicules sur terre et dans le ciel »). Premier lot de la deuxième vague du décor vivant (P22 à P27, dossier du 27 octobre). P11 ne fait voler des oiseaux qu'au-dessus des forêts d'au moins 2 ha : en plaine, le ciel reste vide. Ce lot ajoute, près de la route de chaque tronçon :
- un rapace qui plane en cercle au-dessus d'un terrain ouvert et crie de temps en temps ;
- une volée en V qui traverse le ciel, très haut ;
- des corneilles posées au sol qui s'envolent en croassant quand le cycliste approche, puis se reposent plus loin.

Aucun changement de format : ces oiseaux n'ont besoin que de la route et des forêts déjà connues. Les prés et les champs (P22) les rendront plus justes ensuite.

## 2. À lire

1. `docs/lots/LOT_P11_animaux.md` (placement, comportement, affichage), `docs/lots/LOT_P17_integration_decor_complet.md` (branchement), `docs/lots/LOT_P21_passants_villages.md` (sons brefs synthétisés).
2. Code : `engine/scripts/fauna_placer.gd`, `fauna_behaviour.gd`, `fauna_renderer.gd`, `engine/shaders/fauna.gdshader`, `engine/scripts/sound_player.gd`, `living_decor.gd`, `quality_presets.gd`.

## 3. Prérequis

P11, P17 et P21 livrés.

## 4. Travail demandé

- **`fauna_placer.gd`** : trois nouveaux groupes par tronçon de 1 000 m, tirés du hachage de la longueur du parcours et de l'indice du tronçon, avec une probabilité proportionnelle à `fauna.birds` du thème :
  - `raptor` (6 tronçons sur 10 à `fauna.birds = 1`) : cercle de 35 à 60 m, de 55 à 90 m au-dessus du point le plus haut du sol sous l'orbite, centre de 60 à 180 m de la route, jamais au-dessus d'une forêt ;
  - `vee` (un tronçon sur 2) : 5 à 11 oiseaux en V, de 90 à 160 m du sol, à 11 à 14 m/s, trajectoire droite de 1 800 m qui croise la route (cap de 30 à 150 degrés) à moins de 120 m d'elle ;
  - `crows` (7 tronçons sur 10) : 4 à 9 corneilles posées dans un rayon de 8 m, de 18 à 50 m de la route, hors forêt, avec les exclusions au sol de P11 (couloir de la route, eau, bâtiments, pente au-dessus de 25 %) ; chacune a son point d'arrivée de 50 à 80 m plus loin de la route (la moitié, ou sur place, si ce point est exclu).
- **`fauna_behaviour.gd`** : rapace en cercle lent ailes tendues, qui crie une fois par période de 30 s quand le cycliste est à moins de 250 m (jamais au chargement) ; volée en ligne droite, qui reprend au début de sa trajectoire et rétrécit jusqu'à rien sur ses 150 derniers mètres de chaque côté ; corneilles qui s'envolent l'une après l'autre (0,12 s d'écart) quand le cycliste est à moins de 35 m, montent à 14 m et se reposent en 5 s à leur point d'arrivée. Les sons à jouer sont rendus dans `events`.
- **`fauna_renderer.gd`** : même `MultiMesh` que les oiseaux de P11 (aucun nœud d'affichage de plus), à l'échelle de chaque sorte (rapace x 1,5, volée x 1,8, corneille x 1,05), ailes repliées pour une corneille posée ; amplitude du battement par instance (`INSTANCE_CUSTOM.z` de `fauna.gdshader`). Les corneilles posées sont mises à jour par quart, comme le bétail. Un lecteur 3D créé au démarrage joue `crow_caw` et `raptor_cry` au volume `ambience.volume` du thème (`setup_sound`).
- **`sound_player.gd`** : `crow_caw` (deux croassements rauques) et `raptor_cry` (miaulement de buse qui descend), synthétisés comme les sons des passants de P21, remplaçables par `~/OpenRide/Sounds/<sorte>.ogg`.
- **`quality_presets.gd`** : budget `living(preset).birds` doublé (24, 48, 80), les nouveaux oiseaux comptant dans le même budget que ceux de P11.
- **`living_decor.gd`** : une ligne, `fauna.setup_sound(sound_player)`.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/fauna_placer.gd`, `fauna_behaviour.gd`, `fauna_renderer.gd`, `engine/shaders/fauna.gdshader`, `engine/scripts/sound_player.gd`, `quality_presets.gd`, `living_decor.gd` (une ligne), `engine/tests/unit/test_fauna_placer.gd`, `test_fauna_behaviour.gd`, `test_quality_presets.gd`, `engine/tests/perf_budgets.json`, `engine/tests/README.md`, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** `main.gd`, `osm_streamer.gd`, `crowd_renderer.gd` (fil des personnages), le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune : ni IPC, ni format `.world`, ni thème, ni touche. Désactivé avec le reste par `[render] living = false` ou `fauna.birds = 0` dans le thème.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Placement déterministe (même parcours et même tronçon, même résultat ; un autre parcours tire d'autres oiseaux) ; rapace de 55 à 90 m du sol et de 60 à 180 m de la route ; volée de 5 à 11 oiseaux qui croise la route à moins de 120 m ; aucune corneille dans le couloir de la route, sur une pente de 50 % ni au-dessus d'une forêt ; `fauna.birds = 0` : aucun oiseau.
3. Corneilles posées à 36 m, envolées à 34 m avec un seul croassement, à plus de 10 m du sol à mi-vol, reposées à leur point d'arrivée après le vol.
4. Rapace : sur son cercle, tête dans le sens du vol dans les deux sens de rotation ; à 100 m, 4 cris en 121 s ; à 400 m, aucun.
5. Volée : vitesse et cap justes, forme en V, réduite à rien au bout de sa trajectoire, période de 150 s.
6. Budget : jamais plus que `living(preset).birds` ; aucun nœud créé après le démarrage ; mise à jour de 177 animaux de toutes les sortes (81 oiseaux et 80 bêtes affichés en `high`) sous 0,45 ms par image (`fauna_frame_200`, 0,30 ms avant ce lot pour 40 oiseaux).

**Sur le PC cible (le propriétaire) :** séance en `low` puis `high` sur un parcours de plaine : un rapace ou une volée visible à peu près à chaque kilomètre, corneilles qui s'envolent au passage avec leur cri, ni oiseau enterré ni oiseau dans un arbre ; perte de moins de 1 image/s en `low` (P27 fera la mesure complète de la deuxième vague).

## 8. Hors périmètre

- Oiseaux posés sur les fils, les toits ou les arbres ; mouettes, hérons et autres espèces de biome (U12, version 3.0) ; oiseaux de nuit (P19, version 2.0).
- Prés et champs du format (P22) : quand ils existeront, les rapaces et les corneilles pourront les préférer, sans changer ce lot.

## 9. Livraison

Livré sur la branche `claude/project-thread-rh8cbl`.

- Mesures ici (machine partagée, Godot 4.3 sans écran) : mise à jour de 177 animaux en 0,34 à 0,36 ms par image en `high` (81 oiseaux, 80 bêtes) ; la mise à jour des oiseaux de P11 calcule maintenant position et cap ensemble (`FaunaBehaviour.bird_transform`).
- Tests : `test_fauna_placer.gd` (24 vérifications), `test_fauna_behaviour.gd` (32), `test_quality_presets.gd` (23).
- Reste sur le PC cible : la séance décrite au §7.
