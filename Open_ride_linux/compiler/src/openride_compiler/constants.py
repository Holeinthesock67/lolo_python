"""Constantes du Format .world v1 utilisées par le compilateur.

Certaines sont recopiées du paquet openride-core (le compilateur n'en dépend pas) ;
`tests/test_constants.py` garde les deux copies identiques.
"""

from __future__ import annotations

from pathlib import Path

# Recopiées d'openride-core (route.py, demo_world.py, config.py).
FORMAT_NAME = "openride-world"
DS_M = 10.0
ROUTE_FIELDS = ("lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg")
SURFACES = ("paved", "compacted", "gravel", "dirt", "wood")   # colonne facultative surface (1.6, lot U20 ; wood : 1.7, lot VD1)
ROUTES_DIR = Path.home() / ".local" / "share" / "openride" / "routes"

FORMAT_VERSION = "1.8"   # 1.8 : niveau de terrain horizon (lot JP4) ; 1.6 : colonne surface de la route (lot U20) ; 1.5 : prés, champs et routes voisines (lot P22) ; 1.4 : monde vivant (W1)
SUPPORTED_MAJOR = 1
ROUTE_VERSION = "1.0"
COMPILER_NAME = "openride-compiler"

# Paramètres de la chaîne de traitement (lot B1 §3.2, format §4).
MIN_STEP_M = 1.0             # points plus proches que cela du dernier point gardé : supprimés
MIN_LENGTH_M = 500.0         # trace plus courte : refusée
LOOP_GAP_M = 50.0            # fin à moins de cela du départ : boucle
SAVGOL_WINDOW = 11
SAVGOL_ORDER = 2
GRADE_LIMIT_PCT = 25.0
HEADING_SMOOTH_POINTS = 3    # moyenne circulaire glissante, environ 30 m
LENGTH_EPS_M = 1e-3          # reste de length_m / ds_m en dessous duquel il n'y a pas de point en plus

# Altitude de la route et MNT (lot B2 §3.3) : seuils à ajuster sur des traces réelles.
ALT_OUTLIER_M = 50.0         # écart GPX / MNT au-delà duquel un point est jugé aberrant
ALT_OUTLIER_FRACTION = 0.05  # part de points aberrants au-delà de laquelle on prend le MNT

# Couche terrain (format §5, lot B2 §3.4).
TERRAIN_VERSION = "1.0"
TILE_SAMPLES = 101
NEAR_CELL_M = 10
NEAR_TILE_M = 1000
NEAR_BAND_M = 400.0
FAR_CELL_M = 50
FAR_TILE_M = 5000
FAR_BAND_M = 5000.0
# Niveau « horizon » (lot JP4, version 6.0) : relief lointain très grossier pour voir les grands sommets au-delà
# du brouillard (le mont Fuji depuis Hakone, à 25–30 km). Altitudes abaissées de la courbure terrestre vue depuis
# la route (rayon apparent 7/6 du rayon terrestre, réfraction comprise).
HORIZON_CELL_M = 500
HORIZON_TILE_M = 50000
HORIZON_BAND_M = 40000.0
EARTH_RADIUS_M = 6371000.0
REFRACTION_FACTOR = 7.0 / 6.0
ROAD_HALF_WIDTH_M = 3.0
BLEND_INNER_M = 4.0          # en deçà (depuis le bord du ruban) : altitude de la route − 5 cm
BLEND_OUTER_M = 25.0         # au-delà : MNT seul
ROAD_SINK_M = 0.05

# Couches OpenStreetMap : bâtiments et végétation (format §6 et §7, lot I3).
BUILDINGS_VERSION = "1.0"
VEGETATION_VERSION = "1.0"
CHUNK_LENGTH_M = 1000.0
OSM_BAND_M = 400.0
DENSITY_WOOD = 0.8
DENSITY_SCRUB = 0.4
DENSITY_ORCHARD = 0.5
VEGETATION_WOODED_KINDS = ("wood", "scrub", "orchard")
# Format 1.5 (lot P22) : terrains ouverts, sans arbres (densité 0), pour les animaux et les tracteurs.
DENSITY_OPEN = 0.0
VEGETATION_OPEN_KINDS = ("meadow", "farmland", "grassland")

