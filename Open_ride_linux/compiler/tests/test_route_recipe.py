"""Recettes de cols et construction du pack depuis OpenStreetMap (lot O16), sans réseau.

Le graphe routier est synthétique (réponses Overpass fabriquées) et l'altitude vient du MNT de
test `plane` (5 % de pente vers le nord) : une route qui monte de 1 km vers le nord prend 50 m.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pytest

from conftest import ORIGIN, plane
from openride_compiler import cli
from openride_compiler import route_recipe as rr
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.errors import CompileError
from openride_compiler.route_pack import install_pack
from openride_compiler.route_stats import load_library

LAT0, LON0 = ORIGIN
DLAT = 1.0 / 111195.0                       # degrés de latitude par mètre
DLON = DLAT / math.cos(math.radians(LAT0))


def at(north_m: float, east_m: float = 0.0) -> tuple[float, float]:
    return LAT0 + north_m * DLAT, LON0 + east_m * DLON


def way(wid: int, node_ids: list[int], coords: dict[int, tuple[float, float]], **tags: str) -> dict:
    return {"type": "way", "id": wid, "nodes": node_ids, "tags": {"highway": "secondary", **tags},
            "geometry": [{"lat": coords[n][0], "lon": coords[n][1]} for n in node_ids]}


def two_roads(short_tags: dict[str, str] | None = None) -> dict:
    """Du départ (nœud 1, au sud) au sommet (nœud 9, 2 km au nord) : une route droite (nœuds
    1-2-9, 2 km) et un détour par l'est (nœuds 1-3-4-9, environ 2,8 km)."""
    coords = {1: at(0), 2: at(1000), 9: at(2000), 3: at(0, 400), 4: at(2000, 400)}
    ways = [way(10, [1, 2, 9], coords, **(short_tags or {})), way(11, [1, 3, 4, 9], coords)]
    return {"elements": ways}


def fetcher(response: dict, seen: list[str] | None = None):
    def fetch(query: str) -> dict:
        if seen is not None:
            seen.append(query)
        return response
    return fetch


def recipe(tmp_path: Path, name: str = "col_test", length: float = 2000.0, gain: float = 100.0,
           end_north: float = 2000.0, **extra) -> Path:
    s, e = at(0), at(end_north)
    lines = [f'name = "Col de test"', 'region = "Massif d\'essai"', 'country = "France"',
             f"waypoints = [[{s[0]:.4f}, {s[1]:.4f}], [{e[0]:.4f}, {e[1]:.4f}]]",
             f"ref_length_m = {length}", f"ref_gain_m = {gain}", 'tags = ["col"]']
    lines += [f"{k} = {json.dumps(v)}" for k, v in extra.items()]
    path = tmp_path / "recettes" / f"{name}.toml"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


PROVIDER = SyntheticProvider(*ORIGIN, plane)


def test_shortest_allowed_path_is_chosen(tmp_path: Path) -> None:
    r = rr.load_recipe(recipe(tmp_path))
    climb = rr.build_climb(r, fetcher(two_roads()), PROVIDER)
    assert climb.length_m == pytest.approx(2000.0, abs=20.0)        # route droite
    assert climb.gain_m == pytest.approx(100.0, abs=3.0)
    assert all(abs(lon - LON0) < 1e-6 for _, lon in climb.points)


@pytest.mark.parametrize("tags", [{"bicycle": "no"}, {"highway": "motorway"}, {"access": "private"},
                                  {"highway": "trunk", "bicycle": "no"}, {"surface": "gravel"},
                                  {"highway": "track"}, {"oneway": "-1"}])
def test_excluded_road_forces_detour(tmp_path: Path, tags: dict) -> None:
    graph = rr.build_graph([two_roads(tags)])
    path = rr.route_through(graph, [at(0), at(2000)])
    assert rr.path_length_m(path) == pytest.approx(2000.0 + 2 * 400.0, abs=20.0)


def test_unpaved_allowed_by_recipe(tmp_path: Path) -> None:
    graph = rr.build_graph([two_roads({"surface": "gravel"})], unpaved_ok=True)
    assert rr.path_length_m(rr.route_through(graph, [at(0), at(2000)])) == pytest.approx(2000.0, abs=20.0)


