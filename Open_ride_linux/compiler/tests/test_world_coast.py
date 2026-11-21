"""Mer, côte et plages du monde ouvert (lot W23) : tuiles vectorielles, base locale, carrés."""

from __future__ import annotations

import json

import numpy as np

from openride_compiler import coast as K
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.worldgen import mvt, osmdb, squares
from openride_compiler.worldgen import vector_tiles as vt
from openride_compiler.worldgen.mvt import encode_tile
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter
from openride_compiler.worldgen.square_coast import sea_side, weld_ends
from openride_compiler.worldgen.squares import SquareKey, generate_square
from openride_compiler.worldgen.store import WorldCache

LAT, LON = 43.0, 4.6                       # point fictif (zone 31T), comme les essais des tuiles
TX, TY = mvt.lonlat_to_tile(14, LON, LAT)
E = 4096
COAST_PY = 3000                            # côte est-ouest à ce pixel ; mer au sud (pixels plus grands)
ZONE = "31T"
FRAME = squares.zone_frame(ZONE)


def coast_tile(x: int, y: int) -> bytes:
    """Mer au sud du pixel 3000 (marge de 64 pixels, comme OpenMapTiles) ; plage dans la tuile TX."""
    sea = [(-64, COAST_PY), (-64, 4160), (4160, 4160), (4160, COAST_PY)]
    layers = {"water": [{"id": 1, "type": 3, "tags": {"class": "ocean"}, "paths": [(sea, True)]}]}
    if x == TX:
        beach = [(1000, 2950), (1000, 3010), (1500, 3010), (1500, 2950)]
        layers["landcover"] = [{"id": 2, "type": 3, "tags": {"class": "sand", "subclass": "beach"},
                                "paths": [(beach, True)]}]
    return encode_tile(layers)


def tiles_db(tmp_path) -> OsmDb:
    db = vt.TileDb(tmp_path / "tuiles.sqlite")
    for x in (TX, TX + 1):
        db.load(x, TY, coast_tile(x, TY))
    db.close()
    return OsmDb(tmp_path / "tuiles.sqlite")


def zone_xz(px: float, py: float, tx: int = TX) -> tuple[float, float]:
    lon, lat = mvt.tile_to_lonlat(14, tx, TY, E, px, py)
    x, z = FRAME.to_xz(np.array([lat]), np.array([lon]))
    return float(x[0]), float(z[0])


def provider() -> SyntheticProvider:
    return SyntheticProvider(LAT, LON)


def layers_at(db: OsmDb, x: float, z: float) -> tuple[SquareKey, dict]:
    key = SquareKey.at(ZONE, x, -z)
    near = np.zeros((101, 101), dtype=np.float32)
    return key, squares.square_layers(key, db, near, provider(), FRAME)


def ring_area(ring) -> float:
    a = np.asarray(ring, float)
    return 0.5 * abs(float(np.dot(a[:, 0], np.roll(a[:, 1], -1)) - np.dot(a[:, 1], np.roll(a[:, 0], -1))))


def test_coast_runs_drop_tile_border_and_orient_sea_on_right() -> None:
    box = (0, 0, 4096, 4096)
    ring = vt.clip_polygon([(-64, 3000), (-64, 4160), (4160, 4160), (4160, 3000)], *box)
    runs = vt.coast_runs(ring, True, box)
    assert runs == [[(4096, 3000), (0, 3000)]] or runs == [[(0, 3000), (4096, 3000)]]
    # En pixels, y descend : (est, nord) = (x, −y). La mer (y > 3000) doit être à droite.
    (a, b), = runs
    de, dn = b[0] - a[0], -(b[1] - a[1])
    right = (dn, -de)                      # normale à droite en (est, nord)
    assert right[1] < 0                    # vers le sud : la mer
    # île (trou) refermée, entière dans la tuile : anneau fermé, la terre à gauche
    hole = [(100, 100), (200, 100), (200, 200), (100, 200)]
    (isl,) = vt.coast_runs(hole, False, box)
    assert isl[0] == isl[-1] and len(isl) == 5
    assert K._ring_area_en([(p[0], -p[1]) for p in isl[:-1]]) > 0      # terre à gauche : île


def test_tiles_write_coastline_and_beach_rows(tmp_path) -> None:
    box = (LON - 1, LAT - 1, LON + 1, LAT + 1)
    db = tiles_db(tmp_path)
    try:
        lines = db.coast_lines_in(box)
        beaches = db.beaches_in(box)
        assert db.has_coast and db.meta["schema_version"] == str(osmdb.SCHEMA_VERSION) == "1"
        # Compatibilité : la côte est dans ses propres tables, un lecteur plus ancien ne la voit pas.
        assert db.lines_in(box) == [] and db.areas_in(box) == []
    finally:
        db.close()
    assert len(lines) == 2 and {ln.kind for ln in lines} == {"coastline"}
    assert len(beaches) == 1 and beaches[0].tags == {"natural": "beach"}
    assert osmdb.area_kind(beaches[0].tags) == "beach"


