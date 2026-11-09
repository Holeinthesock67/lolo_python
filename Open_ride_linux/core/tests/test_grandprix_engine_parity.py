"""Lot GP8 : noms, familles et charges des objets du Grand Prix identiques dans le core et dans l'engine.

L'engine (`engine/scripts/grandprix/gp_items.gd`) recopie la liste des objets, leurs noms et leurs familles
pour la case d'objet, la bande de course et le bilan ; le core en est la référence (`grandprix/items.py`).
"""

import re
from pathlib import Path

from openride_core.grandprix import items

GD = Path(__file__).resolve().parents[2] / "engine" / "scripts" / "grandprix" / "gp_items.gd"


def _const(name: str) -> str:
    text = GD.read_text(encoding="utf-8")
    m = re.search(rf"^const {name} := [\[{{](.*?)[\]}}]\n", text, re.S | re.M)
    assert m, name
    return m.group(1)


def _pairs(body: str) -> dict[str, str]:
    return dict(re.findall(r'"(\w+)": "([^"]*)"', body))


def test_ids_labels_families_match_core():
    assert re.findall(r'"(\w+)"', _const("IDS")) == list(items.ITEM_IDS)
    assert _pairs(_const("LABELS")) == items.LABELS
    assert _pairs(_const("FAMILIES")) == items.FAMILIES


def test_charges_match_core():
    charges = {k: int(v) for k, v in re.findall(r'"(\w+)": (\d+)', _const("CHARGES"))}
    assert charges == {i: s.charges for i, s in items.DEFAULT_TABLE.items.items() if s.charges > 1}
