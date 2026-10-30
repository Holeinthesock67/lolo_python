"""Lecture des parcours compilés `.world` et interpolation de la couche route (Format .world v1).

Module commun au core et, par traduction exacte, à l'engine (`engine/scripts/route_data.gd`).
Les deux implémentations sont tenues identiques par des vecteurs de test partagés :
`docs/contracts/world/route_test_vectors.json` (générés par `tools/route_vectors.py`).

Règle d'interpolation (format §4.5) :
- abscisses : s_i = i·ds_m pour i < n−1, et s_{n−1} = length_m ;
- grandeurs scalaires (pente, lat, lon, altitude) : linéaire ;
- cap : par l'écart angulaire le plus court, résultat dans [0, 360) ;
- position (x, alt_m, z) : Catmull-Rom centripète (Barry-Goldman, α = 0,5), points fantômes
  aux extrémités d'un parcours ouvert, indices circulaires pour une boucle.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

from .config import ROUTES_DIR

log = logging.getLogger("route")

FORMAT_NAME = "openride-world"
SUPPORTED_MAJOR = 1
KNOT_EPS_M = 1e-6
ROUTE_FIELDS = ("lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg")


class WorldError(Exception):
    """Parcours absent ou invalide ; `code` est le code d'erreur du contrat IPC."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RouteSample:
    x: float
    y: float
    z: float
    lat: float
    lon: float
    alt_m: float
    grade_pct: float
    heading_deg: float


def _shortest_delta_deg(a: float, b: float) -> float:
    """Écart de a vers b dans ]−180, 180]."""
    d = (b - a) % 360.0
    return d - 360.0 if d > 180.0 else d


def _catmull_rom(p0, p1, p2, p3, u: float) -> tuple[float, float, float]:
    """Point d'une spline de Catmull-Rom centripète entre p1 (u = 0) et p2 (u = 1)."""
    def knot(a, b) -> float:
        return max(math.dist(a, b), KNOT_EPS_M) ** 0.5

    t0 = 0.0
    t1 = t0 + knot(p0, p1)
    t2 = t1 + knot(p1, p2)
    t3 = t2 + knot(p2, p3)
    t = t1 + u * (t2 - t1)

    def lerp(a, b, ta, tb):
        wa, wb = (tb - t) / (tb - ta), (t - ta) / (tb - ta)
        return (wa * a[0] + wb * b[0], wa * a[1] + wb * b[1], wa * a[2] + wb * b[2])

    a1 = lerp(p0, p1, t0, t1)
    a2 = lerp(p1, p2, t1, t2)
    a3 = lerp(p2, p3, t2, t3)
    b1 = lerp(a1, a2, t0, t2)
    b2 = lerp(a2, a3, t1, t3)
    return lerp(b1, b2, t1, t2)


class Route:
    """Couche route d'un `.world`, prête à être échantillonnée en toute position `s`."""

    def __init__(self, data: dict) -> None:
        try:
            self.n = int(data["n"])
            self.ds_m = float(data["ds_m"])
            self.length_m = float(data["length_m"])
            self.type = str(data.get("type", "open"))
            cols = {k: [float(v) for v in data[k]] for k in ROUTE_FIELDS}
        except (KeyError, TypeError, ValueError) as exc:
            raise WorldError("route_invalid", f"route.json incomplet ou mal typé : {exc}") from exc
        if self.n < 2:
            raise WorldError("route_invalid", f"n = {self.n} : il faut au moins 2 points")
        for k, col in cols.items():
            if len(col) != self.n:
                raise WorldError("route_invalid", f"« {k} » a {len(col)} valeurs au lieu de {self.n}")
        if self.ds_m <= 0:
            raise WorldError("route_invalid", "ds_m doit être positif")
        last_regular = (self.n - 2) * self.ds_m
        if not last_regular < self.length_m <= last_regular + self.ds_m + 0.01:
            raise WorldError("route_invalid",
                             f"length_m = {self.length_m} incohérent avec n = {self.n} et ds_m = {self.ds_m}")
        if self.type not in ("open", "loop", "out_and_back"):
            raise WorldError("route_invalid", f"type de parcours inconnu : {self.type}")

        self.lat, self.lon, self.alt_m = cols["lat"], cols["lon"], cols["alt_m"]
        self.x, self.z = cols["x"], cols["z"]
        self.grade_pct, self.heading_deg = cols["grade_pct"], cols["heading_deg"]
        self.s = [i * self.ds_m for i in range(self.n - 1)] + [self.length_m]
        self.points = list(zip(self.x, self.alt_m, self.z))
        if self.type == "loop":
            gap = math.dist((self.x[0], self.z[0]), (self.x[-1], self.z[-1]))
            if gap > 1.0:
                raise WorldError("route_invalid", f"boucle non fermée : {gap:.1f} m entre la fin et le départ")

    # --- positions ---------------------------------------------------------------------

    @property
    def is_loop(self) -> bool:
        return self.type == "loop"

    def wrap(self, s: float) -> float:
        """Boucle : s modulo la longueur ; sinon s borné à [0, longueur]."""
        if self.is_loop:
            return s % self.length_m
        return min(max(s, 0.0), self.length_m)

    def _segment(self, s: float) -> tuple[int, float]:
        """Indice i du segment [i, i+1] contenant s (déjà ramené par wrap) et fraction u."""
        i = min(int(s / self.ds_m), self.n - 2)
        s0, s1 = self.s[i], self.s[i + 1]
        u = (s - s0) / (s1 - s0) if s1 > s0 else 0.0
        return i, min(max(u, 0.0), 1.0)

    def _point(self, k: int) -> tuple[float, float, float]:
        """Point k, avec points fantômes (ouvert) ou indices circulaires (boucle)."""
        n = self.n
        if self.is_loop:
            return self.points[k % (n - 1)]
        if k < 0:
            a, b = self.points[0], self.points[1]
            return (2 * a[0] - b[0], 2 * a[1] - b[1], 2 * a[2] - b[2])
        if k > n - 1:
            a, b = self.points[n - 1], self.points[n - 2]
            return (2 * a[0] - b[0], 2 * a[1] - b[1], 2 * a[2] - b[2])
        return self.points[k]

    # --- échantillonnage -----------------------------------------------------------------

    def grade_at(self, s: float) -> float:
        """Pente en s (linéaire) : chemin rapide pour la boucle à 50 Hz."""
        i, u = self._segment(self.wrap(s))
        g = self.grade_pct
        return g[i] + (g[i + 1] - g[i]) * u

    def sample(self, s: float) -> RouteSample:
        i, u = self._segment(self.wrap(s))

        def lin(col: list[float]) -> float:
            return col[i] + (col[i + 1] - col[i]) * u

        x, y, z = _catmull_rom(self._point(i - 1), self._point(i), self._point(i + 1),
                               self._point(i + 2), u)
        h0 = self.heading_deg[i]
        heading = (h0 + u * _shortest_delta_deg(h0, self.heading_deg[i + 1])) % 360.0
        return RouteSample(x=x, y=y, z=z, lat=lin(self.lat), lon=lin(self.lon),
                           alt_m=lin(self.alt_m), grade_pct=lin(self.grade_pct),
                           heading_deg=heading)