def test_oneway_in_direction_and_cycle_exception() -> None:
    assert rr.path_length_m(rr.route_through(rr.build_graph([two_roads({"oneway": "yes"})]),
                                             [at(0), at(2000)])) == pytest.approx(2000.0, abs=20.0)
    back = rr.route_through(rr.build_graph([two_roads({"oneway": "yes"})]), [at(2000), at(0)])
    assert rr.path_length_m(back) == pytest.approx(2800.0, abs=20.0)
    both = rr.route_through(rr.build_graph([two_roads({"oneway": "yes", "oneway:bicycle": "no"})]),
                            [at(2000), at(0)])
    assert rr.path_length_m(both) == pytest.approx(2000.0, abs=20.0)


def test_tunnel_altitude_is_interpolated_between_portals(tmp_path: Path) -> None:
    """Dans un tunnel, le MNT donne la montagne au-dessus : l'altitude est interpolée entre les entrées."""
    coords = {1: at(0), 2: at(800), 3: at(1200), 9: at(2000)}
    ways = [way(10, [1, 2], coords), way(11, [2, 3], coords, tunnel="yes"), way(12, [3, 9], coords)]
    def bump(x, z):                      # montagne de 300 m au-dessus du tunnel (z vers le sud)
        north = -np.asarray(z, dtype=float)
        return plane(x, z) + np.where((north > 850.0) & (north < 1150.0), 300.0, 0.0)

    r = rr.load_recipe(recipe(tmp_path))
    climb = rr.build_climb(r, fetcher({"elements": ways}), SyntheticProvider(*ORIGIN, bump))
    assert max(climb.alt_m) == pytest.approx(climb.alt_m[-1], abs=1.0)  # pas de bosse de 300 m
    assert climb.gain_m == pytest.approx(100.0, abs=3.0)                # sans les 300 m de montagne


def test_bridge_flag_and_endpoint_run_keep_dem() -> None:
    pts = [at(i * 10.0) for i in range(6)]
    alt = [0.0, 10.0, -50.0, -50.0, 40.0, 50.0]
    assert rr.bridge_off_ground(pts, alt, [False, False, True, True, False, False]) == \
        pytest.approx([0.0, 10.0, 20.0, 30.0, 40.0, 50.0], abs=0.01)
    assert rr.bridge_off_ground(pts, alt, [True, True, False, False, False, False]) == alt


def test_checked_gain_ignores_hairpin_noise() -> None:
    """Lacets : ± 6 m d'oscillation tous les 60 m ne comptent pas, la vraie montée reste mesurée."""
    alt = [i * 0.8 + 6.0 * math.sin(i * 2 * math.pi / 6) for i in range(1000)]   # 800 m sur 10 km
    assert rr.gain_loss(alt)[0] > 1000.0                                          # mesure brute
    assert rr.checked_gain(alt) == pytest.approx(800.0, rel=0.02)
    hill = [min(i, 1000 - i) * 1.0 for i in range(1001)]                          # +500, −500 m
    assert rr.checked_gain(hill) == pytest.approx(500.0, rel=0.02)


def test_gpx_altitude_is_the_checked_profile(tmp_path: Path) -> None:
    """Le GPX reçoit le profil moyenné du contrôle : pas de pente fictive due au bruit des lacets."""
    def noisy(x, z):                     # ± 6 m tous les 62 m (5 périodes par fenêtre de 31 points)
        north = -np.asarray(z, dtype=float)
        lacets = (north > 300.0) & (north < 1700.0)       # lacets au milieu de la montée
        return plane(x, z) + np.where(lacets, 6.0 * np.sin(north * 2 * math.pi / 62.0), 0.0)

    r = rr.load_recipe(recipe(tmp_path))
    climb = rr.build_climb(r, fetcher(two_roads()), SyntheticProvider(*ORIGIN, noisy))
    grades = np.diff(climb.alt_m) / rr.STEP_M * 100.0     # dernier pas plus court : écarté
    assert np.abs(grades[:-1] - 5.0).max() < 2.5                # brut : ± 50 % d'un point à l'autre
    assert climb.gain_m == pytest.approx(rr.gain_loss(climb.alt_m)[0])
    assert "<ele>" in rr.gpx_text(climb)