# Couche routes voisines (format §8 ter, lot P22) : routes OSM du couloir, hors route du parcours.
ROADS_VERSION = "1.0"
ROAD_KINDS = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "track")
ROAD_ROUTE_GAP_M = 20.0        # points plus proches de l'axe du parcours : la route du parcours elle-même
ROAD_PARALLEL_M = 35.0         # pièce dont tous les points sont à moins de cette distance : doublon du parcours
ROAD_DEFAULT_LANES = {"motorway": 4, "trunk": 4, "track": 1}
ROAD_DEFAULT_LANES_OTHER = 2
ROAD_DEFAULT_SPEED_KMH = {"motorway": 130, "trunk": 110, "primary": 80, "secondary": 80, "tertiary": 80,
                          "unclassified": 50, "residential": 30, "track": 20}

# Couches OpenStreetMap : points d'intérêt et eau (format §8, lot I4).
POI_VERSION = "1.0"
WATER_VERSION = "1.0"
POI_KINDS = ("church_bell", "river", "livestock", "village", "viewpoint", "wind_turbine", "flag")   # 1.2 : P12
POI_RADIUS_CHURCH_BELL_M = 300
POI_RADIUS_VILLAGE_M = 300
POI_RADIUS_VIEWPOINT_M = 200
POI_RADIUS_LIVESTOCK_M = 150
POI_RADIUS_RIVER_M = 150
POI_RADIUS_WIND_TURBINE_M = 5000   # portée de vue d'une éolienne (Lot P12)
POI_RADIUS_FLAG_M = 150
WIND_TURBINE_DEFAULT_HEIGHT_M = 100.0
POI_RIVER_PASSAGE_DIST_M = 50.0
WATER_LINE_KINDS = ("river", "stream", "canal")
WATER_AREA_KINDS = ("lake", "pond", "reservoir", "sea")   # 1.6 : sea (lot U1)
WATER_WIDTH_DEFAULT_M = 2.0
WATER_WIDTH_RIVER_M = 6.0
WATER_WIDTH_STREAM_M = 2.0
WATER_WIDTH_CANAL_M = 8.0

# Côte, mer et plages (format §8 et §8 quinquies, lot U3).
COAST_VERSION = "1.0"
COAST_SHORES = ("sand", "shingle", "rock", "cliff")
COAST_BEACH_KINDS = ("sand", "shingle")
SEA_LEVEL_Y = 0.0                         # niveau de la mer (contrat §8 : `level_y` = 0)

# Lot EA1 : niveau des plans d'eau et sol abaissé dessous (`water_terrain.py`).
INLAND_WATER_KINDS = ("lake", "pond", "reservoir")   # la mer garde son niveau 0 (U3) et son sol
LAKE_SAMPLE_M = 30.0          # maille des échantillons du MNT dans un plan d'eau (pixel GLO-30), alignée sur le repère
LAKE_SHORE_CLEAR_M = 30.0     # échantillons gardés pour le niveau : à plus d'un pixel du MNT de toute rive
LAKE_SHORE_STEP_M = 10.0      # pas des échantillons de la rive
LAKE_SHORE_QUANTILE = 0.25    # plafond du niveau : quart le plus bas de la rive (un exutoire seul ne compte pas)
WATER_SINK_M = 1.0            # sol sous un plan d'eau : au plus 1 m sous la surface
COAST_CLIFF_DIST_M = 30.0                 # `natural=cliff` à moins de 30 m : rivage `cliff`
COAST_CLIFF_SLOPE_DEG = 45.0              # ou pente du MNT au-dessus de 45° côté terre
COAST_SLOPE_OFFSETS_M = (0.0, 10.0, 20.0, 30.0)   # points du MNT pris vers la terre pour la pente
COAST_BEACH_DIST_M = 30.0                 # plage à moins de 30 m : rivage `sand` ou `shingle`, plage qui touche la côte
COAST_SHINGLE_SURFACES = ("pebblestone", "shingle", "gravel")
COAST_SAMPLE_STEP_M = 5.0                 # pas des points de comparaison (plages, falaises)
COAST_LINE_STEP_M = 25.0                  # pas des points des lignes de côte écrites
