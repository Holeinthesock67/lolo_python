"""Mode « Grand Prix des objets » (série GP, 4.0 proposée) : règles pures du core (lot GP1).

Plan : `docs/4.0/PLAN_SERIE_GP.md` ; cahier : `docs/lots/LOT_GP1_objets_core.md`.
"""

from .items import DEFAULT_TABLE, ITEM_IDS, LABELS, GrandPrixError, ItemTable, load_table
from .mode import ME, GpInput, GrandPrixMode, RiderIn, lane_index

__all__ = ["DEFAULT_TABLE", "ITEM_IDS", "LABELS", "GrandPrixError", "ItemTable", "load_table", "ME", "GpInput",
           "GrandPrixMode", "RiderIn", "lane_index"]
