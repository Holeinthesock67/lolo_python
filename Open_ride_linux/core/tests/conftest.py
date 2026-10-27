"""Isolation de la suite : HOME temporaire, pas de fenêtre, garde-fou d'écriture, une suite à la fois.

Doit rester le premier code exécuté : les chemins `~/OpenRide/...` d'openride_core sont calculés
à l'import (`scripts/isolation_tests.py`).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from isolation_tests import brancher_pytest  # noqa: E402

globals().update(brancher_pytest())

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def records_and_powerups_in_tmp(tmp_path, monkeypatch):
    """Série T : `records.json` et `powerups.toml` de la séance dans le dossier temporaire du test."""
    from openride_core import powerups, records
    monkeypatch.setattr(records, "RECORDS_FILE", tmp_path / "OpenRide" / "records.json")
    monkeypatch.setattr(powerups, "POWERUPS_FILE", tmp_path / "OpenRide" / "powerups.toml")
