"""Décodeur MVT minimal (lot W0) : tuiles encodées par `mvt.encode_tile`, décodées à l'identique."""

from __future__ import annotations

import gzip

import pytest

from openride_compiler.worldgen import mvt
from openride_compiler.worldgen.mvt import encode_tile


OUTER = [(100, 100), (900, 100), (900, 900), (100, 900)]          # aire positive (y vers le bas)
HOLE = [(300, 300), (300, 600), (600, 600), (600, 300)]           # aire négative
LINE = [(0, 2048), (1000, 2000), (4096, 1900)]


def sample_tile() -> bytes:
    return encode_tile({
        "poi": [{"id": 7, "type": 1, "tags": {"class": "place_of_worship", "rank": 3}, "paths": [([(512, 640)], False)]}],
        "transportation": [{"id": 11, "type": 2, "tags": {"class": "tertiary", "brunnel": "bridge", "oneway": -1},
                            "paths": [(LINE, False)]}],
        "building": [{"id": 13, "type": 3, "tags": {"render_height": 7.5, "flag": True},
                      "paths": [(OUTER, True), (HOLE, True)]}],
    })


@pytest.mark.parametrize("compress", [False, True])
def test_decode_identique(compress: bool) -> None:
    data = sample_tile()
    if compress:
        data = gzip.compress(data)
    layers = mvt.decode_tile(data)
    assert set(layers) == {"poi", "transportation", "building"}

    poi = layers["poi"].features[0]
    assert (poi.id, poi.kind, poi.geometry) == (7, "point", [(512, 640)])
    assert poi.tags == {"class": "place_of_worship", "rank": 3}

    road = layers["transportation"].features[0]
    assert road.kind == "line" and road.geometry == [LINE]
    assert road.tags == {"class": "tertiary", "brunnel": "bridge", "oneway": -1}

    b = layers["building"].features[0]
    assert b.kind == "polygon" and b.tags == {"render_height": 7.5, "flag": True}
    assert b.geometry == [{"outer": OUTER, "holes": [HOLE]}]
    assert mvt.ring_area(b.geometry[0]["outer"]) > 0 > mvt.ring_area(b.geometry[0]["holes"][0])
    assert layers["building"].extent == 4096


def test_deux_polygones_dans_un_objet() -> None:
    other = [(1000, 1000), (1200, 1000), (1200, 1200)]
    data = encode_tile({"water": [{"id": 1, "type": 3, "tags": {}, "paths": [(OUTER, True), (other, True)]}]})
    geom = mvt.decode_tile(data)["water"].features[0].geometry
    assert [p["outer"] for p in geom] == [OUTER, other]


def test_tuile_tronquee() -> None:
    with pytest.raises(mvt.MvtError):
        mvt.decode_tile(sample_tile()[:-5])


def test_coins_de_tuile() -> None:
    z, x, y = 14, 8443, 5843
    n = 2 ** z
    lon0, lat0 = mvt.tile_to_lonlat(z, x, y, 4096, 0, 0)
    lon1, lat1 = mvt.tile_to_lonlat(z, x, y, 4096, 4096, 4096)
    assert lon0 == pytest.approx(x / n * 360 - 180, abs=1e-9)
    assert lon1 == pytest.approx((x + 1) / n * 360 - 180, abs=1e-9)
    assert lat0 > lat1
    # Le coin bas-droit de (x, y) est le coin haut-gauche de (x + 1, y + 1).
    assert (lon1, lat1) == pytest.approx(mvt.tile_to_lonlat(z, x + 1, y + 1, 4096, 0, 0), abs=1e-9)
    assert mvt.lonlat_to_tile(z, (lon0 + lon1) / 2, (lat0 + lat1) / 2) == (x, y)
