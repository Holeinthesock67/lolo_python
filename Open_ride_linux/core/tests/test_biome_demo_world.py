"""Parcours de démonstration des biomes (lots U19 et O37) : `openride_compiler.demo_biomes`, sa ligne de commande
des essais de l'engine `engine/tests/make_biome_world.py` et `openride-core demo-biomes`.

Parts des biomes du tour (10 à 25 %), somme des poids 255 en chaque point, un tiers non revêtu avec
`--gravel`, côte et mer avec `--sea`, validité (`verify` du compilateur et schémas), coordonnées au degré
entier, deux générations identiques au bit près. Lot O37 : noms de parcours et de lieux du jeu de base, variante
de recette aux noms techniques, démonstrations d'avant le lot O37 remplacées à l'installation. Lot O38 : le circuit
de démonstration (boucle fermée de 3 km) et une course du Grand Prix des objets en tours dessus. Lot DB1 : le
tour des nouveaux paysages (sept blocs, variante régionale par bloc) remplace au jeu de base le tour des six
paysages, la route de la côte et la montée alpine, gardés en recette et jamais enlevés chez un joueur.
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
    """Jeu de base : le tour des nouveaux paysages et le circuit (lots O38 et DB1) ; recette : en plus les
    parcours sortis du jeu de base (tour gravel le 9 novembre ; tour, côte et alpin au lot DB1)."""
    names = sorted(p.name for p in demo_set.glob("*.world"))
    assert names == ["demo-biomes-paysages.world", "demo-circuit.world", "demo-volcan.world"]
    retired = ["demo-biomes-alpin.world", "demo-biomes-cote.world", "demo-biomes-gravel.world",
               "demo-biomes-tour.world"]
    assert sorted(p.name for p in recette_set.glob("*.world")) == sorted(names + retired)
    for world in [*demo_set.glob("*.world"), *(recette_set / n for n in retired)]:
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


def test_tour_shares_between_10_and_25(recette_set: Path, mbw) -> None:
    shares = _json(recette_set / "demo-biomes-tour.world" / "manifest.json")["layers"]["biome"]["shares"]
    assert set(shares) == set(mbw.TOUR)
    assert all(10.0 <= v <= 25.0 for v in shares.values()), shares
    assert sum(shares.values()) == pytest.approx(100.0, abs=0.5)
    single = _json(recette_set / "demo-biomes-alpin.world" / "manifest.json")["layers"]["biome"]
    assert single["shares"] == {"alpine": 100.0} and single["default_biome"] == "alpine"


def test_gravel_one_third_unpaved(recette_set: Path) -> None:
    world = recette_set / "demo-biomes-gravel.world"
    route = _json(world / "route.json")
    unpaved = sum(1 for v in route["surface"] if v in ("gravel", "dirt")) / route["n"]
    assert abs(unpaved - 1.0 / 3.0) <= 0.05, unpaved
    assert {"gravel", "dirt"} <= set(route["surface"])
    manifest = _json(world / "manifest.json")
    assert manifest["route"]["surface_source"] == "osm"
    assert manifest["stats"]["surface_pct"]["paved"] == pytest.approx(100.0 * (1 - unpaved), abs=0.2)
    assert "surface" not in _json(recette_set / "demo-biomes-tour.world" / "route.json")


def test_sea_coast_layer_and_sea_areas(recette_set: Path) -> None:
    world = recette_set / "demo-biomes-cote.world"
    manifest = _json(world / "manifest.json")
    coast = manifest["layers"]["coast"]
    assert coast["present"] and coast["lines_count"] >= 6 and coast["beaches_count"] >= 1
    for f in sorted((world / "coast").glob("chunk_*.json")):
        jsonschema.validate(_json(f), _schema("coast"))
    seas = [a for f in (world / "water").glob("chunk_*.json") for a in _json(f)["areas"] if a["kind"] == "sea"]
    assert seas and all(a["level_y"] == 0.0 for a in seas)
    assert manifest["layers"]["water"]["areas_count"] == len(seas)
    assert "coast" not in _json(recette_set / "demo-biomes-tour.world" / "manifest.json")["layers"]


def test_integer_degree_coordinates_in_repo(mbw) -> None:
    assert all(float(v).is_integer() for v in mbw.ORIGIN)
    for path in (SCRIPT, GENERATOR, FAKE_OSM):
        decimals = re.findall(r"\b\d{1,2}\.\d{3,}\b", path.read_text(encoding="utf-8"))
        assert decimals == [], (path.name, decimals)


def test_game_set_has_route_names_and_no_test_labels(demo_set: Path, mbw) -> None:
    """Lot O37 : nom de parcours au menu, aucun « Fictif » ni nom technique dans les fichiers livrés."""
    titles = {name: title for name, title, *_, base in mbw.DEMO_SET if base}
    assert titles == {"demo-biomes-paysages": "Tour des nouveaux paysages", "demo-circuit": "Circuit des Prés",
                      "demo-volcan": "Volcan en flammes"}
    assert mbw.RETIRED_DEMOS == ("demo-biomes-tour", "demo-biomes-gravel", "demo-biomes-cote", "demo-biomes-alpin")
    assert not any((demo_set / f"{n}.world").exists() for n in mbw.RETIRED_DEMOS)
    for name, title in titles.items():
        world = demo_set / f"{name}.world"
        manifest = _json(world / "manifest.json")
        assert manifest["name"] == title and manifest["compiler"]["name"] == "openride-demo-biomes"
        for f in world.rglob("*.json"):
            text = f.read_text(encoding="utf-8")
            assert "Fictif" not in text and "Fictive" not in text and "make_biome_world" not in text, f
    assert _json(demo_set / "demo-biomes-paysages.json")["name"] == "Tour des nouveaux paysages"


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
    """Une démonstration du jeu de base écrite avant le lot O37 (`make_biome_world`) est remplacée, une
    démonstration sortie du jeu de base et d'avant lui enlevée ; un parcours du joueur au même identifiant, jamais.
    Lot DB1 : le tour, la côte et l'alpin écrits par le lot O37 restent installés chez le joueur, tels quels."""
    routes = tmp_path / "routes"
    shutil.copytree(demo_set / "demo-circuit.world", routes / "demo-circuit.world")
    old = routes / "demo-circuit.world" / "manifest.json"
    manifest = _json(old)
    manifest.update(name="demo-circuit", compiler={"name": "make_biome_world", "version": "2.0.0"})
    old.write_text(json.dumps(manifest), encoding="utf-8")
    mine = routes / "demo-biomes-paysages.world"
    mine.mkdir(parents=True)
    (mine / "manifest.json").write_text(json.dumps({"name": "Mes paysages", "compiler": {"name": "openride-compiler"}}),
                                        encoding="utf-8")
    gravel = routes / "demo-biomes-gravel.world"
    shutil.copytree(recette_set / "demo-biomes-gravel.world", gravel)
    (gravel / "manifest.json").write_text(json.dumps({**_json(gravel / "manifest.json"),
                                                      "compiler": {"name": "make_biome_world"}}), encoding="utf-8")
    kept = {}
    for n in ("demo-biomes-tour", "demo-biomes-cote", "demo-biomes-alpin"):   # installés par le lot O37
        shutil.copytree(recette_set / f"{n}.world", routes / f"{n}.world")
        f = routes / f"{n}.world" / "manifest.json"
        f.write_text(json.dumps({**_json(f), "compiler": {"name": "openride-demo-biomes", "version": "1"}}),
                     encoding="utf-8")
        kept[n] = f.read_bytes()
    assert biome_demo_outdated(routes / "demo-circuit.world") and not biome_demo_outdated(mine)
    written, note = contents.install_biome_demos(routes)
    assert note == "" and written == ["demo-circuit", "demo-volcan"]
    assert not gravel.exists()
    assert _json(old)["name"] == "Circuit des Prés"
    assert _json(mine / "manifest.json")["name"] == "Mes paysages"
    assert all((routes / f"{n}.world" / "manifest.json").read_bytes() == b for n, b in kept.items())


