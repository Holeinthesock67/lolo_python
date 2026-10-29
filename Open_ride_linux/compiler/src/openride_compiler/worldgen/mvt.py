"""Décodeur minimal de tuiles vectorielles Mapbox (MVT 2.1), bibliothèque standard seulement (lot W0).

- Lecture protobuf : entiers « varint », champs de longueur, entiers 32 et 64 bits fixes.
- Géométrie : commandes MoveTo (1), LineTo (2), ClosePath (7), paramètres en zigzag relatifs.
- Polygones : un anneau d'aire positive (formule du géomètre en coordonnées de tuile, y vers le
  bas) ouvre un nouveau polygone ; un anneau d'aire négative est un trou du polygone en cours.
- Une tuile compressée en gzip (en-tête 1f 8b) est décompressée d'abord.
"""

from __future__ import annotations

import gzip
import math
import struct
from dataclasses import dataclass, field
from typing import Any

GEOM_KINDS = {1: "point", 2: "line", 3: "polygon"}

Ring = list[tuple[int, int]]


@dataclass
class Feature:
    id: int | None
    kind: str                     # « point », « line », « polygon » ou « unknown »
    tags: dict[str, Any]
    # point : liste de points ; line : liste de lignes ; polygon : liste de {"outer", "holes"}
    geometry: list[Any] = field(default_factory=list)


@dataclass
class Layer:
    name: str
    extent: int
    features: list[Feature]


class MvtError(ValueError):
    """Tuile illisible."""


# --- protobuf ---------------------------------------------------------------------------------

def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise MvtError("varint tronqué")
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7
        if shift > 70:
            raise MvtError("varint trop long")


def _fields(buf: bytes):
    """Itère sur (numéro de champ, type, valeur) ; la valeur d'un champ de longueur est un `bytes`."""
    pos = 0
    n = len(buf)
    while pos < n:
        key, pos = _varint(buf, pos)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _varint(buf, pos)
        elif wire == 1:
            if pos + 8 > n:
                raise MvtError("champ 64 bits tronqué")
            value = buf[pos:pos + 8]
            pos += 8
        elif wire == 2:
            length, pos = _varint(buf, pos)
            if pos + length > n:
                raise MvtError("champ de longueur tronqué")
            value = buf[pos:pos + length]
            pos += length
        elif wire == 5:
            if pos + 4 > n:
                raise MvtError("champ 32 bits tronqué")
            value = buf[pos:pos + 4]
            pos += 4
        else:
            raise MvtError(f"type de champ protobuf non géré : {wire}")
        yield number, wire, value


def _packed(value: bytes) -> list[int]:
    out = []
    pos = 0
    while pos < len(value):
        v, pos = _varint(value, pos)
        out.append(v)
    return out


def _zigzag(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


def _signed64(n: int) -> int:
    return n - (1 << 64) if n >= 1 << 63 else n


def _value(buf: bytes) -> Any:
    out: Any = None
    for number, _, v in _fields(buf):
        if number == 1:
            out = v.decode("utf-8", errors="replace")
        elif number == 2:
            out = struct.unpack("<f", v)[0]
        elif number == 3:
            out = struct.unpack("<d", v)[0]
        elif number == 4:
            out = _signed64(v)
        elif number == 5:
            out = v
        elif number == 6:
            out = _zigzag(v)
        elif number == 7:
            out = bool(v)
    return out


# --- géométrie --------------------------------------------------------------------------------

def ring_area(ring: Ring) -> float:
    """Aire signée (formule du géomètre) en coordonnées de tuile ; positive pour un anneau extérieur."""
    s = 0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _paths(cmds: list[int]) -> list[tuple[Ring, bool]]:
    """Suites de points (chemin, fermé ou non) décodées depuis les commandes."""
    paths: list[tuple[Ring, bool]] = []
    current: Ring = []
    x = y = 0
    i = 0
    while i < len(cmds):
        cmd = cmds[i]
        i += 1
        cid, count = cmd & 7, cmd >> 3
        if cid in (1, 2):
            if cid == 1 and current:
                paths.append((current, False))
                current = []
            for _ in range(count):
                if i + 1 >= len(cmds):
                    raise MvtError("géométrie tronquée")
                x += _zigzag(cmds[i])
                y += _zigzag(cmds[i + 1])
                i += 2
                current.append((x, y))
        elif cid == 7:
            if current:
                paths.append((current, True))
                current = []
        else:
            raise MvtError(f"commande de géométrie inconnue : {cid}")
    if current:
        paths.append((current, False))
    return paths


def _geometry(kind: str, cmds: list[int]) -> list[Any]:
    paths = _paths(cmds)
    if kind == "point":
        return [pt for path, _ in paths for pt in path]
    if kind == "line":
        return [path for path, _ in paths]
    if kind == "polygon":
        polygons: list[dict[str, list[Ring]]] = []
        for ring, _ in paths:
            area = ring_area(ring)
            if area > 0 or not polygons:
                polygons.append({"outer": ring, "holes": []})
            elif area < 0:
                polygons[-1]["holes"].append(ring)
        return polygons
    return []


# --- tuile ------------------------------------------------------------------------------------

def _layer(buf: bytes) -> Layer:
    name = ""
    extent = 4096
    keys: list[str] = []
    values: list[Any] = []
    raw_features: list[bytes] = []
    for number, _, v in _fields(buf):
        if number == 1:
            name = v.decode("utf-8", errors="replace")
        elif number == 2:
            raw_features.append(v)
        elif number == 3:
            keys.append(v.decode("utf-8", errors="replace"))
        elif number == 4:
            values.append(_value(v))
        elif number == 5:
            extent = v
    features = []
    for raw in raw_features:
        fid: int | None = None
        tags: list[int] = []
        gtype = 0
        cmds: list[int] = []
        for number, wire, v in _fields(raw):
            if number == 1:
                fid = v
            elif number == 2:
                tags.extend(_packed(v) if wire == 2 else [v])
            elif number == 3:
                gtype = v
            elif number == 4:
                cmds.extend(_packed(v) if wire == 2 else [v])
        if len(tags) % 2:
            raise MvtError(f"couche {name} : balises en nombre impair")
        decoded = {}
        for k, val in zip(tags[0::2], tags[1::2]):
            if k >= len(keys) or val >= len(values):
                raise MvtError(f"couche {name} : index de balise hors limites")
            decoded[keys[k]] = values[val]
        kind = GEOM_KINDS.get(gtype, "unknown")
        features.append(Feature(fid, kind, decoded, _geometry(kind, cmds)))
    return Layer(name, extent, features)


def decode_tile(data: bytes) -> dict[str, Layer]:
    """Couches d'une tuile, par nom. Lève MvtError si la tuile est illisible."""
    if data[:2] == b"\x1f\x8b":
        try:
            data = gzip.decompress(data)
        except OSError as exc:
            raise MvtError(f"gzip illisible : {exc}") from exc
    layers: dict[str, Layer] = {}
    for number, _, v in _fields(data):
        if number == 3:
            layer = _layer(v)
            layers[layer.name] = layer
    return layers


# --- coordonnées ------------------------------------------------------------------------------

def tile_to_lonlat(z: int, x: int, y: int, extent: int, px: float, py: float) -> tuple[float, float]:
    """Point (px, py) d'une tuile Web Mercator (z, x, y) en (longitude, latitude)."""
    n = 2 ** z
    fx = (x + px / extent) / n
    fy = (y + py / extent) / n
    lon = fx * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * fy))))
    return lon, lat


