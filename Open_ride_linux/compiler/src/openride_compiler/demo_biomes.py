"""Parcours de démonstration des biomes livrés avec le jeu (lots U19 et O37) : un biome partout, ou les six du
premier jalon à la suite.

Produit, avec le compilateur, un `.world` complet (`route`, `terrain`, `buildings`, `vegetation`, `poi`,
`water`) à partir d'une trace et d'un relief synthétiques et d'une réponse Overpass fabriquée (`fake_osm.py` :
aucune donnée réelle, aucun réseau), puis ajoute ce que le compilateur ne sait pas encore écrire (lots U2, U9,
U20) : la couche `biome` (§8 quater), la colonne `surface` de la route et, avec `sea`, la couche `coast`
(§8 quinquies) et des aires d'eau `sea`. Format 1.6.

- un biome sur 6 km (trois blocs de 2 km), ou le tour des six biomes du premier jalon (côte, méditerranéen,
  prairie, cultures, forêt, alpin), 2 km chacun, transitions de 300 m ;
- relief analytique par biome, mélangé par les poids : bord de mer presque plat, collines de cultures,
  vallée boisée, montée de 7,5 % entre des pentes de montagne pour `alpine` ;
- bâtiments, végétation et points d'intérêt inventés, de densité propre à chaque biome ;
- `gravel` : un tiers de chaque bloc de 2 km en `gravel` ou `dirt` (en alternance), le reste `paved` ;
- `sea` : côte inventée à gauche de la route le long du biome `coast` : terrain sous le niveau 0, ligne
  de côte, plage de sable puis côte rocheuse, aires `sea` (`level_y` = 0) de 300 m de large.

Circuit (lot O38) : `--circuit`, boucle fermée de 3 km dans un seul biome (prairie), relief analytique
`circuit_relief` sous la route et autour (la boucle revient à son altitude de départ), hameau au départ, prés,
cultures, verger, étang à l'intérieur ; le parcours en boucle du jeu de base (courses en tours, Grand Prix).

Tour des nouveaux paysages (lot DB1) : `--paysages`, sept blocs de 2 km qui montrent les biomes et les paysages
de la 6.0 (`PAYSAGES`) : fjord (côte avec la mer), landes atlantiques, rizières, Japon, île volcanique, canyon
rouge, hauts plateaux. Chaque bloc porte, en plus de son biome, la variante régionale de ses tuiles (sol, toits
et paysage du lot U25, champ `variant` de la couche biome), comme `--variant` du compilateur mais bloc par bloc.

Récif (lot SM1) : `--recif`, boucle de 8 km sous la mer dans le biome `reef` (fond marin), même mécanisme que le
circuit (`LOOPS`) : relief `reef_relief` de −11 à −29 m sous la route (lagon clair au départ, tombant plus profond
au sud-est), pentes du récif de part et d'autre plafonnées sous la surface (`reef_cap`, jamais au-dessus de
REEF_TOP_M), forêts de laminaires et de coraux (zones `wood`), herbiers clairsemés (`scrub`), étendues de sable ;
noms des lieux sur des points de vue. Pas de maison, pas de mer posée en surface : l'engine rend le biome sous l'eau.

Volcan en flammes (lot DB2) : `--volcan`, boucle de 8 km dans le biome `volcanic`, toutes ses tuiles dans le paysage
`volcan_actif` (variante `VOLCAN_VARIANT` : lave, braises, fumées et lueur de l'engine, volcano_fx.gd) ; relief
`volcano_relief` : départ au plus bas dans la plaine de cendres, montée régulière de 220 m jusqu'à la crête d'un
cratère (à l'intérieur de la boucle) à mi-boucle, descente par l'autre flanc ; hameau de basalte, refuge, belvédères.

Route des Érables (lot DJ1) : `--biome japan`, six kilomètres dans le biome Japon (trois blocs de 2 km : forêts,
villages aux toits kawara, belvédères, sommet au « Col des Cèdres »), avec la variante régionale d'une vraie route
japonaise (`BIOME_VARIANTS`) ; démonstration du Japon en plus de Hakone et du Fuji du pack Cols célèbres.

Route du Sud et Route du Grand Nord (lot DB3, décision du propriétaire du 14 novembre : une démonstration pour
chaque biome) : `--sud`, six blocs de 2 km sur la route ouverte, des oliviers au delta (méditerranéen, steppe, désert
de sable, savane, jungle, zones humides) ; `--nord`, boucle de 10 km en cinq blocs de 2 km (forêt boréale, toundra,
polaire au point le plus éloigné du départ, toundra, forêt boréale), relief `nord_relief` qui monte vers la banquise.
Une boucle à plusieurs blocs suit les mêmes règles que la route ouverte (blocs de 2 km, fondus de 300 m, décor par
bloc) ; la boucle commence et finit dans le même biome, sans fondu au départ.

Route des Trois Forêts (lot V6-r4) : `--forets`, trois blocs de 2 km sur la route ouverte, en montée, du bush à
eucalyptus à la forêt de nuages par la forêt pluviale tempérée (biomes du rang 4 de l'étude 6.0).

Jeu de base (lots O37, O38, DB1, DB2, DJ1, DB3 et V6-r4) : les parcours de `DEMO_SET` marqués pour le jeu de base (le tour des
nouveaux paysages, la route des Érables, le circuit, le récif, le volcan, la Route du Sud, la Route du Grand Nord et la
Route des Trois Forêts) portent au menu un nom de parcours (`name` du manifeste) et
leurs lieux des noms inventés (`PLACE_NAMES`) ; l'identifiant de fichier ne change pas. Le tour des six paysages, la
route de la côte et la montée alpine sont sortis du jeu de base par le lot DB1 (décision du propriétaire du
12 novembre) : ils ne s'installent plus sur un jeu neuf, restent installés chez un joueur qui les a, et servent aux
bancs. Variante de recette (`recette=True`, `--recette`) pour les bancs et les fiches de recette : tous les parcours,
dont le tour gravel, nom de parcours égal à l'identifiant et lieux « Fictif », comme avant le lot O37 ; jamais dans
le jeu de base.
Vit dans le compilateur (et non plus dans `engine/tests/`) pour qu'un jeu installé sans les tests produise
ses parcours de démonstration.

    python -m openride_compiler.demo_biomes --out DOSSIER --demo-set [--recette]
    python -m openride_compiler.demo_biomes --out DOSSIER --tour [--gravel] [--sea] [--recette]
    python -m openride_compiler.demo_biomes --out DOSSIER --biome alpine
    python -m openride_compiler.demo_biomes --out DOSSIER --circuit
    python -m openride_compiler.demo_biomes --out DOSSIER --paysages [--recette]
    python -m openride_compiler.demo_biomes --out DOSSIER --biome japan
    python -m openride_compiler.demo_biomes --out DOSSIER --volcan
    python -m openride_compiler.demo_biomes --out DOSSIER --recif
    python -m openride_compiler.demo_biomes --out DOSSIER --sud | --nord [--recette]
    → DOSSIER/<id>.world/ et DOSSIER/<id>.json (parts des biomes et des surfaces)

Origine inventée au degré entier (45° N, 2° E : latitude tempérée de l'hémisphère nord, aucune ville au
point), date de création fixe : deux générations donnent des fichiers identiques au bit près.
`openride-core demo-biomes` range les parcours du jeu de base dans le dossier des parcours ; `engine/tests/make_biome_world.py`
reste la ligne de commande des essais de l'engine. Code de sortie : 0 si tout est écrit.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import random
import shutil
import socket
import sys
import tempfile
from pathlib import Path

from . import fake_osm as sim   # Overpass fabriqué, route en S

ORIGIN = (45.0, 2.0)                    # degrés entiers, fictifs
CREATED = "2026-10-30T00:00:00+00:00"   # fixe : parcours reproductibles
OSM_DATE = "2026-10-30T00:00:00Z"
FORMAT_VERSION = "1.6"
LAYERS = ("buildings", "vegetation", "poi", "water")
BLOCK_M = 2000.0                        # longueur d'un biome
TRANSITION_M = 300.0                    # fondu entre deux biomes
STEP_M = 5.0
BASE_ALT_M = 6.0
TOUR = ("coast", "mediterranean", "temperate_grassland", "farmland", "temperate_forest", "alpine")
FIRST_MILESTONE = frozenset(TOUR)
DEFAULT_BIOME = "temperate_grassland"
UNPAVED = (700.0, 700.0 + BLOCK_M / 3.0)   # portion non revêtue de chaque bloc (--gravel)
SEA_SIDE = -1                           # la mer à gauche du sens de marche (à l'ouest)
SEA_BAND_M = (70.0, 370.0)              # aires `sea` : de 70 à 370 m de l'axe
BEACH_M = (36.0, 70.0)
NEAR_T, FAR_T, GRID = 1000.0, 5000.0, 17
GENERATOR = "openride-demo-biomes"    # `compiler.name` du manifeste (« make_biome_world » avant le lot O37)
# Parcours de démonstration : (identifiant de fichier, nom affiché au menu, biomes, gravel, mer, jeu de base).
# Le tour gravel n'est que de recette (décision du propriétaire du 9 novembre) : le gravel étant coupé par
# défaut, il s'affichait et se roulait comme le tour asphalté.
# Le circuit (lot O38) est le parcours en boucle du jeu de base : courses en tours, Grand Prix des objets.
# Lot DB1 (décision du propriétaire du 12 novembre) : le tour des nouveaux paysages remplace au jeu de base le tour
# des six paysages, la route de la côte et la montée alpine, gardés pour les bancs et les recettes.
# Démonstration Japon (lot DJ1, décision du propriétaire du 13 novembre) : six kilomètres dans le seul biome `japan`,
# en plus de Hakone et du Fuji du pack Cols célèbres ; construite comme la montée alpine (un biome, trois blocs).
DEMO_SET = (("demo-biomes-paysages", "Tour des nouveaux paysages", "paysages", False, True, True),
            ("demo-japon", "Route des Érables", "japan", False, False, True),
            ("demo-biomes-tour", "Tour des six paysages", "tour", False, False, False),
            ("demo-biomes-gravel", "demo-biomes-gravel", "tour", True, False, False),
            ("demo-biomes-cote", "Route de la côte", "coast", False, True, False),
            ("demo-biomes-alpin", "Montée alpine", "alpine", False, False, False),
            ("demo-circuit", "Circuit des Prés", "circuit", False, False, True),
            ("demo-recif", "Récif des tortues", "recif", False, False, True),
            ("demo-volcan", "Volcan en flammes", "volcan", False, False, True),
            ("demo-biomes-sud", "Route du Sud", "sud", False, False, True),
            ("demo-biomes-nord", "Route du Grand Nord", "nord", False, False, True),
            ("demo-biomes-forets", "Route des Trois Forêts", "forets", False, False, True))
# Tour des nouveaux paysages (lot DB1) : par bloc de 2 km, (biome, paysage du lot U25, sol, toits) ; le paysage,
# le sol et les toits forment la variante régionale des tuiles du bloc (`None` : ce que donne le biome). Ordre
# choisi pour que deux blocs voisins ne partagent aucun biome de base de leurs paysages (section `landscapes`
# du thème) : la transition de 300 m d'un bloc ne prend jamais le paysage de son voisin. Départ au bord de la
# mer, arrivée au sommet des hauts plateaux.
PAYSAGES = (("coast", "fjord", "schiste_sombre", "bois_peint"),
            ("atlantic_heath", None, "granite_gris", "ardoise"),
            ("farmland", "rizieres", "laterite_rouge", None),
            ("japan", None, None, "kawara"),
            ("volcanic", "ile_volcanique", "basalte", None),
            ("rock_desert", "canyon", "gres_rose", None),
            ("high_plateau", None, None, None))
PAYSAGES_BIOMES = tuple(b for b, *_ in PAYSAGES)
# Lot DB3 (décision du propriétaire du 14 novembre : chaque biome a sa démonstration) : mêmes blocs que le tour des
# nouveaux paysages. Route du Sud : des oliviers au delta, sans saut de climat d'un bloc au suivant, sommet entre la
# steppe et le désert, descente de la jungle vers le delta. Route du Grand Nord (en boucle, demande du 14 novembre :
# « le 6 km c'est court, fais une boucle ») : la banquise au point le plus éloigné du départ, la toundra et la taïga
# de part et d'autre ; la boucle commence et finit dans la taïga.
SUD = (("mediterranean", None, None, None),
       ("steppe", None, None, None),
       ("sand_desert", None, None, None),
       ("savanna", None, None, None),
       ("jungle", None, None, None),
       ("wetland", None, None, None))
NORD = (("boreal_forest", None, None, None),
        ("tundra", None, None, None),
        ("polar", None, None, None),
        ("tundra", None, None, None),
        ("boreal_forest", None, None, None))
# Route des Trois Forêts (lot V6-r4 : les biomes du rang 4 de l'étude 6.0 ont leur démonstration, règle du
# propriétaire du 14 novembre) : du bush à eucalyptus, sec et bas, à la forêt pluviale tempérée, puis la montée finit
# dans le brouillard de la forêt de nuages ; l'humidité et l'altitude montent d'un bloc au suivant.
FORETS = (("eucalypt_woodland", None, None, None),
          ("temperate_rainforest", None, None, None),
          ("cloud_forest", None, None, None))
# Parcours en blocs de 2 km : table des blocs de chacun (biome, paysage, sol, toits).
BLOCK_TOURS = {"paysages": PAYSAGES, "sud": SUD, "nord": NORD, "forets": FORETS}
NORD_M = BLOCK_M * len(NORD)
NORD_LOBES = ((2, 0.16, 0.3), (3, 0.06, 1.1))
NORD_CLIMB_M = 120.0         # du départ (taïga) à la banquise ; pente au plus ~6 %, ondulations comprises 8 %
NORD_HILLS_M = 35.0          # collines loin de la route (moraines, croupes de la toundra)
# Variante régionale des parcours d'un seul biome (lot DJ1) : celle que le compilateur donne à une vraie route de
# la région (zones `japon_*` de data/regional_variants.toml : sol basalte, toits kawara, test_japon_demo).
BIOME_VARIANTS = {"japan": {"ground": "basalte", "roofs": "kawara", "landscape": None}}
# Circuit de démonstration (lot O38) : boucle de 3 km (un tour de 5 à 7 minutes), prairie, départ au hameau.
CIRCUIT_M = 3000.0
CIRCUIT_BIOME = "temperate_grassland"
CIRCUIT_LOBES = ((2, 0.3, 0.0), (3, 0.15, 0.5), (4, 0.05, 2.0))   # (k, amplitude, phase) du rayon, voir `fake_osm.LoopRoad`
# Récif de démonstration (lot SM1, demande du propriétaire du 13 novembre : « un parcours démo dans un monde sous-marin
# luxuriant », en boucle) : 8 km sous la mer, biome `reef`.
REEF_M = 8000.0
REEF_BIOME = "reef"
REEF_LOBES = ((2, 0.22, 0.4), (3, 0.12, 1.3), (5, 0.04, 0.2))
REEF_WRECK_S = 7880.0       # lot SM2 : épave 120 m avant l'arrivée (sable entre la forêt du retour et le lagon)
REEF_WRECK_OFFSET_M = 45.0  # à 45 m du bord de la route, côté extérieur
REEF_WRECK_LENGTH_M = 42.0
REEF_TOP_M = -4.0           # le récif ne monte jamais au-dessus (sous le niveau de la mer, 0)
REEF_SOFT_M = 3.0           # plafond adouci sur les 3 derniers mètres
# Étiquettes des parcours de démonstration (fiche `library.tags` du manifeste, `DEMO_LIBRARY`) : un parcours d'un mode à parcours
# propres (lot GP13, `openride_core.mode_routes`) ne se court que dans ce mode : le Circuit des Prés est au Grand
# Prix des objets (décision du propriétaire du 15 novembre). Recette comprise : les bancs passent par le même menu.
# Lot NT1 (intégration des démos dans la version finale) : chaque parcours de démonstration porte sa fiche
# (`library` du manifeste, champs de `route_stats.LIBRARY_KEYS`), comme le vélodrome et les cols du pack : la
# description s'affiche sur la carte du parcours au menu ; mêmes textes que le guide d'utilisation. Une seule table
# pour la fiche entière (description et étiquettes) ; une démonstration écrite avec une autre fiche est remplacée
# par les contenus de départ (`openride_core.demo_world.biome_demo_outdated`).
DEMO_LIBRARY = {
    "demo-biomes-paysages": {"description": "14 km du fjord aux hauts plateaux, par les landes atlantiques, les "
                                            "rizières, le Japon, une île volcanique et un canyon rouge."},
    "demo-japon": {"description": "6 km de montée douce au Japon, entre forêts de cèdres, villages aux toits de "
                                  "tuiles et belvédères."},
    "demo-circuit": {"description": "Boucle de 3 km dans les prés, pour les courses en tours.",
                     "tags": ["grandprix"]},
    "demo-recif": {"description": "Boucle de 8 km sous la mer, du lagon au tombant, entre laminaires et coraux, "
                                  "jusqu'à une épave."},
    "demo-volcan": {"description": "Boucle de 8 km dans un volcan en éruption, entre coulées de lave, braises et "
                                   "fumées, jusqu'à la crête du cratère."},
    "demo-biomes-sud": {"description": "12 km des oliviers au delta, par la steppe, les dunes, la savane et la "
                                       "jungle."},
    "demo-biomes-nord": {"description": "Boucle de 10 km de la taïga à la banquise par la toundra, et retour."},
    "demo-biomes-forets": {"description": "6 km de montée du bush à eucalyptus à la forêt de nuages, par la forêt "
                                          "pluviale tempérée."},
}


def library_of(name: str) -> dict | None:
    """Fiche du manifeste d'un parcours de démonstration (copie), ou None pour un parcours sans fiche."""
    lib = DEMO_LIBRARY.get(name)
    return None if lib is None else {k: list(v) if isinstance(v, list) else v for k, v in lib.items()}


