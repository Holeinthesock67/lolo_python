"""Lot TT8 : banc d'équilibrage des bonus (`tools/bonus_bench.py`)."""

from __future__ import annotations

import json

from openride_core.powerups import DEFAULT_TABLE
from openride_core.tools import bonus_bench as bb


def test_report_is_replayable_and_complete():
    a, b = bb.bench(DEFAULT_TABLE, passes=4, seed=3), bb.bench(DEFAULT_TABLE, passes=4, seed=3)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert set(a["gains"]) == set(bb.KINDS) == set(DEFAULT_TABLE.specs)
    assert all(sum(r.values()) == 4 for r in a["refusals"].values())
    assert sum(a["draws"].values()) == 4


def test_all_bonuses_in_their_target():
    """Valeurs du rapport TT8 pour les bonus tactiques (1,5 à 2,5 s) ; lot TT-BONUS pour la Plume, le Casque et
    la Puissance (× 0,8, × 0,6 et × 1,20 pendant 30 s : 3,5 à 7 s, au-dessus du bruit du trainer)."""
    report = bb.bench(DEFAULT_TABLE, passes=12, seed=8)
    assert bb.verdict(report) == []
    for kind in ("anvil", "draft_plus", "breakaway", "roller"):
        assert 1.5 <= report["gains"][kind]["median_s"] <= 2.5, kind
    for kind in ("feather", "aero", "power"):
        assert 3.5 <= report["gains"][kind]["median_s"] <= 7.0, kind


def test_almost_nothing_outside_the_ideal_terrain():
    report = bb.bench(DEFAULT_TABLE, passes=6, seed=8)
    for kind in ("anvil", "draft_plus", "breakaway", "roller"):
        assert report["gains"][kind]["elsewhere_median_s"] <= 0.1, kind


def test_refusal_reasons_follow_the_table():
    reasons = bb.refusals(DEFAULT_TABLE, passes=40, seed=8)
    assert set(reasons["feather"]) <= {"accepté", "erg"}
    assert set(reasons["anvil"]) <= {"accepté", "erg", "no_descent"}
    assert set(reasons["breakaway"]) <= {"accepté", "erg", "no_bots", "near_finish"}
    assert set(reasons["roller"]) <= {"accepté", "erg", "no_gravel"}


def test_values_file_is_tried(tmp_path, capsys):
    f = tmp_path / "powerups.toml"
    f.write_text("[aero]\nduration_s = 20\n[power]\nduration_s = 18\n", encoding="utf-8")   # valeurs du fichier
    bb.main(["--passages", "6", "--values", str(f), "--json"])
    gains = json.loads(capsys.readouterr().out)["gains"]
    assert (gains["aero"]["duration_s"], gains["power"]["duration_s"]) == (20.0, 18.0)
    assert gains["aero"]["median_s"] >= 1.5 and gains["power"]["median_s"] >= 1.5
