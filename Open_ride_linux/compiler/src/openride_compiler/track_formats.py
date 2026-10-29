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

**Exports Garmin (lot O5)** : `.fit.gz` et `.tcx.gz` sont décompressés en mémoire puis reconnus
par leur contenu ; dans un `.zip`, la première entrée `.fit`, `.tcx` ou `.gpx` (ordre
alphabétique) est lue, les autres sont ignorées et citées dans `notes`. Archive vide,
corrompue ou de plus de `MAX_UNPACKED_BYTES` une fois décompressée : `CompileError` claire.
`TRACK_SUFFIXES`, `track_stem` et `scan_tracks` reprennent les règles de
`openride_core.catalog` (parité vérifiée par `test_catalog_parity.py`).
"""

from __future__ import annotations

import gzip
import io
import math
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

from .errors import CompileError
from .gpx import GpxPoint, _local, parse_gpx, xml_root

SEMICIRCLES_TO_DEG = 180.0 / 2**31
FORMATS = (".gpx", ".fit", ".tcx")
# Extensions des traces, dans l'ordre de priorité en cas de conflit (même ordre que le core).
TRACK_SUFFIXES = (".gpx", ".fit", ".fit.gz", ".tcx", ".tcx.gz", ".zip")
MAX_UNPACKED_BYTES = 50 * 1024 * 1024


def track_stem(name: str) -> tuple[str, int] | None:
    """Nom sans extension de trace et rang de l'extension ; None si ce n'est pas une trace."""
    low = name.lower()
    for rank, suffix in sorted(enumerate(TRACK_SUFFIXES), key=lambda rs: -len(rs[1])):
        if low.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)], rank
    return None


def _track_files(gpx_dir: Path) -> list[Path]:
    """Fichiers de `gpx_dir` et de ses sous-dossiers directs non cachés (packs de parcours, lot O15)."""
    if not gpx_dir.is_dir():
        return []
    files = []
    for p in gpx_dir.iterdir():
        if p.is_file():
            files.append(p)
        elif p.is_dir() and not p.name.startswith("."):
            files.extend(q for q in p.iterdir() if q.is_file())
    return files


def scan_tracks(gpx_dir: Path) -> tuple[list[Path], list[tuple[Path, Path]]]:
    """Traces retenues (une par identifiant, triées par nom) et conflits `(écartée, retenue)`."""
    from .writer import normalize_name

    candidates: list[tuple[str, int, str, Path]] = []
    for p in _track_files(Path(gpx_dir)):
        ts = track_stem(p.name)
        if ts is not None:
            candidates.append((normalize_name(ts[0]), ts[1], p.name, p))
    winners: dict[str, Path] = {}
    conflicts: list[tuple[Path, Path]] = []
    for norm, _rank, _name, p in sorted(candidates):
        if norm in winners:
            conflicts.append((p, winners[norm]))
        else:
            winners[norm] = p
    return sorted(winners.values(), key=lambda p: p.name), conflicts


def _gunzip(data: bytes, name: str) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as fh:
            out = fh.read(MAX_UNPACKED_BYTES + 1)
    except (OSError, EOFError, zlib.error) as exc:
        raise CompileError(f"{name} : archive .gz corrompue ({exc})") from None
    if len(out) > MAX_UNPACKED_BYTES:
        raise CompileError(f"{name} : archive trop grosse une fois décompressée "
                           f"(plus de {MAX_UNPACKED_BYTES // 2**20} Mo)")
    return out


def _unzip(data: bytes, name: str, notes: list[str] | None) -> tuple[bytes, str]:
    """Contenu et nom de la première trace de l'archive (ordre alphabétique)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            entries = sorted((i for i in zf.infolist()
                              if not i.is_dir() and Path(i.filename).suffix.lower() in FORMATS),
                             key=lambda i: i.filename)
            if not entries:
                raise CompileError(f"{name} : archive sans trace .fit, .tcx ou .gpx")
            first = entries[0]
            if first.file_size > MAX_UNPACKED_BYTES:
                raise CompileError(f"{name} : {first.filename} trop gros une fois décompressé "
                                   f"(plus de {MAX_UNPACKED_BYTES // 2**20} Mo)")
            with zf.open(first) as fh:
                out = fh.read(MAX_UNPACKED_BYTES + 1)
    except CompileError:
        raise
    except (zipfile.BadZipFile, OSError, EOFError, zlib.error, NotImplementedError, ValueError) as exc:
        # ValueError : en-tête local incohérent (« negative seek value », fuzz du 28 octobre)
        raise CompileError(f"{name} : archive .zip corrompue ({exc})") from None
    if len(out) > MAX_UNPACKED_BYTES:
        raise CompileError(f"{name} : {first.filename} trop gros une fois décompressé")
    if len(entries) > 1 and notes is not None:
        notes.append(f"{name} : {first.filename} lu, ignoré(s) : " + ", ".join(i.filename for i in entries[1:]))
    return out, first.filename


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


def read_track(path: Path, notes: list[str] | None = None) -> list[GpxPoint]:
    """Points de la trace, quel que soit son format (GPX, FIT ou TCX, éventuellement en `.gz` ou `.zip`).

    `notes` reçoit les remarques à afficher (entrées d'une archive ignorées).
    """
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise CompileError(f"trace illisible : {exc}") from exc
    name = Path(path).name
    inner = name
    if data[:2] == b"\x1f\x8b" or name.lower().endswith(".gz"):
        data = _gunzip(data, name)
        inner = name[:-3] if name.lower().endswith(".gz") else name
    elif data[:4] == b"PK\x03\x04" or name.lower().endswith(".zip"):
        data, inner = _unzip(data, name, notes)
    sniffed = sniff_format(data)
    ext = Path(inner).suffix.lower()
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
    root = xml_root(data, "TCX")
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
