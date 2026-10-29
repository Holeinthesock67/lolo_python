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

# Profils du fuzz des fichiers (lot X26) : 200 exemples par lecteur, `--hypothesis-profile=long` (5 000)
# sur le PC ; pas de délai par exemple (la limite de 2 s est vérifiée dans les tests).
# Le dossier de travail d'hypothesis va dans un dossier temporaire : rien n'est écrit dans le dépôt
# (garde-fou d'isolation), et pas de base d'exemples gardée d'un passage à l'autre.
try:
    import tempfile as _tempfile

    from hypothesis import settings as _hyp_settings
    from hypothesis.configuration import set_hypothesis_home_dir as _hyp_home

    _hyp_home(_tempfile.mkdtemp(prefix="openride-hypothesis-"))
    _hyp_settings.register_profile("default", max_examples=200, deadline=None, database=None)
    _hyp_settings.register_profile("long", max_examples=5000, deadline=None, database=None)
    _hyp_settings.load_profile("default")
except ImportError:   # extra dev absent : les tests test_fuzz_* sont sautés (importorskip)
    pass
