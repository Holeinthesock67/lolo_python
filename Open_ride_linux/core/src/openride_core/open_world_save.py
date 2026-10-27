"""Balade en monde ouvert enregistrée comme parcours de la bibliothèque (lot W14, plan W §2.5).

À la fin d'une séance en monde ouvert (`end_session` avec `save` vrai, au-delà de 500 m), la route
réellement parcourue, et non la route engagée au-delà de l'arrivée, est écrite en GPX dans
`~/OpenRide/GPX/` : points tous les 10 m, altitude du profil, nom « Balade du <date> ». Le compilateur la
traite comme n'importe quelle trace au prochain lancement (lot N11) ; elle ne quitte jamais le dossier
personnel. `openride-core open-world-save <id>` fait la même chose après coup depuis le dossier de séance.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
from xml.sax.saxutils import quoteattr

from .config import GPX_DIR, OpenWorldConfig
from .journal import JOURNAL_DIR, read_journal
from .live_route import LiveRoute
from .route import WorldError

log = logging.getLogger("open_world_save")

MIN_SAVE_M = 500.0     # en deçà, pas de parcours
STEP_M = 10.0          # un point tous les 10 m (pas de la route)


def ride_points(route: Any, s_end: float) -> list[tuple[float, float, float]]:
    """(lat, lon, altitude) tous les 10 m de 0 à `s_end`, dernier point compris."""
    s_end = min(max(s_end, 0.0), route.length_m)
    n = int(s_end // STEP_M)
    stops = [i * STEP_M for i in range(n + 1)]
    if s_end - stops[-1] > 1e-6:
        stops.append(s_end)
    out = []
    for s in stops:
        p = route.sample(s)
        out.append((p.lat, p.lon, p.alt_m))
    return out


def ride_name(ts: float) -> str:
    return "Balade du " + time.strftime("%d/%m/%Y", time.localtime(ts))


def gpx_text(points: list[tuple[float, float, float]], name: str, ts: float) -> str:
    when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
    rows = "\n".join(f'      <trkpt lat="{la:.7f}" lon="{lo:.7f}"><ele>{el:.1f}</ele></trkpt>' for la, lo, el in points)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="OpenRide" xmlns="http://www.topografix.com/GPX/1/1">\n'
            f"  <metadata><name>{name}</name><time>{when}</time></metadata>\n"
            f"  <trk>\n    <name>{name}</name>\n    <trkseg>\n{rows}\n    </trkseg>\n  </trk>\n</gpx>\n")


def save_ride(route: Any, s_end: float, ride_id: str, gpx_dir: Path = GPX_DIR,
              ts: float | None = None) -> Path | None:
    """Écrit `<gpx_dir>/<ride_id>.gpx` ; rien (None) si la balade ne dépasse pas 500 m."""
    if s_end <= MIN_SAVE_M:
        log.info("Balade de %.0f m : pas de parcours enregistré (minimum %.0f m).", s_end, MIN_SAVE_M)
        return None
    ts = time.time() if ts is None else ts
    points = ride_points(route, s_end)
    gpx_dir.mkdir(parents=True, exist_ok=True)
    path = gpx_dir / f"{ride_id}.gpx"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(gpx_text(points, ride_name(ts), ts), encoding="utf-8")
    tmp.replace(path)
    log.info("Balade enregistrée : %s (%.1f km, %d points).", path, s_end / 1000.0, len(points))
    return path


def journal_distance(ride_id: str, journal_dir: Path = JOURNAL_DIR) -> float | None:
    """Distance finale de la séance `ow:<ride_id>` dans le journal le plus récent qui la porte."""
    best: tuple[float, float] | None = None
    for path in sorted(journal_dir.glob("*.jsonl")) if journal_dir.is_dir() else []:
        try:
            lines = list(read_journal(path))
        except OSError:
            continue
        header = next((ln for ln in lines if ln.get("kind") == "header"), {})
        if header.get("route_id") != f"ow:{ride_id}":
            continue
        dist = max((ln.get("distance", 0.0) for ln in lines if ln.get("kind") == "record"), default=0.0)
        mtime = path.stat().st_mtime
        if best is None or mtime >= best[0]:
            best = (mtime, float(dist))
    return best[1] if best else None


def save_from_folder(ride_id: str, cfg: OpenWorldConfig, gpx_dir: Path = GPX_DIR,
                     journal_dir: Path = JOURNAL_DIR, length_m: float | None = None) -> tuple[Path | None, float]:
    """Après coup, depuis `<cache_dir>/seances/<id>.world`. Distance : `length_m`, sinon celle du journal,
    sinon toute la route engagée. Lève `WorldError` si le dossier manque ou est illisible."""
    folder = Path(cfg.cache_dir).expanduser() / "seances" / f"{ride_id}.world"
    if not folder.is_dir():
        raise WorldError("route_not_found", f"dossier de séance absent : {folder}")
    route = LiveRoute(folder)
    route.load()
    s_end = length_m if length_m is not None else journal_distance(ride_id, journal_dir)
    if s_end is None:
        s_end = route.length_m
    path = save_ride(route, min(s_end, route.length_m), ride_id, gpx_dir)
    return path, s_end
