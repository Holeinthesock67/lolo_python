"""Course des bots en temps accéléré (lot X27) : vraie séance au pas de 20 ms, sans trainer ni engine."""

import json

import pytest

from openride_core.tools import bots_race as br


@pytest.fixture
def short_routes(monkeypatch):
    # Parcours courts pour la suite : 1,5 km de plat, et 0,5 km de plat puis 1 km à 6 %.
    monkeypatch.setitem(br.SYNTHETIC, "plat", (1500.0, lambda s: 0.0))
    monkeypatch.setitem(br.SYNTHETIC, "col", (1500.0, lambda s: 0.0 if s < 500.0 else 6.0))


@pytest.mark.parametrize("route", ["plat", "col"])
def test_bots_at_the_rider_level_finish_with_the_rider(short_routes, route):
    out = br.race(route, 85.0, ["climber", "rouleur", "sprinter", "diesel"])
    assert out["rider_finish_s"] is not None
    assert [r["profile"] for r in out["bots"]] == ["climber", "rouleur", "sprinter", "diesel"]
    for r in out["bots"]:
        assert r["finish_s"] is not None and abs(r["gap_pct"]) <= br.GAP_LIMIT_PCT, r
    assert all(c["ok"] for c in out["checks"]) and len(out["checks"]) == 5
    assert 0 < out["state_max_bytes"] <= 4096


def test_stronger_bots_finish_ahead_and_are_not_judged(short_routes):
    out = br.race("col", 80.0, ["rouleur", "climber"], level_pct=110.0)
    assert all(r["gap_pct"] < -5.0 for r in out["bots"])
    assert len(out["checks"]) == 1 and out["checks"][0]["text"].startswith("trame state la plus grande")
    climber = next(r for r in out["bots"] if r["profile"] == "climber")
    assert climber["wbal_min_pct"] < 100.0   # le grimpeur attaque la montée sur sa réserve


def test_two_bots_of_the_same_profile_are_numbered(short_routes):
    out = br.race("plat", 85.0, ["rouleur", "rouleur"])
    assert [r["name"] for r in out["bots"]] == ["Rouleur", "Rouleur 2"]


def test_command_line_codes_and_json(short_routes, capsys):
    assert br.main(["--route", "plat", "--bots", "rouleur", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["bots"][0]["profile"] == "rouleur" and out["route"] == "plat"
    assert br.main(["--route", "plat", "--bots", "rouleur,velo"]) == 2
    assert "profil(s) de bot inconnu(s) : velo" in capsys.readouterr().err
    assert br.main(["--route", "/nulle/part.world", "--bots", "rouleur"]) == 2
    assert br.main(["--bots", ""]) == 2


def test_text_table(short_routes):
    text = br.format_text(br.race("plat", 85.0, ["diesel"]))
    assert "Course des bots sur plat (1.5 km)" in text and "Diesel" in text and "[OK] Diesel au niveau du cycliste" in text
