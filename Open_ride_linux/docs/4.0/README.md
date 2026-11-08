# OpenRide 4.0 – plans

Documents de préparation de la version 4.0. Les cahiers des lots sont dans `docs/lots/` (tableau calculé par `python3 scripts/index_lots.py`) ; les exigences et leur état sont dans la [spécification générale](../SPECIFICATION_GENERALE.md) §5.4. Le code de la 4.0 déjà fusionné reste caché tant que son entrée au menu n'est pas livrée (spécification §2.1).

| Document ou lot | Contenu |
| --- | --- |
| [PLAN_SERIE_TT.md](PLAN_SERIE_TT.md) | Série TT : bonus tactiques (Plume, Casque, Puissance, Enclume, Aspiration +, Échappée, Rouleau compresseur) sur un seul modèle de données ; cahiers TT1 à TT8 (8 novembre) |
| [PLAN_SERIE_GP.md](PLAN_SERIE_GP.md) | Série GP : mode « Grand Prix des objets », treize objets, boîtes, bots qui lancent les objets (lots GP1 à GP11) |
| [PLAN_SERIE_VD.md](PLAN_SERIE_VD.md) | Série VD : vélodrome couvert de 250 m en bois, épreuves de piste (lots VD0 à VD12) |
| Lot K9 | Boîtier gauche du Click gardé déverrouillé sans redémarrage chaque minute |
| Lot U23 | Constructions et faune propres à chaque biome |
| Panneaux d'approche | Plaques plus grandes (+25 %) et plus travaillées (PR #773) |
| Lots RC4 et RC5 | Résistance calculée à basse vitesse et sans pompage à basse cadence |

Ordre : TT1, puis TT2, qui reprend dans sa table unique les effets écrits par GP1 en attendant (`grandprix/effects.py`), puis TT3 à TT5 ; GP4 attend TT4 ; la série CT de la 5.0 attend TT2 à TT5.
