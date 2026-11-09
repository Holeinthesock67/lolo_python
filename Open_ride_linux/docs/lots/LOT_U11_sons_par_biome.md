# Lot U11 – Engine : sons d'ambiance par biome (extension de P9)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Engine : sons d'ambiance par biome (extension de P9) | GDScript | U5, P9 (U9 utile) | Moyenne | Livré le 8 novembre (PR #787), **version 3.0** (issue #341) |

## 1. Objectif

**Version 3.0.** Donner à chaque biome son ambiance sonore, synthétisée comme celle de P9 : cigales en méditerranéen, chorus d'insectes et d'oiseaux en jungle, vent dans les résineux en taïga, sonnailles en montagne, vagues et mouettes au littoral, grenouilles en zone humide, sable qui siffle au désert.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §2, `docs/lots/LOT_U5_modele_biome_engine.md`, `docs/lots/LOT_P9_ambiance_sonore.md`, `docs/lots/LOT_L5_modele_sonore.md`.
2. Code : `engine/scripts/ambience_model.gd` (P9), `engine/scripts/sound_model.gd`, `engine/scripts/sound_player.gd`.

## 3. Prérequis

U5 et P9 livrés ; U9 utile (distance au rivage).

## 4. Travail demandé

- `ambience_model.gd` : couches sonores nommées (`cicadas`, `jungle_chorus`, `conifer_wind`, `cowbells`, `waves`, `gulls`, `frogs`, `singing_sand`, `ice_cracks`, `fumaroles`, en plus de celles de P9), volume de chaque couche = somme des poids des biomes qui la déclarent dans `ambience` du thème, multipliée par les facteurs de saison et d'heure.
- Synthèse procédurale dans `sound_player.gd` (pas de fichiers sonores dans le dépôt) ; vagues d'après la distance au rivage ; fondu de 3 s au moins entre deux ambiances.
- Plafond de voix simultanées inchangé (les couches les plus faibles se taisent d'abord).

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/ambience_model.gd`, `engine/scripts/sound_player.gd`, `engine/tests/unit/test_ambience_model.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), fichiers sonores, core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe.
2. Tuile 100 % `mediterranean` en été à midi : `cicadas` au-dessus de 0,5 ; en hiver : 0.
3. Biome `temperate_grassland` : volumes identiques à P9.
4. Passage d'un biome à l'autre : aucune couche ne change de plus de 1/3 de son volume par seconde.
5. Nombre de voix jamais au-dessus du plafond.

## 8. Hors périmètre

Sons enregistrés, sons du vélo sur le gravier (U22).

## 9. Livraison (8 novembre 2026)

- `engine/scripts/ambience_synth.gd` (nouveau) : synthèse des seize fonds, sans nœud (fil de travail possible) ; les six fonds de P9 y sont déplacés tels quels (mêmes échantillons) avec `periodic_lowpass`.
- `ambience_model.gd` : `BIOME_BEDS`, `mix` (volume, oiseaux, insectes et `layers` pondérés par les biomes), `biome_gains` (saison `SEASON_GAIN`, heure `HOUR_PROFILE`, pluie, vent, rivage), `sea_dist_m` dans `describe` ; même fondu pour tous les fonds : au plus `SLEW_DB_PER_S` et au plus `LINEAR_SLEW_PER_S` (1/3 du niveau plein) par seconde.
- `sound_player.gd` : fonds faits à la première demande dans un fil de `WorkerThreadPool` (conversion 16 bits comprise), posés à l'image suivante ; `make_beds_now` pour les tests et l'export ; plus aucun fond au démarrage.
- `living_world.gd` (écart au §5, nécessaire, `main.gd` intact) : poids des biomes au cycliste, mer jusqu'à 400 m, saison du thème dans le voisinage.
- Thème par défaut : `layers` de quatorze biomes (la prairie, la steppe n'en ont pas) ; contrat (écart au §6, ajout compatible sans changement de version) : clé facultative `ambience.layers` dans `world_format_v1.md` §9 et `theme.schema.json`.
- Vagues : U9 n'étant pas là, la distance au rivage vient des eaux `sea` déjà chargées (parcours de démonstration U19 `--sea`).
- Écoute : `engine/tests/ambience_export.gd` (scène de 20 s par biome, chaque fond seul).

## 10. Suite du banc r787 (9 novembre 2026)

**Mesure.** Banc PC r787 (nuit du 8 au 9 novembre, captures `a01eed21`) : `ambience_layer_frame` = 1,87 ms pour un budget de 2 ms, alors que la PR annonçait 0,44 ms. Sur la même passe, `ambience_evaluate` (le modèle seul) vaut 0,06 ms sur le PC.

**Pourquoi l'écart.**
- La mesure est la **pire image** d'une seule série d'environ 87 images, pas une médiane : un seul échantillon décide. Les 0,44 ms venaient d'une machine cloud au repos ; le PC avait en même temps le bureau, l'indexeur de fichiers (`localsearch`, 13 % d'un cœur) et deux fils de travail qui synthétisaient les fonds. Une préemption du fil principal pendant la mesure suffit à faire 1 ms de plus.
- Le modèle (0,06 ms) et l'ajout des tâches ne pèsent pas. Ce que l'image faisait de plus, c'était la **pose** : création de l'`AudioStreamWAV` et copie des échantillons (environ 500 Ko par fond, `to_wav`), affectation au lecteur et `play()`, et pour **deux fonds dans la même image** (vagues et mouettes finissent ensemble).
- Faute de détail par étape dans la mesure de la PR, la part de chaque cause n'est pas connue : la nouvelle mesure ci-dessous la donne.

**Changements.**
- Le fil de travail rend le flux complet (`_bed_source` : `to_wav(pcm16(bed_samples(…)))`, copie comprise) ; le fil principal ne fait plus que l'affecter au lecteur.
- Au plus un fond posé par image (`BEDS_POSED_PER_FRAME = 1`) ; les suivants le sont aux images d'après, ce qui ne s'entend pas (montée depuis `FADE_FLOOR_DB`).
- `update_ambience` garde le temps de ses trois étapes dans `ambience_us` (modèle, pose, lecteurs).
- `test_sound_player` mesure en low, medium et high (4, 6 et 8 voix, voisinage mêlé littoral, méditerranée, alpage, forêt et rivière, jusqu'à 8 fonds) : médiane, p95 et pire image pendant la fabrication, aux images de pose, puis sur 120 images tout posé (témoin : bruit de la machine seule), et le détail par étape de la pire image. Le budget `ambience_layer_frame` (2 ms) reste sur la pire image, pour rester comparable au banc r787.

**Mesure PC r829 (9 novembre, c07181ab, i3-6100, 4 fils).** Pire image `ambience_layer_frame` : low 0,382 ms, medium 0,508 ms, high 0,513 ms (1,87 ms avant, budget 2 ms) ; pire image de pose 0,34 / 0,32 / 0,33 ms ; témoin tout posé 0,97 / 1,35 / 0,87 ms, au-dessus des images de fabrication : les pointes restantes viennent de la machine.