def test_waypoint_off_road_is_refused() -> None:
    graph = rr.build_graph([two_roads()])
    with pytest.raises(CompileError, match="hors de toute route permise"):
        rr.route_through(graph, [at(0), at(1000, -800)])
    with pytest.raises(CompileError, match="aucune route chargée"):
        rr.route_through(rr.build_graph([{"elements": []}]), [at(0), at(10)])


def test_no_path_between_waypoints() -> None:
    coords = {1: at(0), 2: at(500), 3: at(1000), 4: at(1500)}
    graph = rr.build_graph([{"elements": [way(1, [1, 2], coords), way(2, [3, 4], coords)]}])
    with pytest.raises(CompileError, match="aucun chemin"):
        rr.route_through(graph, [at(0), at(1500)])


def _hairpin_road(surface: str | None = None) -> dict:
    """Route de 2 km qui sort à 3 km à l'est des points (hors du premier rectangle), tronçon du milieu `surface`."""
    coords = {1: at(0), 2: at(0, 3000), 3: at(2000, 3000), 9: at(2000)}
    mid = {"surface": surface} if surface else {}
    return {"elements": [way(1, [1, 2], coords), way(2, [2, 3], coords, **mid), way(3, [3, 9], coords)]}


def _by_margin(full: dict, waypoints: list):
    """Overpass simulé : le premier rectangle n'a que les voies qui le touchent (pas le tronçon à 3 km à l'est),
    le rectangle élargi a toute la route."""
    def fetch(query: str) -> dict:
        if query == rr.roads_query(rr.bbox_around(waypoints, rr.BBOX_MARGINS_M[1])):
            return full
        return {"elements": [w for w in full["elements"] if w["id"] != 2]}
    return fetch


def test_hairpins_outside_first_box_are_found_in_wider_box(tmp_path: Path) -> None:
    r = rr.load_recipe(recipe(tmp_path, length=8000.0, gain=100.0))
    climb = rr.build_climb(r, _by_margin(_hairpin_road(), r.waypoints), PROVIDER)
    assert climb.length_m == pytest.approx(8000.0, abs=50.0)


def test_no_path_says_segment_and_unpaved(tmp_path: Path) -> None:
    r = rr.load_recipe(recipe(tmp_path, length=8000.0, gain=100.0))
    with pytest.raises(CompileError, match=r"tronçon 1.*non revêtues \(unpaved = true\)"):
        rr.build_climb(r, fetcher(_hairpin_road("gravel")), PROVIDER)
    coords = {1: at(0), 2: at(500), 3: at(1500), 9: at(2000)}
    broken = {"elements": [way(1, [1, 2], coords), way(2, [3, 9], coords)]}
    with pytest.raises(CompileError, match="même à 6 km des points"):
        rr.build_climb(r, fetcher(broken), PROVIDER)


@pytest.mark.parametrize("length,gain,needle", [(2300.0, 100.0, r"longueur \d+ m au lieu de 2300 m"),
                                                (2000.0, 150.0, r"dénivelé \d+ m au lieu de 150 m")])
def test_wrong_reference_is_refused(tmp_path: Path, length: float, gain: float, needle: str) -> None:
    r = rr.load_recipe(recipe(tmp_path, length=length, gain=gain))
    with pytest.raises(CompileError, match=needle):
        rr.build_climb(r, fetcher(two_roads()), PROVIDER)


def test_resample_step_and_ends() -> None:
    pts = rr.resample([at(0), at(25), at(25, 7), at(100, 7)])
    steps = [rr.haversine_m(*a, *b) for a, b in zip(pts, pts[1:])]
    assert pts[0] == at(0) and pts[-1] == at(100, 7)
    assert max(steps) <= 10.0 + 1e-6 and len(pts) == 12   # 107 m en pas de 10 m, plus l'arrivée


def test_query_is_bounded_and_cached_by_text(tmp_path: Path) -> None:
    seen: list[str] = []
    rr.build_climb(rr.load_recipe(recipe(tmp_path)), fetcher(two_roads(), seen), PROVIDER)
    s, w, n, e = rr.bbox_around([at(0), at(2000)])
    assert n - s == pytest.approx((2000 + 2 * rr.BBOX_MARGIN_M) * DLAT, abs=2e-4)
    assert seen == [rr.roads_query((s, w, n, e))] and "motorway" not in seen[0]


