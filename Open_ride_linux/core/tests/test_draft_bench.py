"""Banc de l'abri derrière les bots (lot X50) : vraie séance au pas de 20 ms, sans vélo ni engine."""

import json

import pytest

from openride_core import draft as d
from openride_core.tools import draft_bench as db


@pytest.fixture(scope="module")
def out():
    return db.run(250.0, [230.0, 240.0, 250.0], 240.0, 180.0, gaps=(0.5, 3.0, 20.0))


def row(out, n, gap):
    return next(r for r in out["positions"] if r["bots"] == n and r["gap_m"] == gap)


def test_all_checks_pass(out):
    assert all(c["ok"] for c in out["checks"]), [c for c in out["checks"] if not c["ok"]]


def test_gain_in_the_wheel_matches_the_draft_curve(out):
    one = row(out, 1, 0.5)
    # 0,40·exp(−0,2/4) ≈ 0,38 ; l'aérodynamique fait ~85 % des 250 W sur le plat : environ 80 W de moins
    assert one["draft"] == pytest.approx(d.ALPHA_MAX * 2.718281828 ** (-0.2 / d.DECAY_M), abs=0.01)
    assert 70.0 < one["gain_w"] < 90.0
    assert row(out, 3, 0.5)["gain_w"] > row(out, 2, 0.5)["gain_w"] > one["gain_w"]
    assert row(out, 1, 3.0)["gain_w"] < one["gain_w"]


def test_no_gain_beyond_the_cutoff(out):
    for n in (1, 2, 3):
        r = row(out, n, 20.0)
        assert r["draft"] == 0.0 and abs(r["gain_w"]) < 0.5


def test_free_group_shelters_every_racer(out):
    rows = {r["name"]: r for r in out["group"]["rows"]}
    assert set(rows) == {"bot 230 W", "bot 240 W", "bot 250 W", "cycliste"}
    for r in rows.values():
        assert r["shelter_pct"] > 0.0 and 0.0 < r["draft_max"] <= d.ALPHA_CAP + 1e-9 and r["ahead_m"] > 0.0
    # le plus faible gagne le plus à rester dans le groupe
    assert rows["bot 230 W"]["gain_w"] > rows["bot 250 W"]["gain_w"]


def test_cli_json_and_invalid_arguments(capsys, monkeypatch):
    monkeypatch.setattr(db, "GAPS_M", (1.0, 20.0))
    monkeypatch.setattr(db, "HOLD_S", 40.0)
    monkeypatch.setattr(db, "MEASURE_S", 10.0)
    real = db.run
    monkeypatch.setattr(db, "run", lambda *a: real(*a, gaps=db.GAPS_M))
    code = db.main(["--duree", "60", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code in (0, 1) and len(data["positions"]) == 6 and len(data["group"]["rows"]) == 4
    assert db.main(["--groupe", "abc"]) == 2
    assert db.main(["--duree", "0"]) == 2
