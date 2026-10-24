"""Lot I3 : couches OpenStreetMap `buildings` et `vegetation` (critères 1 à 8)."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import jsonschema
import pytest

from conftest import WORLD_CONTRACTS, plane, straight_north
from openride_compiler import cache, cli
from openride_compiler.osm import OverpassClient
from openride_compiler.osm_layers import compute_building_height, signed_area

DATA_DIR = Path(__file__).parent / "data" / "osm"
SAMPLE_JSON = DATA_DIR / "sample_overpass.json"


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeOverpassHttp:
    """Simule l'API Overpass en renvoyant `sample_overpass.json` et en comptant les appels."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls: list[tuple[str, float | None]] = []

    def __call__(self, req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        self.calls.append((url, timeout))
        return io.BytesIO(self.payload)


@pytest.fixture
def fake_overpass(monkeypatch):
    payload = SAMPLE_JSON.read_bytes()
    fake = FakeOverpassHttp(payload)
    monkeypatch.setattr(cache.urllib.request, "urlopen", fake)
    return fake


# Critères 2, 3, 4 : construction des couches buildings et vegetation, multipolygone, hauteurs, base_y ----


def test_build_buildings_and_vegetation_layers(fake_overpass, make_gpx, tmp_path):
    x, z, alt = straight_north(length=2000.0)
    gpx = make_gpx("osm_test.gpx", x, z, alt)
    out_dir = tmp_path / "routes"

    rc = run("build", gpx, "--out", out_dir, "--layers", "route,terrain,buildings,vegetation")
    assert rc == 0

    world = out_dir / "osm-test.world"
    assert run("verify", world) == 0

    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    b_man = manifest["layers"]["buildings"]
    v_man = manifest["layers"]["vegetation"]

    # 3 bâtiments retenus (w1001, w1002 dans chunk 0 ; w1003 dans chunk 1),
    # 1 hors bande (> 400 m : w1004), 1 dégénéré ignoré (w1005)
    assert b_man["present"] is True
    assert b_man["version"] == "1.0"
    assert b_man["count"] == 3
    assert b_man["ignored_count"] == 1
    assert b_man["osm_date"] == "2026-03-15T10:00:00Z"

    # 3 zones de végétation (r2001 dans chunk 0 ; w2002 et w2003 dans chunk 1)
    assert v_man["present"] is True
    assert v_man["version"] == "1.0"
    assert v_man["source"] == "osm"
    assert v_man["count"] == 3
    assert v_man["ignored_count"] == 0

    # Validation contre les schémas JSON du contrat
    b_schema = json.loads((WORLD_CONTRACTS / "buildings.schema.json").read_text(encoding="utf-8"))
    v_schema = json.loads((WORLD_CONTRACTS / "vegetation.schema.json").read_text(encoding="utf-8"))

    b_chunk0 = json.loads((world / "buildings" / "chunk_0.json").read_text(encoding="utf-8"))
    b_chunk1 = json.loads((world / "buildings" / "chunk_1.json").read_text(encoding="utf-8"))
    jsonschema.validate(b_chunk0, b_schema)
    jsonschema.validate(b_chunk1, b_schema)

    v_chunk0 = json.loads((world / "vegetation" / "chunk_0.json").read_text(encoding="utf-8"))
    v_chunk1 = json.loads((world / "vegetation" / "chunk_1.json").read_text(encoding="utf-8"))
    jsonschema.validate(v_chunk0, v_schema)
    jsonschema.validate(v_chunk1, v_schema)

    by_id = {b["id"]: b for b in b_chunk0["buildings"] + b_chunk1["buildings"]}
    assert set(by_id) == {"w1001", "w1002", "w1003"}

    # Critère 3 : height_m ("12 m" -> 12, levels=3 -> 9, sans étiquette -> dans [4, 10] et déterministe)
    assert by_id["w1001"]["height_m"] == 12.0
    assert by_id["w1002"]["height_m"] == 9.0
    assert 4.0 <= by_id["w1003"]["height_m"] <= 10.0
    assert by_id["w1003"]["height_m"] == compute_building_height("w1003", {"building": "yes"})

    # Critère 4 : base_y égale le minimum du terrain sous l'empreinte à 1 cm près
    # Pour w1001 (x in [50, 70], z in [-300, -280]), plane(x, z) = 1000 - 0.05 * z -> min à z = -280 : 1014.0 m
    expected_min_y = float(plane(50.0, -280.0))
    assert abs(by_id["w1001"]["base_y"] - expected_min_y) <= 0.01

    # Critère 2 : tous les outer sont antihoraires (> 0) et le multipolygone r2001 a 1 outer et 1 hole horaire (< 0)
    for b in by_id.values():
        assert signed_area(b["outer"]) > 0
        assert b["outer"][0] != b["outer"][-1]

    v_by_id = {a["id"]: a for a in v_chunk0["areas"] + v_chunk1["areas"]}
    assert set(v_by_id) == {"r2001", "w2002", "w2003"}
    r2001 = v_by_id["r2001"]
    assert r2001["kind"] == "wood" and r2001["density"] == 0.8
    assert signed_area(r2001["outer"]) > 0
    assert len(r2001["holes"]) == 1
    assert signed_area(r2001["holes"][0]) < 0
    assert v_by_id["w2002"]["kind"] == "scrub" and v_by_id["w2002"]["density"] == 0.4
    assert v_by_id["w2003"]["kind"] == "orchard" and v_by_id["w2003"]["density"] == 0.5


# Critère 5 : reproductibilité octet pour octet avec le cache et --offline -------------------------


def test_offline_cache_byte_for_byte_identical(fake_overpass, make_gpx, tmp_path):
    x, z, alt = straight_north(length=2000.0)
    gpx = make_gpx("repro.gpx", x, z, alt)

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    assert run("build", gpx, "--out", out1, "--layers", "route,terrain,buildings,vegetation") == 0
    calls_after_first = len(fake_overpass.calls)
    assert calls_after_first == 1

    # Seconde compilation avec --offline : aucun appel HTTP supplémentaire, fichiers identiques octet pour octet
    assert run("build", gpx, "--out", out2, "--layers", "route,terrain,buildings,vegetation", "--offline") == 0
    assert len(fake_overpass.calls) == calls_after_first

    w1 = out1 / "repro.world"
    w2 = out2 / "repro.world"
    for sub in ("buildings/chunk_0.json", "buildings/chunk_1.json", "vegetation/chunk_0.json", "vegetation/chunk_1.json"):
        assert (w1 / sub).read_bytes() == (w2 / sub).read_bytes()


def test_offline_without_cache_fails_cleanly(make_gpx, tmp_path):
    x, z, alt = straight_north(length=1000.0)
    gpx = make_gpx("nocache.gpx", x, z, alt)
    assert run("build", gpx, "--out", tmp_path / "out", "--layers", "route,buildings", "--offline") == 1


# Critère 6 : add-layer buildings ne touche ni route.json ni terrain ------------------------------


def test_add_layer_buildings_preserves_route_and_terrain(fake_overpass, make_gpx, tmp_path):
    x, z, alt = straight_north(length=2000.0)
    gpx = make_gpx("addlayer.gpx", x, z, alt)
    out_dir = tmp_path / "routes"

    assert run("build", gpx, "--out", out_dir) == 0
    world = out_dir / "addlayer.world"
    assert not (world / "buildings").exists()

    route_sha_before = sha256_file(world / "route.json")
    terrain_shas_before = {
        p.relative_to(world): sha256_file(p)
        for p in sorted((world / "terrain").rglob("*.f32"))
    }

    assert run("add-layer", world, "buildings") == 0
    assert (world / "buildings" / "chunk_0.json").is_file()
    assert run("verify", world) == 0

    assert sha256_file(world / "route.json") == route_sha_before
    terrain_shas_after = {
        p.relative_to(world): sha256_file(p)
        for p in sorted((world / "terrain").rglob("*.f32"))
    }
    assert terrain_shas_after == terrain_shas_before


# Critère 7 : verify rejette un chunk dont un anneau est horaire ----------------------------------


def test_verify_rejects_clockwise_outer_ring(fake_overpass, make_gpx, tmp_path, capsys):
    x, z, alt = straight_north(length=2000.0)
    gpx = make_gpx("badring.gpx", x, z, alt)
    out_dir = tmp_path / "routes"
    assert run("build", gpx, "--out", out_dir, "--layers", "route,buildings") == 0
    world = out_dir / "badring.world"
    assert run("verify", world) == 0

    chunk0_path = world / "buildings" / "chunk_0.json"
    chunk0 = json.loads(chunk0_path.read_text(encoding="utf-8"))
    chunk0["buildings"][0]["outer"].reverse()  # rend l'anneau extérieur horaire
    chunk0_path.write_text(json.dumps(chunk0), encoding="utf-8")

    assert run("verify", world) == 1
    out = capsys.readouterr().out
    assert "non antihoraire" in out


# Critère 8 : test réseau réel Overpass (désélectionné par défaut) --------------------------------


@pytest.mark.network
def test_overpass_real_network_small_bbox(tmp_path):
    """Interroge réellement Overpass sur une toute petite boîte autour du Bourg-d'Oisans."""
    client = OverpassClient(cache_dir=tmp_path / "osm_net_cache", offline=False)
    bbox = (45.0550, 6.0280, 45.0570, 6.0310)
    resp = client.fetch_bbox(bbox)
    assert isinstance(resp, dict)
    assert "elements" in resp
    assert len(list((tmp_path / "osm_net_cache").glob("*.json"))) == 1
