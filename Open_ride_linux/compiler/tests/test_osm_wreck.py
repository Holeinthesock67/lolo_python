"""Lot SM2 : épaves de navire (`wreck`, OSM `historic=wreck`) de la couche poi (format 1.8, ajout compatible).

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
from openride_compiler.osm_layers import _poi_kind_and_radius, wreck_length


def _node(node_id: int, x: float, z: float, tags: dict) -> dict:
    lat, lon = to_latlon(x, z)
    return {"type": "node", "id": node_id, "lat": round(float(lat[0]), 8), "lon": round(float(lon[0]), 8), "tags": tags}


def _payload() -> bytes:
    elements = [
        _node(7001, 60.0, -800.0, {"historic": "wreck", "length": "55 m", "name": "Épave fictive"}),
        _node(7002, -45.0, -1800.0, {"historic": "wreck"}),
        _node(7003, 50.0, -2400.0, {"historic": "castle"}),
    ]
    doc = {"version": 0.6, "generator": "OpenRide test fixture SM2", "osm3s": {"timestamp_osm_base": "2026-03-16T08:00:00Z"},
           "elements": elements}
    return json.dumps(doc).encode("utf-8")


@pytest.fixture
def fake_overpass(monkeypatch):
    payload = _payload()
    monkeypatch.setattr(cache.urllib.request, "urlopen", lambda req, timeout=None: io.BytesIO(payload))


def test_classification_and_length():
    assert _poi_kind_and_radius({"historic": "wreck"}) == ("wreck", 400)
    assert _poi_kind_and_radius({"historic": "castle"}) is None
    assert wreck_length({"length": "55 m"}) == 55.0
    assert wreck_length({"length": "30,5"}) == 30.5
    assert wreck_length({}) == 42.0
    assert wreck_length({"length": "long"}) == 42.0


def test_overpass_query_unchanged():
    """La requête Overpass ne demande pas les épaves : la changer ferait retélécharger les données de tous les
    parcours déjà compilés (cache indexé par la requête) et casserait la reconstruction hors réseau du pack des
    cols. Une épave vient des données fournies au compilateur (parcours de démonstration, réponse d'Overpass)."""
    q = build_overpass_query([(45.0, 6.0, 45.1, 6.1)])
    assert "wreck" not in q and "historic" not in q


def test_build_wrecks(fake_overpass, make_gpx, tmp_path):
    x, z, alt = straight_north(length=3000.0)
    gpx = make_gpx("epaves.gpx", x, z, alt)
    out_dir = tmp_path / "routes"
    assert cli.main(["build", str(gpx), "--out", str(out_dir), "--layers", "route,terrain,poi"]) == 0
    world = out_dir / "epaves.world"
    assert cli.main(["verify", str(world)]) == 0

    schema = json.loads((WORLD_CONTRACTS / "poi.schema.json").read_text(encoding="utf-8"))
    points = []
    for f in sorted((world / "poi").glob("chunk_*.json")):
        chunk = json.loads(f.read_text(encoding="utf-8"))
        jsonschema.validate(chunk, schema)
        points.extend(chunk["points"])
    by_id = {p["id"]: p for p in points}
    assert set(by_id) == {"n7001", "n7002"}   # le château n'est pas retenu
    assert by_id["n7001"]["kind"] == "wreck" and by_id["n7001"]["length_m"] == 55.0
    assert by_id["n7001"]["radius_m"] == 400 and by_id["n7001"]["name"] == "Épave fictive"
    assert by_id["n7002"]["kind"] == "wreck" and by_id["n7002"]["length_m"] == 42.0
