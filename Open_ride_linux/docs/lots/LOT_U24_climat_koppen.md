# Lot U24 – Compilateur : zone climatique des biomes tirée d'une carte de Köppen-Geiger embarquée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Compilateur : zone climatique des biomes d'après une carte de Köppen-Geiger embarquée, paysages volcaniques | Python | U2 | Petite | En PR le 9 novembre, **version 3.0** |

## 1. Objectif

Constat de l'étape 1 de la recette U18 (9 novembre, compilation de six cols du pack dans le cloud, sans OSM :
`/mnt/project-files/mesures/2026-11-09-u18-etape1/cloud_sans_osm.txt`) : le lot U2 choisissait la zone
climatique d'après la latitude seule, si bien que tout ce qui est entre 30° et 44° devenait méditerranéen.
L'Angliru (Asturies, vert et océanique) sortait à 88 % méditerranéen, le Fuji à 99 %, et le Teide n'avait
aucune part volcanique (aucune règle ne produisait `volcanic`). Demande du propriétaire (« Ok », 9 novembre) :
lire une vraie carte des climats, embarquée, sans appel réseau à l'exécution.

## 2. Ce qui change

- **Carte embarquée** `compiler/src/openride_compiler/data/koppen_1986_2010.u8.xz` (214 Ko ; 12 960 × 6 480
  pixels de 100″, environ 3 km ; provenance et licence dans `data/koppen_LISEZMOI.md`, refaite par
  `scripts/prepare_koppen.py`). Module `koppen.py` : lecture une fois par processus (0,2 s, 84 Mo), code d'un
  point, parts des six zones sur un voisinage de 5 × 5 pixels (noyau binomial).
- **Climat → zone** (`koppen.ZONE_OF`) : A → tropicale ; B → aride ; **Csa seul** → tempérée chaude (biome
  méditerranéen) ; Cfa, Cfb, Csb, Csc, Cwa, Cwb, Dfa, Dfb, Dsa, Dsb, Dwa, Dwb → tempérée ; Cfc, Cwc, Dfc, Dfd,
  Dsc, Dsd, Dwc, Dwd → boréale ; ET, EF → polaire. Csb va en tempérée : la carte range la Galice, les Asturies
  et l'Oregon en Csb, à la végétation atlantique. La toundra de montagne (ET, EF sous 58° de latitude, rampe
  jusqu'à 62°) compte comme boréale : l'étage alpin vient déjà de l'altitude. En pleine mer, les bandes de
  latitude du lot U2 restent le repli (`biomes.latitude_zone_weights`).
- **Paysages volcaniques** `data/volcanic_areas.toml` : une quarantaine de disques (centre au centième,
  rayon en km) établis à la main pour ce lot ; le sol nu de WorldCover et le sable OSM (`natural=sand`,
  cendres et lapilli) qui y tombent donnent `volcanic` ; le disque du Teide couvre toute la montée depuis
  Vilaflor. Forêts,
  prairies et cultures gardent leur biome.
- `layers.biome.sources` nomme `koppen_1986_2010` au lieu de `latitude` (texte libre, journal du format
  `.world` complété, sans changement de format ni de version de la couche).
- `Inputs.zones` et `Inputs.volcanic` : fonctions injectables ; les tests de U2 qui visent des latitudes
  fictives gardent les bandes de latitude.

## 3. Critères

1. Aucun accès réseau pour le climat ; la carte s'installe avec la roue (`package-data`).
2. Sur les six cols de l'étape 1 de U18 (mêmes traces avant et après), parts plausibles : Angliru en forêt et
   prairie tempérées, Fuji en forêt, Teide avec une part `volcanic`, Galibier, Ballon d'Alsace et Ventoux
   peu changés.
3. Tests : `compiler/tests/test_koppen.py` (zones de lieux connus, mer, toundra de montagne, table des
   volcans, sol nu volcanique), suites U2 inchangées sur le fond.

## 4. Hors périmètre

- Rendu : aucun changement dans l'engine ; seules les parts de biomes des parcours recompilés changent.
  Captures à valider par le propriétaire lors de la passe PC de l'étape 1 de U18.
- Carte de Beck et al. (1 km, CC BY 4.0) : injoignable depuis le cloud ; le fichier garde la même forme si on
  la prend plus tard (voir `koppen_LISEZMOI.md`).

## 5. Mesure du 9 novembre (cloud, sans OSM)

Mêmes traces avant et après (points de passage du pack reliés en ligne droite), WorldCover et MNT réels ;
fichier complet et scripts : `/mnt/project-files/mesures/2026-11-09-u24-koppen/`.

| Col | Avant (latitude) | Après (Köppen) |
| --- | --- | --- |
| Angliru | méditerranéen 88 %, forêt 9 %, prairie 3 % | forêt tempérée 72 %, prairie 28 % |
| Ballon d'Alsace | forêt 90 %, prairie 10 % | inchangé |
| Galibier | alpin 51 %, forêt 23 %, prairie 20 %, rocaille 5 % | alpin 51 %, prairie 20 %, forêt boréale 19 %, toundra 6 %, forêt 3 % |
| Fuji | méditerranéen 98 %, alpin 1 %, rocaille 1 % | forêt tempérée 59 %, forêt boréale 35 %, prairie 4 %, alpin 1 %, volcanique 0,4 % |
| Ventoux | forêt 38 %, méditerranéen 36 %, rocaille 12 %, prairie 9 % | forêt 63 %, prairie 15 %, rocaille 12 %, méditerranéen 5 % |
| Teide | steppe 63 %, désert de sable 31 %, savane 7 % | prairie 59 %, volcanique 31 %, forêt 6 %, steppe 4 % |