def test_tile_db_of_another_schema_is_rebuilt(tmp_path) -> None:
    path = tmp_path / "tuiles.sqlite"
    db = vt.TileDb(path)
    db.load(TX, TY, coast_tile(TX, TY))
    db.db.execute("UPDATE meta SET value = '2' WHERE key = 'schema_version'")     # essai d'une version de la branche
    db.close()
    db = vt.TileDb(path)
    try:
        assert not db.loaded(TX, TY) and db.counts()["coast_lines"] == 0          # refaite : la tuile se reverse
    finally:
        db.close()


def test_tile_db_without_coast_gets_coast_only(tmp_path) -> None:
    """Base des tuiles écrite par une version sans côte : la côte s'ajoute, rien n'est versé deux fois."""
    path = tmp_path / "tuiles.sqlite"
    db = vt.TileDb(path)
    db.load(TX, TY, coast_tile(TX, TY))
    before = db.counts()
    for t in ("coast_lines", "coast_areas", "coast_lines_rt", "coast_areas_rt", "coast_loaded"):
        db.db.execute(f"DROP TABLE {t}")
    db.db.execute("DELETE FROM meta WHERE key = 'coast'")
    db.close()
    with OsmDb(path) as old:
        assert not old.has_coast and old.coast_lines_in((LON - 1, LAT - 1, LON + 1, LAT + 1)) == []
    db = vt.TileDb(path)
    try:
        assert db.loaded(TX, TY) and not db.complete(TX, TY)
        added = db.load(TX, TY, coast_tile(TX, TY))
        assert added == {"coast_lines": 1, "coast_areas": 1} and db.complete(TX, TY)
        assert db.counts() == before and db.load(TX, TY, coast_tile(TX, TY)) == {}
    finally:
        db.close()


def test_tile_db_general_tables_emptied_keep_coast_once(tmp_path) -> None:
    """Tables générales revidées (nouvelle conversion, comme le lot EA3) : elles seules se reversent."""
    path = tmp_path / "tuiles.sqlite"
    db = vt.TileDb(path)
    try:
        db.load(TX, TY, coast_tile(TX, TY))
        before = db.counts()
        for t in ("roads", "areas", "lines", "points"):
            db.db.execute(f"DELETE FROM {t}")
            db.db.execute(f"DELETE FROM {t}_rt")
        db.db.execute("DELETE FROM tiles_loaded")
        assert not db.loaded(TX, TY) and db.coast_loaded(TX, TY)
        added = db.load(TX, TY, coast_tile(TX, TY))
        assert "coast_lines" not in added and "coast_areas" not in added
        assert db.counts() == before and db.complete(TX, TY)
    finally:
        db.close()


def test_region_tags_give_coast_kinds() -> None:
    assert osmdb.line_kind({"natural": "coastline"}) == "coastline"
    assert osmdb.line_kind({"natural": "cliff"}) == "cliff"
    assert osmdb.line_kind({"waterway": "river"}) == "river"
    assert osmdb.area_kind({"natural": "beach", "surface": "pebblestone"}) == "beach"
    assert osmdb.useful_tags({"natural": "beach", "surface": "pebblestone"})["surface"] == "pebblestone"


def test_weld_and_sea_side() -> None:
    a = [(0.0, 0.0), (100.0, 0.0)]
    b = [(101.5, 0.5), (200.0, 0.0)]
    (line,) = K.assemble_coastlines(weld_ends([a, b]))
    assert line[0] == (0.0, 0.0) and line[-1] == (200.0, 0.0) and len(line) == 3
    assert sea_side((50.0, -30.0), [line]) is True         # vers l'est, la mer au sud (à droite)
    assert sea_side((50.0, 30.0), [line]) is False
    assert sea_side((0.0, 0.0), []) is None
    # au plus près d'un sommet (coin de la côte), le côté ne dépend pas du segment retenu
    corner = [(0.0, 100.0), (0.0, 0.0), (100.0, 0.0)]      # vers le sud puis vers l'est : mer au sud-ouest
    assert sea_side((-10.0, -10.0), [corner]) is True
    assert sea_side((10.0, 10.0), [corner]) is False


