"""Isolation de la suite : HOME temporaire, pas de fenêtre, garde-fou d'écriture, une suite à la fois.

Doit rester le premier code exécuté : les chemins `~/OpenRide/...` d'openride_core sont calculés
à l'import (`scripts/isolation_tests.py`).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from isolation_tests import brancher_pytest  # noqa: E402

globals().update(brancher_pytest())
