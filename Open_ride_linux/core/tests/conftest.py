"""Configuration commune des tests du core.

Aucune fenêtre ni notification sur le bureau de la personne qui lance les tests : sans cela, les
faux échecs simulés (par exemple « Mise à jour refusée » de `scripts/update.sh`) s'affichaient
comme de vrais messages d'OpenRide.
"""

from __future__ import annotations

import os

os.environ["OPENRIDE_NO_GUI"] = "1"
for _var in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
    os.environ.pop(_var, None)
