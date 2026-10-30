"""Lot P22 : terrains ouverts de la couche `vegetation` et couche `roads` des routes voisines (format 1.5)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import jsonschema
import pytest

from conftest import WORLD_CONTRACTS, straight_north
from openride_compiler import cache, cli
from openride_compiler import constants as C
from openride_compiler.osm import build_overpass_query
from openride_compiler.osm_layers import road_lanes, road_speed_kmh

SAMPLE = Path(__file__).parent / "data" / "osm" / "sample_open_roads.json"


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


@pytest.fixture
def fake_overpass_open_roads(monkeypatch):
    payload = SAMPLE.read_bytes()
    monkeypatch.setattr(cache.urllib.request, "urlopen", lambda req, timeout=None: io.BytesIO(payload))


def _chunks(world: Path, layer: str, key: str) -> dict[int, list[dict]]:
    schema = json.loads((WORLD_CONTRACTS / f"{layer}.schema.json").read_text(encoding="utf-8"))
    out = {}
    for f in sorted((world / layer).glob("chunk_*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        jsonschema.validate(doc, schema)
        out[int(f.stem.split("_")[1])] = doc[key]
    return out


@pytest.fixture
def built(fake_overpass_open_roads, make_gpx, tmp_path):
    x, z, alt = straight_north(length=3000.0)
    gpx = make_gpx("open_roads.gpx", x, z, alt)
    assert run("build", gpx, "--out", tmp_path / "routes", "--layers", "route,terrain,vegetation,roads") == 0
    world = tmp_path / "routes" / "open-roads.world"
    assert run("verify", world) == 0
    return world


def test_query_asks_open_land_and_roads():
    q = build_overpass_query([(45.0, 6.0, 45.1, 6.1)])
    assert 'way["landuse"~"^(meadow|farmland|grass)$"]' in q
    assert 'way["natural"~"^(grassland|heath)$"]' in q
    assert 'way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|track)$"]' in q


def test_open_land_kinds_density_zero_and_edge_rule(built):
    manifest = json.loads((built / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format_version"] == "1.6"
    jsonschema.validate(manifest, json.loads((WORLD_CONTRACTS / "manifest.schema.json").read_text(encoding="utf-8")))
    areas = {a["id"]: (k, a) for k, items in _chunks(built, "vegetation", "areas").items() for a in items}
    assert {i: a["kind"] for i, (_, a) in areas.items()} == {
        "w6001": "meadow", "w6002": "farmland", "w6003": "grassland", "w6004": "grassland"}
    assert all(a["density"] == C.DENSITY_OPEN for _, a in areas.values())
    # w6002 : centre à 600 m de la route, hors du couloir de 400 m, mais un bord à 300 m : gardé au tronçon 1
    assert areas["w6002"][0] == 1
    # w6005 : entièrement à plus de 1 500 m : écarté
    assert "w6005" not in areas
    assert manifest["layers"]["vegetation"]["count"] == 4


def test_roads_layer_pieces_attributes(built):
    manifest = json.loads((built / "manifest.json").read_text(encoding="utf-8"))
    r_man = manifest["layers"]["roads"]
    assert r_man["present"] is True and r_man["version"] == C.ROADS_VERSION
    chunks = _chunks(built, "roads", "lines")
    lines = {li["id"]: (k, li) for k, items in chunks.items() for li in items}
    assert r_man["count"] == len(lines)
    # w7003 suit la route du parcours (3 m) et w7004 n'en sort pas de 35 m : aucun morceau ; footway ignoré
    assert not any(i.startswith(("w7003", "w7004", "w7007")) for i in lines)
    # w7001 parallèle à 100 m sur 2,4 km : un morceau par tronçon, 0, 1 et 2
    sec = sorted((k, li) for i, (k, li) in lines.items() if i.startswith("w7001"))
    assert [k for k, _ in sec] == [0, 1, 2]
    assert all(li["kind"] == "secondary" and li["speed_kmh"] == 70 and li["lanes"] == 2 and li["oneway"] is False
               for _, li in sec)
    # w7002 croise la route : coupée de part et d'autre, aucun point à moins de 20 m du parcours
    res = [li for i, (_, li) in lines.items() if i.startswith("w7002")]
    assert len(res) == 2 and all(li["speed_kmh"] == 30 for li in res)
    assert {li["points"][0][0] < 0 for li in res} == {True, False}
    for _, li in lines.values():
        assert all(abs(p[0]) >= C.ROAD_ROUTE_GAP_M - 0.5 for p in li["points"])
        steps = [((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for a, b in zip(li["points"], li["points"][1:])]
        assert max(steps) <= 25.0 + 1e-6
    # autoroute : sens unique, lanes=3 de l'étiquette, 130 km/h ; tertiaire à sens unique : une voie
    mw = [li for i, (_, li) in lines.items() if i.startswith("w7005")]
    assert mw and all(li["oneway"] is True and li["lanes"] == 3 and li["speed_kmh"] == 130 for li in mw)
    ter = [li for i, (_, li) in lines.items() if i.startswith("w7006")]
    assert ter and all(li["oneway"] is True and li["lanes"] == 1 and li["speed_kmh"] == 80 for li in ter)
    # altitude : le sol du plan de test (5 % vers le nord)
    k, li = sec[0]
    p = li["points"][0]
    assert p[2] == pytest.approx(1000.0 - 0.05 * p[1], abs=0.5)


def test_road_defaults():
    assert road_lanes("motorway", {}) == 4 and road_lanes("track", {}) == 1 and road_lanes("primary", {}) == 2
    assert road_lanes("primary", {"lanes": "3;2"}) == 3 and road_lanes("primary", {"lanes": "x"}) == 2
    assert road_lanes("trunk", {"oneway": "yes"}) == 4 and road_lanes("secondary", {"oneway": "yes"}) == 1
    assert road_speed_kmh("residential", {}) == 30 and road_speed_kmh("primary", {"maxspeed": "90"}) == 90
    assert road_speed_kmh("primary", {"maxspeed": "FR:rural"}) == 80
    assert road_speed_kmh("primary", {"maxspeed": "50 mph"}) == 80


def test_add_layer_roads_and_verify_rejects_bad_roads(built):
    before = {p.name: p.read_bytes() for p in (built / "vegetation").glob("*.json")}
    assert run("add-layer", built, "roads") == 0
    assert {p.name: p.read_bytes() for p in (built / "vegetation").glob("*.json")} == before
    f = sorted((built / "roads").glob("chunk_*.json"))[0]
    doc = json.loads(f.read_text(encoding="utf-8"))
    doc["lines"][0]["lanes"] = 0
    doc["lines"][0]["points"][0][0] = 2.0          # sur la route du parcours
    f.write_text(json.dumps(doc), encoding="utf-8")
    assert run("verify", built) != 0


def test_verify_rejects_open_land_with_trees(built):
    f = sorted((built / "vegetation").glob("chunk_*.json"))[0]
    doc = json.loads(f.read_text(encoding="utf-8"))
    doc["areas"][0]["density"] = 0.5
    f.write_text(json.dumps(doc), encoding="utf-8")
    assert run("verify", built) != 0