@dataclass
class World:
    path: Path
    manifest: dict
    route: Route
    segments: tuple = ()        # couche `segments.json` (format 1.3, série T), vide si absente

    @property
    def name(self) -> str:
        return str(self.manifest.get("name") or self.path.stem)


def routes_dir() -> Path:
    return ROUTES_DIR


def find_world(route_id: str, root: Path | None = None) -> Path:
    return (root or routes_dir()) / f"{route_id}.world"


def _read_json(path: Path, what: str) -> dict:
    if not path.is_file():
        raise WorldError("route_invalid", f"{what} absent : {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorldError("route_invalid", f"{what} illisible : {exc}") from exc
    if not isinstance(data, dict):
        raise WorldError("route_invalid", f"{what} n'est pas un objet JSON")
    return data


def load_world(path: Path) -> World:
    """Charge et valide un dossier `.world` (format §10). Lève WorldError."""
    path = Path(path)
    if not path.is_dir():
        raise WorldError("route_not_found", f"parcours introuvable : {path}")
    manifest = _read_json(path / "manifest.json", "manifest.json")
    if manifest.get("format") != FORMAT_NAME:
        raise WorldError("route_invalid", f"format inattendu : {manifest.get('format')!r}")
    try:
        major = int(str(manifest.get("format_version", "")).split(".")[0])
    except ValueError as exc:
        raise WorldError("route_invalid", "format_version illisible") from exc
    if major > SUPPORTED_MAJOR:
        raise WorldError("route_invalid",
                         f"format_version {manifest['format_version']} trop récent (majeur {SUPPORTED_MAJOR} lu)")
    if manifest.get("live") is True:                     # monde vivant (§13) : route en parties de 1 km, lue telle quelle
        from .live_route import read_route
        route = read_route(path)
    else:
        route_file = (manifest.get("route") or {}).get("file", "route.json")
        route = Route(_read_json(path / route_file, route_file))
    return World(path=path, manifest=manifest, route=route, segments=load_segments(path, manifest, route))


def load_segments(path: Path, manifest: dict, route: Route) -> tuple:
    """Couche facultative `segments.json` (format §8 bis) ; invalide : ignorée avec un avertissement.

    La séance reste possible sans segment : la couche n'est jamais une raison de refuser un parcours.
    """
    from .segments import Segment

    layer = (manifest.get("layers") or {}).get("segments")
    if not isinstance(layer, dict) or not layer.get("present"):
        return ()
    name = str(layer.get("file") or "segments.json")
    try:
        data = _read_json(path / name, name)
        if not str(data.get("version", "")).startswith("1."):
            raise ValueError(f"version {data.get('version')!r} inconnue")
        out = []
        for item in data["segments"]:
            seg = Segment(**{k: item[k] for k in Segment.__dataclass_fields__})
            if seg.type not in ("sprint", "climb") or not 0.0 <= seg.s_start < seg.s_end <= route.length_m + 0.1:
                raise ValueError(f"segment {seg.id} invalide")
            out.append(seg)
        if len({s.id for s in out}) != len(out):
            raise ValueError("identifiants en double")
    except (WorldError, KeyError, TypeError, ValueError) as exc:
        log.warning("%s : couche segments ignorée (%s)", path.name, exc)
        return ()
    return tuple(sorted(out, key=lambda s: s.s_start))
