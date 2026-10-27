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
ROUTES_DIR = Path.home() / ".local" / "share" / "openride" / "routes"

FORMAT_VERSION = "1.1"
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
WATER_AREA_KINDS = ("lake", "pond", "reservoir")
WATER_WIDTH_DEFAULT_M = 2.0
WATER_WIDTH_RIVER_M = 6.0
WATER_WIDTH_STREAM_M = 2.0
WATER_WIDTH_CANAL_M = 8.0
