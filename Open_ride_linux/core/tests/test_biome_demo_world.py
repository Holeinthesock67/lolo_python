"""Parcours de démonstration des biomes (lots U19 et O37) : `openride_compiler.demo_biomes`, sa ligne de commande
des essais de l'engine `engine/tests/make_biome_world.py` et `openride-core demo-biomes`.

Parts des biomes du tour (10 à 25 %), somme des poids 255 en chaque point, un tiers non revêtu avec
`--gravel`, côte et mer avec `--sea`, validité (`verify` du compilateur et schémas), coordonnées au degré
entier, deux générations identiques au bit près. Lot O37 : noms de parcours et de lieux du jeu de base, variante
de recette aux noms techniques, démonstrations d'avant le lot O37 remplacées à l'installation. Lot O38 : le circuit
de démonstration (boucle fermée de 3 km) et une course du Grand Prix des objets en tours dessus. Lot SM1 : le récif
sous la mer (boucle de 8 km, biome `reef`), sans circulation ni cyclistes du décor au core. Lot DB1 : le tour des
nouveaux paysages (sept blocs, variante régionale par bloc) remplace au jeu de base le tour des six paysages, la route
de la côte et la montée alpine, gardés en recette et jamais enlevés chez un joueur. Lot DJ1 : la route des Érables,
démonstration du biome Japon au jeu de base.
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
    """Jeu de base : le tour des nouveaux paysages, le circuit, le récif et le volcan (lots O38, SM1, DB1 et DB2) ;
    recette : en plus les parcours sortis du jeu de base (tour gravel le 9 novembre ; tour, côte et alpin au lot DB1)."""
    names = sorted(p.name for p in demo_set.glob("*.world"))
    assert names == ["demo-biomes-forets.world", "demo-biomes-nord.world", "demo-biomes-paysages.world", "demo-biomes-sud.world",
                     "demo-circuit.world", "demo-corniche.world", "demo-japon.world", "demo-recif.world",
                     "demo-vignes.world", "demo-volcan.world"]
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
    assert titles == {"demo-biomes-paysages": "Tour des nouveaux paysages", "demo-japon": "Route des Érables",
                      "demo-circuit": "Circuit des Prés", "demo-recif": "Récif des tortues",
                      "demo-volcan": "Volcan en flammes", "demo-biomes-sud": "Route du Sud",
                      "demo-biomes-nord": "Route du Grand Nord", "demo-corniche": "Boucle de la Corniche",
                      "demo-vignes": "Route des Vignes", "demo-biomes-forets": "Route des Trois Forêts"}
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


def test_game_set_has_library_fiche(demo_set: Path, mbw) -> None:
    """Lot NT1 : chaque démonstration du jeu de base porte sa fiche (description sur la carte du parcours au menu),
    valide pour le catalogue ; une démonstration d'avant sa fiche est remplacée, jamais un parcours du joueur."""
    from openride_core.route_stats import check_library

    assert sorted(mbw.DEMO_LIBRARY) == sorted(mbw.GAME_DEMOS)
    for name in mbw.GAME_DEMOS:
        world = demo_set / f"{name}.world"
        lib = _json(world / "manifest.json")["library"]
        assert lib == mbw.library_of(name) == check_library(lib), name
        assert 30 <= len(lib["description"]) <= 200 and lib["description"].endswith("."), name
        assert not biome_demo_outdated(world)
    copy = demo_set.parent / "nt1-avant-fiche" / "demo-japon.world"
    shutil.copytree(demo_set / "demo-japon.world", copy)
    manifest = _json(copy / "manifest.json")
    del manifest["library"]   # écrite avant le lot NT1
    (copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert biome_demo_outdated(copy)
    # « Contenus de départ » la compte comme manquante (en partie installé), pour proposer de la réécrire
    dirs = contents.ContentDirs(workouts=copy.parent / "w", plans=copy.parent / "p", routes=copy.parent)
    assert contents.starter_parts(dirs)["routes"][0] == 0
    shutil.rmtree(copy)
    shutil.copytree(demo_set / "demo-japon.world", copy)
    assert contents.starter_parts(dirs)["routes"][0] == 1


def test_place_names_per_block(mbw) -> None:
    alpin = mbw.Plan(("alpine",) * 3, False, False)
    assert [alpin.place("col", i) for i in range(3)] == [
        "Belvédère du Glacier", "Belvédère des Marmottes", "Col des Edelweiss"]   # le sommet au dernier bloc
    assert [alpin.place("port", i) for i in range(2)] == ["Port-Lanterne", "Anse aux Mouettes"]
    tour = mbw.Plan(mbw.TOUR, False, False)
    assert tour.place("col", len(mbw.TOUR) - 1) == "Col des Edelweiss"
    assert mbw.Plan(mbw.TOUR, False, False, recette=True).place("col", 5) == "Col Fictif"


def test_summit_name_only_at_the_end(mbw) -> None:
    """Lot DL1 : sur une route ouverte de vingt et un blocs `japan`, le nom du sommet n'est porté que par le dernier
    bloc ; les autres reprennent les noms suivants dans l'ordre ; un lieu ordinaire reprend sa liste au début."""
    plan = mbw.Plan(mbw.tour_blocks("japan")[0], False, False)
    n = len(plan.biomes)
    views = [plan.place("japon_vue", i) for i in range(n)]
    assert views[-1] == "Col des Cèdres" and views.count("Col des Cèdres") == 1
    assert views[:3] == list(mbw.PLACE_NAMES["japon_vue"][1:4])
    villages = mbw.PLACE_NAMES["japon"]
    assert [plan.place("japon", i) for i in range(n)] == [villages[i % len(villages)] for i in range(n)]
    tour = mbw.Plan(mbw.tour_blocks("paysages")[0], False, False)
    assert [tour.place("plateau", i) for i in range(len(tour.biomes) - 3, len(tour.biomes))] == [
        "Belvédère des Vigognes", "Belvédère de l'Altiplano", "Col des Lamas"]


def test_game_lines_at_least_40_km(mbw) -> None:
    """Lot DL1 : chaque route ouverte du jeu de base fait au moins 40 km, ses blocs de 2 km répétés à la suite dans
    l'ordre ; sa variante de recette (bancs) garde ses blocs d'avant, comme les boucles et les parcours de recette
    seuls ; le Col du lacet fait 40 km dans le jeu, 5 km en recette."""
    from openride_core import demo_world

    assert demo_world.DEMO_LENGTH_M >= mbw.LINE_MIN_M and demo_world.DEMO_RECETTE_LENGTH_M == 5000.0
    lines = [which for _n, _t, which, *_, base in mbw.DEMO_SET if base and which not in mbw.LOOPS]
    assert sorted(lines) == ["forets", "japan", "paysages", "sud"]
    for which in lines:
        biomes, variants = mbw.tour_blocks(which)
        short, short_variants = mbw.tour_blocks(which, recette=True)
        k = mbw.line_repeat(which, len(short))
        assert mbw.LINE_MIN_M <= len(biomes) * mbw.BLOCK_M < mbw.LINE_MIN_M + len(short) * mbw.BLOCK_M
        assert biomes == tuple(b for b in short for _ in range(k))
        assert variants == (None if short_variants is None else tuple(v for v in short_variants for _ in range(k)))
    assert {w: len(mbw.tour_blocks(w)[0]) for w in lines} == {"paysages": 21, "japan": 21, "sud": 24,
                                                          "forets": 21}
    assert {w: len(mbw.tour_blocks(w, recette=True)[0]) for w in lines} == {"paysages": 7, "japan": 3, "sud": 6,
                                                                        "forets": 3}
    for which in ("tour", "coast", "alpine", "nord", "circuit", "recif", "volcan"):
        assert mbw.tour_blocks(which) == mbw.tour_blocks(which, recette=True), which
    assert mbw.library_of("demo-biomes-sud")["description"].startswith("48 km ")
    assert mbw.library_of("demo-biomes-sud", recette=True)["description"].startswith("12 km ")


def test_recette_variant_stays_short(recette_set: Path, mbw) -> None:
    """Lot DL1 : la variante de recette des bancs garde les longueurs d'avant (14, 6 et 12 km) et sa fiche le dit ;
    elle n'est pas périmée pour les contenus de départ, et le Col du lacet de recette (5 km) n'est pas réécrit."""
    from openride_core import demo_world

    for name, km in (("demo-biomes-paysages", 14.0), ("demo-japon", 6.0), ("demo-biomes-sud", 12.0)):
        world = recette_set / f"{name}.world"
        assert _json(world / "route.json")["length_m"] == pytest.approx(km * 1000.0, rel=0.02), name
        assert _json(world / "manifest.json")["library"] == mbw.library_of(name, recette=True)
        assert not demo_world.biome_demo_outdated(world), name


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
    assert note == "" and sorted(written) == ["demo-biomes-forets", "demo-biomes-nord", "demo-biomes-sud", "demo-circuit", "demo-corniche",
                                                 "demo-japon", "demo-recif", "demo-vignes", "demo-volcan"]
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
    assert "demo-biomes-paysages (Tour des nouveaux paysages) : 42.5 km" in out and "demo-biomes-gravel" not in out
    assert "demo-circuit (Circuit des Prés) : " in out and "demo-recif (Récif des tortues) : " in out
    assert "demo-volcan (Volcan en flammes) : 8.0 km" in out and "demo-biomes-tour" not in out
    assert "demo-japon (Route des Érables) : 42.5 km" in out
    assert "demo-biomes-sud (Route du Sud) : 48.5 km" in out
    assert "demo-biomes-nord (Route du Grand Nord) : 10.0 km" in out
    assert "demo-corniche (Boucle de la Corniche) : 2.5 km" in out and "demo-vignes (Route des Vignes) : 5.0 km" in out
    assert "demo-biomes-forets (Route des Trois Forêts) : " in out
    assert len(list(tmp_path.glob("*.world"))) == 10


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
    """Volcan en flammes (lot DB2) : boucle fermée de 8 km dans le paysage `volcan_actif` (toutes les tuiles),
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
    plan = mbw.Plan(("volcanic",), False, False, loop="volcan")
    terrain = mbw.make_terrain(plan)
    px, pz = plan.road.xz(plan.length_m / 2.0)
    cx, cz = mbw.volcano_crater()
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
    """Lot DB1 : sept biomes ou paysages de la 6.0 (trois blocs de 2 km chacun depuis le lot DL1), un septième chacun ; chaque tuile proche
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
    # les quatre paysages du lot U25 (le volcan actif du lot DB2 a sa propre boucle, `demo-volcan`)
    assert landscapes == {"canyon", "fjord", "ile_volcanique", "rizieres"} and landscapes <= set(LANDSCAPES)
    seen = set()
    for f in (world / "biome" / "near").glob("tile_*.json"):
        tile = _json(f)
        iz = int(f.stem.split("_")[2])
        variants = mbw.paysages_variants()
        block = min(max(-iz - 1, 0) // 2, len(variants) - 1)    # tuile de 1 km vers le nord : bloc de 2 km
        assert tile["variant"] == variants[block], f.name
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
    assert route["length_m"] == pytest.approx(21 * mbw.BLOCK_M, rel=0.02)   # trois blocs par paysage (lot DL1)
    assert max(route["grade_pct"]) <= 8.0 and min(route["grade_pct"]) >= -4.0
    top = max(range(route["n"]), key=lambda i: route["alt_m"][i])
    assert top * route["ds_m"] > 18 * mbw.BLOCK_M and route["alt_m"][top] - route["alt_m"][0] >= 600.0
    pois = "".join(f.read_text(encoding="utf-8") for f in (world / "poi").glob("*.json"))
    assert "Col des Lamas" in pois and "Belvédère du Canyon Rouge" in pois
    info = _json(demo_set / "demo-biomes-paysages.json")
    assert info["coast"]["sea_areas"] > 0 and info["generated"]["buildings"] > 0


def test_far_relief_bounded(demo_set: Path, recette_set: Path) -> None:
    """Lot DB1 (banc r866, ciel zébré) : le relief lointain des démonstrations reste un paysage de collines et de
    montagnes jusqu'à l'horizon (40 km), au plus 600 m au-dessus du point le plus haut de la route ; plus bas, seule
    la courbure terrestre de l'horizon (lot JP4). Lot DB3 : la Route du Sud, plate au bout (delta), montre la courbure
    seule au coin le plus éloigné des tuiles d'horizon (−614 m, près de 90 km du départ), là où le relief des
    autres démonstrations la cache en partie : 700 m de marge au lieu de 400."""
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
            assert lo >= min(min(alt), 0.0) - 25.0 - (700.0 if level == "horizon" else 0.0), (world.name, level, lo)


def test_decor_cyclists_never_touch(demo_set: Path, recette_set: Path) -> None:
    """Lot DB1 (banc r866, des milliers de contacts) : sur chaque démonstration, à 25, 40 et 50 km/h, aucun cycliste
    du décor n'en touche un autre (groupes différents) ni le cycliste (à moins de 1,7 m en long et 0,6 m en travers,
    comme le compte de `living_decor.gd`)."""
    import itertools

    from openride_core import road_cyclists as rc
    from openride_core.route import load_world

    from openride_core import traffic

    worlds = sorted(demo_set.glob("demo-*.world")) + sorted(recette_set.glob("demo-biomes-*.world"))
    for world in worlds:
        if traffic.underwater_route(_json(world / "manifest.json")):
            continue                                    # récif sous la mer : aucun cycliste du décor (lot SM1)
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


def test_japon_demo(demo_set: Path, mbw) -> None:
    """Lot DJ1 : la route des Érables, 42 km dans le seul biome `japan` (vingt et un blocs, lot DL1), sol et toits d'une
    vraie route japonaise sur chaque tuile, montée douce (1 à 5 %, 1 200 à 1 600 m) jusqu'au « Col des Cèdres », villages et
    belvédères nommés, aucune mer ; installée sur un jeu neuf comme les autres démonstrations du jeu de base."""
    from openride_compiler.regional import variant_for

    assert mbw.BIOME_VARIANTS["japan"] == variant_for(35.0, 138.0, {"japan": 100.0})   # zones japon_* du compilateur
    world = demo_set / "demo-japon.world"
    manifest = _json(world / "manifest.json")
    assert manifest["name"] == "Route des Érables"
    assert manifest["layers"]["biome"]["shares"] == {"japan": 100.0}
    assert manifest["layers"]["biome"]["default_biome"] == "japan"
    assert "coast" not in manifest["layers"]
    tiles = [_json(f) for level in ("near", "far") for f in (world / "biome" / level).glob("tile_*.json")]
    assert tiles and all(t["variant"] == mbw.BIOME_VARIANTS["japan"] for t in tiles)
    route = _json(world / "route.json")
    assert route["length_m"] == pytest.approx(21 * mbw.BLOCK_M, rel=0.02)
    assert 0.5 <= min(route["grade_pct"]) and max(route["grade_pct"]) <= 5.5
    alt = route["alt_m"]
    assert 1200.0 <= alt[-1] - alt[0] <= 1600.0 and max(alt) == pytest.approx(alt[-1], abs=2.0)
    pois = "".join(f.read_text(encoding="utf-8") for f in (world / "poi").glob("*.json"))
    for name in (*mbw.PLACE_NAMES["japon"], *mbw.PLACE_NAMES["japon_vue"]):
        assert name in pois, name
    assert mbw.Plan(("japan",) * 3, False, False).place("japon_vue", 2) == "Col des Cèdres"
    assert _json(demo_set / "demo-japon.json")["generated"]["buildings"] >= 30
    assert "demo-japon" in mbw.GAME_DEMOS


def test_recif_loop_under_the_sea(demo_set: Path, mbw) -> None:
    """Lot SM1 : boucle fermée de 8 km dans le seul biome `reef`, route de −30 à −10 m (sous la mer, pentes douces),
    relief tout entier sous REEF_TOP_M (le récif ne sort jamais de l'eau), lieux nommés, aucune construction, et ni
    circulation ni cyclistes du décor au core."""
    import numpy as np
    from openride_core import traffic
    from openride_core.route import load_world

    world = demo_set / "demo-recif.world"
    route = _json(world / "route.json")
    manifest = _json(world / "manifest.json")
    assert route["type"] == "loop" and route["length_m"] == pytest.approx(mbw.REEF_M, abs=5.0)
    assert manifest["layers"]["biome"]["shares"] == {"reef": 100.0}
    assert -30.0 <= min(route["alt_m"]) and max(route["alt_m"]) <= -10.0
    assert -4.0 <= min(route["grade_pct"]) and max(route["grade_pct"]) <= 4.0
    assert (route["x"][0], route["z"][0], route["alt_m"][0]) == (route["x"][-1], route["z"][-1], route["alt_m"][-1])
    info = _json(demo_set / "demo-recif.json")
    assert info["generated"]["buildings"] == 0 and info["generated"]["poi"] == 5   # quatre lieux et l'épave (SM2)
    plan = mbw.Plan(("reef",), False, False, loop="recif")
    terrain = mbw.make_terrain(plan)
    xs, zs = np.meshgrid(np.linspace(-3000.0, 3000.0, 121), np.linspace(-3000.0, 3000.0, 121))
    assert float(np.max(terrain(xs, zs))) <= mbw.REEF_TOP_M
    # La route garde l'altitude du relief : le plafond n'agit qu'au-dessus de REEF_TOP_M − REEF_SOFT_M
    s = np.arange(0.0, mbw.REEF_M, 50.0)
    x, z = zip(*(plan.road.xz(v) for v in s))
    assert np.allclose(terrain(np.array(x), np.array(z)), mbw.reef_relief(np.array(x), np.array(z)), atol=0.05)
    names = "".join(f.read_text(encoding="utf-8") for f in (world / "poi").glob("*.json"))
    assert all(n in names for n in ("Lagon des Tortues", "Forêt des Laminaires", "Jardin de Corail", "Tombant Bleu"))
    assert traffic.underwater_route(manifest) and not traffic.underwater_route(_json(demo_set / "demo-circuit.world" / "manifest.json"))
    assert load_world(world).route.is_loop


def test_recif_wreck_before_finish(demo_set: Path, mbw) -> None:
    """Lot SM2 : une épave (`wreck`, longueur 42 m) couchée sur le sable avant l'arrivée du récif, à 45 m du bord
    de la route, hors des forêts de laminaires, posée sur le fond, assez profond pour que le navire (moins de 8 m
    au-dessus du fond, wrecks.gd) reste à plus de 2 m sous la surface ; nommée au menu du jeu de base."""
    import math

    world = demo_set / "demo-recif.world"
    route = _json(world / "route.json")
    points = [p for f in sorted((world / "poi").glob("chunk_*.json")) for p in _json(f)["points"]]
    wrecks = [p for p in points if p["kind"] == "wreck"]
    assert len(wrecks) == 1
    w = wrecks[0]
    assert w["name"] == "Épave de la Belle-Tortue" and w["length_m"] == 42.0 and w["radius_m"] == 400
    i = round(mbw.REEF_WRECK_S / route["ds_m"])
    assert math.dist((w["x"], w["z"]), (route["x"][i], route["z"][i])) == pytest.approx(mbw.REEF_WRECK_OFFSET_M, abs=1.0)
    assert route["length_m"] - mbw.REEF_WRECK_S <= 200.0   # vue en approchant de l'arrivée
    assert w["y"] + 8.0 < -2.0


def test_every_biome_has_a_game_demo(mbw) -> None:
    """Lot DB3 (décision du propriétaire du 14 novembre) : chaque biome réel du compilateur est montré par une
    démonstration du jeu de base (le Col du lacet, écrit par le core, montre la forêt tempérée et l'alpin)."""
    from openride_compiler.biomes import BIOMES

    shown = {"temperate_forest", "alpine"}
    for _name, _title, which, *_, base in mbw.DEMO_SET:
        if base:
            shown |= set(mbw.tour_blocks(which)[0])
    assert set(BIOMES) - {"reef"} <= shown, sorted(set(BIOMES) - shown)


def test_sud_route(demo_set: Path, mbw) -> None:
    """Route du Sud (lot DB3) : six biomes de 8 km (quatre blocs de 2 km chacun, lot DL1) sur la route ouverte, des
    oliviers au delta, parts égales, pente de
    −5 à +6 %, sommet avant la descente de la jungle, mares du delta à l'arrivée, aucune variante régionale."""
    import numpy as np

    world = demo_set / "demo-biomes-sud.world"
    route = _json(world / "route.json")
    assert route["type"] == "open" and route["length_m"] == pytest.approx(48000.0, abs=800.0)
    shares = _json(world / "manifest.json")["layers"]["biome"]["shares"]
    assert list(shares) == [b for b, *_ in mbw.SUD]
    assert all(v == pytest.approx(100.0 / 6, abs=0.6) for v in shares.values()), shares
    assert -5.0 <= min(route["grade_pct"]) and max(route["grade_pct"]) <= 6.0
    alt = np.array(route["alt_m"])
    top = int(np.argmax(alt)) * route["ds_m"]
    assert 24000.0 <= top <= 34000.0, top                     # fin de la savane, avant la jungle
    assert _json(demo_set / "demo-biomes-sud.json")["generated"]["water_areas"] >= 5   # oasis et mares du delta
    for f in (world / "biome" / "near").glob("*.json"):
        assert _json(f)["variant"] is None, f.name


def test_nord_loop(demo_set: Path, mbw) -> None:
    """Route du Grand Nord (lot DB3, « fais une boucle ») : boucle fermée de 10 km en cinq blocs de 2 km, taïga au
    départ et à l'arrivée, banquise au point le plus éloigné et le plus haut, 100 à 160 m de montée, pente d'au plus
    8 %, chaque tuile proche dans le biome du bloc de la route la plus proche, relief continu et borné."""
    import numpy as np

    world = demo_set / "demo-biomes-nord.world"
    route = _json(world / "route.json")
    manifest = _json(world / "manifest.json")
    assert route["type"] == "loop" and route["length_m"] == pytest.approx(mbw.NORD_M, abs=5.0)
    assert (route["x"][0], route["z"][0], route["alt_m"][0]) == (route["x"][-1], route["z"][-1], route["alt_m"][-1])
    shares = manifest["layers"]["biome"]["shares"]
    assert shares["boreal_forest"] == pytest.approx(40.0, abs=1.0) and shares["tundra"] == pytest.approx(40.0, abs=1.0)
    assert shares["polar"] == pytest.approx(20.0, abs=1.0)
    assert max(abs(g) for g in route["grade_pct"]) <= 8.0
    alt = np.array(route["alt_m"])
    climb = float(np.clip(np.diff(alt), 0.0, None).sum())
    assert 100.0 <= climb <= 160.0, climb
    assert abs(int(np.argmax(alt)) * route["ds_m"] - route["length_m"] / 2.0) < 600.0
    # Départ dans la taïga : la tuile proche du départ (repère du .world, centré sur le départ) est boréale.
    start = [f for f in (world / "biome" / "near").glob("*.json") if f.stem == "tile_0_0" or f.stem == "tile_-1_0"]
    assert start and all("boreal_forest" in _json(f)["biomes"] for f in start)
    plan = mbw.Plan(mbw.tour_blocks("nord")[0], False, False, loop="nord")
    terrain = mbw.make_terrain(plan)
    xs, zs = np.meshgrid(np.linspace(-2500.0, 2500.0, 126), np.linspace(-2500.0, 2500.0, 126))
    h = terrain(xs.ravel(), zs.ravel()).reshape(xs.shape)
    assert float(max(np.abs(np.diff(h, axis=0)).max(), np.abs(np.diff(h, axis=1)).max())) < 10.0   # pas de marche
    far = terrain(np.linspace(-40000.0, 40000.0, 81), np.linspace(40000.0, -40000.0, 81))
    assert float(np.max(np.abs(far))) < 400.0


def test_loop_blocks_must_fill_the_loop(mbw) -> None:
    with pytest.raises(ValueError, match="2 km par bloc"):
        mbw.Plan(("tundra", "polar"), False, False, loop="nord")


# --- Parcours du Grand Prix des objets (lot GP13b) -------------------------------------------------------------

GRAND_PRIX = ("demo-circuit", "demo-corniche", "demo-vignes")


def _radius_min(route: dict) -> float:
    """Plus petit rayon de virage (m) de la route compilée, mesuré sur 20 m."""
    import numpy as np
    h = np.unwrap(np.radians(np.asarray(route["heading_deg"], dtype=float)))
    k = max(1, int(round(10.0 / float(route["ds_m"]))))
    turn = np.abs(h[2 * k:] - h[:-2 * k])
    return float(2 * k * float(route["ds_m"]) / max(float(turn.max()), 1e-9))


def test_grand_prix_routes_are_wide_paved_and_without_hairpin(demo_set: Path, mbw) -> None:
    """Lot GP13 §2.1 : chaque parcours du Grand Prix du jeu de base (étiquette `grandprix`) est revêtu de bout en
    bout (aucune portion gravel ou terre, où le core resserre les vélos), sa chaussée fait 6 m (trois voies) et il
    n'a pas d'épingle (rayon de virage d'au moins 25 m)."""
    from openride_core import mode_routes

    tagged = sorted(n for n in mbw.GAME_DEMOS if mode_routes.mode_of(mbw.library_of(n)) == "grandprix")
    assert tagged == sorted(GRAND_PRIX)
    for name in tagged:
        world = demo_set / f"{name}.world"
        route = _json(world / "route.json")
        manifest = _json(world / "manifest.json")
        assert set(route.get("surface", ["paved"])) == {"paved"}, name
        assert not [g for n, *_, g, _sea, base in mbw.DEMO_SET if n == name and g], name
        assert 2.0 * manifest["layers"]["terrain"]["road_half_width_m"] >= 6.0, name
        assert _radius_min(route) >= 25.0, (name, _radius_min(route))


def test_corniche_loop(demo_set: Path, mbw) -> None:
    """Boucle de la Corniche (lot GP13b) : boucle fermée de 2,5 km dans le méditerranéen, pente de −6 à +6 %, 30 à
    45 m de montée par tour, l'autre rive à plus de 400 m ; la mer à gauche le long du côté est : côte rocheuse
    sans plage, aires `sea` jusqu'à 1 600 m (au-delà du trou de l'anneau d'horizon), falaise sous la route, terrain
    sous la mer seulement dans les aires `sea`."""
    import numpy as np
    from openride_compiler.fake_osm import LoopRoad

    world = demo_set / "demo-corniche.world"
    route = _json(world / "route.json")
    manifest = _json(world / "manifest.json")
    assert route["type"] == "loop" and route["length_m"] == pytest.approx(mbw.CORNICHE_M, abs=5.0)
    assert (route["x"][0], route["z"][0], route["alt_m"][0]) == (route["x"][-1], route["z"][-1], route["alt_m"][-1])
    assert -6.0 <= min(route["grade_pct"]) and max(route["grade_pct"]) <= 6.0
    climb = sum(max(b - a, 0.0) for a, b in zip(route["alt_m"], route["alt_m"][1:]))
    assert 30.0 <= climb <= 45.0, climb
    assert min(route["alt_m"]) > 15.0                     # la route reste en haut de la falaise
    assert manifest["layers"]["biome"]["shares"] == {"mediterranean": 100.0}
    road = LoopRoad(mbw.CORNICHE_M, mbw.CORNICHE_LOBES)
    pts = np.column_stack((road._x[:-1], road._z[:-1]))
    far = [np.hypot(*(pts[i] - pts[j])) for i in range(0, len(pts), 25) for j in range(0, len(pts), 25)
           if min(abs(i - j), len(pts) - abs(i - j)) * road.STEP > 600.0]
    assert min(far) > 400.0
    coast = manifest["layers"]["coast"]
    assert coast["present"] and coast["lines_count"] >= 2 and coast["beaches_count"] == 0
    for f in sorted((world / "coast").glob("chunk_*.json")):
        jsonschema.validate(_json(f), _schema("coast"))
        assert all(line["shore"] == "rock" for line in _json(f)["lines"])
    seas = [a for f in (world / "water").glob("chunk_*.json") for a in _json(f)["areas"] if a["kind"] == "sea"]
    assert seas and manifest["layers"]["water"]["areas_count"] == len(seas)
    reach = max(float(np.hypot(*np.subtract(p, (route["x"][k], route["z"][k])))) for a in seas for p in a["outer"]
                for k in range(0, route["n"], 5))
    assert reach > 1500.0
    # Relief : la mer à gauche du tronçon `sea` (sous 0 à 300 m de la route), la terre partout ailleurs près de la
    # route, à gauche avant le tronçon et à droite (l'intérieur de la boucle).
    plan = mbw.Plan(("mediterranean",), False, True, loop="corniche")
    terrain = mbw.make_terrain(plan)
    s0, s1 = mbw.CORNICHE_SEA
    mid = (s0 + s1) / 2.0
    for s, off, below in ((mid, -300.0, True), (mid, -150.0, True), (mid, 150.0, False), (mid, -20.0, False),
                          (s0 - 100.0, -150.0, False), (s1 + 300.0, -150.0, False)):
        h = float(terrain(*map(np.asarray, plan.road.point(s, off))))
        assert (h < 0.0) == below, (s, off, h)
    assert _json(demo_set / "demo-corniche.json")["generated"]["poi"] >= 2


def test_vignes_loop(demo_set: Path, mbw) -> None:
    """Route des Vignes (lot GP13b, en boucle depuis la remarque du propriétaire du 19 novembre) : boucle fermée et
    sinueuse de 5 km dans le biome `farmland` (rangs de vigne du thème) : au moins huit virages francs (cap qui tourne
    de plus de 40° sur 100 m) mais aucun sous 25 m de rayon, l'autre rive à plus de 200 m ; vallonnée (pente de −6 à
    +6 %, 50 à 80 m de montée par tour) ; vignes des deux côtés, village, hameau, clos, trois domaines et trois
    belvédères."""
    import numpy as np
    from openride_compiler.fake_osm import LoopRoad

    world = demo_set / "demo-vignes.world"
    route = _json(world / "route.json")
    assert route["type"] == "loop" and route["length_m"] == pytest.approx(mbw.VIGNES_M, abs=5.0)
    assert (route["x"][0], route["z"][0], route["alt_m"][0]) == (route["x"][-1], route["z"][-1], route["alt_m"][-1])
    assert _json(world / "manifest.json")["layers"]["biome"]["shares"] == {"farmland": 100.0}
    assert -6.0 <= min(route["grade_pct"]) and max(route["grade_pct"]) <= 6.0
    climb = sum(max(b - a, 0.0) for a, b in zip(route["alt_m"], route["alt_m"][1:]))
    assert 50.0 <= climb <= 80.0, climb
    road = LoopRoad(mbw.VIGNES_M, mbw.VIGNES_LOBES, mbw.VIGNES_WIGGLES)
    assert road.radius_min() >= 25.0
    h = np.degrees(np.unwrap(np.arctan2(road._hx, -road._hz)))
    k = int(round(100.0 / road.STEP))
    turns = np.abs(h[k:] - h[:-k]) > 40.0
    bends = int(np.count_nonzero(turns[1:] & ~turns[:-1]))   # débuts de virage franc
    assert bends >= 8, bends
    pts = np.column_stack((road._x[:-1], road._z[:-1]))
    far = [np.hypot(*(pts[i] - pts[j])) for i in range(0, len(pts), 25) for j in range(0, len(pts), 25)
           if min(abs(i - j), len(pts) - abs(i - j)) * road.STEP > 700.0]
    assert min(far) > 200.0
    generated = _json(demo_set / "demo-vignes.json")["generated"]
    assert generated["vegetation"] >= 8 and generated["poi"] >= 6
    for f in (world / "biome" / "near").glob("*.json"):
        assert _json(f)["variant"] is None, f.name


def test_loop_wiggles_keep_the_loop_closed() -> None:
    """Lot GP13b : les lacets d'une boucle (`wiggles`) gardent la longueur et la fermeture, avec à peu près l'amplitude
    voulue de part et d'autre de la boucle sans lacets."""
    import numpy as np
    from openride_compiler.fake_osm import LoopRoad

    plain = LoopRoad(3000.0, ((2, 0.2, 0.0),))
    wavy = LoopRoad(3000.0, ((2, 0.2, 0.0),), ((10, 30.0, 0.0),))
    assert wavy.length_m == plain.length_m == 3000.0
    assert np.hypot(*np.subtract(wavy.xz(0.0), wavy.xz(2999.9))) < 1.0
    _, dx = plain.locate(wavy._x[:-1], wavy._z[:-1])
    assert 20.0 < float(dx.max() - dx.min()) / 2.0 < 40.0   # amplitude des lacets (la remise à la longueur resserre un peu la boucle)
    assert wavy.radius_min() < plain.radius_min()
