"""Lecture d'une trace GPX, FIT ou TCX (lot M7) : mêmes points `GpxPoint` pour le compilateur.

Le format se choisit d'après l'extension (`.gpx`, `.fit`, `.tcx`, insensible à la casse) et,
pour une extension inconnue ou trompeuse, d'après les premiers octets : en-tête FIT (« .FIT »
aux octets 8 à 11), XML `TrainingCenterDatabase` (TCX) ou `gpx`.

- **FIT** (activité Garmin ou parcours « course ») : messages `record`, `enhanced_altitude`
  préférée à `altitude`. `fit-tool` rend `position_lat` et `position_long` déjà convertis des
  semi-cercles en degrés ; une valeur hors de ±180 serait encore en semi-cercles et est
  convertie (× 180 / 2³¹). Les points sans position (début d'activité sans GPS, tunnel) sont
  ignorés ; un FIT sans aucune position (séance sur home trainer) est refusé.
- **TCX** : `Trackpoint` avec `Position/LatitudeDegrees`, `LongitudeDegrees` et `AltitudeMeters`,
  dans les `Lap` d'une activité (mis bout à bout) ou le `Track` d'un parcours (`Course`) ;
  espaces de noms ignorés comme dans `gpx.py`.
Les points consécutifs identiques sont fusionnés.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import CompileError
from .gpx import GpxPoint, _local, parse_gpx

SEMICIRCLES_TO_DEG = 180.0 / 2**31
FORMATS = (".gpx", ".fit", ".tcx")


def sniff_format(data: bytes) -> str | None:
    """« .fit », « .tcx » ou « .gpx » d'après le contenu ; None si inconnu."""
    if len(data) >= 12 and data[8:12] == b".FIT":
        return ".fit"
    head = data[:2048].lower()
    if b"trainingcenterdatabase" in head:
        return ".tcx"
    if b"<gpx" in head:
        return ".gpx"
    return None


def read_track(path: Path) -> list[GpxPoint]:
    """Points de la trace, quel que soit son format (GPX, FIT ou TCX)."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise CompileError(f"trace illisible : {exc}") from exc
    sniffed = sniff_format(data)
    ext = Path(path).suffix.lower()
    fmt = sniffed or (ext if ext in FORMATS else None)
    if fmt is None:
        raise CompileError(f"{Path(path).name} : format inconnu (attendu GPX, FIT ou TCX)")
    if fmt == ".gpx":
        return parse_gpx(data)
    points = parse_fit(data) if fmt == ".fit" else parse_tcx(data)
    return _dedup(points)


def _dedup(points: list[GpxPoint]) -> list[GpxPoint]:
    out: list[GpxPoint] = []
    for p in points:
        if out and (out[-1].lat, out[-1].lon) == (p.lat, p.lon):
            continue
        out.append(p)
    return out


def _deg(v: float | None) -> float | None:
    if v is None or not math.isfinite(v):
        return None
    return v * SEMICIRCLES_TO_DEG if abs(v) > 180.0 else float(v)


def _valid(lat: float | None, lon: float | None) -> bool:
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def parse_fit(data: bytes) -> list[GpxPoint]:
    from fit_tool.fit_file import FitFile
    from fit_tool.profile.messages.record_message import RecordMessage

    try:
        fit = FitFile.from_bytes(data)
    except Exception as exc:
        raise CompileError(f"FIT illisible : {exc}") from exc
    points = []
    for rec in fit.records:
        m = rec.message
        if not isinstance(m, RecordMessage):
            continue
        lat, lon = _deg(m.position_lat), _deg(m.position_long)
        if not _valid(lat, lon):
            continue   # point sans GPS (début d'activité, tunnel)
        alt = m.enhanced_altitude if m.enhanced_altitude is not None else m.altitude
        alt = float(alt) if alt is not None and math.isfinite(alt) else None
        points.append(GpxPoint(lat, lon, alt))
    if not points:
        raise CompileError("aucune position GPS dans ce FIT")
    return points


def _child(el: ET.Element, name: str) -> ET.Element | None:
    return next((c for c in el if _local(c.tag) == name), None)


def _float(el: ET.Element | None) -> float | None:
    if el is None:
        return None
    try:
        v = float((el.text or "").strip())
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def parse_tcx(data: bytes) -> list[GpxPoint]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise CompileError(f"TCX illisible : {exc}") from exc
    points = []
    for el in root.iter():   # ordre du document : tours d'une activité, puis piste d'un parcours
        if _local(el.tag) != "Trackpoint":
            continue
        pos = _child(el, "Position")
        if pos is None:
            continue
        lat, lon = _float(_child(pos, "LatitudeDegrees")), _float(_child(pos, "LongitudeDegrees"))
        if not _valid(lat, lon):
            continue
        points.append(GpxPoint(lat, lon, _float(_child(el, "AltitudeMeters"))))
    if not points:
        raise CompileError("TCX sans point de trace (Trackpoint avec Position)")
    return points
