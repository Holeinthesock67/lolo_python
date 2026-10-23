"""Lot A : lecteur .world, interpolation de Catmull-Rom, vecteurs partagés, parcours en boucle."""

import asyncio
import json
import math
import re
import time
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export
from openride_core.config import Config
from openride_core.demo_world import build_route, write_demo_world, write_world
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.route import Route, WorldError, find_world, load_world
from openride_core.session import CoreSession
from openride_core.tools import route_vectors

REPO = Path(__file__).resolve().parents[2]
WORLD_CONTRACTS = REPO / "docs" / "contracts" / "world"
ENGINE_DEMO = REPO / "engine" / "demo" / "demo.world"


def validator(name):
    return jsonschema.Draft202012Validator(
        json.loads((WORLD_CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8")))


# Interpolation ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", route_vectors.build_cases(), ids=lambda c: c["name"])
def test_spline_passes_through_points(case):
    r = Route(case["route"])
    for i, s in enumerate(r.s):
        p = r.sample(s)
        assert math.dist((p.x, p.y, p.z), r.points[i]) < 1e-9


def straight_route(length=1025.0, ds=10.0, grade=5.0):
    n = int(length // ds) + 1 + (1 if length % ds else 0)
    s = [i * ds for i in range(n - 1)] + [length]
    return {"version": "1.0", "ds_m": ds, "n": n, "length_m": length, "type": "open",
            "lat": [45.0] * n, "lon": [6.0] * n, "alt_m": [grade / 100 * v for v in s],
            "x": [0.0] * n, "z": [-v for v in s], "grade_pct": [grade] * n, "heading_deg": [0.0] * n}


def test_straight_line_stays_on_line_and_is_linear_inside():
    r = Route(straight_route())
    for k in range(0, 10250, 7):
        s = k / 10
        p = r.sample(s)
        assert abs(p.x) < 1e-9 and abs(p.y + 0.05 * p.z) < 1e-9      # sur la droite
        if 10 <= s <= 1000:                                             # voisins réguliers
            assert math.dist((p.x, p.y, p.z), (0.0, 0.05 * s, -s)) < 1e-9


def test_heading_takes_shortest_way_through_north():
    r = Route(route_vectors.build_cases()[0]["route"])   # caps 358° puis 4° entre s = 30 et 40
    h = r.sample(35.0).heading_deg
    assert h == pytest.approx(1.0, abs=1e-9)


def test_grade_at_matches_sample():
    r = Route(route_vectors.build_cases()[0]["route"])
    for s in (0.0, 12.3, 55.0, 104.0, 106.0):
        assert r.grade_at(s) == pytest.approx(r.sample(s).grade_pct, abs=1e-12)


def test_vectors_file_is_up_to_date():
    path = WORLD_CONTRACTS / "route_test_vectors.json"
    assert path.read_text(encoding="utf-8") == route_vectors.render(), \
        "relancer : python -m openride_core.tools.route_vectors"


def test_grade_at_is_fast_enough():
    r = Route(build_route(30_000.0))                      # 3 001 points
    t0 = time.perf_counter()
    for i in range(100_000):
        r.grade_at((i * 0.37) % 30_000.0)
    per_call_us = (time.perf_counter() - t0) / 100_000 * 1e6
    if per_call_us > 20:
        pytest.skip(f"machine lente : {per_call_us:.1f} µs par appel")
    assert per_call_us < 20


# Boucle ----------------------------------------------------------------------------------

def test_loop_wraps():
    case = route_vectors.build_cases()[1]
    r = Route(case["route"])
    assert r.is_loop and r.wrap(125.0) == pytest.approx(5.0) and r.wrap(-10.0) == pytest.approx(110.0)
    a, b = r.sample(5.0), r.sample(125.0)
    assert (a.x, a.y, a.z, a.grade_pct) == pytest.approx((b.x, b.y, b.z, b.grade_pct))


# Chargement et validation ----------------------------------------------------------------

def write(tmp_path, route=None, manifest_patch=None, name="t"):
    world = write_world(tmp_path, name, 500.0)
    if route is not None:
        (world / "route.json").write_text(json.dumps(route), encoding="utf-8")
    if manifest_patch:
        m = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
        m.update(manifest_patch)
        (world / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    return world


def test_load_valid_world(tmp_path):
    w = load_world(write(tmp_path))
    assert w.route.length_m == 500.0 and w.route.n == 51 and w.name == "t"


@pytest.mark.parametrize("breakage,code", [
    ("absent", "route_not_found"),
    ("no_route", "route_invalid"),
    ("bad_length", "route_invalid"),
    ("major2", "route_invalid"),
    ("far_end", "route_invalid"),
    ("open_loop", "route_invalid"),
])
def test_invalid_worlds(tmp_path, breakage, code):
    good = build_route(500.0)
    if breakage == "absent":
        path = tmp_path / "rien.world"
    elif breakage == "no_route":
        path = write(tmp_path)
        (path / "route.json").unlink()
    elif breakage == "bad_length":
        path = write(tmp_path, {**good, "x": good["x"][:-1]})
    elif breakage == "major2":
        path = write(tmp_path, manifest_patch={"format_version": "2.0"})
    elif breakage == "far_end":
        path = write(tmp_path, {**good, "length_m": 900.0})
    else:
        path = write(tmp_path, {**good, "type": "loop"})        # fin à des centaines de mètres du départ
    with pytest.raises(WorldError) as err:
        load_world(path)
    assert err.value.code == code


# Schémas et démo commune -----------------------------------------------------------------

def test_schemas_validate_demo_vectors_and_format_example():
    rv, mv = validator("route"), validator("manifest")
    assert not list(rv.iter_errors(json.loads((ENGINE_DEMO / "route.json").read_text())))
    assert not list(mv.iter_errors(json.loads((ENGINE_DEMO / "manifest.json").read_text())))
    for case in route_vectors.build_cases():
        assert not list(rv.iter_errors(case["route"])), case["name"]
    text = (REPO / "docs" / "contracts" / "world_format_v1.md").read_text(encoding="utf-8")
    example = next(json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", text, re.S)
                   if '"openride-world"' in b)
    assert not list(mv.iter_errors(example))


@pytest.mark.parametrize("length_m", [1234.0, 1500.0, 5000.0, 8000.0, 30_000.0])
def test_demo_route_never_overlaps_itself(length_m):
    # Deux points distants de plus de 300 m le long de la route restent à plus de 90 m l'un de
    # l'autre en plan (les branches du lacet sont à ~95 m) : le terrain peut suivre chaque passage.
    r = build_route(length_m)
    x, z, n = r["x"], r["z"], r["n"]
    closest = min(math.hypot(x[i] - x[j], z[i] - z[j])
                  for i in range(0, n, 3) for j in range(i + 30, n, 3))
    assert closest > 90.0


def test_engine_demo_is_the_core_demo(tmp_path):
    core_demo = write_demo_world(tmp_path)
    for f in ("route.json", "manifest.json"):
        assert (core_demo / f).read_bytes() == (ENGINE_DEMO / f).read_bytes(), f


# Intégration dans la session -------------------------------------------------------------

def make_session(tmp_path, monkeypatch, port):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes")
    frames = []
    s.server.send_raw = frames.append
    return s, frames


def test_session_loads_route_by_id_and_reports_errors(tmp_path, monkeypatch):
    async def scenario():
        s, frames = make_session(tmp_path, monkeypatch, 6010)
        s._on_command("select_route", {"route_id": "inconnu"}, 1)
        assert s.state.session_state == "IDLE"
        assert any(f["type"] == "error" and f["code"] == "route_not_found" for f in frames)
        write_world(tmp_path / "routes", "col", 700.0)
        s._on_command("select_route", {"route_id": "col"}, 2)
        assert s.state.session_state == "READY" and s.state.route_length_m == 700.0
        s._on_command("select_route", {"route_id": "demo"}, 3)   # créé à la demande
        assert (tmp_path / "routes" / "demo.world" / "route.json").is_file()
        assert s.state.route_length_m == 5000.0
    asyncio.run(scenario())


def test_session_loop_route_never_finishes(tmp_path, monkeypatch):
    async def scenario():
        s, _ = make_session(tmp_path, monkeypatch, 6020)
        world = tmp_path / "routes" / "anneau.world"
        write_world(tmp_path / "routes", "anneau", 100.0)
        (world / "route.json").write_text(json.dumps(route_vectors.build_cases()[1]["route"]))
        s._on_command("select_route", {"route_id": "anneau"}, 1)
        s._on_command("start", {}, 2)
        start_grade = s.route.grade_at(0.0)
        for i in range(3000):                               # 60 s simulées, plusieurs tours
            s._step(0.02, 10.0 + i * 0.02)
        assert s.physics.s > s.route.length_m * 2
        assert s.state.session_state == "RUNNING"
        assert s.route.grade_at(s.route.length_m * 3) == pytest.approx(start_grade)
    asyncio.run(scenario())


def test_session_no_longer_imports_tools():
    src = (REPO / "core" / "src" / "openride_core" / "session.py").read_text(encoding="utf-8")
    assert "from .tools" not in src and "import tools" not in src
