# OpenRide 3.0 – plans

Documents de préparation de la version 3.0. Les cahiers des lots sont dans `docs/lots/` (tableau calculé par `python3 scripts/index_lots.py`) ; les exigences et leur état sont dans la [spécification générale](../SPECIFICATION_GENERALE.md) §5.3.

| Document ou lot | Contenu |
| --- | --- |
| [PLAN_SERIE_U.md](PLAN_SERIE_U.md) | Série U : seize biomes, classification au compilateur (WorldCover, OSM, altitude, latitude), variantes régionales, mer et côtes, saisons par biome, option « gravel » (lots U0 à U22) |
| [PACK_BIOMES_CC0.md](PACK_BIOMES_CC0.md) | Textures CC0 des biomes, téléchargées en packs hors du dépôt |
| Lot PL1 | Peloton d'environ 12 coureurs (11 bots et un fantôme, révision IPC 1.6) |
| Lot DS8 | Dernier survivant jusqu'à 11 adversaires |
| Lot X56 | FIT accepté par Garmin Connect et GoldenCheetah (ligne 21 de la recette 1.0) |
| Lots P33 et P34 | Vent d'après la météo locale (reporté de la 2.0) ; roue lenticulaire et vent de travers (V-Q13) |
| Écran de démarrage | « Start your engines », maquette A (PR #714) |

Ordre à tenir pour fermer la 3.0 (8 novembre) : U2 avant l'étape 1 de la recette U18 ; U3 avant U9 ; U4 avant U14 ; **U13 attend P18 et P19** (jour, nuit et saisons de la 2.0, PR #781) ; étape gravel de U18 à refaire en « Chemins réels ».
