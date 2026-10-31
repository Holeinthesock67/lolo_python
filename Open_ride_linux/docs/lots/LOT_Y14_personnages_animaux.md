# Lot Y14 – Personnages, cyclistes et animaux plus fins

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Personnages plus fins : corps articulé construit par code (`people_mesh.gd`), tenues variées par teintes, animations par articulations ; coureur casqué qui pédale sur un vrai vélo pour les bots d'O7 ; animaux refaits avec le même constructeur (vache pie, mouton à tête noire, chevreuil, oiseaux à rémiges) | GDScript + shader | P11, P15, P21, P23, O7 | Moyenne | Prototype le 27 octobre (spectateurs et passants), en attente de l'accord du propriétaire et de la mesure sur la GTX 1060 ; bots après O7 (#407) |

**Statut : prototype le 27 octobre (PR #445, avec Y11)**, en attente de l'accord du propriétaire et de la mesure sur la GTX 1060.

## 1. Objectif

Demande du propriétaire du 27 octobre : « l'herbe et les personnages sont trop grossièrement modélisés », puis « augmenter les détails des bots, personnages et animaux, qui sont trop simplistes ». Avant ce lot, un spectateur fait 72 triangles (pavés), un animal 72 (oiseau 14), les bots d'O7 sont une capsule et deux disques.

## 2. Règles communes (pas d'exception)

- **Un seul constructeur** : `engine/scripts/people_mesh.gd` (`Builder` : prismes effilés et ellipsoïdes à normales lissées, pavés), sans texture ni fichier de modèle. Personnages, chien, banc, coureur, vélo et animaux en sortent tous.
- **Placement et comportement inchangés** : les modèles (`crowd_model.gd`, `passersby_model.gd`, `fauna_behaviour.gd`) et les budgets du décor vivant (`QualityPresets.LIVING`) ne bougent pas ; seuls les maillages et les shaders changent.
- **Animation dans le shader** : articulations (hanche, genou, épaule) pour les personnages dans `crowd.gdshader`, pédalier et roues pour le vélo ; battement d'ailes (UV.x, `INSTANCE_CUSTOM.z` du lot P23) et tête qui broute (UV.y, progressive le long du cou) dans `fauna.gdshader`.
- **Couleurs par zones** (`CUSTOM0.x`) et palettes passées au shader : tenue tirée par personne (`INSTANCE_CUSTOM.w`), robe, teinte d'appoint, sombre, corne et clair par espèce, taches claires de la vache dans le shader.

## 3. Contenu

| Élément | Avant | Après | Triangles |
| --- | --- | --- | --- |
| Spectateur, passant | pavés | corps articulé (cuisse, tibia, bassin, buste, cou, tête avec oreilles et yeux, cheveux courts ou longs, col, ceinture, mains avec pouce, chaussures) | 892 (au plus 1 000) |
| Coureur des bots (O7, branché le 30 octobre) | capsule | casque à aérations, lunettes, maillot à bande, gants, pied sur la pédale (jambe résolue au genou), mains au cintre | 892 |
| Vélo des bots | deux disques | cadre, fourche, selle, cintre, bidon, chaîne, dérailleur, cassette, roues à rayons qui tournent avec la cadence | — |
| Vache, mouton, chevreuil | pavés (72) | vache pie, mouton à toison en bosses et tête noire, chevreuil à miroir blanc et petits bois | 1 000 à 1 200 (au plus 1 500) |
| Oiseau (nuées, rapaces, vols en V, corneilles) | corps et deux triangles (14) | corps fuselé, tête, bec, queue en éventail, ailes à rémiges écartées, 0,9 m d'envergure le long de x | 326 |

Au maximum en `high` : 160 spectateurs et 80 passants (214 000 triangles), 80 oiseaux et 80 bêtes (environ 120 000), mêmes appels de dessin qu'avant.

## 4. Vérification

- Tests : `test_people_mesh.gd`, `test_fauna_mesh.gd`, `render/test_crowd_render.gd`, `render/test_fauna_render.gd`.
- Captures avant et après : vitrine de rendu `engine/tests/vitrine_rendu.gd` (vues `foule`, `passants`, `cyclistes`, `cycliste_profil`, `animaux`, `animaux_pres`).
- Mesure sur la GTX 1060 (banc simulé, 2 min en `low` et `medium`, main contre la branche) : au moins 55 images/s en `low`, p99 sous 25 ms.

## 5. Suite

- Fait le 30 octobre : les bots d'O7 (`bots_view.gd`) sont ce coureur et ce vélo, maillot à la couleur du bot, pédalier calé sur la distance parcourue (`RoadCyclistsModel.DEVELOPMENT_M`, comme les cyclistes du décor P28) ; le fantôme utilise `bot_ghost.gdshader` (même corps `crowd.gdshaderinc`, translucide, sans éclairage).
- Si la mesure dépasse : niveau de détail par distance (maillage réduit au-delà de 40 m), sans changer le reste.
