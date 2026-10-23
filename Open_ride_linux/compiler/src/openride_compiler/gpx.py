"""Lecture d'une trace GPX 1.0 ou 1.1 avec la bibliothèque standard.

Les espaces de noms sont ignorés : seuls comptent les noms locaux des éléments
(`trkpt`, `rtept`, `ele`). Les extensions inconnues sont ignorées.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .errors import CompileError


@dataclass(frozen=True)
class GpxPoint:
    lat: float
    lon: float
    ele: float | None


def _local(tag: object) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _point(el: ET.Element) -> GpxPoint:
    try:
        lat, lon = float(el.attrib["lat"]), float(el.attrib["lon"])
    except (KeyError, ValueError) as exc:
        raise CompileError(f"GPX invalide : point sans lat/lon lisibles ({exc})") from exc
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise CompileError(f"GPX invalide : coordonnées hors limites ({lat}, {lon})")
    ele = None
    for child in el:
        if _local(child.tag) == "ele":
            try:
                ele = float((child.text or "").strip())
            except ValueError:
                ele = None
            if ele is not None and not math.isfinite(ele):
                ele = None
            break
    return GpxPoint(lat, lon, ele)


def parse_gpx(data: bytes) -> list[GpxPoint]:
    """Tous les `trkpt` (tous les `trk` et `trkseg`, dans l'ordre), à défaut les `rtept`."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise CompileError(f"GPX illisible : {exc}") from exc
    trkpts, rtepts = [], []
    for el in root.iter():
        name = _local(el.tag)
        if name == "trkpt":
            trkpts.append(el)
        elif name == "rtept":
            rtepts.append(el)
    points = [_point(el) for el in (trkpts or rtepts)]
    if not points:
        raise CompileError("GPX sans point de trace (trkpt) ni de route (rtept)")
    return points


def read_gpx(path: Path) -> list[GpxPoint]:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise CompileError(f"GPX illisible : {exc}") from exc
    return parse_gpx(data)
