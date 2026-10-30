"""Lot I4 : couches OpenStreetMap `poi` et `water` (critères 1 à 6)."""

from __future__ import annotations

import hashlib
import io
import json
from collections import Counter
from pathlib import Path

import jsonschema
import pytest

from conftest import WORLD_CONTRACTS, straight_north
from openride_compiler import cache, cli
from openride_compiler.osm_layers import signed_area

DATA_DIR = Path(__file__).parent / "data" / "osm"
SAMPLE_POI_WATER = DATA_DIR / "sample_poi_water.json"


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeOverpassHttp:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls: list[tuple[str, float | None]] = []

    def __call__(self, req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        self.calls.append((url, timeout))
        return io.BytesIO(self.payload)


@pytest.fixture
def fake_overpass_poi_water(monkeypatch):
    payload = SAMPLE_POI_WATER.read_bytes()
    fake = FakeOverpassHttp(payload)
    monkeypatch.setattr(cache.urllib.request, "urlopen", fake)
    return fake


# Critères 2, 3, 4 : construction poi et water, lac avec île, rivière de 2,5 km en 3 morceaux, width_m ----


def test_build_poi_and_water_layers(fake_overpass_poi_water, make_gpx, tmp_path):
    x, z, alt = straight_north(length=3000.0)
    gpx = make_gpx("poi_water.gpx", x, z, alt)
    out_dir = tmp_path / "routes"

    rc = run("build", gpx, "--out", out_dir, "--layers", "route,terrain,poi,water")
    assert rc == 0

    world = out_dir / "poi-water.world"
    assert run("verify", world) == 0

    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    p_man = manifest["layers"]["poi"]
    w_man = manifest["layers"]["water"]

    assert p_man["present"] is True and p_man["version"] == "1.0"
    assert p_man["count"] == 5  # church_bell, village, viewpoint, livestock, river
    assert w_man["present"] is True and w_man["version"] == "1.0"
    assert w_man["lines_count"] == 5  # 3 morceaux de w4001 + w4002 + w4003
    assert w_man["areas_count"] == 3  # r5001 (lake), w5002 (pond), w5003 (reservoir)

    poi_schema = json.loads((WORLD_CONTRACTS / "poi.schema.json").read_text(encoding="utf-8"))
    water_schema = json.loads((WORLD_CONTRACTS / "water.schema.json").read_text(encoding="utf-8"))

    all_pois = []
    for p_file in sorted((world / "poi").glob("chunk_*.json")):
        chunk = json.loads(p_file.read_text(encoding="utf-8"))
        jsonschema.validate(chunk, poi_schema)
        all_pois.extend(chunk["points"])

    poi_kinds = Counter(p["kind"] for p in all_pois)
    assert poi_kinds == {
        "church_bell": 1,
        "village": 1,
        "viewpoint": 1,
        "livestock": 1,
        "river": 1,
    }

    water_by_chunk = {}
    all_lines = []
    all_areas = []
    for w_file in sorted((world / "water").glob("chunk_*.json")):
        k = int(w_file.stem.split("_")[1])
        chunk = json.loads(w_file.read_text(encoding="utf-8"))
        jsonschema.validate(chunk, water_schema)
        water_by_chunk[k] = chunk
        all_lines.extend(chunk["lines"])
        all_areas.extend(chunk["areas"])

    # Critère 3 : la rivière w4001 de 2,5 km parallèle à la route est coupée en 3 morceaux (tronçons 0, 1, 2)
    w4001_chunks = [
        k for k, ch in sorted(water_by_chunk.items())
        if any(li["id"].startswith("w4001") for li in ch["lines"])
    ]
    assert w4001_chunks == [0, 1, 2]

    # Critère 4 : width=4 donne 4 ; un stream sans étiquette donne 2
    lines_by_id = {li["id"]: li for li in all_lines}
    assert lines_by_id["w4001_0"]["width_m"] == 4.0
    assert lines_by_id["w4002"]["kind"] == "stream" and lines_by_id["w4002"]["width_m"] == 2.0
    assert lines_by_id["w4003"]["kind"] == "canal" and lines_by_id["w4003"]["width_m"] == 8.0

    # Critère 2 : un lac avec île donne un holes correct (outer antihoraire, hole horaire)
    areas_by_id = {a["id"]: a for a in all_areas}
    assert set(areas_by_id) == {"r5001", "w5002", "w5003"}
    lake = areas_by_id["r5001"]
    assert lake["kind"] == "lake"
    assert signed_area(lake["outer"]) > 0
    assert len(lake["holes"]) == 1
    assert signed_area(lake["holes"][0]) < 0
    assert areas_by_id["w5002"]["kind"] == "pond"
    assert areas_by_id["w5003"]["kind"] == "reservoir"


# Critère 5 : recompilation --offline identique octet pour octet ; add-layer water isolé ----------


def test_offline_and_add_layer_water_preserves_other_layers(fake_overpass_poi_water, make_gpx, tmp_path):
    x, z, alt = straight_north(length=3000.0)
    gpx = make_gpx("water_repro.gpx", x, z, alt)

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    assert run("build", gpx, "--out", out1, "--layers", "route,terrain,poi,water") == 0
    calls_first = len(fake_overpass_poi_water.calls)
    assert calls_first == 2                # couches OSM, puis voies du couloir de la surface (lot U20)

    assert run("build", gpx, "--out", out2, "--layers", "route,terrain,poi,water", "--offline") == 0
    assert len(fake_overpass_poi_water.calls) == calls_first

    w1 = out1 / "water-repro.world"
    w2 = out2 / "water-repro.world"
    for rel in ("poi/chunk_0.json", "water/chunk_0.json", "water/chunk_1.json", "water/chunk_2.json"):
        assert (w1 / rel).read_bytes() == (w2 / rel).read_bytes()

    # add-layer water sur un parcours existant ne modifie ni route.json, ni terrain, ni poi
    out3 = tmp_path / "run3"
    assert run("build", gpx, "--out", out3, "--layers", "route,terrain,poi", "--offline") == 0
    w3 = out3 / "water-repro.world"
    assert not (w3 / "water").exists()

    route_sha = sha256_file(w3 / "route.json")
    poi_shas = {p.name: sha256_file(p) for p in sorted((w3 / "poi").glob("*.json"))}
    terrain_shas = {p.relative_to(w3): sha256_file(p) for p in sorted((w3 / "terrain").rglob("*.f32"))}

    assert run("add-layer", w3, "water", "--offline") == 0
    assert (w3 / "water" / "chunk_0.json").is_file()
    assert run("verify", w3) == 0

    assert sha256_file(w3 / "route.json") == route_sha
    assert {p.name: sha256_file(p) for p in sorted((w3 / "poi").glob("*.json"))} == poi_shas
    assert {p.relative_to(w3): sha256_file(p) for p in sorted((w3 / "terrain").rglob("*.f32"))} == terrain_shas


# Critère 6 : verify rejette un kind inconnu dans poi ---------------------------------------------


def test_verify_rejects_unknown_poi_kind(fake_overpass_poi_water, make_gpx, tmp_path, capsys):
    x, z, alt = straight_north(length=1000.0)
    gpx = make_gpx("bad_poi.gpx", x, z, alt)
    out_dir = tmp_path / "routes"
    assert run("build", gpx, "--out", out_dir, "--layers", "route,poi") == 0
    world = out_dir / "bad-poi.world"
    assert run("verify", world) == 0

    chunk0_path = world / "poi" / "chunk_0.json"
    chunk0 = json.loads(chunk0_path.read_text(encoding="utf-8"))
    chunk0["points"][0]["kind"] = "unknown_sound_source"
    chunk0_path.write_text(json.dumps(chunk0), encoding="utf-8")

    assert run("verify", world) == 1
    out = capsys.readouterr().out
    assert "kind inconnu" in out