def lonlat_to_tile(z: int, lon: float, lat: float) -> tuple[int, int]:
    """Tuile Web Mercator (x, y) qui contient le point."""
    n = 2 ** z
    lat = max(min(lat, 85.05112878), -85.05112878)
    fx = (lon + 180.0) / 360.0
    fy = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0
    return min(int(fx * n), n - 1), min(int(fy * n), n - 1)


# --- encodeur (le strict nécessaire de MVT 2.1 : faux serveur de tuiles X28 et tests) ---------

def _enc_varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _enc_key(num: int, wire: int) -> bytes:
    return _enc_varint(num << 3 | wire)


def _enc_ld(num: int, payload: bytes) -> bytes:
    return _enc_key(num, 2) + _enc_varint(len(payload)) + payload


def _enc_packed(values: list[int]) -> bytes:
    return b"".join(_enc_varint(v) for v in values)


def _enc_zigzag(n: int) -> int:
    return (n << 1) ^ (n >> 63)


def _enc_value(v) -> bytes:
    if isinstance(v, bool):
        return _enc_key(7, 0) + _enc_varint(int(v))
    if isinstance(v, str):
        return _enc_ld(1, v.encode())
    if isinstance(v, float):
        return _enc_key(3, 1) + struct.pack("<d", v)
    if v < 0:
        return _enc_key(6, 0) + _enc_varint(_enc_zigzag(v))
    return _enc_key(5, 0) + _enc_varint(v)


def _enc_paths(paths: list[tuple[list[tuple[int, int]], bool]]) -> list[int]:
    cmds: list[int] = []
    x = y = 0
    for pts, closed in paths:
        px, py = pts[0]
        cmds += [1 | 1 << 3, _enc_zigzag(px - x), _enc_zigzag(py - y)]
        x, y = px, py
        cmds.append(2 | (len(pts) - 1) << 3)
        for px, py in pts[1:]:
            cmds += [_enc_zigzag(px - x), _enc_zigzag(py - y)]
            x, y = px, py
        if closed:
            cmds.append(7 | 1 << 3)
    return cmds


def _enc_layer(name: str, features: list[dict], extent: int = 4096) -> bytes:
    keys: list[str] = []
    values: list = []
    body = _enc_key(15, 0) + _enc_varint(2) + _enc_ld(1, name.encode())
    for f in features:
        tags: list[int] = []
        for k, v in f["tags"].items():
            if k not in keys:
                keys.append(k)
            if v not in values:
                values.append(v)
            tags += [keys.index(k), values.index(v)]
        fb = _enc_key(1, 0) + _enc_varint(f["id"]) + _enc_ld(2, _enc_packed(tags)) + _enc_key(3, 0) + _enc_varint(f["type"])
        fb += _enc_ld(4, _enc_packed(_enc_paths(f["paths"])))
        body += _enc_ld(2, fb)
    for k in keys:
        body += _enc_ld(3, k.encode())
    for v in values:
        body += _enc_ld(4, _enc_value(v))
    body += _enc_key(5, 0) + _enc_varint(extent)
    return body


def encode_tile(layers: dict[str, list[dict]], extent: int = 4096) -> bytes:
    """Tuile MVT 2.1 non compressée : `{couche: [{"id", "type" (1 point, 2 ligne, 3 surface), "tags", "paths"}]}`."""
    return b"".join(_enc_ld(3, _enc_layer(n, f, extent)) for n, f in layers.items())
