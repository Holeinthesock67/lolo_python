"""Décodeur MVT minimal (lot W0) : tuiles encodées par le test, décodées à l'identique."""

from __future__ import annotations

import gzip
import struct

import pytest

from openride_compiler.worldgen import mvt


# --- encodeur de test (le strict nécessaire de MVT 2.1) ---------------------------------------

def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def key(num: int, wire: int) -> bytes:
    return varint(num << 3 | wire)


def ld(num: int, payload: bytes) -> bytes:
    return key(num, 2) + varint(len(payload)) + payload


def packed(values: list[int]) -> bytes:
    return b"".join(varint(v) for v in values)


def zz(n: int) -> int:
    return (n << 1) ^ (n >> 63)


def encode_value(v) -> bytes:
    if isinstance(v, bool):
        return key(7, 0) + varint(int(v))
    if isinstance(v, str):
        return ld(1, v.encode())
    if isinstance(v, float):
        return key(3, 1) + struct.pack("<d", v)
    if v < 0:
        return key(6, 0) + varint(zz(v))
    return key(5, 0) + varint(v)


def encode_paths(paths: list[tuple[list[tuple[int, int]], bool]]) -> list[int]:
    cmds: list[int] = []
    x = y = 0
    for pts, closed in paths:
        px, py = pts[0]
        cmds += [1 | 1 << 3, zz(px - x), zz(py - y)]
        x, y = px, py
        cmds.append(2 | (len(pts) - 1) << 3)
        for px, py in pts[1:]:
            cmds += [zz(px - x), zz(py - y)]
            x, y = px, py
        if closed:
            cmds.append(7 | 1 << 3)
    return cmds


def encode_layer(name: str, features: list[dict], extent: int = 4096) -> bytes:
    keys: list[str] = []
    values: list = []
    body = key(15, 0) + varint(2) + ld(1, name.encode())
    for f in features:
        tags: list[int] = []
        for k, v in f["tags"].items():
            if k not in keys:
                keys.append(k)
            if v not in values:
                values.append(v)
            tags += [keys.index(k), values.index(v)]
        fb = key(1, 0) + varint(f["id"]) + ld(2, packed(tags)) + key(3, 0) + varint(f["type"])
        fb += ld(4, packed(encode_paths(f["paths"])))
        body += ld(2, fb)
    for k in keys:
        body += ld(3, k.encode())
    for v in values:
        body += ld(4, encode_value(v))
    body += key(5, 0) + varint(extent)
    return body


def encode_tile(layers: dict[str, list[dict]], extent: int = 4096) -> bytes:
    return b"".join(ld(3, encode_layer(n, f, extent)) for n, f in layers.items())


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
