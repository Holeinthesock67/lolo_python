"""Monde ouvert synthétique (lot W15) : base fictive, monde vivant écrit d'un coup, faux générateur."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from openride_compiler.worldgen import osmdb
from openride_compiler.worldgen.graph import RoadGraph
from openride_compiler.worldgen.osmdb import OsmDb
from openride_compiler.worldgen.squares import zone_frame
from openride_compiler.worldgen.synthetic import (ORIGIN_LAT, ORIGIN_LON, default_script, synthetic_db,
                                                  write_live_world)

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "docs" / "contracts" / "world"
SRC = Path(__file__).resolve().parents[1] / "src"


def schema(name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads((SCHEMAS / name).read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def db(tmp_path_factory) -> OsmDb:
    path = tmp_path_factory.mktemp("synth") / "synthetic.sqlite"
    synthetic_db(path, seed=3)
    return OsmDb(path)


def test_synthetic_db_content_and_bbox_queries(db) -> None:
    lon0, lat0, lon1, lat1 = map(float, db.meta["bbox"].split(","))
    assert lon0 < ORIGIN_LON < lon1 and lat0 < ORIGIN_LAT < lat1 and lat1 - lat0 < 0.2   # en mer, 10 km
    roads = db.roads_in((lon0 - 1, lat0 - 1, lon1 + 1, lat1 + 1))
    assert {r.road_class for r in roads} == {"s", "t", "m", "c", "k"}
    assert sum(r.bridge for r in roads) == 2 and sum(r.tunnel for r in roads) == 1
    assert any(r.junction == "roundabout" for r in roads)
    areas = db.areas_in((lon0 - 1, lat0 - 1, lon1 + 1, lat1 + 1))
    assert {a.kind for a in areas} == {"building", "wood", "water"}
    step = 0.013
    for k in range(12):
        b = (lon0 + k * step, lat0 + k * step / 2, lon0 + k * step + 0.02, lat0 + k * step / 2 + 0.02)
        assert [r.id for r in db.roads_in(b)] == [r.id for r in roads if osmdb.polyline_touches(r.coords, b)]
    # Graphe : une impasse et un rond-point réduit à un seul nœud de choix.
    g = RoadGraph.build(db, (lon0, lat0, lon1, lat1), zone_frame("31T"))
    assert any(n.ring for n in g.nodes.values())
    assert any(g.dead_end(e) or g.dead_end(e, forward=False) for e in g.edges.values())


def test_synthetic_db_is_deterministic(tmp_path) -> None:
    a, b = tmp_path / "a.sqlite", tmp_path / "b.sqlite"
    assert synthetic_db(a, seed=5) == synthetic_db(b, seed=5)
    with OsmDb(a) as da, OsmDb(b) as dbb:
        box = tuple(map(float, da.meta["bbox"].split(",")))
        assert [(r.osm_id, r.coords) for r in da.roads_in(box)] == [(r.osm_id, r.coords) for r in dbb.roads_in(box)]


def _validate_live(world: Path) -> dict:
    manifest = json.loads((world / "manifest.json").read_text())
    schema("manifest.schema.json").validate(manifest)
    live = json.loads((world / "live.json").read_text())
    schema("live.schema.json").validate(live)
    schema("junctions.schema.json").validate(json.loads((world / "junctions.json").read_text()))
    parts = [json.loads((world / "route" / f"part_{k}.json").read_text()) for k in range(live["route"]["parts"])]
    for p in parts:
        schema("route_part.schema.json").validate(p)
    for layer, name in (("buildings", "buildings"), ("vegetation", "vegetation"), ("water", "water"), ("poi", "poi")):
        v = schema(f"{name}.schema.json")
        for f in (world / layer).glob("tile_*.json"):
            v.validate(json.loads(f.read_text()))
    for ix, iz in live["tiles"]["near"]:
        assert (world / "terrain" / "near" / f"tile_{ix}_{iz}.f32").stat().st_size == 101 * 101 * 4
    return {"manifest": manifest, "live": live, "parts": parts}


def _assemble(parts: list[dict]) -> dict:
    cols = ("lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg")
    out = {k: [] for k in cols}
    for k, p in enumerate(parts):
        for c in cols:
            out[c] += p[c][1:] if k else p[c]
    n = len(out["x"])
    return {"n": n, "ds_m": 10.0, "length_m": parts[-1]["s0_m"] + parts[-1]["length_m"], "type": "open", **out}


def test_write_live_world_is_valid_and_readable_by_core(tmp_path) -> None:
    info = write_live_world(tmp_path / "w.world", default_script(6000.0, seed=2))
    assert info["parts"] == 6 and info["junctions"] >= 3 and info["buildings"] >= 10
    v = _validate_live(tmp_path / "w.world")
    route = _assemble(v["parts"])
    assert route["length_m"] == pytest.approx(6000.0)
    if importlib.util.find_spec("openride_core") is not None:
        from openride_core.route import Route
        r = Route(route)
        assert r.length_m == pytest.approx(6000.0) and abs(r.sample(3000.0).grade_pct) < 25
    assert write_live_world(tmp_path / "w2.world", default_script(6000.0, seed=2)) == info


def test_make_sim_world_live(tmp_path) -> None:
    spec = importlib.util.spec_from_file_location("make_sim_world", ROOT / "engine" / "tests" / "make_sim_world.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.main(["--out", str(tmp_path), "--live"]) == 0
    v = _validate_live(tmp_path / "monde-ouvert-simule.world")
    assert v["live"]["route"]["length_m"] == pytest.approx(20_000.0) and v["live"]["route"]["parts"] == 20


class Fake:
    """Faux générateur en sous-processus, dialogue ligne à ligne."""

    def __init__(self, tmp_path: Path, *opts: str) -> None:
        self.session = tmp_path / "seance.world"
        self.p = subprocess.Popen(
            [sys.executable, "-m", "openride_compiler.worldgen.synthetic", "--session", str(self.session),
             "--work-dir", str(tmp_path / "work"), "--size-km", "8", *opts],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, "PYTHONPATH": str(SRC)})
        self.out: list[dict] = []

    def send(self, msg: dict) -> None:
        assert self.p.stdin is not None
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def read_until(self, pred) -> dict:
        assert self.p.stdout is not None
        while True:
            line = self.p.stdout.readline()
            assert line, f"processus terminé : {self.p.stderr.read() if self.p.stderr else ''}"
            msg = json.loads(line)
            self.out.append(msg)
            if pred(msg):
                return msg

    def sync(self) -> None:
        """Requête sans effet qui reçoit toujours une réponse : tout ce qui précède est traité."""
        self.send({"type": "choose", "junction_id": "sync", "branch": 0})
        self.read_until(lambda m: m["type"] == "error" and m["code"] == "unknown_junction")

    def close(self) -> int:
        self.send({"type": "close"})
        self.read_until(lambda m: m["type"] == "closed")
        return self.p.wait(30)


OPEN = {"type": "open", "lat": 48.0, "lon": 7.0, "heading_deg": 90, "nav": "ride", "target": None,
        "loop_km": None, "seed": 1, "network": True}


def test_fake_worldgen_dialogue(tmp_path) -> None:
    f = Fake(tmp_path)
    f.send(OPEN)
    rev = f.read_until(lambda m: m["type"] == "revision")
    phases = [m["phase"] for m in f.out if m["type"] == "status"]
    assert phases[0] == "osm" and phases[-1] == "ready" and rev["length_m"] >= 3000
    length = rev["length_m"]
    for s in range(100, 10_001, 100):
        f.send({"type": "progress", "s_m": float(s), "v_mps": 10.0})
        f.sync()
        length = max([length] + [m["length_m"] for m in f.out if m["type"] == "revision"])
        assert length - s >= 3000
    j = json.loads((f.session / "junctions.json").read_text())
    ahead = [x for x in j["junctions"] if x["s_m"] > 10_000 + 150 and len(x["branches"]) >= 2]
    target = ahead[0]
    n = len(f.out)
    f.send({"type": "choose", "junction_id": target["id"], "branch": 1 - target["default"] if target["default"] < 2 else 0})
    f.sync()
    assert any(m["type"] == "revision" for m in f.out[n:])
    f.send({"type": "progress", "s_m": target["s_m"] - 10.0, "v_mps": 10.0})
    f.send({"type": "choose", "junction_id": target["id"], "branch": target["default"]})
    f.read_until(lambda m: m["type"] == "error")
    assert f.out[-1]["code"] == "branch_locked"
    assert f.close() == 0


def test_fake_worldgen_failures(tmp_path) -> None:
    f = Fake(tmp_path / "a", "--offline")
    f.send({**OPEN, "network": False})
    f.read_until(lambda m: m["type"] == "revision")
    assert any(m["type"] == "status" and m["data"] == "offline" for m in f.out)
    assert f.close() == 0

    f = Fake(tmp_path / "b", "--missing-after-m", "500")
    f.send(OPEN)
    f.read_until(lambda m: m["type"] == "revision")
    f.send({"type": "progress", "s_m": 600.0, "v_mps": 10.0})
    f.read_until(lambda m: m["type"] == "status" and m["data"] == "missing")
    assert f.close() == 0

    f = Fake(tmp_path / "c", "--crash-after-m", "300")
    f.send(OPEN)
    f.read_until(lambda m: m["type"] == "revision")
    f.send({"type": "progress", "s_m": 400.0, "v_mps": 10.0})
    assert f.p.wait(30) == 3
