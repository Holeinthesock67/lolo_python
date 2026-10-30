"""Surface de la route d'après OSM (lot U20) : correspondance voie-trace par distance et cap, règles de
`surface` et `tracktype`, lissage des portions de moins de 50 m, colonne omise pour une trace revêtue,
`--no-surface`, parts dans `stats`, `verify`. Réseau coupé : réponses Overpass fabriquées."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from conftest import WORLD_CONTRACTS, straight_north, to_latlon
from openride_compiler import cli
from openride_compiler import surface as S
from openride_compiler.verify import verify_world


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


def way(wid: int, xz: list[tuple[float, float]], **tags) -> dict:
    lat, lon = to_latlon([p[0] for p in xz], [p[1] for p in xz])
    return {"type": "way", "id": wid, "tags": {"highway": "unclassified", **tags},
            "geometry": [{"lat": float(a), "lon": float(o)} for a, o in zip(lat, lon)]}


class FakeClient:
    """Client Overpass : les voies du couloir pour la requête de surface, rien pour les couches."""

    def __init__(self, ways: list[dict]) -> None:
        self.ways = ways
        self.queries: list[str] = []

    def fetch_query(self, query: str) -> dict:
        self.queries.append(query)
        surface_query = all('way["highway"](' in ln for ln in query.splitlines() if ln.startswith("  "))
        return {"elements": self.ways if surface_query else []}

    def fetch_for_route(self, route, frame) -> list[dict]:
        return [{"elements": []}]


def build(tmp_path: Path, monkeypatch, ways: list[dict], *extra: str, length: float = 3000.0) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    gpx = tmp_path / "trace.gpx"
    from conftest import write_gpx
    write_gpx(gpx, *straight_north(length=length))
    client = FakeClient(ways)
    monkeypatch.setattr(cli, "make_osm_client", lambda offline, log=None: client)
    out = tmp_path / "routes"
    assert run("build", gpx, "--out", out, "--force", "--layers", "route,buildings", *extra) == 0
    return out / "trace.world"


def _route(world: Path) -> dict:
    return json.loads((world / "route.json").read_text(encoding="utf-8"))


def _manifest(world: Path) -> dict:
    return json.loads((world / "manifest.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("tags, expected", [
    ({"surface": "asphalt"}, "paved"), ({"surface": "paving_stones"}, "paved"),
    ({"surface": "fine_gravel"}, "compacted"), ({"surface": "compacted"}, "compacted"),
    ({"surface": "pebblestone"}, "gravel"), ({"surface": "gravel"}, "gravel"),
    ({"surface": "ground"}, "dirt"), ({"surface": "sand"}, "dirt"), ({"surface": "mud"}, "dirt"),
    ({"highway": "track", "tracktype": "grade1"}, "paved"), ({"highway": "track", "tracktype": "grade2"}, "compacted"),
    ({"highway": "track", "tracktype": "grade3"}, "gravel"), ({"highway": "track", "tracktype": "grade5"}, "dirt"),
    ({"highway": "track"}, "gravel"), ({"highway": "residential"}, "paved"),
    ({"highway": "track", "surface": "asphalt", "tracktype": "grade4"}, "paved"),
])
def test_way_surface_rules(tags, expected) -> None:
    assert S.way_surface(tags) == expected


def test_smooth_merges_short_runs() -> None:
    v = ["paved"] * 20 + ["dirt"] * 3 + ["paved"] * 20
    assert S.smooth(v, 10.0) == ["paved"] * 43
    v = ["paved"] * 20 + ["gravel"] * 4 + ["dirt"] * 30
    assert S.smooth(v, 10.0) == ["paved"] * 20 + ["dirt"] * 34      # rattachée à la plus longue voisine
    v = ["dirt"] * 2 + ["gravel"] * 40
    assert S.smooth(v, 10.0) == ["gravel"] * 42                     # bord de la route
    assert S.smooth(["dirt"] * 3, 10.0) == ["dirt"] * 3              # une seule portion : gardée


def test_gravel_way_over_2km_and_perpendicular_way_ignored(tmp_path: Path, monkeypatch) -> None:
    gravel = way(1, [(0.0, -500.0), (0.0, -2500.0)], surface="gravel")
    # Voie de terre à 12 m de la trace, en dents de peigne d'est en ouest : cap perpendiculaire.
    ladder = [way(100 + k, [(5.0, -z), (20.0, -z)], surface="dirt") for k, z in enumerate(np.arange(50.0, 3000.0, 40.0))]
    world = build(tmp_path, monkeypatch, [gravel, *ladder])
    route = _route(world)
    s = np.arange(route["n"]) * route["ds_m"]
    on = [si for si, v in zip(s, route["surface"]) if v == "gravel"]
    assert abs((on[-1] - on[0] + route["ds_m"]) - 2000.0) <= 20.0
    assert abs(on[0] - 500.0) <= 20.0
    assert "dirt" not in route["surface"]
    manifest = _manifest(world)
    assert manifest["route"]["surface_source"] == "osm" and manifest["format_version"] == "1.6"
    pct = manifest["stats"]["surface_pct"]
    assert pct["gravel"] == pytest.approx(100.0 * len(on) / route["n"], abs=0.1)
    assert sum(pct.values()) == pytest.approx(100.0, abs=0.2)
    assert verify_world(world) == []
    jsonschema.validate(route, json.loads((WORLD_CONTRACTS / "route.schema.json").read_text(encoding="utf-8")))
    jsonschema.validate(manifest, json.loads((WORLD_CONTRACTS / "manifest.schema.json").read_text(encoding="utf-8")))


def test_paved_trace_has_no_column_and_same_route(tmp_path: Path, monkeypatch) -> None:
    asphalt = way(1, [(0.0, 10.0), (0.0, -3100.0)], surface="asphalt")
    world = build(tmp_path / "a", monkeypatch, [asphalt])
    before = build(tmp_path / "b", monkeypatch, [asphalt], "--no-surface")
    assert "surface" not in _route(world)
    assert (world / "route.json").read_bytes() == (before / "route.json").read_bytes()
    manifest = _manifest(world)
    assert "surface_source" not in manifest["route"] and "surface_pct" not in manifest["stats"]


def test_isolated_30m_dirt_attached_to_neighbours(tmp_path: Path, monkeypatch) -> None:
    ways = [way(1, [(0.0, 10.0), (0.0, -1500.0)], surface="gravel"),
            way(2, [(0.0, -1500.0), (0.0, -1530.0)], surface="dirt"),
            way(3, [(0.0, -1530.0), (0.0, -3100.0)], surface="gravel")]
    route = _route(build(tmp_path, monkeypatch, ways))
    assert set(route["surface"]) == {"gravel"}


def test_no_surface_option_skips_the_query(tmp_path: Path, monkeypatch) -> None:
    gravel = way(1, [(0.0, 10.0), (0.0, -3100.0)], surface="gravel")
    gpx = tmp_path / "trace.gpx"
    from conftest import write_gpx
    write_gpx(gpx, *straight_north(length=1000.0))
    client = FakeClient([gravel])
    monkeypatch.setattr(cli, "make_osm_client", lambda offline, log=None: client)
    assert run("build", gpx, "--out", tmp_path / "r", "--layers", "route,poi", "--no-surface") == 0
    assert client.queries == []
    assert "surface" not in _route(tmp_path / "r" / "trace.world")


def test_verify_rejects_bad_surface_column(tmp_path: Path, monkeypatch) -> None:
    world = build(tmp_path, monkeypatch, [way(1, [(0.0, 10.0), (0.0, -3100.0)], surface="dirt")])
    route = _route(world)
    route["surface"][3] = "sand"
    (world / "route.json").write_text(json.dumps(route), encoding="utf-8")
    assert any("surface" in p for p in verify_world(world))
    route["surface"] = route["surface"][:-1]
    (world / "route.json").write_text(json.dumps(route), encoding="utf-8")
    assert any("surface" in p for p in verify_world(world))
