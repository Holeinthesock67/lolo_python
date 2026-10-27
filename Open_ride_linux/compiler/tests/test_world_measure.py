"""Script de mesure du monde ouvert (lot W0), sans réseau."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from openride_compiler import cli
from openride_compiler.errors import CompileError
from openride_compiler.worldgen import measure
from openride_compiler.worldgen.measure import FrameRelief, Measure, MeasureConfig

from test_mvt import encode_tile

START = (45.09, 6.06)       # lieu d'exemple des tests du compilateur (Oisans)


class FakeNet:
    """Faux serveur : TileJSON et une tuile par clé, avec une route et un bâtiment."""

    TEMPLATE = "https://tuiles.invalid/test/{z}/{x}/{y}.pbf"

    def __init__(self) -> None:
        self.requests = 0
        self.urls: list[str] = []

    def get(self, url: str) -> bytes:
        self.requests += 1
        self.urls.append(url)
        assert url == measure.OPENFREEMAP_TILEJSON
        return json.dumps({"tiles": [self.TEMPLATE]}).encode()

    def head_size(self, url: str) -> int:
        self.requests += 1
        self.urls.append(url)
        return 2_000_000_000

    def download(self, url: str, dest: Path) -> int:
        self.requests += 1
        self.urls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if url.endswith(".osm.pbf"):
            dest.write_bytes(b"pbf" * 100)
        else:
            dest.write_bytes(encode_tile({
                "transportation": [
                    {"id": 1, "type": 2, "tags": {"class": "minor"}, "paths": [([(0, 2048), (4096, 2100)], False)]},
                    {"id": 2, "type": 2, "tags": {"class": "motorway"}, "paths": [([(2048, 0), (2048, 4096)], False)]},
                ],
                "building": [{"id": 3, "type": 3, "tags": {"render_height": 9},
                              "paths": [([(1000, 1000), (1100, 1000), (1100, 1100), (1000, 1100)], True)]}],
            }))
        return dest.stat().st_size


def make(tmp_path: Path, **kw) -> tuple[Measure, FakeNet]:
    net = FakeNet()
    cfg = MeasureConfig(lat=START[0], lon=START[1], heading_deg=kw.pop("heading", 90.0), km=kw.pop("km", 2.0),
                        out=tmp_path / "out", cache_dir=tmp_path / "cache", **kw)
    m = Measure(cfg, net=net, log=lambda _: None, confirm=lambda _: False)
    if not cfg.synthetic:
        m.provider = FrameRelief(m.frame)
    return m, net


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("OPENRIDE_DEM_CACHE", str(tmp_path / "dem"))
    return home


def test_origine_sur_la_grille_de_5_km() -> None:
    frame, (x, z) = measure.session_frame(*START)
    assert frame.e0 % 5000 == 0 and frame.n0 % 5000 == 0
    assert abs(x) <= 2500 and abs(z) <= 2500
    lat, lon = frame.to_latlon(np.array([x]), np.array([z]))
    assert (float(lat[0]), float(lon[0])) == pytest.approx(START, abs=1e-7)


def test_carres_le_long_de_la_ligne() -> None:
    pts = measure.path_points((10.0, -10.0), 90.0, 2500.0)
    assert measure.squares_along(pts) == [(0, -1), (1, -1), (2, -1)]


def test_mesure_synthetique_par_la_ligne_de_commande(tmp_path, isolated_home) -> None:
    out = tmp_path / "rapport"
    code = cli.main(["world-measure", "--lat", str(START[0]), "--lon", str(START[1]), "--heading", "45",
                     "--km", "3", "--synthetic", "--out", str(out), "--cache-dir", str(tmp_path / "cache")])
    assert code == 0
    report = json.loads((out / "rapport.json").read_text())
    md = (out / "rapport.md").read_text()
    gen = report["generation"]
    assert gen["nombre"] >= 3
    for sq in gen["carres"]:
        folder = out / "carres" / f"{sq['carre'][0]}_{sq['carre'][1]}"
        assert sq["octets"] == sum(p.stat().st_size for p in folder.iterdir())
        assert sq["total_s"] > 0 and all(v >= 0 for v in sq["secondes"].values())
        assert (folder / "near.f32").stat().st_size == 101 * 101 * 4
    assert gen["octets_total"] == sum(s["octets"] for s in gen["carres"])
    assert gen["secondes_par_km"] > 0 and gen["marge_30_kmh"] > gen["marge_70_kmh"] > 0
    assert report["tuile_lointaine"]["octets"] == 101 * 101 * 4
    assert "Génération par carré de 1 km" in md and "**Total**" in md
    # Rien hors du dossier du rapport : ni dans le dossier personnel, ni dans le cache.
    assert list(isolated_home.iterdir()) == []
    assert not (tmp_path / "cache").exists()


def test_terrain_fondu_avec_les_routes(tmp_path) -> None:
    m, _ = make(tmp_path, synthetic=True, km=1.0)
    src = measure.synthetic_sources(m.points, 90.0)
    ix, iz = measure.squares_along(m.points)[0]
    m.generate_square(ix, iz, src, tmp_path / "sq")
    grid = np.frombuffer((tmp_path / "sq" / "near.f32").read_bytes(), "<f4").reshape(101, 101)
    gx, gz = measure.tile_coords(ix, iz, measure.NEAR)
    relief = measure.analytic_relief(gx, gz)
    rpts, rids = m._square_roads(ix, iz, src.roads)
    near = np.zeros(gx.shape, bool)
    for p in rpts:
        near |= np.hypot(gx - p[0], gz - p[1]) < 1.0
    assert near.any()
    # Sur l'axe des routes, le terrain suit la route (5 cm sous la chaussée) ; loin, le relief.
    lat, lon = m.frame.to_latlon(gx[near], gz[near])
    assert grid[near] == pytest.approx(m.provider.elevations(lat, lon) - 0.05, abs=0.3)
    far = np.ones(gx.shape, bool)
    for p in rpts:
        far &= np.hypot(gx - p[0], gz - p[1]) > 60.0
    assert grid[far] == pytest.approx(relief[far], abs=1e-3)
    assert len(np.unique(rids)) >= 2


def test_tuiles_vectorielles_et_cache(tmp_path) -> None:
    m, net = make(tmp_path)
    report = m.run()
    vt = report["tuiles_vectorielles"]
    n = vt["tuiles"]
    assert n > 0 and vt["telechargees"] == n and vt["en_cache"] == 0
    assert vt["objets_par_couche"] == {"transportation": 2 * n, "building": n}
    assert vt["routes_gardees"] == n                           # l'autoroute est écartée
    assert net.urls[0] == measure.OPENFREEMAP_TILEJSON
    files = list((tmp_path / "cache" / "brut" / "tuiles" / "14").rglob("*.mvt"))
    assert len(files) == n
    assert report["generation"]["nombre"] >= 2

    # Deuxième passage : tout vient du cache, aucune tuile retéléchargée.
    m2, net2 = make(tmp_path)
    vt2 = m2.run()["tuiles_vectorielles"]
    assert vt2["en_cache"] == n and vt2["telechargees"] == 0 and net2.requests == 0


def test_hors_ligne_aucune_requete(tmp_path) -> None:
    m, net = make(tmp_path, offline=True)
    report = m.run()
    assert net.requests == 0
    assert report["tuiles_vectorielles"]["absentes"] == report["tuiles_vectorielles"]["tuiles"]
    with pytest.raises(CompileError):
        m.net.get("https://exemple.invalid")


def test_extrait_regional_confirmation(tmp_path) -> None:
    m, net = make(tmp_path, region="europe/test")
    refused = m.measure_region()
    assert refused["note"] == "refusé"
    assert not (tmp_path / "cache" / "brut" / "osm").exists()
    m2, _ = make(tmp_path, region="europe/test", yes=True)
    done = m2.measure_region()
    assert done["octets"] == 300 and done["octets_annonces"] == 2_000_000_000
    assert (tmp_path / "cache" / "brut" / "osm" / "europe_test-latest.osm.pbf").is_file()
    again, _ = make(tmp_path, region="europe/test")
    assert again.measure_region()["en_cache"] is True
