"""Balade du monde ouvert enregistrée comme parcours (lot W14) : GPX de la route parcourue."""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from openride_core import __main__ as cli
from openride_core.config import Config
from openride_core.demo_world import build_route
from openride_core.live_route import LiveRoute
from openride_core.open_world_save import MIN_SAVE_M, gpx_text, journal_distance, ride_points, save_ride
from openride_core.route import Route
from test_live_route import split, write_session
from test_open_world_session import make_session, open_world, step, wait_until

NS = "{http://www.topografix.com/GPX/1/1}"


def read_gpx(path: Path):
    root = ET.parse(path).getroot()
    pts = [(float(p.get("lat")), float(p.get("lon")), float(p.find(NS + "ele").text)) for p in root.iter(NS + "trkpt")]
    return root.find(NS + "metadata").find(NS + "name").text, pts


def length_m(pts):
    total = 0.0
    for (la1, lo1, _), (la2, lo2, _) in zip(pts, pts[1:]):
        dy = (la2 - la1) * 111_320.0
        dx = (lo2 - lo1) * 111_320.0 * math.cos(math.radians((la1 + la2) / 2))
        total += math.hypot(dx, dy)
    return total


def test_points_every_10_m_up_to_the_ridden_distance():
    route = Route(build_route(3000.0))
    pts = ride_points(route, 1234.0)
    assert len(pts) == 125                 # 0, 10, … 1230 puis 1234
    assert length_m(pts) == pytest.approx(1234.0, rel=0.01)
    assert pts[0][2] == pytest.approx(route.sample(0.0).alt_m)
    assert ride_points(route, 99_999.0)[-1][:2] == pytest.approx((route.lat[-1], route.lon[-1]))   # borné à la route


def test_gpx_is_valid_and_has_the_ride_name(tmp_path):
    route = Route(build_route(2000.0))
    path = save_ride(route, 1500.0, "ow-20261027-120000", tmp_path / "GPX", ts=1_793_000_000.0)
    assert path == tmp_path / "GPX" / "ow-20261027-120000.gpx"
    name, pts = read_gpx(path)
    assert name.startswith("Balade du ") and len(pts) == 151


def test_short_ride_writes_nothing(tmp_path):
    route = Route(build_route(2000.0))
    assert save_ride(route, MIN_SAVE_M, "ow-x", tmp_path) is None       # 500 m : pas de GPX
    assert save_ride(route, 300.0, "ow-x", tmp_path) is None
    assert list(tmp_path.glob("*.gpx")) == []


def ride_and_end(tmp_path, monkeypatch, port, meters):
    s = make_session(tmp_path, monkeypatch, port, power=450.0)
    s.gpx_dir = tmp_path / "GPX"
    open_world(s)
    s._on_command("start", {}, 2)
    t0 = __import__("time").time()
    while s.physics.s < meters and __import__("time").time() - t0 < 120:
        step(s, 5.0)
    assert s.physics.s >= meters
    final = s.physics.s
    s._on_command("end_session", {"save": True}, 3)
    return s, final


def test_session_of_12_km_writes_the_ridden_route(tmp_path, monkeypatch):
    s, final = ride_and_end(tmp_path, monkeypatch, 7060, 12_000.0)
    files = list((tmp_path / "GPX").glob("ow-*.gpx"))
    assert len(files) == 1
    _, pts = read_gpx(files[0])
    assert length_m(pts) == pytest.approx(final, abs=20.0)           # 20 m près
    assert final >= 12_000.0 and files[0].stem == s.state.route_id[3:]


def test_session_under_500_m_writes_nothing(tmp_path, monkeypatch):
    ride_and_end(tmp_path, monkeypatch, 7062, 300.0)
    assert not (tmp_path / "GPX").exists() or list((tmp_path / "GPX").glob("*.gpx")) == []


def test_abandoned_session_writes_nothing(tmp_path, monkeypatch):
    s = make_session(tmp_path, monkeypatch, 7064, power=450.0)
    s.gpx_dir = tmp_path / "GPX"
    open_world(s)
    s._on_command("start", {}, 2)
    while s.physics.s < 800.0:
        step(s, 5.0)
    s._on_command("end_session", {"save": False}, 3)
    assert not (tmp_path / "GPX").exists() or list((tmp_path / "GPX").glob("*.gpx")) == []


def test_gpx_compiles_to_a_world_of_the_same_length(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    cli_mod = pytest.importorskip("openride_compiler.cli")
    from openride_compiler.elevation import SyntheticProvider
    s, final = ride_and_end(tmp_path, monkeypatch, 7066, 2_500.0)
    gpx = next((tmp_path / "GPX").glob("ow-*.gpx"))
    _, pts = read_gpx(gpx)
    monkeypatch.setattr(cli_mod, "make_provider", lambda offline, log=None: SyntheticProvider(pts[0][0], pts[0][1]))
    out = tmp_path / "world"
    assert cli_mod.main(["build", str(gpx), "--out", str(out), "--layers", "route", "--offline"]) == 0
    world = Route(__import__("json").loads(next(out.glob("*.world")).joinpath("route.json").read_text(encoding="utf-8")))
    assert world.length_m == pytest.approx(final, rel=0.01)


# --- après coup ------------------------------------------------------------------------------

def test_open_world_save_command_after_the_fact(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "cache" / "seances" / "ow-20261027-130000.world"
    write_session(folder, split(build_route(4000.0)))
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[open_world]\ncache_dir = "{tmp_path / "cache"}"\n', encoding="utf-8")
    gpx = tmp_path / "GPX"
    assert cli.main(["open-world-save", "ow-20261027-130000", "--km", "2.5", "--config", str(cfg),
                     "--gpx-dir", str(gpx), "--journal-dir", str(tmp_path / "j")]) == 0
    _, pts = read_gpx(gpx / "ow-20261027-130000.gpx")
    assert length_m(pts) == pytest.approx(2500.0, rel=0.01)
    assert "Balade enregistrée" in capsys.readouterr().out
    assert cli.main(["open-world-save", "ow-absent", "--config", str(cfg), "--gpx-dir", str(gpx)]) == 1
    assert cli.main(["open-world-save", "ow-20261027-130000", "--km", "0.3", "--config", str(cfg),
                     "--gpx-dir", str(tmp_path / "g2")]) == 0
    assert not (tmp_path / "g2").exists()


def test_distance_comes_from_the_journal_when_not_given(tmp_path):
    jdir = tmp_path / "j"
    jdir.mkdir()
    (jdir / "a.jsonl").write_text(
        '{"kind":"header","version":1,"route_id":"ow:ow-1","workout_id":null}\n'
        '{"kind":"record","ts":1,"t":1,"distance":800.0,"speed":9}\n'
        '{"kind":"record","ts":2,"t":2,"distance":1900.5,"speed":9}\n', encoding="utf-8")
    (jdir / "b.jsonl").write_text('{"kind":"header","version":1,"route_id":"demo","workout_id":null}\n', encoding="utf-8")
    assert journal_distance("ow-1", jdir) == 1900.5
    assert journal_distance("ow-2", jdir) is None and journal_distance("ow-1", tmp_path / "rien") is None
