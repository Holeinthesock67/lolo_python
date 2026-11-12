# OpenRide 5.0 – plans

Documents de préparation de la version 5.0 (séries CT, CO et BC ; la série WF a été abandonnée le 12 novembre). La charte cartoon (CT9) et le simulateur d'équilibrage (CT0) sont commencés : la série dépend de la 2.0 (séries AS, T, R, W, lot Y10) et de la 4.0 (power-ups, série TT). Les cahiers des lots sont listés dans `docs/lots/00_INDEX.md`.

| Document | Contenu |
| --- | --- |
| [PLAN_SERIE_CT.md](PLAN_SERIE_CT.md) | Série CT : mode « Course tactique » (étude du document « Triangle Tactique Unifié », décisions du 29 octobre, lots CT0 à CT12) |
| [CHARTE_CARTOON_CT9.md](CHARTE_CARTOON_CT9.md) | Lot CT9 : charte cartoon du mode (palette, formes, effets en low, medium et high, réglage « Effets », confort) et liste des maquettes à valider |
| [RAPPORT_EQUILIBRAGE_CT0.md](RAPPORT_EQUILIBRAGE_CT0.md) | Lot CT0 : courses simulées (200 par circuit et par stratégie du cycliste), victoires par stratégie et par profil, Burnouts, catapultes et capacités ; produit par `python -m openride_core.tools.tactical_sim` |
| [PLAN_SERIE_WF.md](PLAN_SERIE_WF.md) | Série WF : trainer en Wi-Fi (Direct Connect) et mode de mesures rapides ; mesure WF1 d'abord, pilote Wi-Fi (WF2 à WF6) seulement si la mesure le justifie (décision du 31 octobre). **Abandonnée le 12 novembre** (décision du propriétaire), gardée pour l'historique |
| [PLAN_SERIE_CO.md](PLAN_SERIE_CO.md) | Série CO : séance conseillée au menu selon les courses et le besoin du joueur (aérobie léger, aérobie intense, anaérobie) ; comment identifier ces besoins, règles, écran, suggestion de la montre Garmin, séances de jeu calibrées, lots CO0 à CO9 (demandes du 7 novembre) |
| [PLAN_SERIE_BC.md](PLAN_SERIE_BC.md) | Série BC : badges et cartes à collectionner (accomplissements, saisons, anniversaires), recalculés depuis le journal ; catalogue `core/src/openride_core/data/collection.toml` (lot BC1), visuels par l'IA d'images Gemini (lot BC4) |
| [VISUELS_BC4.md](VISUELS_BC4.md) | Lot BC4 : consignes des 42 visuels de la collection pour Nano Banana (Gemini) : bloc de style commun, couleur par rareté, une consigne par carte, planche d'essai de 6 cartes |