# Volcan en flammes (lot DB2, demande du 13 novembre : « parcours démo exagéré feu et flammes », en boucle) : 8 km,
# biome volcanique dans le paysage `volcan_actif` (lave, braises, fumées : engine volcano_fx.gd), départ dans la plaine
# de cendres, montée régulière jusqu'à la crête du cratère à mi-boucle, descente par l'autre flanc.
VOLCAN_M = 8000.0
VOLCAN_BIOME = "volcanic"
VOLCAN_LOBES = ((2, 0.18, 0.4), (3, 0.08, 1.3))
VOLCAN_VARIANT = {"ground": "basalte", "roofs": None, "landscape": "volcan_actif"}
VOLCAN_CLIMB_M = 220.0       # montée du départ à la crête (pente au plus 220 π / 8 000 ≈ 8,6 %, ondulations comprises 10 %)
VOLCAN_RIM_M = 620.0         # centre du cratère à 620 m de la route, à l'intérieur de la boucle, à mi-boucle : la route
                             # tourne du même côté que la crête et la suit sur un bon kilomètre, cratère à droite
VOLCAN_CRATER_M = 600.0      # rayon du creux du cratère, juste en deçà de la route
VOLCAN_DEPTH_M = 150.0       # profondeur du cratère sous sa crête
VOLCAN_WALL_M = 140.0        # largeur des parois du cratère (pente moyenne d'environ 45 %), fond plat au-delà
VOLCAN_CONE_M = 1300.0       # largeur du cône (relief loin de la route)
VOLCAN_ROAD_M = 220.0        # au-delà, le relief ne suit plus le profil de la route mais le cône
GAME_DEMOS = tuple(name for name, *_, base in DEMO_SET if base)     # écrits par les contenus de départ
RETIRED_DEMOS = tuple(name for name, *_, base in DEMO_SET if not base)
# Lieux du jeu de base : un nom par bloc du même biome (trois blocs au plus), dans l'ordre de la route ; le col
# est compté depuis la fin (le dernier bloc alpin porte le sommet, nommé sur son panneau). Variante de recette :
# les noms « Fictif » d'avant le lot O37.
PLACE_NAMES = {
    "port": ("Port-Lanterne", "Anse aux Mouettes", "Port-Galets"),
    "pointe": ("Pointe des Goélands", "Pointe du Phare", "Pointe aux Sternes"),
    "mas": ("Mas des Oliviers", "Mas de la Cigale", "Mas des Lavandes"),
    "hameau": ("Hameau des Prés", "Les Granges", "Hameau du Ruisseau"),
    "etang": ("Étang des Saules", "Étang du Moulin", "Étang aux Hérons"),
    "col": ("Col des Edelweiss", "Belvédère du Glacier", "Belvédère des Marmottes"),
    # Tour des nouveaux paysages (lot DB1) : un bloc par biome, un nom par clé.
    "fjord": ("Port-Bouleau",),
    "fjord_vue": ("Belvédère du Fjord",),
    "lande": ("Hameau des Murets",),
    "lande_vue": ("Pointe des Ajoncs",),
    "rizieres": ("Village des Rizières",),
    # Route des Érables (lot DJ1) : trois blocs `japan` ; le dernier belvédère est le sommet du parcours.
    "japon": ("Village des Érables", "Hameau du Torii", "Village des Lanternes"),
    "japon_vue": ("Belvédère des Cerisiers", "Belvédère du Lac", "Col des Cèdres"),
    "volcan": ("Cratère des Fumerolles",),
    "canyon": ("Belvédère du Canyon Rouge",),
    "plateau": ("Col des Lamas",),
    "lagon": ("Lagon des Tortues",),
    "laminaires": ("Forêt des Laminaires",),
    "corail": ("Jardin de Corail",),
    "tombant": ("Tombant Bleu",),
    "epave": ("Épave de la Belle-Tortue",),
    # Volcan en flammes : hameau du départ, belvédère des coulées, crête du cratère.
    "scories": ("Hameau des Scories",),
    "coulees": ("Belvédère des Coulées",),
    "brasier": ("Cratère du Brasier",),
    # Route du Sud et Route du Grand Nord (lot DB3) : deux noms quand la boucle repasse dans le même biome.
    "yourtes": ("Campement des Yourtes",),
    "oasis": ("Oasis des Palmiers",),
    "dunes": ("Belvédère des Dunes",),
    "savane": ("Village des Baobabs",),
    "savane_vue": ("Point de vue des Girafes",),
    "canopee": ("Belvédère de la Canopée",),
    "pilotis": ("Village des Pilotis",),
    "delta": ("Pointe des Palétuviers",),
    "mares": ("Mare aux Hérons",),
    "chenal": ("Chenal des Roseaux",),
    "trappeurs": ("Hameau des Trappeurs", "Cabanes du Lac Gelé"),
    "lac_nord": ("Lac des Huards", "Lac aux Castors"),
    "toundra": ("Refuge du Caribou", "Refuge des Lichens"),
    "banquise": ("Station de la Banquise",),
    "banquise_vue": ("Belvédère des Glaces",),
    # Route des Trois Forêts (lot V6-r4) : un bloc par biome.
    "bush": ("Ferme des Kangourous",),
    "bush_vue": ("Belvédère des Gommiers",),
    "cedres": ("Cabanes des Grands Cèdres",),
    "cascade": ("Cascade des Mousses",),
    "finca": ("Finca des Palmiers",),
    "nuages": ("Col des Nuages",),
}
RECETTE_PLACE_NAMES = {"port": "Port Fictif", "pointe": "Pointe Fictive", "mas": "Mas Fictif",
                       "hameau": "Hameau Fictif", "etang": "Étang Fictif", "col": "Col Fictif",
                       "fjord": "Port Fictif", "fjord_vue": "Pointe Fictive", "lande": "Hameau Fictif",
                       "lande_vue": "Pointe Fictive", "rizieres": "Village Fictif", "japon": "Village Fictif",
                       "japon_vue": "Belvédère Fictif", "volcan": "Cratère Fictif", "canyon": "Belvédère Fictif",
                       "plateau": "Col Fictif",
                       "lagon": "Lagon Fictif", "laminaires": "Laminaires Fictives", "corail": "Corail Fictif",
                       "tombant": "Tombant Fictif", "epave": "Épave Fictive",
                       "scories": "Hameau Fictif", "coulees": "Belvédère Fictif",
                       "brasier": "Cratère Fictif",
                       "yourtes": "Hameau Fictif", "oasis": "Village Fictif", "dunes": "Belvédère Fictif",
                       "savane": "Village Fictif", "savane_vue": "Belvédère Fictif", "canopee": "Belvédère Fictif",
                       "pilotis": "Village Fictif", "delta": "Pointe Fictive", "mares": "Étang Fictif",
                       "chenal": "Étang Fictif", "trappeurs": "Hameau Fictif",
                       "lac_nord": "Étang Fictif", "toundra": "Hameau Fictif", "banquise": "Hameau Fictif",
                       "banquise_vue": "Belvédère Fictif",
                       "bush": "Hameau Fictif", "bush_vue": "Belvédère Fictif", "cedres": "Hameau Fictif",
                       "cascade": "Étang Fictif", "finca": "Village Fictif", "nuages": "Col Fictif"}