def test_square_across_tile_seam_has_sea_coast_and_beach(tmp_path) -> None:
    db = tiles_db(tmp_path)
    try:
        xs, zc = zone_xz(E, COAST_PY)                        # côte au bord commun des deux tuiles
        key, lay = layers_at(db, xs, zc)
        x0, z0 = key.corner
        sea = [a for a in lay["water"]["areas"] if a["kind"] == "sea"]
        assert len(sea) == 1 and sea[0]["level_y"] == 0.0 and sea[0]["holes"] == []
        expected = 1000.0 * (z0 + 1000.0 - zc)               # la mer au sud de la côte (z plus grand)
        assert abs(ring_area(sea[0]["outer"]) - expected) < 0.02 * 1000 * 1000
        lines = lay["coast"]["lines"]
        assert lines and all(ln["shore"] in ("rock", "sand") for ln in lines)
        pts = [p for ln in lines for p in ln["points"]]
        assert all(0.0 <= p[0] <= 1000.0 and 0.0 <= p[1] <= 1000.0 for p in pts)   # relatives au coin
        # mer à droite : une côte est-ouest, la mer au sud, se parcourt vers l'est
        assert lines[0]["points"][-1][0] > lines[0]["points"][0][0]
        assert lay["coast"]["version"] == "1.0"

        bx, bz = zone_xz(1250, 2980)                          # au milieu de la plage
        _, lay_b = layers_at(db, bx, bz)
        assert [b["kind"] for b in lay_b["coast"]["beaches"]] == ["sand"]
        assert "sand" in {ln["shore"] for ln in lay_b["coast"]["lines"]}

        _, south = layers_at(db, xs, zc + 2500.0)              # en pleine mer, sans côte dans le carré
        (full,) = [a for a in south["water"]["areas"] if a["kind"] == "sea"]
        assert abs(ring_area(full["outer"]) - 1e6) < 1.0 and south["coast"]["lines"] == []
        _, north = layers_at(db, xs, zc - 2500.0)
        assert not [a for a in north["water"]["areas"] if a["kind"] == "sea"]
        assert north["coast"] == {"version": "1.0", "lines": [], "beaches": []}
    finally:
        db.close()


def test_square_without_coast_writes_empty_coast_file(tmp_path) -> None:
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/terre")
    w.add_point("n1", "village", "Hameau", LON, LAT)
    w.finish(osm_date="2026-10-20T00:00:00Z")
    cache = WorldCache(tmp_path / "cache", 10**9, log=lambda _m: None)
    x, z = FRAME.to_xz(np.array([LAT]), np.array([LON]))
    key = SquareKey.at(ZONE, float(x[0]), -float(z[0]))
    with OsmDb(tmp_path / "osm.sqlite") as db:
        folder = generate_square(key, db, provider(), cache)
    doc = json.loads((folder / "coast.json").read_text(encoding="utf-8"))
    assert doc == {"version": "1.0", "lines": [], "beaches": []}
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    assert meta["counts"]["coast_lines"] == 0 and meta["counts"]["beaches"] == 0


def test_open_world_session_links_sea_and_coast(tmp_path) -> None:
    """Séance sans extrait régional : route à ~400 m de la mer ; mer et côte liées dans la séance."""
    import re
    from pathlib import Path

    from openride_compiler.worldgen.process import FakeClock, WorldSession

    def tile(x: int, y: int) -> bytes:
        sea = [(-64, COAST_PY), (-64, 4160), (4160, 4160), (4160, COAST_PY)]
        return encode_tile({
            "transportation": [{"id": 1, "type": 2, "tags": {"class": "tertiary"},
                                "paths": [([(-64, 2048), (4160, 2048)], False)]},
                               {"id": 2, "type": 2, "tags": {"class": "minor"},
                                "paths": [([(2048, -64), (2048, 2900)], False)]}],
            "water": [{"id": 3, "type": 3, "tags": {"class": "ocean"}, "paths": [(sea, True)]}]})

    class Net:
        TEMPLATE = "https://tuiles.invalid/t/{z}/{x}/{y}.pbf"

        def get(self, url: str) -> bytes:
            return json.dumps({"tiles": [self.TEMPLATE]}).encode()

        def download(self, url: str, dest: Path) -> int:
            _z, x, y = map(int, re.findall(r"/(\d+)/(\d+)/(\d+)\.pbf$", url)[0])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(tile(x, y))
            return dest.stat().st_size

    c = WorldCache(tmp_path / "cache", 10**9, log=lambda _m: None)
    rec: list[dict] = []
    s = WorldSession(c, SyntheticProvider(LAT, LON), rec.append, {}, tmp_path / "s.world", network=True,
                     clock=FakeClock(), log=lambda _m: None)
    s.tile_net = Net()
    s_lon, s_lat = mvt.tile_to_lonlat(14, TX, TY, E, 1500, 2048)
    s.handle({"type": "open", "lat": s_lat, "lon": s_lon, "heading_deg": 90, "nav": "ride", "target": None,
              "loop_km": None, "seed": 1, "network": True})
    assert rec[-1]["type"] == "revision"
    for _ in range(400):
        if not s.has_work():
            break
        s.work()
    world = s.session_dir
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["layers"]["coast"] == {"present": True, "version": "1.0"}
    coast_files = sorted((world / "coast").glob("tile_*.json"))
    water_files = sorted((world / "water").glob("tile_*.json"))
    assert coast_files and len(coast_files) == len(water_files)
    seas = [a for f in water_files for a in json.loads(f.read_text(encoding="utf-8"))["areas"] if a["kind"] == "sea"]
    lines = [ln for f in coast_files for ln in json.loads(f.read_text(encoding="utf-8"))["lines"]]
    assert seas and lines and s.stats["sea_squares"] > 0
