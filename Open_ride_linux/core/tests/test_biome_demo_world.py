"""Parcours de démonstration des biomes (lots U19 et O37) : `openride_compiler.demo_biomes`, sa ligne de commande
des essais de l'engine `engine/tests/make_biome_world.py` et `openride-core demo-biomes`.

Parts des biomes du tour (10 à 25 %), somme des poids 255 en chaque point, un tiers non revêtu avec
`--gravel`, côte et mer avec `--sea`, validité (`verify` du compilateur et schémas), coordonnées au degré
entier, deux générations identiques au bit près. Lot O37 : noms de parcours et de lieux du jeu de base, variante
de recette aux noms techniques, démonstrations d'avant le lot O37 remplacées à l'installation. Lot O38 : le circuit
de démonstration (boucle fermée de 3 km) et une course du Grand Prix des objets en tours dessus.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

pytest.importorskip("openride_compiler")
jsonschema = pytest.importorskip("jsonschema")

from openride_compiler.verify import verify_world  # noqa: E402

from openride_core.__main__ import main  # noqa: E402
from openride_core import contents  # noqa: E402
from openride_core.demo_world import biome_demo_outdated, write_biome_demo_worlds  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "engine" / "tests" / "make_biome_world.py"
GENERATOR = REPO / "compiler" / "src" / "openride_compiler" / "demo_biomes.py"
FAKE_OSM = REPO / "compiler" / "src" / "openride_compiler" / "fake_osm.py"
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


@pytest.fixture(scope="module")
def recette_set(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("demo-biomes-recette")
    write_biome_demo_worlds(out, recette=True)
    return out


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_demo_set_valid_worlds(demo_set: Path, recette_set: Path) -> None:
    """Jeu de base : quatre parcours (le tour gravel retiré le 9 novembre, le circuit ajouté par le lot O38) ;
    recette : les cinq."""
    names = sorted(p.name for p in demo_set.glob("*.world"))
    assert names == ["demo-biomes-alpin.world", "demo-biomes-cote.world", "demo-biomes-tour.world",
                     "demo-circuit.world"]
    assert sorted(p.name for p in recette_set.glob("*.world")) == sorted(names + ["demo-biomes-gravel.world"])
    for world in [*demo_set.glob("*.world"), recette_set / "demo-biomes-gravel.world"]:
        assert verify_world(world) == [], world.name
        manifest = _json(world / "manifest.json")
        jsonschema.validate(manifest, _schema("manifest"))
        jsonschema.validate(_json(world / "route.json"), _schema("route"))
        assert manifest["format_version"] == "1.6"
        biome = manifest["layers"]["biome"]
        terrain_tiles = manifest["layers"]["terrain"]["tiles"]   # niveau horizon (1.8) : sans couche biome
        assert biome["present"] and biome["forced"] is None
        assert biome["tiles"] == {lv: terrain_tiles[lv] for lv in ("near", "far")}
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


def test_gravel_one_third_unpaved(demo_set: Path, recette_set: Path) -> None:
    world = recette_set / "demo-biomes-gravel.world"
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
    for path in (SCRIPT, GENERATOR, FAKE_OSM):
        decimals = re.findall(r"\b\d{1,2}\.\d{3,}\b", path.read_text(encoding="utf-8"))
        assert decimals == [], (path.name, decimals)


def test_game_set_has_route_names_and_no_test_labels(demo_set: Path, mbw) -> None:
    """Lot O37 : nom de parcours au menu, aucun « Fictif » ni nom technique dans les fichiers livrés."""
    titles = {name: title for name, title, *_, base in mbw.DEMO_SET if base}
    assert titles == {"demo-biomes-tour": "Tour des six paysages", "demo-biomes-cote": "Route de la côte",
                      "demo-biomes-alpin": "Montée alpine", "demo-circuit": "Circuit des Prés"}
    assert mbw.RETIRED_DEMOS == ("demo-biomes-gravel",) and not (demo_set / "demo-biomes-gravel.world").exists()
    for name, title in titles.items():
        world = demo_set / f"{name}.world"
        manifest = _json(world / "manifest.json")
        assert manifest["name"] == title and manifest["compiler"]["name"] == "openride-demo-biomes"
        for f in world.rglob("*.json"):
            text = f.read_text(encoding="utf-8")
            assert "Fictif" not in text and "Fictive" not in text and "make_biome_world" not in text, f
    assert _json(demo_set / "demo-biomes-alpin.json")["name"] == "Montée alpine"


def test_place_names_per_block(mbw) -> None:
    alpin = mbw.Plan(("alpine",) * 3, False, False)
    assert [alpin.place("col", i) for i in range(3)] == [
        "Belvédère des Marmottes", "Belvédère du Glacier", "Col des Edelweiss"]   # le sommet au dernier bloc
    assert [alpin.place("port", i) for i in range(2)] == ["Port-Lanterne", "Anse aux Mouettes"]
    tour = mbw.Plan(mbw.TOUR, False, False)
    assert tour.place("col", len(mbw.TOUR) - 1) == "Col des Edelweiss"
    assert mbw.Plan(mbw.TOUR, False, False, recette=True).place("col", 5) == "Col Fictif"


def test_recette_variant_keeps_technical_names(tmp_path: Path) -> None:
    infos = write_biome_demo_worlds(tmp_path, recette=True)
    assert [i["name"] for i in infos] == [i["route"] for i in infos]
    for info in infos:
        assert _json(tmp_path / f"{info['route']}.world" / "manifest.json")["name"] == info["route"]
    texts = "".join(f.read_text(encoding="utf-8") for f in (tmp_path / "demo-biomes-alpin.world" / "poi").glob("*.json"))
    assert "Col Fictif" in texts


def test_outdated_demos_replaced_at_install(tmp_path: Path, demo_set: Path, recette_set: Path) -> None:
    """Une démonstration écrite avant le lot O37 (`make_biome_world`) est remplacée, le tour gravel d'avant lui
    enlevé ; un parcours du joueur au même identifiant, jamais."""
    routes = tmp_path / "routes"
    shutil.copytree(demo_set / "demo-biomes-tour.world", routes / "demo-biomes-tour.world")
    old = routes / "demo-biomes-tour.world" / "manifest.json"
    manifest = _json(old)
    manifest.update(name="demo-biomes-tour", compiler={"name": "make_biome_world", "version": "2.0.0"})
    old.write_text(json.dumps(manifest), encoding="utf-8")
    mine = routes / "demo-biomes-alpin.world"
    mine.mkdir(parents=True)
    (mine / "manifest.json").write_text(json.dumps({"name": "Mon alpin", "compiler": {"name": "openride-compiler"}}),
                                        encoding="utf-8")
    gravel = routes / "demo-biomes-gravel.world"
    shutil.copytree(recette_set / "demo-biomes-gravel.world", gravel)
    (gravel / "manifest.json").write_text(json.dumps({**_json(gravel / "manifest.json"),
                                                      "compiler": {"name": "make_biome_world"}}), encoding="utf-8")
    assert biome_demo_outdated(routes / "demo-biomes-tour.world") and not biome_demo_outdated(mine)
    written, note = contents.install_biome_demos(routes)
    assert note == "" and sorted(written) == ["demo-biomes-cote", "demo-biomes-tour", "demo-circuit"]
    assert not gravel.exists()
    assert _json(old)["name"] == "Tour des six paysages"
    assert _json(mine / "manifest.json")["name"] == "Mon alpin"


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
    assert "demo-biomes-tour (Tour des six paysages) : " in out and "demo-biomes-gravel" not in out
    assert "demo-circuit (Circuit des Prés) : " in out
    assert len(list(tmp_path.glob("*.world"))) == 4


def test_circuit_loop(demo_set: Path, mbw) -> None:
    """Lot O38 : boucle fermée de 3 km (le compilateur la reconnaît), pente de −6 à +6 %, montée de 30 à 50 m par
    tour, un seul biome, pas de virage plus serré que 40 m, l'autre rive de la boucle à plus de 400 m."""
    import numpy as np
    from openride_compiler.fake_osm import LoopRoad
    from openride_core.route import load_world

    world = demo_set / "demo-circuit.world"
    route = _json(world / "route.json")
    assert route["type"] == "loop" and _json(world / "manifest.json")["route"]["type"] == "loop"
    assert route["length_m"] == pytest.approx(mbw.CIRCUIT_M, abs=5.0)
    assert (route["x"][0], route["z"][0], route["alt_m"][0]) == (route["x"][-1], route["z"][-1], route["alt_m"][-1])
    assert -6.0 <= min(route["grade_pct"]) and max(route["grade_pct"]) <= 6.0
    climb = sum(max(b - a, 0.0) for a, b in zip(route["alt_m"], route["alt_m"][1:]))
    assert 30.0 <= climb <= 50.0, climb
    assert _json(world / "manifest.json")["layers"]["biome"]["shares"] == {mbw.CIRCUIT_BIOME: 100.0}
    loaded = load_world(world).route
    assert loaded.is_loop and loaded.length_m == pytest.approx(route["length_m"])
    road = LoopRoad(mbw.CIRCUIT_M, mbw.CIRCUIT_LOBES)
    assert road.radius_min() >= 40.0
    pts = np.column_stack((road._x[:-1], road._z[:-1]))
    far = [np.hypot(*(pts[i] - pts[j])) for i in range(0, len(pts), 25) for j in range(0, len(pts), 25)
           if min(abs(i - j), len(pts) - abs(i - j)) * road.STEP > 700.0]
    assert min(far) > 400.0
    assert _json(demo_set / "demo-circuit.json")["generated"]["water_areas"] == 1   # l'étang de l'intérieur