# Pente de la route (%) dans un bloc, selon la position u (m) dans le bloc.
GRADE = {
    "coast": lambda u: 0.3 * math.sin(u / 260.0),
    "mediterranean": lambda u: 3.0 + 2.0 * math.sin(u / 300.0),
    "temperate_grassland": lambda u: 1.0 + 1.5 * math.sin(u / 250.0),
    "farmland": lambda u: 2.5 * math.sin(2.0 * math.pi * u / 700.0),
    "temperate_forest": lambda u: 4.0 + 1.0 * math.sin(u / 200.0),
    "alpine": lambda u: 7.5 + 1.5 * math.sin(u / 350.0),
    # Lot DB1 : landes ondulées, vallée japonaise, flanc du volcan, fond de canyon, haut plateau presque plat.
    "atlantic_heath": lambda u: 1.0 + 1.5 * math.sin(u / 230.0),
    "japan": lambda u: 3.0 + 2.0 * math.sin(u / 240.0),
    "volcanic": lambda u: 5.0 + 1.5 * math.sin(u / 300.0),
    "rock_desert": lambda u: 2.0 + 2.5 * math.sin(u / 280.0),
    "high_plateau": lambda u: 1.5 + 1.0 * math.sin(u / 320.0),
    # Lot DB3 : steppe en faux plat, dunes, savane ondulée, descente de la jungle vers le delta, delta plat ; la
    # taïga, la toundra et la banquise (pentes de la route ouverte ; la boucle du Grand Nord suit son relief).
    "steppe": lambda u: 1.0 + 1.0 * math.sin(u / 280.0),
    "sand_desert": lambda u: 1.2 * math.sin(2.0 * math.pi * u / 600.0),
    "savanna": lambda u: 0.5 + 1.0 * math.sin(u / 260.0),
    "jungle": lambda u: -2.0 + 1.5 * math.sin(u / 220.0),
    "wetland": lambda u: 0.2 * math.sin(u / 300.0),
    "boreal_forest": lambda u: 2.0 + 1.5 * math.sin(u / 250.0),
    "tundra": lambda u: 1.5 + 1.0 * math.sin(u / 300.0),
    "polar": lambda u: 1.0 + 1.0 * math.sin(u / 330.0),
    # Lot V6-r4 : collines du bush en faux plat, montée sous les grands conifères, montée plus raide dans les nuages.
    "eucalypt_woodland": lambda u: 1.5 + 1.5 * math.sin(u / 260.0),
    "temperate_rainforest": lambda u: 4.0 + 1.5 * math.sin(u / 220.0),
    "cloud_forest": lambda u: 5.5 + 1.5 * math.sin(u / 240.0),
}
# Relief de part et d'autre de la route : (pente des flancs, pente au-delà de 160 m, amplitude des collines).
FAR_RISE_M = 800.0   # longueur de la pente lointaine : palier à far_slope × 800 m (360 m en montagne)
SIDES = {
    "coast": (0.03, 0.02, 4.0),
    "mediterranean": (0.10, 0.08, 40.0),
    "temperate_grassland": (0.04, 0.03, 15.0),
    "farmland": (0.06, 0.04, 25.0),
    "temperate_forest": (0.12, 0.15, 30.0),
    "alpine": (0.25, 0.45, 80.0),
    "atlantic_heath": (0.05, 0.04, 12.0),
    "japan": (0.15, 0.25, 50.0),
    "volcanic": (0.12, 0.20, 60.0),
    "rock_desert": (0.25, 0.55, 60.0),        # parois du canyon
    "high_plateau": (0.03, 0.04, 25.0),
    "reef": (0.06, 0.10, 12.0),        # lot SM1 : pentes du récif, plafonnées sous la surface (reef_cap)
    "steppe": (0.04, 0.03, 20.0),
    "sand_desert": (0.02, 0.02, 25.0),       # dunes
    "savanna": (0.03, 0.02, 12.0),
    "jungle": (0.12, 0.15, 40.0),
    "wetland": (0.01, 0.01, 2.0),            # delta plat
    "boreal_forest": (0.06, 0.05, 25.0),
    "tundra": (0.03, 0.03, 15.0),
    "polar": (0.02, 0.03, 30.0),
    "eucalypt_woodland": (0.04, 0.04, 25.0),
    "temperate_rainforest": (0.14, 0.20, 50.0),
    "cloud_forest": (0.20, 0.35, 70.0),      # versants raides des Andes
}


