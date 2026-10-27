"""Base locale OpenStreetMap du monde ouvert (lot W3) : schéma, classes de route, requêtes."""

from __future__ import annotations

import random
import sqlite3

import pytest

from openride_compiler.errors import CompileError
from openride_compiler.worldgen import osmdb
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter, road_class


@pytest.mark.parametrize("tags,expected", [
    ({"highway": "primary"}, "p"),
    ({"highway": "secondary_link"}, "s"),
    ({"highway": "tertiary"}, "t"),
    ({"highway": "residential"}, "m"),
    ({"highway": "living_street"}, "m"),
    ({"highway": "service"}, "m"),
    ({"highway": "service", "service": "parking_aisle"}, "x"),
    ({"highway": "cycleway"}, "c"),
    ({"highway": "path", "bicycle": "designated", "surface": "asphalt"}, "c"),
    ({"highway": "path", "bicycle": "designated"}, "x"),
    ({"highway": "path"}, "x"),
    ({"highway": "track", "surface": "asphalt"}, "k"),
    ({"highway": "track", "tracktype": "grade1"}, "k"),
    ({"highway": "track"}, "x"),
    ({"highway": "motorway"}, "x"),
    ({"highway": "trunk_link"}, "x"),
    ({"highway": "unclassified", "surface": "gravel"}, "x"),
    ({"highway": "residential", "access": "private"}, "x"),
    ({"highway": "secondary", "bicycle": "no"}, "x"),
    ({"highway": "footway"}, None),
    ({"highway": "steps"}, None),
    ({"building": "yes"}, None),
])
def test_road_class(tags, expected) -> None:
    assert road_class(tags) == expected


def test_fold_and_tags() -> None:
    assert osmdb.fold("Évian-les-Bains") == "evian les bains"
    assert osmdb.fold("Le Hameau d'Été") == "le hameau d ete"
    assert osmdb.useful_tags({"building": "yes", "source": "x", "addr:street": "y", "height": "9"}) == \
        {"height": "9", "building": "yes"}


def test_pack_roundtrip() -> None:
    ids = [1, 2**40, -5]
    coords = [(6.5, 46.25), (6.125, 46.0)]
    assert osmdb.unpack_ids(osmdb.pack_ids(ids)) == ids
    assert osmdb.unpack_coords(osmdb.pack_coords(coords)) == coords


def _random_db(path, n: int = 400, seed: int = 3):
    rnd = random.Random(seed)
    w = OsmDbWriter(path, "geofabrik", "test/aleatoire")
    for i in range(n):
        x, y = rnd.uniform(0, 1), rnd.uniform(0, 1)
        pts = [(x, y)]
        for _ in range(rnd.randint(1, 4)):
            x, y = x + rnd.uniform(-0.05, 0.05), y + rnd.uniform(-0.05, 0.05)
            pts.append((x, y))
        w.add_road(i, {"highway": "residential"}, list(range(len(pts))), pts)
        cx, cy, r = rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0.002, 0.03)
        w.add_area(f"w{i}", "wood", {"natural": "wood"}, [(cx - r, cy - r), (cx + r, cy - r), (cx, cy + r)])
        w.add_point(f"n{i}", "village", f"Lieu {i}", rnd.uniform(0, 1), rnd.uniform(0, 1))
    w.finish(osm_date="2026-10-20T00:00:00Z")
    return path


def test_bbox_queries_match_pure_python_filter(tmp_path) -> None:
    """Le R-tree plus le contrôle exact renvoient les mêmes objets qu'un balayage complet."""
    db = OsmDb(_random_db(tmp_path / "r.sqlite"))
    all_roads = db.roads_in((-1, -1, 2, 2))
    all_areas = db.areas_in((-1, -1, 2, 2))
    all_points = db.points_in((-1, -1, 2, 2))
    assert (len(all_roads), len(all_areas), len(all_points)) == (400, 400, 400)
    rnd = random.Random(7)
    for _ in range(25):
        x, y, s = rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0.01, 0.2)
        b = (x, y, x + s, y + s)
        assert [r.id for r in db.roads_in(b)] == [r.id for r in all_roads if osmdb.polyline_touches(r.coords, b)]
        assert [a.id for a in db.areas_in(b)] == \
            [a.id for a in all_areas if osmdb.polygon_touches({"outer": a.outer}, b)]
        assert [p.id for p in db.points_in(b)] == \
            [p.id for p in all_points if b[0] <= p.lon <= b[2] and b[1] <= p.lat <= b[3]]


def test_touch_predicates_are_exact(tmp_path) -> None:
    """Une route en L dont l'emprise couvre la requête sans la toucher n'est pas renvoyée."""
    w = OsmDbWriter(tmp_path / "l.sqlite", "geofabrik", "test/l")
    w.add_road(1, {"highway": "primary"}, [1, 2, 3], [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])
    w.add_road(2, {"highway": "primary"}, [4, 5], [(0.2, 0.2), (0.8, 0.8)])
    w.add_road(3, {"highway": "motorway"}, [6, 7], [(0.0, 0.5), (1.0, 0.5)])
    w.add_area("w1", "building", {"building": "yes"}, [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
    w.finish()
    with OsmDb(tmp_path / "l.sqlite") as db:
        b = (0.1, 0.6, 0.3, 0.9)                       # dans le coin vide du L, à côté de la diagonale
        assert db.roads_in(b) == []
        assert [r.osm_id for r in db.roads_in((0.4, 0.4, 0.6, 0.6))] == [2]
        assert [r.osm_id for r in db.roads_in((0.4, 0.4, 0.6, 0.6), include_excluded=True)] == [2, 3]
        assert [a.osm_id for a in db.areas_in(b)] == ["w1"]          # emprise à l'intérieur du bâtiment
        assert db.areas_in((2, 2, 3, 3)) == []


def test_search_places(tmp_path) -> None:
    w = OsmDbWriter(tmp_path / "s.sqlite", "geofabrik", "test/s")
    w.add_point("n1", "town", "Évian-les-Bains", 6.59, 46.40)
    w.add_point("n2", "hamlet", "Grande Rive d'Évian", 6.60, 46.41)
    w.add_point("n3", "mountain_pass", "Col de l'Évian", 6.70, 46.30)
    w.add_point("n4", "viewpoint", "Vue d'Évian", 6.61, 46.41)
    w.finish()
    with OsmDb(tmp_path / "s.sqlite") as db:
        names = [p.name for p in db.search_places("evian")]
        assert names == ["Évian-les-Bains", "Grande Rive d'Évian", "Col de l'Évian"]
        assert [p.name for p in db.search_places("EVIAN", limit=1)] == ["Évian-les-Bains"]
        assert db.search_places("  ") == []


def test_meta_and_schema_version(tmp_path) -> None:
    path = _random_db(tmp_path / "m.sqlite", n=3)
    with OsmDb(path) as db:
        assert db.meta["schema_version"] == "1" and db.meta["source"] == "geofabrik"
        assert db.meta["osm_date"] == "2026-10-20T00:00:00Z"
        lon0, lat0, lon1, lat1 = map(float, db.meta["bbox"].split(","))
        assert lon0 < lon1 and lat0 < lat1
        assert {db.count(t) for t in ("roads", "areas", "points")} == {3} and db.count("lines") == 0
    con = sqlite3.connect(path)
    con.execute("UPDATE meta SET value = '0' WHERE key = 'schema_version'")
    con.commit()
    con.close()
    with pytest.raises(CompileError, match="schéma"):
        OsmDb(path)
    with pytest.raises(CompileError, match="absente"):
        OsmDb(tmp_path / "rien.sqlite")
