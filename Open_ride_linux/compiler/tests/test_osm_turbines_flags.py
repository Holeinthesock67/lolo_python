"""Lot P12 : éoliennes (`wind_turbine`) et mâts de drapeau (`flag`) de la couche poi (format 1.2).

Données OSM fictives générées autour du parcours de test (aucune coordonnée réelle).
"""

from __future__ import annotations

import io
import json

import jsonschema
import pytest

from conftest import WORLD_CONTRACTS, straight_north, to_latlon
from openride_compiler import cache, cli
from openride_compiler.osm import build_overpass_query
from openride_compiler.osm_layers import _poi_kind_and_radius, wind_turbine_height


def _node(node_id: int, x: float, z: float, tags: dict) -> dict:
    lat, lon = to_latlon(x, z)
    return {"type": "node", "id": node_id, "lat": round(float(lat[0]), 8), "lon": round(float(lon[0]), 8), "tags": tags}


def _payload() -> bytes:
    elements = [
        _node(6001, 150.0, -500.0, {"power": "generator", "generator:source": "wind", "height": "120 m"}),
        _node(6002, -200.0, -1500.0, {"power": "generator", "generator:source": "wind"}),
        _node(6003, 120.0, -1000.0, {"power": "generator", "generator:source": "solar"}),
        _node(6004, 40.0, -2200.0, {"man_made": "flagpole"}),
    ]
    doc = {"version": 0.6, "generator": "OpenRide test fixture P12", "osm3s": {"timestamp_osm_base": "2026-03-16T08:00:00Z"},
           "elements": elements}
    return json.dumps(doc).encode("utf-8")


@pytest.fixture
def fake_overpass(monkeypatch):
    payload = _payload()
    monkeypatch.setattr(cache.urllib.request, "urlopen", lambda req, timeout=None: io.BytesIO(payload))


def test_classification_and_height():
    assert _poi_kind_and_radius({"power": "generator", "generator:source": "wind"})[0] == "wind_turbine"
    assert _poi_kind_and_radius({"power": "generator", "generator:source": "solar"}) is None
    assert _poi_kind_and_radius({"man_made": "flagpole"})[0] == "flag"
    assert wind_turbine_height({"height": "120 m"}) == 120.0
    assert wind_turbine_height({"height": "85,5"}) == 85.5
    assert wind_turbine_height({}) == 100.0
    assert wind_turbine_height({"height": "haute"}) == 100.0


def test_overpass_query_asks_for_turbines_and_flagpoles():
    q = build_overpass_query([(45.0, 6.0, 45.1, 6.1)])
    assert 'node["power"="generator"]["generator:source"="wind"]' in q
    assert 'node["man_made"="flagpole"]' in q


def test_build_turbines_and_flags(fake_overpass, make_gpx, tmp_path):
    x, z, alt = straight_north(length=3000.0)
    gpx = make_gpx("eoliennes.gpx", x, z, alt)
    out_dir = tmp_path / "routes"
    assert cli.main(["build", str(gpx), "--out", str(out_dir), "--layers", "route,terrain,poi"]) == 0
    world = out_dir / "eoliennes.world"
    assert cli.main(["verify", str(world)]) == 0

    schema = json.loads((WORLD_CONTRACTS / "poi.schema.json").read_text(encoding="utf-8"))
    points = []
    for f in sorted((world / "poi").glob("chunk_*.json")):
        chunk = json.loads(f.read_text(encoding="utf-8"))
        jsonschema.validate(chunk, schema)
        points.extend(chunk["points"])
    by_id = {p["id"]: p for p in points}
    assert set(by_id) == {"n6001", "n6002", "n6004"}   # le générateur solaire n'est pas retenu
    assert by_id["n6001"]["kind"] == "wind_turbine" and by_id["n6001"]["height_m"] == 120.0
    assert by_id["n6002"]["kind"] == "wind_turbine" and by_id["n6002"]["height_m"] == 100.0
    assert by_id["n6004"]["kind"] == "flag" and "height_m" not in by_id["n6004"]