def test_circuit_grand_prix_in_laps(demo_set: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lot O38 : le Grand Prix des objets se court en tours sur le circuit livré (recette GP11, étape 3)."""
    from openride_core import fit_export, profile
    from openride_core.config import Config
    from openride_core.input_providers import NullProvider
    from openride_core.mock_driver import MockDriver
    from openride_core.session import CoreSession

    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "profile.json")
    shutil.copytree(demo_set / "demo-circuit.world", tmp_path / "routes" / "demo-circuit.world")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = 6880, 6881
    cfg.grandprix.opponents, cfg.grandprix.laps = 2, 2
    s = CoreSession(cfg, driver=MockDriver(base_power_w=200.0, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes",
                    workouts_dir=tmp_path / "Workouts", records_path=tmp_path / "records.json",
                    powerups_path=tmp_path / "powerups.toml", wtf_path=tmp_path / "wtf.toml",
                    grandprix_path=tmp_path / "grandprix.toml")
    errors: list = []
    s.server.send_raw = lambda m, max_size=None: None
    s.server.send_error = lambda code, msg: errors.append((code, msg))
    s.server.send_input_event = lambda ev: None
    s._on_command("select_route", {"route_id": "demo-circuit"}, 1)
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors and s.state.session_state == "RUNNING"
    gp = s.grandprix
    assert gp.lap_m == pytest.approx(s.route.length_m) and gp.length_m == pytest.approx(2 * s.route.length_m)
    in_lap = [round((r - gp.origin_m) % gp.lap_m, 1) for r in gp.boxes.rows]
    assert in_lap and len(in_lap) == 2 * len(set(in_lap))   # mêmes rangées de boîtes à chaque tour