def test_build_pack_installs_with_osm_credits(tmp_path: Path) -> None:
    src = recipe(tmp_path).parent
    recipe(tmp_path, name="mauvais", length=9000.0)
    (src / "pack.toml").write_text('name = "Essai"\nlicense = "ODbL 1.0"\n', encoding="utf-8")
    logs: list[str] = []
    target, done, refused = rr.build_pack(src, tmp_path / "travail", fetcher(two_roads()), PROVIDER,
                                          log=logs.append)
    assert done == ["col-test"] and len(refused) == 1 and "mauvais" in refused[0]
    assert sorted(p.name for p in target.iterdir()) == ["col-test.gpx", "col-test.toml", "pack.toml"]
    sheet = load_library(target / "col-test.toml")
    assert "OpenStreetMap" in sheet["credits"] and sheet["region"] == "Massif d'essai, France"
    name, count, folder = install_pack(target, tmp_path / "GPX")
    assert (name, count) == ("essai", 1) and (folder / "col-test.gpx").is_file()
    assert cli.main(["build", str(folder / "col-test.gpx"), "--out", str(tmp_path / "routes"),
                     "--layers", "route"]) == 0
    manifest = json.loads((tmp_path / "routes" / "col-test.world" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["library"]["credits"].startswith("© contributeurs OpenStreetMap")
    assert manifest["stats"]["gain_m"] == pytest.approx(100.0, abs=3.0)


def test_cli_route_pack_build(tmp_path: Path, monkeypatch, capsys) -> None:
    src = recipe(tmp_path).parent

    class FakeClient:
        def fetch_query(self, query: str) -> dict:
            return two_roads()

    monkeypatch.setattr(cli, "make_osm_client", lambda offline, log=None: FakeClient())
    assert cli.main(["route-pack-build", str(src), "--out", str(tmp_path / "travail"), "--install",
                     "--gpx-dir", str(tmp_path / "GPX")]) == 0
    out = capsys.readouterr().out
    assert "1 col(s) construit(s), 0 refusé(s)" in out and (tmp_path / "GPX" / "recettes" / "col-test.gpx").is_file()
    assert cli.main(["route-pack-build", str(src), "--out", str(tmp_path / "t2"), "--only", "inconnu"]) == 1


@pytest.mark.parametrize("text,needle", [
    ('waypoints = [[45.1, 6.0]]', "au moins deux"),
    ('waypoints = [[45.12345, 6.0], [45.2, 6.0]]', "4 décimales"),
    ('waypoints = [[95.0, 6.0], [45.2, 6.0]]', "point invalide"),
    ('ref_length_m = -3', "positif"),
    ('auteur = "x"', "inconnue"),
    ('tags = ["Pas Bon"]', "étiquette invalide"),
])
def test_recipe_validation(tmp_path: Path, text: str, needle: str) -> None:
    base = {"name": '"Col"', "region": '"Massif"', "country": '"France"',
            "waypoints": "[[45.1, 6.0], [45.2, 6.0]]", "ref_length_m": "1000", "ref_gain_m": "50"}
    key = text.split(" = ")[0]
    base[key] = text.split(" = ", 1)[1]
    path = tmp_path / "col.toml"
    path.write_text("\n".join(f"{k} = {v}" for k, v in base.items()) + "\n", encoding="utf-8")
    with pytest.raises(CompileError, match=needle):
        rr.load_recipe(path)


def test_builtin_pack_recipes() -> None:
    folder = rr.pack_dir("cols_celebres")
    recipes = rr.load_recipes(folder)
    assert len(recipes) == 21   # 16 du lot O16, Hakone et Fuji Azami Line (JP6), Khardung La, Abra Málaga, Ticlio (HP1)
    assert {"alpe-d-huez", "mont-ventoux-bedoin", "grand-ballon", "fuji-subaru-line"} <= {r.id for r in recipes}
    assert all("col" in r.tags and len(r.waypoints) >= 2 for r in recipes)
    # Aucune trace dans le dépôt : seulement des recettes et pack.toml.
    assert {p.suffix for p in folder.iterdir()} == {".toml"}
    for r in recipes:
        sheet = rr.library_toml(r)
        assert "OpenStreetMap" in sheet and not re.search(r"\d+\.\d{3,}", sheet)   # pas de coordonnées
    with pytest.raises(CompileError, match="introuvable"):
        rr.pack_dir("pack_absent")