class Plan:
    """Suite de biomes le long de la route et tout ce qui en découle (poids, altitude, surface).

    Route ouverte (`circuit` faux) : deux grands S vers le nord sur 2 km par biome, altitude intégrée de la pente
    `GRADE` du biome. Boucle (`loop`, une clé de `LOOPS` ; `circuit` vrai seul : le circuit du lot O38) : la boucle
    `lobes` de `length_m`, altitude lue sur son relief `relief(x, z, s, d)` (point, abscisse de la route la plus
    proche et distance à son axe ; la boucle revient forcément à son altitude de départ) : un seul biome (`biome` de
    la boucle), ou un bloc de 2 km par biome comme la route ouverte, les blocs faisant toute la boucle (Route du
    Grand Nord, lot DB3)."""

    def __init__(self, biomes: tuple[str, ...], gravel: bool, sea: bool, recette: bool = False,
                 circuit: bool = False, loop: str | None = None,
                 variants: tuple[dict | None, ...] | None = None) -> None:
        loop = loop or ("circuit" if circuit else None)
        circuit = loop is not None
        if circuit and LOOPS[loop]["biome"] is not None and len(set(biomes)) != 1:
            raise ValueError("circuit : un seul biome")
        if circuit and LOOPS[loop]["biome"] is None and abs(BLOCK_M * len(biomes) - LOOPS[loop]["length_m"]) > 1.0:
            raise ValueError("boucle à plusieurs blocs : 2 km par bloc, sur toute la boucle")
        if variants is not None and len(variants) != len(biomes):
            raise ValueError("une variante par bloc")
        self.biomes = biomes
        # Variante régionale de chaque bloc (lot DB1) : {"ground", "roofs", "landscape"} ou None.
        self.variants = tuple(variants) if variants is not None else (None,) * len(biomes)
        self.recette = recette
        self.gravel = gravel
        self.circuit = circuit
        self.loop = loop
        self.relief = LOOPS[loop]["relief"] if loop else None
        self.sea = sea and "coast" in biomes and not circuit
        self.road = sim.LoopRoad(LOOPS[loop]["length_m"], LOOPS[loop]["lobes"]) if loop \
            else sim.SRoad(BLOCK_M * len(biomes))
        self.length_m = self.road.length_m
        self.offset = tuple(float(v) for v in self.road.xz(0.0))
        self._alt = [self.altitude_at(*self.road.xz(0.0), 0.0)]
        n = int(self.length_m / STEP_M)
        for k in range(n):
            s = (k + 0.5) * STEP_M
            if circuit:
                self._alt.append(self.altitude_at(*self.road.xz((k + 1) * STEP_M), (k + 1) * STEP_M))
            else:
                self._alt.append(self._alt[-1] + STEP_M * self.grade(s) / 100.0)

    def s_of_world(self, x, z):
        """Abscisse de la route au point (x, z) du repère du `.world` compilé : le compilateur centre son repère sur le
        départ de la trace (`offset` dans le repère de la route fabriquée : nul sur la route ouverte, qui part de
        l'origine, rayon de la boucle au nord du centre pour une boucle)."""
        import numpy as np
        return self.road.s_of(np.asarray(x, dtype=float) + self.offset[0], np.asarray(z, dtype=float) + self.offset[1])

    def altitude_at(self, x, z, s=0.0):
        """Relief de la boucle sous la route (m) au point (x, z) d'abscisse `s` ; la route ouverte n'a pas de relief
        propre (altitude intégrée)."""
        return self.relief(x, z, s, 0.0) if self.circuit else BASE_ALT_M

    def base(self, s, x, z, d=None):
        """Altitude de référence du terrain au point (x, z) dont la route la plus proche est en `s`, à `d` m de son
        axe (boucles seulement)."""
        import numpy as np
        if self.circuit:
            return self.relief(x, z, s, np.zeros_like(np.asarray(x, dtype=float)) if d is None else d)
        return np.interp(s, np.arange(len(self._alt)) * STEP_M, self._alt)

    def place(self, key: str, i: int) -> str:
        """Nom du lieu `key` dans le bloc `i` (voir `PLACE_NAMES`)."""
        if self.recette:
            return RECETTE_PLACE_NAMES[key]
        biome = self.biomes[i]
        k = self.biomes[i + 1:].count(biome) if key == "col" else self.biomes[:i].count(biome)
        return PLACE_NAMES[key][k % len(PLACE_NAMES[key])]

    def block(self, s: float) -> int:
        """Bloc de 2 km de l'abscisse `s`."""
        return min(max(int(s // BLOCK_M), 0), len(self.biomes) - 1)

    def decor(self, i: int) -> str:
        """Clé du décor du bloc `i` dans `BLOCKS` : son paysage (lot DB1), sinon son biome."""
        variant = self.variants[i]
        return (variant or {}).get("landscape") or self.biomes[i]

    def weights(self, s: float) -> dict[str, float]:
        """Part (0 à 1) de chaque biome à l'abscisse `s` : fondu linéaire de 300 m centré sur chaque limite."""
        s = min(max(s, 0.0), self.length_m)
        out: dict[str, float] = {}
        for i, b in enumerate(self.biomes):
            lo, hi = i * BLOCK_M, (i + 1) * BLOCK_M
            w_in = 1.0 if i == 0 else _ramp((s - (lo - TRANSITION_M / 2)) / TRANSITION_M)
            w_out = 1.0 if i == len(self.biomes) - 1 else 1.0 - _ramp((s - (hi - TRANSITION_M / 2)) / TRANSITION_M)
            w = min(w_in, w_out)
            if w > 0.0:
                out[b] = out.get(b, 0.0) + w
        return out

    def weights_np(self, s):
        """`weights` sur un tableau d'abscisses : {biome: tableau de parts}."""
        import numpy as np
        s = np.clip(np.asarray(s, dtype=float), 0.0, self.length_m)
        out: dict = {}
        last = len(self.biomes) - 1
        for i, b in enumerate(self.biomes):
            lo, hi = i * BLOCK_M, (i + 1) * BLOCK_M
            w_in = 1.0 if i == 0 else np.clip((s - (lo - TRANSITION_M / 2)) / TRANSITION_M, 0.0, 1.0)
            w_out = 1.0 if i == last else 1.0 - np.clip((s - (hi - TRANSITION_M / 2)) / TRANSITION_M, 0.0, 1.0)
            out[b] = out.get(b, 0.0) + np.minimum(w_in, w_out) * np.ones_like(s)
        return out

    def grade(self, s: float) -> float:
        u = s % BLOCK_M
        return sum(w * GRADE[b](u) for b, w in self.weights(s).items())

    def altitude(self, s: float) -> float:
        s = min(max(s, 0.0), self.length_m)
        k = min(int(s / STEP_M), len(self._alt) - 2)
        t = (s - k * STEP_M) / STEP_M
        return self._alt[k] * (1.0 - t) + self._alt[k + 1] * t

    def surface(self, s: float) -> str:
        if not self.gravel:
            return "paved"
        block = min(int(s // BLOCK_M), len(self.biomes) - 1)
        u = s - block * BLOCK_M
        if UNPAVED[0] <= u < UNPAVED[1]:
            return "gravel" if block % 2 == 0 else "dirt"
        return "paved"


def circuit_relief(x, z, s=None, d=None):
    """Relief du circuit (m) : une croupe au nord-ouest, un vallon au sud-est, une pente douce vers l'est.
    Pente de la route de −5 à +5 % environ, 37 m de montée par tour (`test_circuit_loop`)."""
    import numpy as np
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    return (BASE_ALT_M + 40.0 + 14.0 * np.sin(x / 210.0 + 0.6) * np.cos(z / 260.0)
            - 12.0 * np.exp(-((x - 260.0) ** 2 + (z - 200.0) ** 2) / 90000.0) + _soft_cap(x / 60.0, 15.0, 30.0))


def _soft_cap(v, knee: float, rise: float):
    """`v` tel quel jusqu'à ±`knee`, puis un palier doux à ±(`knee` + `rise`) (lot DB1) : un relief analytique
    reste borné jusqu'à l'horizon (40 km) sans changer près de la route."""
    import numpy as np
    a = np.abs(v)
    return np.sign(v) * np.where(a <= knee, a, knee + rise * (1.0 - np.exp(-(a - knee) / rise)))


def reef_relief(x, z, s=None, d=None):
    """Fond du récif sous la route (m, lot SM1) : −16 m en moyenne, bosses de 5 m, cuvette du tombant (−9 m de plus)
    au sud-est, lagon moins profond au nord (départ) ; de −11 à −29 m, pentes de route sous 4 % environ."""
    import numpy as np
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    return reef_cap(-16.0 + 5.0 * np.sin(x / 380.0 + 0.3) * np.cos(z / 330.0)
                    - 9.0 * np.exp(-((x - 700.0) ** 2 + (z - 650.0) ** 2) / 450000.0)
                    + 4.0 * np.exp(-(x ** 2 + (z + 1300.0) ** 2) / 250000.0))


def reef_cap(h):
    """Plafond du récif (lot SM1) : `h` inchangé jusqu'à REEF_TOP_M − REEF_SOFT_M, puis approche de REEF_TOP_M sans
    l'atteindre (raccord continu et de pente continue ; idempotent sous le seuil, donc la route garde son altitude)."""
    import numpy as np
    h = np.asarray(h, dtype=float)
    a = REEF_TOP_M - REEF_SOFT_M
    return np.where(h <= a, h, REEF_TOP_M - REEF_SOFT_M * np.exp(-(np.maximum(h, a) - a) / REEF_SOFT_M))


_VOLCAN_ROAD = []


def volcano_road():
    """Boucle du volcan (`fake_osm.LoopRoad`), la même que celle de `Plan` : le relief se construit sur elle."""
    if not _VOLCAN_ROAD:
        _VOLCAN_ROAD.append(sim.LoopRoad(VOLCAN_M, VOLCAN_LOBES))
    return _VOLCAN_ROAD[0]


def volcano_crater() -> tuple[float, float]:
    """Centre du cratère : à `VOLCAN_RIM_M` de la route à mi-boucle, vers l'intérieur de la boucle (son centre)."""
    road = volcano_road()
    px, pz = road.xz(road.length_m / 2.0)
    r0 = math.hypot(px, pz)
    return px * (1.0 - VOLCAN_RIM_M / r0), pz * (1.0 - VOLCAN_RIM_M / r0)


def volcano_relief(x, z, s, d):
    """Relief du volcan en flammes (lot DB2) : profil de la route en cosinus surélevé (départ au plus bas, crête du
    cratère à mi-boucle, `VOLCAN_CLIMB_M` de montée, petites ondulations) ; loin de la route, un cône centré sur le
    cratère (à l'intérieur de la boucle), creusé d'un cratère de `VOLCAN_CRATER_M` de rayon dont la route suit la crête
    (`VOLCAN_RIM_M`) ; entre les deux, fondu sur `VOLCAN_ROAD_M` (le profil de la route ne fait jamais de marche au
    milieu de la boucle). Borné partout."""
    import numpy as np
    road = volcano_road()
    length = road.length_m
    cx, cz = volcano_crater()
    peak = BASE_ALT_M + VOLCAN_CLIMB_M

    def profile(s):
        return (BASE_ALT_M + VOLCAN_CLIMB_M * 0.5 * (1.0 - np.cos(2.0 * np.pi * s / length))
                + 1.2 * np.sin(2.0 * np.pi * s / 500.0) * np.sin(np.pi * s / length))

    def field(x, z):
        r = np.hypot(x - cx, z - cz)
        cone = peak * np.exp(-(r / VOLCAN_CONE_M) ** 2)
        # Parois raides sur VOLCAN_WALL_M puis fond plat (lacs de lave du paysage `volcan_actif`)
        t = np.clip((VOLCAN_CRATER_M - r) / VOLCAN_WALL_M, 0.0, 1.0)
        crater = -VOLCAN_DEPTH_M * t * t * (3.0 - 2.0 * t)
        crest = 15.0 * np.exp(-((r - VOLCAN_RIM_M) / 70.0) ** 2)
        return cone + crater + crest + 8.0 * np.sin(x / 190.0) * np.cos(z / 230.0)

    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    s = np.asarray(s, dtype=float)
    rx, rz = road.xz_np(s)
    w = np.clip(1.0 - np.asarray(d, dtype=float) / VOLCAN_ROAD_M, 0.0, 1.0)
    w = w * w * (3.0 - 2.0 * w)
    return field(x, z) + w * (profile(s) - field(np.asarray(rx), np.asarray(rz)))



_NORD_ROAD = []


def nord_road():
    """Boucle de la Route du Grand Nord (`fake_osm.LoopRoad`), la même que celle de `Plan`."""
    if not _NORD_ROAD:
        _NORD_ROAD.append(sim.LoopRoad(NORD_M, NORD_LOBES))
    return _NORD_ROAD[0]


def nord_relief(x, z, s, d):
    """Relief de la Route du Grand Nord (lot DB3), qui ne dépend que du point (x, z) et de la distance à la route (la
    boucle revient à son altitude de départ, aucune marche entre deux rives) : pente douce le long de l'axe du départ
    (taïga) au point le plus éloigné (banquise), `NORD_CLIMB_M` de montée en marche lissée, petites ondulations et
    collines de `NORD_HILLS_M` loin de la route. Borné partout (axe borné, collines bornées). Flancs dans le relief
    (`sides` faux) : ceux de `SIDES` dépendent du bloc de la route la plus proche, ce qui ferait une marche à
    mi-chemin de deux blocs qui se font face."""
    import numpy as np
    road = nord_road()
    x0, z0 = road.xz(0.0)
    x1, z1 = road.xz(road.length_m / 2.0)
    ux, uz = x1 - x0, z1 - z0
    span2 = ux * ux + uz * uz
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    t = np.clip(((x - x0) * ux + (z - z0) * uz) / span2, 0.0, 1.0)
    away = np.clip((np.asarray(d, dtype=float) - 60.0) / 300.0, 0.0, 1.0)
    hills = NORD_HILLS_M * away * (0.5 + 0.5 * np.sin(x / 330.0) * np.cos(z / 290.0))
    return BASE_ALT_M + NORD_CLIMB_M * t * t * (3.0 - 2.0 * t) + 4.0 * np.sin(x / 240.0) * np.cos(z / 270.0) + hills


def _ramp(t: float) -> float:
    return min(1.0, max(0.0, t))


def make_terrain(plan: Plan):
    """Relief `f(x, z)` : altitude de la route, flancs et collines des biomes, fond marin côté mer."""
    import numpy as np

    def terrain(x, z):
        x = np.asarray(x, dtype=float)
        z = np.asarray(z, dtype=float)
        s, dx = plan.road.locate(x, z)
        d = np.abs(dx)
        base = plan.base(s, x, z, d)
        weights = plan.weights_np(s)
        side = np.zeros_like(base)
        # Lot DB1 : une boucle dont le relief porte déjà ses flancs (`sides` faux : le volcan du lot DB2) n'en reçoit
        # pas d'autres de `SIDES` (le biome `volcanic` y a des flancs pour le tour des nouveaux paysages)
        sides = SIDES if not plan.loop or LOOPS[plan.loop].get("sides", True) else {}
        for b, (slope, far_slope, hills) in sides.items():
            w = weights.get(b)
            if w is None or not np.any(w):
                continue
            ramp = np.clip((d - 40.0) / 260.0, 0.0, 1.0)
            bump = hills * ramp * (0.5 + 0.5 * np.sin(x / 310.0) * np.cos(z / 270.0))
            # Lot DB1 : au-delà de 162 m, la pente lointaine s'adoucit jusqu'à un palier (`FAR_RISE_M`) : sans borne,
            # les tuiles lointaines et d'horizon (jusqu'à 40 km) montaient à plusieurs kilomètres, en murs dans le ciel
            far = _soft_cap(np.clip(d - 162.0, 0.0, None), 0.0, FAR_RISE_M)
            side += w * (slope * np.clip(d - 12.0, 0.0, 150.0) + far_slope * far + bump)
        if plan.sea:
            sea = weights.get("coast", 0.0) * (np.sign(dx) == SEA_SIDE)
            # Plage de la route au niveau 0 entre 36 et 70 m de l'axe, puis fond marin jusqu'à −25 m.
            t = d - BEACH_M[0]
            shore = np.where(d < BEACH_M[1], base * (1.0 - t / (BEACH_M[1] - BEACH_M[0])), -0.1 * (d - BEACH_M[1]))
            shore = np.where(d < BEACH_M[0], base, np.maximum(shore, -25.0))
            return np.where(sea > 0.0, (1.0 - sea) * (base + side) + sea * shore, base + side)
        if plan.loop == "recif":
            return reef_cap(base + side)
        return base + side

    return terrain


def build_overpass(frame, plan: Plan, seed: int) -> sim.Overpass:
    """Éléments OSM fictifs par bloc de 2 km, selon le biome du bloc."""
    rng = random.Random(seed)
    op = sim.Overpass(frame, rng, plan.road)
    if plan.loop in LOOP_BLOCKS:
        LOOP_BLOCKS[plan.loop](op, rng, plan)
        return op
    for i in range(len(plan.biomes)):
        s0 = i * BLOCK_M
        BLOCKS[plan.decor(i)](op, rng, s0, s0 + BLOCK_M, plan, i)
    return op


def _veg(op: sim.Overpass, s0: float, s1: float, side: int, near: float, far: float, tags: dict) -> None:
    lo, hi = (near, far) if side > 0 else (-far, -near)
    op.way(op.band(s0, s1, lo, hi), tags)
    op.counts["vegetation"] += 1


def _houses(op: sim.Overpass, rng: random.Random, s0: float, s1: float, sides: tuple[int, ...], colours: list[str],
            name: str, gap: tuple[float, float] = (20.0, 28.0), church: bool = True) -> None:
    s = s0
    while s < s1:
        for side in sides:
            if rng.random() < 0.15:
                continue
            tags: dict = {"building": rng.choice(["house", "house", "house", "garage", "yes"]),
                          "building:colour": rng.choice(colours)}
            length, depth = (rng.uniform(5, 7), rng.uniform(5, 6)) if tags["building"] == "garage" \
                else (rng.uniform(9, 14), rng.uniform(7, 10))
            tags["building:levels"] = str(rng.randint(1, 3))
            op.building(s, side * (rng.uniform(13.0, 17.0) + depth / 2), tags, length, depth)
        s += rng.uniform(*gap)
    mid = (s0 + s1) / 2
    if church:
        side = sides[-1]
        op.building(mid, side * 34.0, {"building": "church", "amenity": "place_of_worship", "height": "15 m"}, 26.0, 13.0)
    op.node(*op.point(mid, sides[0] * 30.0), {"place": "village", "name": name})


def _farms(op: sim.Overpass, spots: tuple[float, ...], colour: str) -> None:
    for k, s in enumerate(spots):
        side = 1 if k % 2 else -1
        op.building(s, side * 32.0, {"building": "farm", "building:levels": "2", "building:colour": colour}, 16.0, 11.0)
        op.building(s + 22.0, side * 38.0, {"building": "barn", "height": "8 m"}, 22.0, 13.0)


def _coast(op, rng, s0, s1, plan, i):
    land = -SEA_SIDE
    _houses(op, rng, s0 + 250.0, s0 + 650.0, (land,), ["#f0e6d2", "#ffffff", "#e8dcc4", "#d4e4ee"], plan.place("port", i))
    _veg(op, s0 + 700.0, s1 - 100.0, land, 22.0, 200.0, {"landuse": "grass"})
    if not plan.sea:
        _veg(op, s0 + 100.0, s1 - 100.0, -land, 22.0, 140.0, {"natural": "scrub"})
    op.node(*op.point(s0 + 1200.0, land * 25.0), {"tourism": "viewpoint", "name": plan.place("pointe", i)})


def _mediterranean(op, rng, s0, s1, plan, i):
    _veg(op, s0 + 150.0, s1 - 150.0, -1, 22.0, 220.0, {"natural": "scrub"})
    _veg(op, s0 + 150.0, s0 + 900.0, 1, 22.0, 160.0, {"landuse": "orchard"})
    _veg(op, s0 + 1500.0, s1 - 150.0, 1, 22.0, 200.0, {"natural": "scrub"})
    _houses(op, rng, s0 + 1000.0, s0 + 1400.0, (1, -1), ["#f0e6d2", "#e3c9a8", "#f5efe0", "#e8b98a"], plan.place("mas", i))


def _grassland(op, rng, s0, s1, plan, i):
    _veg(op, s0 + 100.0, s1 - 100.0, 1, 22.0, 250.0, {"landuse": "meadow"})
    _veg(op, s0 + 100.0, s0 + 1100.0, -1, 22.0, 250.0, {"landuse": "meadow", "animal": "cattle"})
    _veg(op, s0 + 1300.0, s1 - 100.0, -1, 22.0, 120.0, {"natural": "scrub"})
    _farms(op, (s0 + 400.0, s0 + 1600.0), "#d9cfc1")
    _houses(op, rng, s0 + 900.0, s0 + 1200.0, (-1, 1), sim.COLOURS, plan.place("hameau", i), gap=(30.0, 45.0), church=False)
    mid = s0 + 1450.0
    op.way([op.point(mid, d) for d in range(-250, 251, 25)], {"waterway": "stream"}, close=False)
    op.counts["water_lines"] += 1


def _farmland(op, rng, s0, s1, plan, i):
    for side in (-1, 1):
        _veg(op, s0 + 100.0, s0 + 950.0, side, 22.0, 300.0, {"landuse": "farmland"})
        _veg(op, s0 + 1050.0, s1 - 100.0, side, 22.0, 300.0, {"landuse": "farmland"})
    _veg(op, s0 + 950.0, s0 + 1050.0, 1, 22.0, 180.0, {"landuse": "orchard"})
    _farms(op, (s0 + 300.0, s0 + 800.0, s0 + 1300.0, s0 + 1750.0), "#c9b59a")
    for s, off in ((s0 + 600.0, 260.0), (s0 + 1100.0, 320.0), (s0 + 1550.0, 280.0)):
        op.node(*op.point(s, off), {"power": "generator", "generator:source": "wind", "height": "95"})


def _forest(op, rng, s0, s1, plan, i):
    _veg(op, s0 + 50.0, s1 - 50.0, 1, 20.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 50.0, s0 + 900.0, -1, 20.0, 300.0, {"natural": "wood"})
    _veg(op, s0 + 1250.0, s1 - 50.0, -1, 20.0, 300.0, {"landuse": "forest"})
    lake_s = s0 + 1080.0
    _pond(op, lake_s, -110.0, plan.place("etang", i))
    op.building(s0 + 1500.0, -28.0, {"building": "house", "building:levels": "2", "building:colour": "#b9a48a"}, 11.0, 8.0)


def _alpine(op, rng, s0, s1, plan, i):
    _veg(op, s0 + 50.0, s0 + 700.0, 1, 20.0, 260.0, {"natural": "wood"})
    _veg(op, s0 + 700.0, s1 - 50.0, 1, 20.0, 260.0, {"natural": "heath"})
    _veg(op, s0 + 50.0, s1 - 50.0, -1, 20.0, 200.0, {"natural": "grassland"})
    _veg(op, s0 + 1100.0, s0 + 1500.0, -1, 200.0, 320.0, {"natural": "scrub"})
    for s in (s0 + 450.0, s0 + 1250.0, s0 + 1800.0):
        op.building(s, 26.0, {"building": "house", "height": "9 m", "building:colour": "#8a6a4a"}, 12.0, 10.0)
        op.building(s + 18.0, -30.0, {"building": "barn", "height": "7 m", "building:colour": "#7a5a3a"}, 14.0, 10.0)
    op.node(*op.point(s1 - 150.0, -25.0), {"tourism": "viewpoint", "name": plan.place("col", i)})


def _pond(op: sim.Overpass, s: float, offset: float, name: str) -> None:
    c = op.point(s, offset)
    op.way([(c[0] + 60.0 * math.cos(a / 12 * 2 * math.pi), c[1] + 40.0 * math.sin(a / 12 * 2 * math.pi))
            for a in range(12)], {"natural": "water", "water": "lake", "name": name})
    op.counts["water_areas"] += 1


def _circuit(op, rng, plan):
    """Circuit (lot O38) : départ et arrivée au hameau, prés et cultures à l'extérieur de la boucle, verger,
    broussailles et étang à l'intérieur (côté droit, bandes de 120 m au plus : l'intérieur n'en croise jamais
    l'autre rive), une ferme, un bois et deux éoliennes."""
    inside, out = sim.LoopRoad.INSIDE, -sim.LoopRoad.INSIDE
    _houses(op, rng, 40.0, 340.0, (inside, out), sim.COLOURS, plan.place("hameau", 0))
    _veg(op, 420.0, 1350.0, out, 22.0, 250.0, {"landuse": "meadow", "animal": "cattle"})
    _veg(op, 400.0, 1000.0, inside, 22.0, 120.0, {"landuse": "orchard"})
    _veg(op, 1100.0, 1550.0, inside, 22.0, 110.0, {"natural": "scrub"})
    _pond(op, 1950.0, inside * 140.0, plan.place("etang", 0))
    _veg(op, 1450.0, 2100.0, out, 22.0, 280.0, {"landuse": "farmland"})
    _veg(op, 2100.0, 2850.0, inside, 22.0, 120.0, {"landuse": "meadow"})
    _veg(op, 2500.0, 2900.0, out, 20.0, 260.0, {"natural": "wood"})
    _farms(op, (700.0, 1600.0), "#d9cfc1")
    for s in (1000.0, 2000.0):
        op.node(*op.point(s, out * 280.0), {"power": "generator", "generator:source": "wind", "height": "95"})


# --- Tour des nouveaux paysages (lot DB1) : un décor par bloc, choisi par le paysage du bloc ou son biome ---

def _fjord(op, rng, s0, s1, plan, i):
    """Fjord : la mer à gauche (`--sea`), maisons de bois peint et bois de conifères côté terre, belvédère."""
    land = -SEA_SIDE
    _houses(op, rng, s0 + 250.0, s0 + 650.0, (land,), ["#8c2f2a", "#c9a227", "#f2efe6", "#5a6e7f"],
            plan.place("fjord", i), church=False)
    _veg(op, s0 + 700.0, s1 - 100.0, land, 22.0, 260.0, {"natural": "wood"})
    if not plan.sea:
        _veg(op, s0 + 100.0, s1 - 100.0, -land, 22.0, 140.0, {"natural": "grassland"})
    op.node(*op.point(s0 + 1300.0, land * 25.0), {"tourism": "viewpoint", "name": plan.place("fjord_vue", i)})


def _atlantic(op, rng, s0, s1, plan, i):
    """Landes atlantiques : bruyères et ajoncs des deux côtés, prés, hameau de granit (les murets viennent du
    biome, lot AT1)."""
    _veg(op, s0 + 100.0, s0 + 1200.0, 1, 22.0, 260.0, {"natural": "heath"})
    _veg(op, s0 + 100.0, s1 - 100.0, -1, 22.0, 260.0, {"natural": "heath"})
    _veg(op, s0 + 1300.0, s1 - 100.0, 1, 22.0, 200.0, {"landuse": "meadow", "animal": "sheep"})
    _veg(op, s0 + 1250.0, s0 + 1600.0, -1, 200.0, 300.0, {"natural": "scrub"})
    _houses(op, rng, s0 + 700.0, s0 + 1000.0, (1, -1), ["#9a9a94", "#b4b1a8", "#e8e4da"], plan.place("lande", i),
            gap=(30.0, 45.0), church=False)
    op.node(*op.point(s0 + 1500.0, -25.0), {"tourism": "viewpoint", "name": plan.place("lande_vue", i)})


def _paddies(op, rng, s0, s1, plan, i):
    """Rizières : cultures des deux côtés (le paysage du lot U25 en fait des rizières), un village, un ruisseau."""
    for side in (-1, 1):
        _veg(op, s0 + 100.0, s0 + 850.0, side, 22.0, 300.0, {"landuse": "farmland"})
        _veg(op, s0 + 1200.0, s1 - 100.0, side, 22.0, 300.0, {"landuse": "farmland"})
    _houses(op, rng, s0 + 900.0, s0 + 1150.0, (-1, 1), ["#c9b28f", "#a8835a", "#e0d2b4"], plan.place("rizieres", i),
            gap=(30.0, 45.0), church=False)
    mid = s0 + 1500.0
    op.way([op.point(mid, d) for d in range(-250, 251, 25)], {"waterway": "stream"}, close=False)
    op.counts["water_lines"] += 1


def _japan(op, rng, s0, s1, plan, i):
    """Japon : forêt sur les pentes, village aux toits de tuiles (`kawara`), étang, belvédère."""
    _veg(op, s0 + 50.0, s0 + 700.0, 1, 20.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 50.0, s1 - 50.0, -1, 20.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 1300.0, s1 - 50.0, 1, 20.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 750.0, s0 + 1250.0, 1, 60.0, 200.0, {"landuse": "farmland"})
    _houses(op, rng, s0 + 800.0, s0 + 1200.0, (1,), ["#3b3330", "#f1ece2", "#6b4e3a"], plan.place("japon", i),
            gap=(22.0, 30.0), church=False)
    op.node(*op.point(s0 + 1700.0, -25.0), {"tourism": "viewpoint", "name": plan.place("japon_vue", i)})


def _volcanic_island(op, rng, s0, s1, plan, i):
    """Île volcanique : prairies et broussailles sur le flanc, quelques maisons blanches, belvédère du cratère."""
    _veg(op, s0 + 100.0, s1 - 100.0, 1, 22.0, 220.0, {"natural": "grassland"})
    _veg(op, s0 + 100.0, s0 + 1100.0, -1, 22.0, 220.0, {"natural": "scrub"})
    _veg(op, s0 + 1200.0, s1 - 100.0, -1, 22.0, 180.0, {"natural": "grassland"})
    for s in (s0 + 350.0, s0 + 900.0):
        op.building(s, 24.0, {"building": "house", "building:levels": "1", "building:colour": "#f4f1ea"}, 11.0, 8.0)
    op.node(*op.point(s1 - 200.0, -25.0), {"tourism": "viewpoint", "name": plan.place("volcan", i)})


def _canyon(op, rng, s0, s1, plan, i):
    """Canyon rouge : broussailles clairsemées entre les parois, un ranch, belvédère."""
    _veg(op, s0 + 150.0, s0 + 900.0, 1, 30.0, 160.0, {"natural": "scrub"})
    _veg(op, s0 + 1200.0, s1 - 150.0, -1, 30.0, 160.0, {"natural": "scrub"})
    op.building(s0 + 600.0, -30.0, {"building": "farm", "building:levels": "1", "building:colour": "#b5683e"}, 14.0, 9.0)
    op.building(s0 + 620.0, -45.0, {"building": "barn", "height": "6 m", "building:colour": "#8a5a3a"}, 12.0, 9.0)
    op.node(*op.point(s0 + 1100.0, 25.0), {"tourism": "viewpoint", "name": plan.place("canyon", i)})


def _plateau(op, rng, s0, s1, plan, i):
    """Hauts plateaux : herbes rases à perte de vue, quelques maisons de terre, le sommet du tour en fin de bloc."""
    for side in (-1, 1):
        _veg(op, s0 + 100.0, s1 - 100.0, side, 22.0, 300.0, {"natural": "grassland"})
    for s in (s0 + 500.0, s0 + 1300.0):
        op.building(s, -26.0, {"building": "house", "building:levels": "1", "building:colour": "#a07a55"}, 10.0, 7.0)
    op.node(*op.point(s1 - 150.0, -25.0), {"tourism": "viewpoint", "name": plan.place("plateau", i)})


# --- Route du Sud et Route du Grand Nord (lot DB3) : un décor par biome ; les arbres, la faune et les sons viennent
# du biome (engine), les éléments OSM ne posent que les zones, les maisons, l'eau et les lieux nommés ---

def _steppe(op, rng, s0, s1, plan, i):
    """Steppe : herbes rases à perte de vue, broussailles rares, campement de yourtes (petits bâtiments clairs)."""
    for side in (-1, 1):
        _veg(op, s0 + 100.0, s1 - 100.0, side, 22.0, 300.0, {"natural": "grassland"})
    _veg(op, s0 + 1300.0, s0 + 1700.0, 1, 200.0, 300.0, {"natural": "scrub"})
    for k, s in enumerate((s0 + 800.0, s0 + 830.0, s0 + 860.0)):
        op.building(s, (-1) ** k * 26.0, {"building": "hut", "building:levels": "1", "building:colour": "#efe8d8"},
                    7.0, 7.0)
    op.node(*op.point(s0 + 840.0, 30.0), {"place": "hamlet", "name": plan.place("yourtes", i)})


def _sand_desert(op, rng, s0, s1, plan, i):
    """Désert de sable : rien que des dunes (biome), une oasis avec son étang, ses vergers et ses maisons de terre,
    belvédère des dunes au sommet de la route (début du bloc)."""
    op.node(*op.point(s0 + 250.0, -25.0), {"tourism": "viewpoint", "name": plan.place("dunes", i)})
    _pond(op, s0 + 1200.0, 95.0, plan.place("oasis", i))
    _veg(op, s0 + 1050.0, s0 + 1350.0, 1, 22.0, 60.0, {"landuse": "orchard"})
    _veg(op, s0 + 1100.0, s0 + 1300.0, -1, 22.0, 80.0, {"landuse": "orchard"})
    for s in (s0 + 1120.0, s0 + 1180.0, s0 + 1260.0):
        op.building(s, -28.0, {"building": "house", "building:levels": "1", "building:colour": "#c9a77c"}, 9.0, 8.0)


def _savanna(op, rng, s0, s1, plan, i):
    """Savane : herbes hautes et bosquets (le biome y pose acacias, termitières, zèbres et girafes), village de
    cases, point de vue."""
    _veg(op, s0 + 100.0, s1 - 100.0, 1, 22.0, 300.0, {"natural": "grassland"})
    _veg(op, s0 + 100.0, s0 + 900.0, -1, 22.0, 300.0, {"natural": "grassland"})
    _veg(op, s0 + 1000.0, s1 - 100.0, -1, 22.0, 250.0, {"natural": "scrub"})
    for k, s in enumerate((s0 + 600.0, s0 + 640.0, s0 + 690.0, s0 + 730.0)):
        op.building(s, (-1) ** k * 25.0, {"building": "hut", "building:levels": "1", "building:colour": "#a86b3c"},
                    6.0, 6.0)
    op.node(*op.point(s0 + 660.0, 30.0), {"place": "village", "name": plan.place("savane", i)})
    op.node(*op.point(s0 + 1500.0, -25.0), {"tourism": "viewpoint", "name": plan.place("savane_vue", i)})


def _jungle(op, rng, s0, s1, plan, i):
    """Jungle : forêt des deux côtés, une clairière avec un ruisseau, belvédère sur la canopée."""
    _veg(op, s0 + 50.0, s1 - 50.0, 1, 20.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 50.0, s0 + 1000.0, -1, 20.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 1200.0, s1 - 50.0, -1, 20.0, 300.0, {"landuse": "forest"})
    mid = s0 + 1100.0
    op.way([op.point(mid, d) for d in range(-250, 251, 25)], {"waterway": "stream"}, close=False)
    op.counts["water_lines"] += 1
    op.node(*op.point(s0 + 400.0, -25.0), {"tourism": "viewpoint", "name": plan.place("canopee", i)})


def _wetland(op, rng, s0, s1, plan, i):
    """Zones humides : delta plat, mares et chenaux des deux côtés (palétuviers et roseaux du biome), village sur
    pilotis, pointe à l'arrivée."""
    for k, s in enumerate((s0 + 300.0, s0 + 700.0, s0 + 1150.0, s0 + 1600.0)):
        _pond(op, s, (-1) ** k * 90.0, plan.place("mares", i) if k < 2 else plan.place("chenal", i))
    for side in (-1, 1):
        _veg(op, s0 + 100.0, s1 - 100.0, side, 22.0, 60.0, {"natural": "grassland"})
    _veg(op, s0 + 400.0, s0 + 1000.0, 1, 150.0, 300.0, {"natural": "wood"})
    for s in (s0 + 900.0, s0 + 930.0, s0 + 965.0):
        op.building(s, -24.0, {"building": "house", "building:levels": "1", "building:colour": "#8a6a48"}, 8.0, 6.0)
    op.node(*op.point(s0 + 930.0, -30.0), {"place": "village", "name": plan.place("pilotis", i)})
    op.node(*op.point(s1 - 150.0, 25.0), {"tourism": "viewpoint", "name": plan.place("delta", i)})


def _boreal(op, rng, s0, s1, plan, i):
    """Taïga : forêt de conifères des deux côtés, un lac, hameau de cabanes de rondins."""
    _veg(op, s0 + 50.0, s1 - 50.0, -1, 20.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 50.0, s0 + 800.0, 1, 20.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 1300.0, s1 - 50.0, 1, 20.0, 300.0, {"landuse": "forest"})
    _pond(op, s0 + 1050.0, 120.0, plan.place("lac_nord", i))
    for s in (s0 + 950.0, s0 + 990.0, s0 + 1150.0):
        op.building(s, 26.0, {"building": "hut", "building:levels": "1", "building:colour": "#6e4b2e"}, 9.0, 7.0)
    op.node(*op.point(s0 + 1000.0, 32.0), {"place": "hamlet", "name": plan.place("trappeurs", i)})


def _tundra(op, rng, s0, s1, plan, i):
    """Toundra : mousses et herbes rases (biome), arbustes nains par taches, un refuge."""
    for side in (-1, 1):
        _veg(op, s0 + 100.0, s1 - 100.0, side, 22.0, 300.0, {"natural": "grassland"})
    _veg(op, s0 + 500.0, s0 + 900.0, -1, 120.0, 260.0, {"natural": "scrub"})
    op.building(s0 + 1200.0, 28.0, {"building": "hut", "building:levels": "1", "building:colour": "#b03a2e"}, 8.0, 6.0)
    op.node(*op.point(s0 + 1200.0, 36.0), {"place": "hamlet", "name": plan.place("toundra", i)})


def _polar(op, rng, s0, s1, plan, i):
    """Banquise : glace à perte de vue (biome), une station de recherche, belvédère au point le plus haut."""
    for s, colour in ((s0 + 700.0, "#d8382c"), (s0 + 740.0, "#f2f2ee")):
        op.building(s, -30.0, {"building": "yes", "building:levels": "1", "building:colour": colour}, 14.0, 8.0)
    op.node(*op.point(s0 + 720.0, -40.0), {"place": "hamlet", "name": plan.place("banquise", i)})
    op.node(*op.point(s0 + BLOCK_M / 2.0, 25.0), {"tourism": "viewpoint", "name": plan.place("banquise_vue", i)})


# --- Route des Trois Forêts (lot V6-r4) : arbres, faune et sons du biome ; les éléments OSM posent les zones,
# les maisons, l'eau et les lieux nommés ---

def _eucalypt(op, rng, s0, s1, plan, i):
    """Bush à eucalyptus : forêt claire des deux côtés (eucalyptus, acacias, kangourous du biome), une ferme aux
    toits de tôle et ses enclos, belvédère sur les collines."""
    _veg(op, s0 + 50.0, s1 - 50.0, -1, 20.0, 300.0, {"natural": "wood"})
    _veg(op, s0 + 50.0, s0 + 700.0, 1, 20.0, 300.0, {"natural": "wood"})
    _veg(op, s0 + 1200.0, s1 - 50.0, 1, 20.0, 300.0, {"natural": "wood"})
    _veg(op, s0 + 750.0, s0 + 1150.0, 1, 60.0, 260.0, {"natural": "grassland"})
    for s in (s0 + 850.0, s0 + 900.0, s0 + 1000.0):
        op.building(s, 27.0, {"building": "house", "building:levels": "1", "building:colour": "#e8dcc4"}, 11.0, 9.0)
    op.node(*op.point(s0 + 920.0, 34.0), {"place": "hamlet", "name": plan.place("bush", i)})
    op.node(*op.point(s0 + 1700.0, -25.0), {"tourism": "viewpoint", "name": plan.place("bush_vue", i)})


def _rainforest(op, rng, s0, s1, plan, i):
    """Forêt pluviale tempérée : grands douglas et thuyas des deux côtés, un torrent et sa cascade, cabanes de
    bardeaux de cèdre."""
    _veg(op, s0 + 50.0, s1 - 50.0, 1, 18.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 50.0, s0 + 900.0, -1, 18.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 1250.0, s1 - 50.0, -1, 18.0, 300.0, {"landuse": "forest"})
    mid = s0 + 1100.0
    op.way([op.point(mid, d) for d in range(-250, 251, 25)], {"waterway": "stream"}, close=False)
    op.counts["water_lines"] += 1
    _pond(op, mid, -110.0, plan.place("cascade", i))
    for s in (s0 + 450.0, s0 + 500.0):
        op.building(s, -26.0, {"building": "hut", "building:levels": "1", "building:colour": "#6e4630"}, 9.0, 7.0)
    op.node(*op.point(s0 + 480.0, -34.0), {"place": "hamlet", "name": plan.place("cedres", i)})


def _cloud_forest(op, rng, s0, s1, plan, i):
    """Forêt de nuages : fougères arborescentes et palmiers à cire des deux côtés, une finca aux tuiles rondes et ses
    caféiers, le col dans le brouillard à l'arrivée."""
    _veg(op, s0 + 50.0, s1 - 50.0, -1, 18.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 50.0, s0 + 500.0, 1, 18.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 1000.0, s1 - 50.0, 1, 18.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 550.0, s0 + 950.0, 1, 60.0, 220.0, {"landuse": "orchard"})
    _houses(op, rng, s0 + 600.0, s0 + 900.0, (1,), ["#f2ede2", "#e6dccb", "#2f6b8a"], plan.place("finca", i),
            gap=(24.0, 32.0), church=False)
    op.node(*op.point(s1 - 150.0, -25.0), {"tourism": "viewpoint", "name": plan.place("nuages", i)})


def _recif(op, rng, plan):
    """Récif (lot SM1) : lagon de sable clair au départ, forêt de laminaires, herbiers clairsemés et sable,
    jardin de corail des deux côtés, tombant plus profond (au sud-est, côté extérieur), retour par une forêt ;
    aucune construction. Bandes de 200 m au plus à l'intérieur (l'intérieur n'en croise jamais l'autre rive)."""
    inside, out = sim.LoopRoad.INSIDE, -sim.LoopRoad.INSIDE
    op.node(*op.point(120.0, out * 30.0), {"tourism": "viewpoint", "name": plan.place("lagon", 0)})
    _veg(op, 250.0, 700.0, inside, 25.0, 120.0, {"natural": "scrub"})
    for side in (inside, out):
        _veg(op, 800.0, 2300.0, side, 14.0, 200.0, {"natural": "wood"})
    op.node(*op.point(1500.0, out * 25.0), {"tourism": "viewpoint", "name": plan.place("laminaires", 0)})
    _veg(op, 2500.0, 3300.0, inside, 20.0, 160.0, {"natural": "scrub"})
    _veg(op, 2500.0, 3500.0, out, 30.0, 220.0, {"natural": "scrub"})
    for side in (inside, out):
        _veg(op, 3700.0, 5200.0, side, 12.0, 180.0, {"natural": "wood"})
    op.node(*op.point(4400.0, inside * 25.0), {"tourism": "viewpoint", "name": plan.place("corail", 0)})
    _veg(op, 5400.0, 6600.0, out, 40.0, 260.0, {"natural": "scrub"})
    op.node(*op.point(6000.0, out * 30.0), {"tourism": "viewpoint", "name": plan.place("tombant", 0)})
    _veg(op, 6700.0, 7800.0, inside, 14.0, 180.0, {"natural": "wood"})
    _veg(op, 6800.0, 7700.0, out, 14.0, 220.0, {"natural": "wood"})
    # Lot SM2 : épave d'un caboteur couchée sur le sable avant l'arrivée, côté extérieur, vue de loin en
    # approchant de la ligne (hors des forêts, entre le retour par les laminaires et le lagon).
    op.node(*op.point(REEF_WRECK_S, out * REEF_WRECK_OFFSET_M),
            {"historic": "wreck", "length": f"{REEF_WRECK_LENGTH_M:g}", "name": plan.place("epave", 0)})


def _volcan(op, rng, plan):
    """Volcan en flammes (lot DB2) : hameau de basalte au départ dans la plaine de cendres, refuge et belvédère sur la
    crête du cratère à mi-boucle, broussailles rares sur le bas des flancs ; la lave, les braises et les fumées sont
    celles du paysage `volcan_actif` (engine), pas des éléments OSM."""
    half = plan.length_m / 2.0
    inside, out = sim.LoopRoad.INSIDE, -sim.LoopRoad.INSIDE
    _houses(op, rng, 60.0, 300.0, (inside,), ["#3d3b3a", "#4e3b33", "#5a5450"], plan.place("scories", 0), church=False)
    _veg(op, 400.0, 1400.0, inside, 24.0, 160.0, {"natural": "scrub"})
    _veg(op, plan.length_m - 1400.0, plan.length_m - 400.0, out, 24.0, 160.0, {"natural": "scrub"})
    op.building(half - 120.0, inside * 26.0, {"building": "hut", "building:levels": "1", "building:colour": "#4e3b33"}, 9.0, 7.0)
    op.node(*op.point(half, out * 24.0), {"tourism": "viewpoint", "name": plan.place("brasier", 0)})
    op.node(*op.point(half * 0.5, out * 30.0), {"tourism": "viewpoint", "name": plan.place("coulees", 0)})


BLOCKS = {"coast": _coast, "mediterranean": _mediterranean, "temperate_grassland": _grassland,
          "farmland": _farmland, "temperate_forest": _forest, "alpine": _alpine,
          # lot DB1 : décor par paysage (U25) ou par biome de la 6.0
          "fjord": _fjord, "atlantic_heath": _atlantic, "rizieres": _paddies, "japan": _japan,
          "ile_volcanique": _volcanic_island, "canyon": _canyon, "high_plateau": _plateau,
          # lot DB3 : les neuf biomes qui n'avaient pas de démonstration (le méditerranéen garde le sien)
          "steppe": _steppe, "sand_desert": _sand_desert, "savanna": _savanna, "jungle": _jungle,
          "wetland": _wetland, "boreal_forest": _boreal, "tundra": _tundra, "polar": _polar,
          # lot V6-r4 : les trois biomes du rang 4
          "eucalypt_woodland": _eucalypt, "temperate_rainforest": _rainforest, "cloud_forest": _cloud_forest}


# Boucles (lots O38, SM1, DB2 et DB3) : longueur, lobes du rayon (`fake_osm.LoopRoad`), biome (`None` : un bloc de 2 km
# par biome, décor de chaque bloc pris dans `BLOCKS`, sans entrée dans `LOOP_BLOCKS`), relief `relief(x, z, s, d)`,
# variante régionale de toutes ses tuiles (`variant`, absente : aucune), flancs de `SIDES` (`sides`, absent : oui ;
# lot DB1), contenu.
LOOPS = {
    "circuit": {"length_m": CIRCUIT_M, "lobes": CIRCUIT_LOBES, "biome": CIRCUIT_BIOME, "relief": circuit_relief},
    "recif": {"length_m": REEF_M, "lobes": REEF_LOBES, "biome": REEF_BIOME, "relief": reef_relief},
    "volcan": {"length_m": VOLCAN_M, "lobes": VOLCAN_LOBES, "biome": VOLCAN_BIOME, "relief": volcano_relief,
               "variant": VOLCAN_VARIANT, "sides": False},
    "nord": {"length_m": NORD_M, "lobes": NORD_LOBES, "biome": None, "relief": nord_relief, "sides": False},
}
LOOP_BLOCKS = {"circuit": _circuit, "recif": _recif, "volcan": _volcan}


def tour_blocks(which: str) -> tuple[tuple[str, ...], tuple[dict | None, ...] | None]:
    """Biomes et variantes du parcours `which` de `DEMO_SET` : un bloc de 2 km par ligne de `BLOCK_TOURS` (tour des
    nouveaux paysages, Route du Sud, Route du Grand Nord), les six biomes du premier jalon, le biome unique d'une
    boucle, sinon trois blocs du même biome (variante de `BIOME_VARIANTS`)."""
    if which in BLOCK_TOURS:
        out = []
        for _biome, landscape, ground, roofs in BLOCK_TOURS[which]:
            variant = {"ground": ground, "roofs": roofs, "landscape": landscape}
            out.append(variant if any(variant.values()) else None)
        return tuple(b for b, *_ in BLOCK_TOURS[which]), (tuple(out) if any(out) else None)
    if which == "tour":
        return TOUR, None
    if which in LOOPS:
        return (LOOPS[which]["biome"],), None
    biomes = (which,) * 3
    return biomes, biome_variants(biomes)


class Frame(sim.Frame):
    def __init__(self) -> None:
        super().__init__(ORIGIN)


def write_gpx(path: Path, frame: Frame, plan: Plan, name: str) -> None:
    """Trace du parcours ; celle du circuit finit sur son départ (le compilateur en fait une boucle)."""
    pts = []
    for k in range(int(plan.length_m / STEP_M) + 1):
        s = k * STEP_M
        lat, lon = frame.latlon(*plan.road.xz(s))
        pts.append(f'<trkpt lat="{lat:.10f}" lon="{lon:.10f}"><ele>{plan.altitude(s):.3f}</ele></trkpt>')
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<gpx version="1.1" creator="openride-demo-biomes" xmlns="http://www.topografix.com/GPX/1/1">'
                    f"<trk><name>{name}</name><trkseg>{''.join(pts)}</trkseg></trk></gpx>\n", encoding="utf-8")


# --- Couches ajoutées après la compilation (format 1.6) ----------------------------------------------------

def _int_weights(parts: dict[str, float]) -> dict[str, int]:
    """Poids entiers dont la somme vaut 255 (le reste de l'arrondi va au biome le plus lourd)."""
    total = sum(parts.values())
    out = {b: int(round(255 * w / total)) for b, w in parts.items()}
    top = max(out, key=lambda b: (out[b], b))
    out[top] += 255 - sum(out.values())
    return out


def biome_tile(plan: Plan, size: float, ix: int, iz: int) -> dict:
    import numpy as np
    k = np.arange(GRID) * size / (GRID - 1)
    x, z = np.meshgrid(ix * size + k, iz * size + k)           # ligne j, colonne i
    points = [_int_weights(plan.weights(float(s))) for s in plan.s_of_world(x, z).ravel()]
    used = [b for b in plan.biomes if any(p.get(b, 0) > 0 for p in points)]
    used = list(dict.fromkeys(used))
    if len(used) > 4:
        raise ValueError(f"tuile {ix}_{iz} : {len(used)} biomes (4 au plus)")
    return {"version": "1.0", "biomes": used, "grid": GRID,
            "weights": [[p.get(b, 0) for p in points] for b in used],
            "variant": LOOPS[plan.loop].get("variant") if plan.loop else tile_variant(plan, size, ix, iz)}


def tile_variant(plan: Plan, size: float, ix: int, iz: int) -> dict | None:
    """Variante régionale d'une tuile (lot DB1) : celle du bloc qui couvre le plus de points de la tuile (à
    égalité, le premier sur la route). Les tuiles proches de 1 km tombent chacune dans un seul bloc de 2 km."""
    if not any(plan.variants):
        return None
    import numpy as np
    k = np.arange(GRID) * size / (GRID - 1)
    x, z = np.meshgrid(ix * size + k, iz * size + k)
    counts: dict[int, int] = {}
    for s in plan.s_of_world(x, z).ravel():
        b = plan.block(float(s))
        counts[b] = counts.get(b, 0) + 1
    best = min(counts, key=lambda b: (-counts[b], b))
    variant = plan.variants[best]
    return dict(variant) if variant else None


def write_biome_layer(world: Path, plan: Plan, manifest: dict, route: dict) -> dict[str, float]:
    tiles = manifest["layers"]["terrain"]["tiles"]
    for level, size in (("near", NEAR_T), ("far", FAR_T)):
        folder = world / "biome" / level
        folder.mkdir(parents=True, exist_ok=True)
        for ix, iz in tiles[level]:
            data = biome_tile(plan, size, ix, iz)
            (folder / f"tile_{ix}_{iz}.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    shares: dict[str, float] = {}
    for s in plan.s_of_world(route["x"], route["z"]):
        for b, w in _int_weights(plan.weights(float(s))).items():
            shares[b] = shares.get(b, 0.0) + w / 255.0
    shares = {b: round(100.0 * v / route["n"], 1) for b, v in shares.items() if v > 0}
    forced = plan.biomes[0] if len(set(plan.biomes)) == 1 else None
    manifest["layers"]["biome"] = {"present": True, "version": "1.0",
                                   "default_biome": forced or DEFAULT_BIOME, "forced": None,
                                   "sources": ["synthetic"], "shares": shares,
                                   "tiles": {"near": tiles["near"], "far": tiles["far"]}}
    return shares


def write_surface(plan: Plan, manifest: dict, route: dict) -> dict[str, float]:
    # Abscisse de la trace fabriquée : la route compilée la suit, `s_of` suffit à 1 % près.
    route["surface"] = [plan.surface(float(s)) for s in plan.s_of_world(route["x"], route["z"])]
    pct: dict[str, float] = {}
    for v in route["surface"]:
        pct[v] = pct.get(v, 0.0) + 1.0
    pct = {k: round(100.0 * v / route["n"], 1) for k, v in sorted(pct.items())}
    manifest["route"]["surface_source"] = "osm"
    if isinstance(manifest.get("stats"), dict):
        manifest["stats"]["surface_pct"] = pct
    return pct


def write_sea(world: Path, plan: Plan, manifest: dict, route: dict) -> dict[str, int]:
    """Couche côte et aires `sea` le long du biome `coast` (tronçons de 1 km de la route)."""
    from openride_compiler.constants import CHUNK_LENGTH_M
    coast_s = [i * BLOCK_M for i, b in enumerate(plan.biomes) if b == "coast"]
    chunks: dict[int, dict] = {}
    water_dir = world / "water"
    water_dir.mkdir(exist_ok=True)
    areas_added = 0

    def side_pt(s: float, d: float) -> list[float]:
        px, pz = plan.road.point(s, SEA_SIDE * d)
        return [round(px - plan.offset[0], 2), round(pz - plan.offset[1], 2)]

    for b0 in coast_s:
        for k in range(int(b0 // CHUNK_LENGTH_M), int((b0 + BLOCK_M) // CHUNK_LENGTH_M)):
            c0, c1 = k * CHUNK_LENGTH_M, (k + 1) * CHUNK_LENGTH_M
            if k == 0:
                c0 = 0.0
            sandy = k % 2 == 0
            # Côte parcourue du nord au sud (z croissant) : la mer, à l'ouest, est à droite du sens des points.
            line = [side_pt(s, BEACH_M[1]) for s in _frange(c1, c0, -25.0)]
            entry = chunks.setdefault(k, {"version": "1.0", "lines": [], "beaches": []})
            entry["lines"].append({"id": f"c{k}", "shore": "sand" if sandy else "rock", "points": line})
            if sandy:
                inner = [side_pt(s, BEACH_M[0]) for s in _frange(c0 + 50.0, c1 - 50.0, 25.0)]
                outer = [side_pt(s, BEACH_M[1]) for s in _frange(c1 - 50.0, c0 + 50.0, -25.0)]
                entry["beaches"].append({"id": f"b{k}", "kind": "sand", "outer": _ccw(inner + outer), "holes": []})
            water_file = water_dir / f"chunk_{k}.json"
            water = json.loads(water_file.read_text(encoding="utf-8")) if water_file.is_file() \
                else {"version": "1.0", "lines": [], "areas": []}
            for a0 in [c0 + 250.0 * m for m in range(int(math.ceil((c1 - c0) / 250.0)))]:
                a1 = min(a0 + 250.0, c1)
                near = [side_pt(s, SEA_BAND_M[0]) for s in _frange(a0, a1, 25.0)]
                far = [side_pt(s, SEA_BAND_M[1]) for s in _frange(a1, a0, -25.0)]
                water["areas"].append({"id": f"s{k}_{int(a0 - c0)}", "kind": "sea", "level_y": 0.0,
                                       "outer": _ccw(near + far), "holes": []})
                areas_added += 1
            water_file.write_text(json.dumps(water, separators=(",", ":")), encoding="utf-8")
    folder = world / "coast"
    folder.mkdir(exist_ok=True)
    for k, data in sorted(chunks.items()):
        (folder / f"chunk_{k}.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    lines = sum(len(c["lines"]) for c in chunks.values())
    beaches = sum(len(c["beaches"]) for c in chunks.values())
    manifest["layers"]["coast"] = {"present": True, "version": "1.0", "lines_count": lines,
                                   "beaches_count": beaches, "osm_date": OSM_DATE}
    w = manifest["layers"]["water"]
    w["present"] = True
    w["areas_count"] = int(w.get("areas_count", 0)) + areas_added
    w.setdefault("version", "1.0")
    w.setdefault("lines_count", 0)
    return {"lines": lines, "beaches": beaches, "sea_areas": areas_added}


def _ccw(ring: list[list[float]]) -> list[list[float]]:
    """Anneau extérieur dans le sens antihoraire du format (aire signée positive, comme `verify`)."""
    from openride_compiler.osm_layers import signed_area
    return ring if signed_area(ring) > 0 else ring[::-1]


def _frange(a: float, b: float, step: float) -> list[float]:
    """De `a` à `b` inclus par pas de `step` (positif ou négatif)."""
    n = max(1, int(round(abs(b - a) / abs(step))))
    return [a + (b - a) * k / n for k in range(n + 1)]


# --- Génération ------------------------------------------------------------------------------------------

@contextlib.contextmanager
def _offline_compiler(payload: bytes, terrain, cache: Path):
    """Compilateur sans réseau : réponse Overpass et relief fabriqués ; tout est rétabli à la sortie."""
    import urllib.request

    from . import cli
    from .elevation import SyntheticProvider
    saved = (socket.socket.connect, socket.create_connection, urllib.request.urlopen, cli.make_provider,
             {k: os.environ.get(k) for k in ("OPENRIDE_DEM_CACHE", "OPENRIDE_OSM_CACHE")})
    os.environ["OPENRIDE_DEM_CACHE"] = str(cache / "dem-cache")
    os.environ["OPENRIDE_OSM_CACHE"] = str(cache / "osm-cache")
    socket.socket.connect = sim.no_network              # type: ignore[method-assign]
    socket.create_connection = sim.no_network           # type: ignore[assignment]
    urllib.request.urlopen = lambda *_a, **_k: io.BytesIO(payload)   # type: ignore[assignment]
    cli.make_provider = lambda offline, log=None: SyntheticProvider(*ORIGIN, terrain)   # type: ignore[assignment]
    try:
        yield cli
    finally:
        socket.socket.connect, socket.create_connection, urllib.request.urlopen, cli.make_provider = saved[:4]
        for k, v in saved[4].items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def generate(out: Path, name: str, biomes: tuple[str, ...], gravel: bool = False, sea: bool = False,
             seed: int = 0, title: str | None = None, recette: bool = False, circuit: bool = False,
             loop: str | None = None, variants: tuple[dict | None, ...] | None = None) -> dict:
    """Écrit `out/<name>.world` et `out/<name>.json` ; renvoie le résumé (parts des biomes et des surfaces).
    `title` : nom affiché au menu (`name` du manifeste) ; sans lui ou avec `recette`, l'identifiant `name`.
    `circuit` : la boucle du circuit de démonstration (lot O38) au lieu de la route ouverte, un seul biome ;
    `loop` : une boucle de `LOOPS` (`recif` : le récif du lot SM1, seul à employer le biome `reef`) ;
    `variants` : variante régionale de chaque bloc (lot DB1, voir `PAYSAGES`)."""
    plan = Plan(biomes, gravel, sea, recette, circuit, loop, variants)
    if plan.loop in LOOP_BLOCKS:
        unknown = [b for b in biomes if b != LOOPS[plan.loop]["biome"]]
    else:
        unknown = [plan.decor(i) for i in range(len(biomes)) if plan.decor(i) not in BLOCKS or biomes[i] not in GRADE]
    if unknown:
        raise ValueError(f"biome sans décor de démonstration : {', '.join(unknown)} (premier jalon : "
                         f"{', '.join(TOUR)} ; nouveaux paysages : --paysages ; --sud, --nord)")
    out.mkdir(parents=True, exist_ok=True)
    frame = Frame()
    op = build_overpass(frame, plan, seed)
    payload = json.dumps({"version": 0.6, "generator": "OpenRide demo_biomes",
                          "osm3s": {"timestamp_osm_base": OSM_DATE}, "elements": op.elements}).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="openride_demo_biomes_") as tmp:
        work = Path(tmp)
        gpx = work / f"{name}.gpx"
        write_gpx(gpx, frame, plan, name)
        with _offline_compiler(payload, make_terrain(plan), work) as cli:
            log = io.StringIO()
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                rc = cli.main(["build", str(gpx), "--out", str(work), "--force",
                               "--layers", "route,terrain," + ",".join(LAYERS)])
        built = work / f"{name}.world"
        if rc != 0 or not built.is_dir():
            raise RuntimeError(f"compilation impossible (code {rc}) : {log.getvalue()[-400:]}")
        world = out / f"{name}.world"
        if world.exists():
            shutil.rmtree(world)
        shutil.move(str(built), str(world))
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    shares = write_biome_layer(world, plan, manifest, route)
    surface = write_surface(plan, manifest, route) if gravel else None
    coast = write_sea(world, plan, manifest, route) if plan.sea else None
    manifest["format_version"] = FORMAT_VERSION
    manifest["created"] = CREATED
    manifest["name"] = name if recette or not title else title
    manifest["compiler"] = {"name": GENERATOR, "version": manifest["compiler"]["version"]}
    if library_of(name):
        manifest["library"] = library_of(name)
    (world / "route.json").write_text(json.dumps(route, separators=(",", ":")), encoding="utf-8")
    (world / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    info = {"route": name, "name": manifest["name"], "length_m": route["length_m"], "type": route["type"],
            "biomes": list(biomes), "shares": shares,
            "surface_pct": surface, "coast": coast, "generated": op.counts,
            "layers": sorted(k for k, v in manifest["layers"].items() if isinstance(v, dict) and v.get("present"))}
    (out / f"{name}.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return info


def paysages_variants() -> tuple[dict | None, ...]:
    """Variante régionale de chaque bloc du tour des nouveaux paysages (lot DB1)."""
    return tour_blocks("paysages")[1]


def biome_variants(biomes: tuple[str, ...]) -> tuple[dict | None, ...] | None:
    """Variante régionale de chaque bloc d'un parcours de biomes (lot DJ1, `BIOME_VARIANTS`) ; None sans aucune."""
    out = tuple(dict(BIOME_VARIANTS[b]) if b in BIOME_VARIANTS else None for b in biomes)
    return out if any(out) else None


def write_demo_set(out: Path, seed: int = 0, recette: bool = False) -> list[dict]:
    """Parcours de `openride-core demo-biomes` : tour des nouveaux paysages, route des Érables, circuit, récif, volcan,
    Route du Sud et Route du Grand Nord (jeu de base, lots O38, SM1, DB1, DB2, DJ1 et DB3) ; `recette` : variante des bancs et des recettes (noms techniques), avec en plus les
    parcours sortis du jeu de base (tour des six paysages, côte avec la mer, alpin, tour gravel)."""
    infos = []
    for name, title, which, gravel, sea, base in DEMO_SET:
        if not (base or recette):
            continue
        loop = which if which in LOOPS else None
        biomes, variants = tour_blocks(which)
        infos.append(generate(out, name, biomes, gravel=gravel, sea=sea, seed=seed, title=title, recette=recette,
                              loop=loop, variants=variants))
    return infos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path, help="dossier de sortie (créé si besoin)")
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--biome", choices=TOUR + ("japan",), help="un seul biome sur 6 km")
    what.add_argument("--tour", action="store_true", help="les six biomes du premier jalon, 2 km chacun")
    what.add_argument("--circuit", action="store_true", help="la boucle de 3 km du circuit de démonstration (prairie)")
    what.add_argument("--paysages", action="store_true",
                      help="le tour des nouveaux paysages (lot DB1) : sept blocs de 2 km, mer le long du fjord")
    what.add_argument("--recif", action="store_true", help="la boucle de 8 km du récif sous la mer (fond marin)")
    what.add_argument("--volcan", action="store_true",
                      help="la boucle de 8 km du volcan en flammes (paysage volcan_actif, crête du cratère à mi-boucle)")
    what.add_argument("--sud", action="store_true",
                      help="la Route du Sud (lot DB3) : six blocs de 2 km, du méditerranéen aux zones humides")
    what.add_argument("--nord", action="store_true",
                      help="la Route du Grand Nord (lot DB3) : boucle de 10 km, taïga, toundra et banquise")
    what.add_argument("--forets", action="store_true",
                      help="la Route des Trois Forêts (lot V6-r4) : bush à eucalyptus, forêt pluviale, forêt de nuages")
    what.add_argument("--demo-set", action="store_true", help="les parcours de demo-biomes (le tour gravel en plus avec --recette)")
    parser.add_argument("--gravel", action="store_true", help="un tiers de la route en gravel ou dirt")
    parser.add_argument("--sea", action="store_true", help="côte inventée et mer le long du biome coast")
    parser.add_argument("--name", help="identifiant du parcours (défaut : biomes-tour ou biomes-<ID>)")
    parser.add_argument("--title", help="nom affiché au menu (défaut : l'identifiant ; ignoré avec --demo-set)")
    parser.add_argument("--recette", action="store_true",
                        help="variante des bancs et des recettes : noms techniques, jamais dans le jeu de base")
    parser.add_argument("--seed", type=int, default=0, help="graine du placement des bâtiments (défaut 0)")
    args = parser.parse_args(argv)
    try:
        if args.demo_set:
            infos = write_demo_set(args.out, args.seed, args.recette)
        else:
            which = ("tour" if args.tour else "circuit" if args.circuit else "recif" if args.recif
                     else "volcan" if args.volcan else "paysages" if args.paysages else "sud" if args.sud
                     else "nord" if args.nord else "forets" if args.forets else args.biome)
            loop = which if which in LOOPS else None
            biomes, variants = tour_blocks(which)
            name = args.name or ("biomes-tour" if args.tour else which if which in ("circuit", "recif", "volcan")
                                 else f"biomes-{which}")
            infos = [generate(args.out, name, biomes, gravel=args.gravel, sea=args.sea or args.paysages,
                              seed=args.seed, title=args.title, recette=args.recette, loop=loop,
                              variants=variants)]
    except (RuntimeError, ValueError) as exc:
        print(f"demo_biomes : {exc}", file=sys.stderr)
        return 1
    for info in infos:
        shares = ", ".join(f"{b} {v:.1f} %" for b, v in info["shares"].items())
        extra = f" ; surfaces {info['surface_pct']}" if info["surface_pct"] else ""
        print(f"demo_biomes : {args.out / (info['route'] + '.world')} ({shares}{extra})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
