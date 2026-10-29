"""Lot X31 : pente maximale, D+ et longueur d'un parcours face aux valeurs de Garmin Connect (recette 1.0 ligne 22)."""

from __future__ import annotations

import json

from conftest import straight_north
from openride_compiler import cli
from openride_compiler.route_stats import compare_garmin


def ramp_route(grade_pct=8.0, ramp_m=500.0, flat_m=500.0, ds=5.0):
    """Plat, rampe de `grade_pct` sur `ramp_m`, plat : colonnes de route.json."""
    length = 2 * flat_m + ramp_m
    n = int(length / ds) + 1
    alt = []
    for i in range(n):
        s = i * ds
        alt.append(300.0 + grade_pct / 100.0 * min(max(s - flat_m, 0.0), ramp_m))
    return {"n": n, "ds_m": ds, "length_m": length, "alt_m": alt}


def test_ramp_of_8_percent():
    rows = {r["mesure"]: r for r in compare_garmin(ramp_route(), 8.0, 40.0, 1.5)}
    grade = rows["pente maximale sur 100 m (%)"]
    assert abs(grade["parcours"] - 8.0) <= 0.1 and grade["ok"]
    assert rows["dénivelé positif (m)"]["parcours"] == 40 and rows["dénivelé positif (m)"]["ok"]
    assert rows["longueur (km)"]["parcours"] == 1.5 and rows["longueur (km)"]["ok"]


def test_two_points_off_fails():
    rows = compare_garmin(ramp_route(), 10.0, 40.0)
    assert [r["ok"] for r in rows] == [False, True]
    assert rows[0]["ecart"] == -2.0
    assert len(rows) == 2                       # sans --longueur, pas de ligne de longueur


def test_tolerances_of_gain_and_length():
    route = ramp_route()
    assert compare_garmin(route, 8.0, 41.5)[1]["ok"]          # 39,6 m (hystérésis de 1 m) pour 41,5 : 4,6 %
    assert not compare_garmin(route, 8.0, 43.0)[1]["ok"]      # 7 %
    assert not compare_garmin(route, 8.0, 40.0, 1.52)[2]["ok"]


def test_window_changes_the_measure():
    # Rampe de 50 m à 8 % : sur 100 m, la pente vue n'est que de 4 %, sur 50 m, de 8 %.
    route = ramp_route(ramp_m=50.0)
    assert compare_garmin(route, 4.0, 4.0)[0]["parcours"] == 4.0
    assert compare_garmin(route, 8.0, 4.0, window=50.0)[0]["parcours"] == 8.0


def test_cli(make_gpx, tmp_path, capsys):
    gpx = make_gpx("Col d'Essai.gpx", *straight_north())       # 2 km à 5 %
    out = tmp_path / "routes"
    assert cli.main(["build", str(gpx), "--out", str(out)]) == 0
    world = out / "col-d-essai.world"
    capsys.readouterr()
    assert cli.main(["compare-garmin", str(world), "--pente-max", "5", "--dplus", "100", "--longueur", "2"]) == 0
    text = capsys.readouterr().out
    assert "[OK] pente maximale sur 100 m (%) : parcours 5.0" in text and text.rstrip().endswith("conforme")
    assert cli.main(["compare-garmin", str(world), "--pente-max", "7", "--dplus", "100", "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False and [m["ok"] for m in data["mesures"]] == [False, True]
    assert not any(p.suffix in (".json", ".txt") for p in tmp_path.iterdir())   # rien d'écrit
    assert cli.main(["compare-garmin", str(tmp_path / "absent.world"), "--pente-max", "5", "--dplus", "1"]) == 1
