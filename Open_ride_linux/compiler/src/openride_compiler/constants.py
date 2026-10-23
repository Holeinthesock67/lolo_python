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

FORMAT_VERSION = "1.0"
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