def test_two_generations_are_identical(tmp_path: Path, mbw) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    mbw.generate(a, "biomes-tour", mbw.TOUR, gravel=True, sea=True)
    mbw.generate(b, "biomes-tour", mbw.TOUR, gravel=True, sea=True)
    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    assert files_a == sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert all((a / f).read_bytes() == (b / f).read_bytes() for f in files_a)
    assert verify_world(a / "biomes-tour.world") == []


def test_unknown_biome_refused(tmp_path: Path, mbw) -> None:
    with pytest.raises(ValueError, match="sans décor de démonstration : volcanic"):
        mbw.generate(tmp_path, "x", ("volcanic",))
    with pytest.raises(SystemExit):
        mbw.main(["--out", str(tmp_path), "--biome", "volcanic"])


def test_cli_demo_biomes(tmp_path: Path, capsys) -> None:
    assert main(["demo-biomes", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "demo-biomes-paysages (Tour des nouveaux paysages) : 14.2 km" in out and "demo-biomes-gravel" not in out
    assert "demo-circuit (Circuit des Prés) : " in out and "demo-biomes-tour" not in out
    assert "demo-volcan (Volcan en flammes) : 8.0 km" in out
    assert len(list(tmp_path.glob("*.world"))) == 3


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


def test_volcan_loop(demo_set: Path, mbw) -> None:
    """Volcan en flammes (13 novembre) : boucle fermée de 8 km dans le paysage `volcan_actif` (toutes les tuiles),
    pente d'au plus 10 %, une montée de 200 à 240 m jusqu'à la crête du cratère à mi-boucle, cratère creusé à côté
    de la route (à l'intérieur de la boucle), relief borné jusqu'à l'horizon, pas de mur au départ."""
    import numpy as np

    world = demo_set / "demo-volcan.world"
    route = _json(world / "route.json")
    manifest = _json(world / "manifest.json")
    assert route["type"] == "loop" and route["length_m"] == pytest.approx(mbw.VOLCAN_M, abs=5.0)
    assert manifest["layers"]["biome"]["shares"] == {"volcanic": 100.0}
    assert max(abs(g) for g in route["grade_pct"]) <= 10.0
    alt = np.array(route["alt_m"])
    climb = float(np.clip(np.diff(alt), 0.0, None).sum())
    assert 200.0 <= climb <= 240.0, climb
    top = int(np.argmax(alt))
    assert abs(top * route["ds_m"] - route["length_m"] / 2.0) < 400.0, top
    for level in ("near", "far"):
        for tile in (world / "biome" / level).glob("*.json"):
            assert _json(tile)["variant"] == mbw.VOLCAN_VARIANT, tile.name
    plan = mbw.Plan(("volcanic",), False, False, circuit="volcan")
    terrain = mbw.make_terrain(plan)
    px, pz = plan.road.xz(plan.length_m / 2.0)
    cx, cz = mbw.volcano_crater(plan.road)
    rim = float(terrain(np.array([px]), np.array([pz]))[0])
    crater = float(terrain(np.array([cx]), np.array([cz]))[0])
    assert crater < rim - 60.0, (crater, rim)
    far = terrain(np.linspace(-40000.0, 40000.0, 81), np.linspace(40000.0, -40000.0, 81))
    assert float(np.max(np.abs(far))) < 400.0
    # Départ : terrain à 200 m de part et d'autre à moins de 40 m de la route (pas de mur dans la plaine)
    sx, sz = plan.road.xz(0.0)
    hx, hz = plan.road.heading(0.0)
    sides = terrain(np.array([sx - hz * 200.0, sx + hz * 200.0]), np.array([sz + hx * 200.0, sz - hx * 200.0]))
    assert float(np.max(np.abs(sides - route["alt_m"][0]))) < 40.0, sides


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


def test_paysages_tour(demo_set: Path, mbw) -> None:
    """Lot DB1 : sept blocs de 2 km, un par biome ou paysage de la 6.0, un septième chacun ; chaque tuile proche
    porte la variante (sol, toits, paysage du lot U25) de son bloc ; mer le long du fjord ; montée au sommet des
    hauts plateaux ; aucun paysage posé sur le biome du bloc voisin."""
    from openride_compiler.regional import LANDSCAPES

    world = demo_set / "demo-biomes-paysages.world"
    manifest = _json(world / "manifest.json")
    shares = manifest["layers"]["biome"]["shares"]
    assert list(shares) == list(mbw.PAYSAGES_BIOMES)
    assert {"atlantic_heath", "japan", "high_plateau"} <= set(shares)
    assert all(v == pytest.approx(100.0 / 7, abs=0.6) for v in shares.values()), shares
    landscapes = {landscape for _, landscape, *_ in mbw.PAYSAGES if landscape}
    assert landscapes == set(LANDSCAPES) - {"volcan_actif"}   # le volcan en feu a sa propre boucle
    seen = set()
    for f in (world / "biome" / "near").glob("tile_*.json"):
        tile = _json(f)
        iz = int(f.stem.split("_")[2])
        block = min(max(-iz - 1, 0) // 2, len(mbw.PAYSAGES) - 1)    # tuile de 1 km vers le nord : bloc de 2 km
        assert tile["variant"] == mbw.paysages_variants()[block], f.name
        if tile["variant"] and tile["variant"]["landscape"]:
            seen.add(tile["variant"]["landscape"])
    assert seen == landscapes
    theme = json.loads((REPO / "engine" / "themes" / "default" / "theme.json").read_text(encoding="utf-8"))
    for i, (biome, landscape, *_) in enumerate(mbw.PAYSAGES):
        bases = theme["landscapes"][landscape]["biomes"] if landscape else {}
        assert not landscape or biome in bases
        for j in (i - 1, i + 1):
            if 0 <= j < len(mbw.PAYSAGES):
                assert mbw.PAYSAGES[j][0] not in bases, (landscape, mbw.PAYSAGES[j][0])
    assert manifest["layers"]["coast"]["present"]
    route = _json(world / "route.json")
    assert route["length_m"] == pytest.approx(7 * mbw.BLOCK_M, rel=0.02)
    assert max(route["grade_pct"]) <= 8.0 and min(route["grade_pct"]) >= -4.0
    top = max(range(route["n"]), key=lambda i: route["alt_m"][i])
    assert top * route["ds_m"] > 6 * mbw.BLOCK_M and route["alt_m"][top] - route["alt_m"][0] >= 200.0
    pois = "".join(f.read_text(encoding="utf-8") for f in (world / "poi").glob("*.json"))
    assert "Col des Lamas" in pois and "Belvédère du Canyon Rouge" in pois
    info = _json(demo_set / "demo-biomes-paysages.json")
    assert info["coast"]["sea_areas"] > 0 and info["generated"]["buildings"] > 0


def test_far_relief_bounded(demo_set: Path, recette_set: Path) -> None:
    """Lot DB1 (banc r866, ciel zébré) : le relief lointain des démonstrations reste un paysage de collines et de
    montagnes jusqu'à l'horizon (40 km), au plus 600 m au-dessus du point le plus haut de la route ; plus bas, seule
    la courbure terrestre de l'horizon (au plus 400 m à 57 km)."""
    np = pytest.importorskip("numpy")
    worlds = sorted(demo_set.glob("*.world")) + sorted(recette_set.glob("*.world"))
    assert len(worlds) >= 7
    for world in worlds:
        alt = _json(world / "route.json")["alt_m"]
        for level in ("near", "far", "horizon"):
            tiles = [np.fromfile(f, dtype=np.float32) for f in (world / "terrain" / level).glob("*.f32")]
            assert tiles, (world.name, level)
            hi = max(float(t.max()) for t in tiles)
            lo = min(float(t.min()) for t in tiles)
            assert hi <= max(alt) + 600.0, (world.name, level, hi)
            assert lo >= min(min(alt), 0.0) - 25.0 - (400.0 if level == "horizon" else 0.0), (world.name, level, lo)


def test_decor_cyclists_never_touch(demo_set: Path, recette_set: Path) -> None:
    """Lot DB1 (banc r866, des milliers de contacts) : sur chaque démonstration, à 25, 40 et 50 km/h, aucun cycliste
    du décor n'en touche un autre (groupes différents) ni le cycliste (à moins de 1,7 m en long et 0,6 m en travers,
    comme le compte de `living_decor.gd`)."""
    import itertools

    from openride_core import road_cyclists as rc
    from openride_core.route import load_world

    worlds = sorted(demo_set.glob("demo-*.world")) + sorted(recette_set.glob("demo-biomes-*.world"))
    for world in worlds:
        route = load_world(world).route
        for kmh in (25.0, 40.0, 50.0):
            model = rc.RoadCyclists(route, rc.climbs_for(route, []), [], seed=rc.SEED)
            s, v, dt = 0.0, kmh / 3.6, 1.0 / 30.0
            while s < route.length_m - 50.0:
                model.update(s, v, dt)
                riders = model.state_list(s)
                for r in riders:
                    assert not (abs(r["s"] - s) < 1.7 and abs(r["lane_m"] - rc.RIDER_LATERAL_M) < 0.6), \
                        (world.name, kmh, round(s), r["id"])
                for a, b in itertools.combinations(riders, 2):
                    if a["id"].rsplit("-", 1)[0] != b["id"].rsplit("-", 1)[0]:
                        assert not (abs(a["s"] - b["s"]) < 1.7 and abs(a["lane_m"] - b["lane_m"]) < 0.6), \
                            (world.name, kmh, round(s), a["id"], b["id"])
                s += v * dt
