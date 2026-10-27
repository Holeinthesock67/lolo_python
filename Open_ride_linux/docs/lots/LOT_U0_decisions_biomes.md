# Lot U0 – Décisions de la série U et liste définitive des biomes (version 3.0)

## 1. Objectif

**Version 3.0.** Consigner, avant tout code, les décisions du propriétaire qui fixent la série U (biomes, textures régionales, saisons par biome, option « gravel ») et la liste définitive des biomes, pour que le contrat U1 et les lots suivants n'aient plus rien à trancher.

**Lot du propriétaire :** il ne contient que des décisions.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` (en entier, surtout §2, §7 et §10), `docs/SPECIFICATION_GENERALE.md` §5.3.
2. `docs/2.0/PLAN_SERIE_W.md` (question W-Q2, chemins de terre).

## 3. Prérequis

Aucun.

## 4. Décisions

| # | Sujet | Décision du propriétaire |
| --- | --- | --- |
| U-Q1 | Biome automatique ou forcé | Les deux : automatique d'après les données réelles, forçage au compilateur (`--biome`, lot U2) et au menu (lot U16) |
| U-Q2 | ESA WorldCover | Téléchargé par le compilateur seulement, mis en cache comme le MNT ; jamais de réseau pendant la séance |
| U-Q3 | Origine des textures | Packs CC0 (ambientCG, Poly Haven) installés par `theme-install`, jamais dans le dépôt ; bibliothèque plafonnée à 5 Go, le pack utilisé le moins récemment est retiré ; couleurs unies par défaut ; images Gemini seulement pour panneaux, affiches, motifs et teintes, selon la méthode du lot P20 |
| U-Q4 | Budget sur la GTX 1060 | `low` : 3 biomes au plus par tuile, textures de 1 024 px ; `medium` : 4 biomes, 1 024 px ; `high` : 4 biomes, 2 048 px ; deux cartes compressées par sol ; 1 Go de mémoire vidéo au plus pour le décor ; 55 images/s ou plus en `low` |
| U-Q5 | Premier jalon | Prairie, forêt tempérée, vignobles et cultures, haute montagne, méditerranéen, littoral ; ensuite désert, savane, jungle, polaire, volcanique et les autres |
| U-G1 | Option « gravel » | Réglage des menus, coupé par défaut |
| U-G2 | Ressenti du gravel | Résistance au roulement 2 à 3 fois celle du bitume, transmise en SIM comme supplément de pente sous le même plafond que le vent (`[wind] max_grade_offset_pct`, 4 points par défaut) ; en ERG, seule la vitesse virtuelle change |

**Liste définitive des biomes :** les seize biomes du plan §2, dans cet ordre, avec l'identifiant que fixe le contrat U1 :

| # | Biome | Identifiant |
| --- | --- | --- |
| 1 | Prairie et bocage tempérés (par défaut) | `temperate_grassland` |
| 2 | Forêt tempérée feuillue et mixte | `temperate_forest` |
| 3 | Vignobles et grandes cultures | `farmland` |
| 4 | Forêt boréale (taïga) | `boreal_forest` |
| 5 | Haute montagne alpine | `alpine` |
| 6 | Toundra | `tundra` |
| 7 | Polaire (banquise et glacier) | `polar` |
| 8 | Méditerranéen | `mediterranean` |
| 9 | Steppe | `steppe` |
| 10 | Savane | `savanna` |
| 11 | Désert de sable | `sand_desert` |
| 12 | Désert de roche et canyon | `rock_desert` |
| 13 | Jungle (forêt tropicale humide) | `jungle` |
| 14 | Zones humides | `wetland` |
| 15 | Littoral | `coast` |
| 16 | Volcanique | `volcanic` |

## 5. Livraison (25 octobre 2026)

Décisions U-Q1 à U-Q5 prises par le propriétaire le 25 octobre 2026, U-G1 et U-G2 le même jour (question W-Q2 du monde ouvert) ; complément du 26 octobre pour les images Gemini (U-Q3). Liste et identifiants reportés ici le 27 octobre à la rédaction des cahiers. Les questions nées de la rédaction des cahiers (U-Q6 et suivantes) sont listées au §11 du plan et se règlent dans U1.
