"""Parcours de démonstration des biomes (lot U19) : `engine/tests/make_biome_world.py` et `openride-core demo-biomes`.

Parts des biomes du tour (10 à 25 %), somme des poids 255 en chaque point, un tiers non revêtu avec
`--gravel`, côte et mer avec `--sea`, validité (`verify` du compilateur et schémas), coordonnées au degré
entier, deux générations identiques au bit près.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("openride_compiler")
jsonschema = pytest.importorskip("jsonschema")

from openride_compiler.verify import verify_world  # noqa: E402

from openride_core.__main__ import main  # noqa: E402
from openride_core.demo_world import write_biome_demo_worlds  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "engine" / "tests" / "make_biome_world.py"
SCHEMAS = REPO / "docs" / "contracts" / "world"


def _load():
    spec = importlib.util.spec_from_file_location("make_biome_world", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mbw():
    return _load()


@pytest.fixture(scope="module")
def demo_set(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("demo-biomes")
    write_biome_demo_worlds(out)
    return out


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_demo_set_four_valid_worlds(demo_set: Path) -> None:
    names = sorted(p.name for p in demo_set.glob("*.world"))
    assert names == ["demo-biomes-alpin.world", "demo-biomes-cote.world", "demo-biomes-gravel.world",
                     "demo-biomes-tour.world"]
    for world in demo_set.glob("*.world"):
        assert verify_world(world) == [], world.name
        manifest = _json(world / "manifest.json")
        jsonschema.validate(manifest, _schema("manifest"))
        jsonschema.validate(_json(world / "route.json"), _schema("route"))
        assert manifest["format_version"] == "1.6"
        biome = manifest["layers"]["biome"]
        assert biome["present"] and biome["forced"] is None and biome["tiles"] == manifest["layers"]["terrain"]["tiles"]
        tile_schema = _schema("biome")
        for level in ("near", "far"):
            files = sorted((world / "biome" / level).glob("tile_*.json"))
            assert len(files) == len(biome["tiles"][level])
            for f in files:
                tile = _json(f)
                jsonschema.validate(tile, tile_schema)
                assert len(tile["weights"]) == len(tile["biomes"])
                assert all(sum(g[i] for g in tile["weights"]) == 255 for i in range(289)), f.name


def test_tour_shares_between_10_and_25(demo_set: Path, mbw) -> None:
    shares = _json(demo_set / "demo-biomes-tour.world" / "manifest.json")["layers"]["biome"]["shares"]
    assert set(shares) == set(mbw.TOUR)
    assert all(10.0 <= v <= 25.0 for v in shares.values()), shares
    assert sum(shares.values()) == pytest.approx(100.0, abs=0.5)
    single = _json(demo_set / "demo-biomes-alpin.world" / "manifest.json")["layers"]["biome"]
    assert single["shares"] == {"alpine": 100.0} and single["default_biome"] == "alpine"


def test_gravel_one_third_unpaved(demo_set: Path) -> None:
    world = demo_set / "demo-biomes-gravel.world"
    route = _json(world / "route.json")
    unpaved = sum(1 for v in route["surface"] if v in ("gravel", "dirt")) / route["n"]
    assert abs(unpaved - 1.0 / 3.0) <= 0.05, unpaved
    assert {"gravel", "dirt"} <= set(route["surface"])
    manifest = _json(world / "manifest.json")
    assert manifest["route"]["surface_source"] == "osm"
    assert manifest["stats"]["surface_pct"]["paved"] == pytest.approx(100.0 * (1 - unpaved), abs=0.2)
    assert "surface" not in _json(demo_set / "demo-biomes-tour.world" / "route.json")


def test_sea_coast_layer_and_sea_areas(demo_set: Path) -> None:
    world = demo_set / "demo-biomes-cote.world"
    manifest = _json(world / "manifest.json")
    coast = manifest["layers"]["coast"]
    assert coast["present"] and coast["lines_count"] >= 6 and coast["beaches_count"] >= 1
    for f in sorted((world / "coast").glob("chunk_*.json")):
        jsonschema.validate(_json(f), _schema("coast"))
    seas = [a for f in (world / "water").glob("chunk_*.json") for a in _json(f)["areas"] if a["kind"] == "sea"]
    assert seas and all(a["level_y"] == 0.0 for a in seas)
    assert manifest["layers"]["water"]["areas_count"] == len(seas)
    assert "coast" not in _json(demo_set / "demo-biomes-tour.world" / "manifest.json")["layers"]


def test_integer_degree_coordinates_in_repo(mbw) -> None:
    assert all(float(v).is_integer() for v in mbw.ORIGIN)
    text = SCRIPT.read_text(encoding="utf-8")
    decimals = re.findall(r"\b\d{1,2}\.\d{3,}\b", text)
    assert decimals == [], decimals


def test_two_generations_are_identical(tmp_path: Path, mbw) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    mbw.generate(a, "biomes-tour", mbw.TOUR, gravel=True, sea=True)
    mbw.generate(b, "biomes-tour", mbw.TOUR, gravel=True, sea=True)
    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    assert files_a == sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert all((a / f).read_bytes() == (b / f).read_bytes() for f in files_a)
    assert verify_world(a / "biomes-tour.world") == []


def test_unknown_biome_refused(tmp_path: Path, mbw) -> None:
    with pytest.raises(ValueError, match="premier jalon"):
        mbw.generate(tmp_path, "x", ("volcanic",))
    with pytest.raises(SystemExit):
        mbw.main(["--out", str(tmp_path), "--biome", "volcanic"])


def test_cli_demo_biomes(tmp_path: Path, capsys) -> None:
    assert main(["demo-biomes", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "demo-biomes-tour : " in out and "non revêtu 33 %" in out
    assert len(list(tmp_path.glob("*.world"))) == 4
