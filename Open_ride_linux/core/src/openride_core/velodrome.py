"""Générateur de la piste du vélodrome (série VD, lots VD2 et VD3 ; plan `docs/4.0/PLAN_SERIE_VD.md` §3 et §4).

Module pur, bibliothèque standard seulement. Le vélodrome est un `.world` en boucle (`type = loop`) que le
core écrit lui-même, sans GPX ni compilateur, comme le parcours de démonstration (`demo_world.py`).

Géométrie (§3.1) : la route est la **ligne de mesure** (noire, à 0,20 m du bord intérieur). Un tour se lit
ainsi, dans le sens inverse des aiguilles d'une montre vu du dessus (virages à gauche) :

    demi-droite d'arrivée, raccordement d'entrée, arc, raccordement de sortie, droite opposée,
    raccordement d'entrée, arc, raccordement de sortie, demi-droite d'arrivée

Les raccordements sont des clothoïdes : la courbure varie linéairement de 0 à 1/R. Un virage tourne de
180° : 2 × c / (2R) + b / R = π, d'où l'arc b = πR − c ; la longueur d'un tour vaut 2a + 2(πR + c), d'où la
droite a = L / 2 − πR − c, résolue exactement pour la longueur demandée. `s = 0` est au milieu de la droite
d'arrivée : ligne d'arrivée et ligne de poursuite A ; la ligne de poursuite B est au milieu de la droite
opposée (s = L / 2) et la ligne des 200 m à s = L − 200.

Relèvement : proportionnel à la courbure, de `bank_straight_deg` dans les droites à `bank_bend_deg` sur
l'arc, donc continu (variation linéaire le long des clothoïdes). Pente le long de la trajectoire nulle
partout : l'altitude de la ligne de mesure est constante, le relèvement est perpendiculaire au sens de marche.

Distance (§4.2, lot VD3) : `progress_factor(s, height_m)` est le rapport R / (R + h · cos θ) entre l'avance
sur la ligne de mesure et le chemin parcouru à `height_m` mètres au-dessus d'elle, mesurés sur la piste :
rouler 1 m plus haut coûte environ 5 m par tour de 250 m.

Écriture : `write_velodrome(out_dir)` écrit `velodrome-250.world` (manifeste, route, couche `venue.json`),
reproductible octet pour octet (date de création fixe), dans un dossier temporaire voisin renommé ensuite.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .route_stats import compute_stats

TRACK_ID = "velodrome-250"
CREATED = "2026-11-07T00:00:00+01:00"   # fixe : le parcours est reproductible octet pour octet
FORMAT_VERSION = "1.7"
VENUE_VERSION = "1.0"
DS_M = 0.25                  # un point tous les 25 cm : relèvement continu (moins de 0,5° par point)
ORIGIN_LAT = 46.0            # repère géographique neutre (salle fictive, aucune coordonnée réelle)
ORIGIN_LON = 2.0
ORIGIN_ALT_M = 200.0
EARTH_R = 6_371_000.0
START_HEADING_DEG = 90.0     # droite d'arrivée vers l'est, virages à gauche
BANK_MAX_DEG = 50.0
GAUSS = ((-0.906179845938664, 0.236926885056189), (-0.538469310105683, 0.478628670499366),
         (0.0, 0.568888888888889), (0.538469310105683, 0.478628670499366),
         (0.906179845938664, 0.236926885056189))


class VelodromeError(ValueError):
    """Forme de piste impossible (longueur trop courte, relèvement hors bornes, largeur nulle…)."""


@dataclass(frozen=True)
class TrackSpec:
    """Forme d'une piste (§3.1) ; une seule piste listée, `velodrome-250` (décision du 6 novembre 2026)."""

    id: str
    name: str
    length_m: float
    radius_m: float              # rayon de l'arc, à la ligne de mesure
    transition_m: float          # longueur de chaque clothoïde
    bank_straight_deg: float
    bank_bend_deg: float
    track_width_m: float = 7.0
    apron_width_m: float = 1.0   # côte d'azur, non relevée, à l'intérieur
    safety_width_m: float = 4.0
    measure_line_m: float = 0.20     # depuis le bord intérieur de la piste
    sprinters_line_m: float = 0.85
    stayers_line_m: float = 2.45
    surface: str = "wood"
    indoor: bool = True

    @property
    def straight_m(self) -> float:
        """Longueur de chaque droite, résolue pour tomber sur `length_m`."""
        return 0.5 * self.length_m - math.pi * self.radius_m - self.transition_m

    @property
    def arc_m(self) -> float:
        return math.pi * self.radius_m - self.transition_m


TRACKS: dict[str, TrackSpec] = {
    TRACK_ID: TrackSpec(id=TRACK_ID, name="Vélodrome 250 m", length_m=250.0, radius_m=23.0, transition_m=18.0,
                        bank_straight_deg=12.0, bank_bend_deg=42.0),
}


def check_spec(spec: TrackSpec) -> None:
    """Lève VelodromeError si la forme est impossible."""
    if spec.radius_m <= 0.0 or spec.transition_m < 0.0:
        raise VelodromeError(f"{spec.id} : rayon et raccordement doivent être positifs")
    if spec.arc_m <= 0.0:
        raise VelodromeError(f"{spec.id} : raccordement de {spec.transition_m} m trop long pour un rayon de "
                             f"{spec.radius_m} m (arc négatif)")
    if spec.straight_m <= 0.0:
        shortest = 2.0 * (math.pi * spec.radius_m + spec.transition_m)
        raise VelodromeError(f"{spec.id} : longueur de {spec.length_m} m impossible, au moins {shortest:.2f} m "
                             f"avec ce rayon et ces raccordements")
    for name, deg in (("relèvement des droites", spec.bank_straight_deg), ("relèvement des virages",
                                                                            spec.bank_bend_deg)):
        if not 0.0 <= deg <= BANK_MAX_DEG:
            raise VelodromeError(f"{spec.id} : {name} de {deg}° hors de 0 à {BANK_MAX_DEG:.0f}°")
    if spec.bank_bend_deg < spec.bank_straight_deg:
        raise VelodromeError(f"{spec.id} : virages moins relevés que les droites")
    if spec.track_width_m <= 0.0 or spec.apron_width_m < 0.0 or spec.safety_width_m < 0.0:
        raise VelodromeError(f"{spec.id} : largeurs invalides")
    if not 0.0 <= spec.measure_line_m < spec.sprinters_line_m < spec.stayers_line_m < spec.track_width_m:
        raise VelodromeError(f"{spec.id} : lignes peintes hors de la piste ou dans le désordre")


class TrackGeometry:
    """Courbure, cap et relèvement de la ligne de mesure en toute position `s` (boucle)."""

    def __init__(self, spec: TrackSpec) -> None:
        check_spec(spec)
        self.spec = spec
        a, c, b = spec.straight_m, spec.transition_m, spec.arc_m
        k = 1.0 / spec.radius_m
        # Morceaux (longueur, courbure au début, courbure à la fin), à partir du milieu de la droite d'arrivée.
        bend = [(c, 0.0, k), (b, k, k), (c, k, 0.0)]
        self.pieces = [(0.5 * a, 0.0, 0.0), *bend, (a, 0.0, 0.0), *bend, (0.5 * a, 0.0, 0.0)]
        self.starts: list[float] = []
        self.turned_at_start: list[float] = []
        s0, t0 = 0.0, 0.0
        for length, k0, k1 in self.pieces:
            self.starts.append(s0)
            self.turned_at_start.append(t0)
            s0 += length
            t0 += 0.5 * (k0 + k1) * length
        self.length_m = spec.length_m

    def _piece(self, s: float) -> tuple[int, float]:
        p = s % self.length_m
        for i in range(len(self.pieces) - 1, -1, -1):
            if p >= self.starts[i]:
                return i, p - self.starts[i]
        return 0, p

    def curvature(self, s: float) -> float:
        """Courbure (1/m) de la ligne de mesure, positive : virage à gauche."""
        i, u = self._piece(s)
        length, k0, k1 = self.pieces[i]
        return k0 + (k1 - k0) * (u / length if length > 0 else 0.0)

    def turned(self, s: float) -> float:
        """Angle tourné (rad) depuis s = 0, intégrale exacte de la courbure (2π au bout d'un tour)."""
        laps, p = divmod(s, self.length_m)
        i, u = self._piece(p)
        length, k0, k1 = self.pieces[i]
        slope = (k1 - k0) / length if length > 0 else 0.0
        return 2.0 * math.pi * laps + self.turned_at_start[i] + k0 * u + 0.5 * slope * u * u

    def heading_deg(self, s: float) -> float:
        """Cap horaire depuis le nord : un virage à gauche le fait baisser."""
        return (START_HEADING_DEG - math.degrees(self.turned(s))) % 360.0

    def bank_deg(self, s: float) -> float:
        sp = self.spec
        return sp.bank_straight_deg + (sp.bank_bend_deg - sp.bank_straight_deg) * self.curvature(s) * sp.radius_m

    def progress_factor(self, s: float, height_m: float) -> float:
        """Avance sur la ligne de mesure par mètre roulé à `height_m` au-dessus d'elle (sur la piste) :
        R / (R + h · cos θ) = 1 / (1 + h · cos θ · κ) ; 1 dans les droites et sur la ligne de mesure."""
        h = max(0.0, min(height_m, self.spec.track_width_m - self.spec.measure_line_m))
        lateral = h * math.cos(math.radians(self.bank_deg(s)))
        return 1.0 / (1.0 + lateral * self.curvature(s))

    def lap_length_at(self, height_m: float, step_m: float = 0.05) -> float:
        """Longueur d'un tour roulé à `height_m` au-dessus de la ligne de mesure (outil de test)."""
        n = int(round(self.length_m / step_m))
        return sum(step_m / self.progress_factor((j + 0.5) * step_m, height_m) for j in range(n))

    def positions(self, s_values: list[float]) -> list[tuple[float, float]]:
        """(x, z) de la ligne de mesure en chaque s croissant (x vers l'est, z vers le sud), par Gauss-Legendre
        à 5 points sur chaque pas : erreur sous le micron pour des pas de 25 cm."""
        out = [(0.0, 0.0)]
        x = z = 0.0
        for s0, s1 in zip(s_values, s_values[1:]):
            half, mid = 0.5 * (s1 - s0), 0.5 * (s0 + s1)
            for node, weight in GAUSS:
                h = math.radians(self.heading_deg(mid + half * node))
                x += half * weight * math.sin(h)
                z -= half * weight * math.cos(h)
            out.append((x, z))
        return out


def geometry(track_id: str = TRACK_ID) -> TrackGeometry:
    try:
        return TrackGeometry(TRACKS[track_id])
    except KeyError as exc:
        raise VelodromeError(f"piste inconnue : {track_id}") from exc


def geometry_from_venue(venue: dict) -> TrackGeometry:
    """Géométrie relue depuis la couche `venue.json` d'un `.world` (lot VD3) ; lève VelodromeError."""
    try:
        g = venue["geometry"]
        lines = {line["id"]: float(line["offset_m"]) for line in venue["lines"]}
        spec = TrackSpec(id=str(venue.get("track_id", "venue")), name=str(venue.get("track_id", "venue")),
                         length_m=float(g["length_m"]), radius_m=float(g["radius_m"]),
                         transition_m=float(g["transition_m"]), bank_straight_deg=float(g["bank_straight_deg"]),
                         bank_bend_deg=float(g["bank_bend_deg"]), track_width_m=float(venue["track_width_m"]),
                         apron_width_m=float(venue["apron_width_m"]),
                         safety_width_m=float(venue.get("safety_width_m", 4.0)),
                         measure_line_m=lines["measure"], sprinters_line_m=lines["sprinters"],
                         stayers_line_m=lines["stayers"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VelodromeError(f"couche venue incomplète : {exc}") from exc
    return TrackGeometry(spec)


# --- écriture du .world ----------------------------------------------------------------------------


def build_route(spec: TrackSpec) -> dict:
    """Couche route (format §4) : ligne de mesure, un point tous les `DS_M`, boucle fermée exactement."""
    geo = TrackGeometry(spec)
    n = int(round(spec.length_m / DS_M)) + 1
    s_values = [min(i * DS_M, spec.length_m) for i in range(n)]
    pts = geo.positions(s_values)
    pts[-1] = pts[0]        # bouclage exact : l'écart d'intégration est sous le micron (test)
    lat0 = math.radians(ORIGIN_LAT)
    r = lambda v, d: [round(x, d) for x in v]  # noqa: E731
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    headings = [geo.heading_deg(s) for s in s_values]
    headings[-1] = headings[0]
    banks = [geo.bank_deg(s) for s in s_values]
    banks[-1] = banks[0]
    return {
        "version": "1.0",
        "ds_m": DS_M,
        "n": n,
        "length_m": float(spec.length_m),
        "type": "loop",
        "lat": r([ORIGIN_LAT + math.degrees(-z / EARTH_R) for z in zs], 8),
        "lon": r([ORIGIN_LON + math.degrees(x / (EARTH_R * math.cos(lat0))) for x in xs], 8),
        "alt_m": [ORIGIN_ALT_M] * n,
        "x": r(xs, 4),
        "z": r(zs, 4),
        "grade_pct": [0.0] * n,
        "heading_deg": [h if h < 359.9999 else 0.0 for h in r(headings, 4)],
        "surface": [spec.surface] * n,
        "bank_deg": r(banks, 3),
    }


def build_venue(spec: TrackSpec) -> dict:
    """Couche `venue.json` (format §8 sexies) : piste, lignes peintes, repères, virages."""
    geo = TrackGeometry(spec)
    half = 0.5 * spec.length_m
    a, c, b = spec.straight_m, spec.transition_m, spec.arc_m
    bends = []
    for k in range(2):
        start = 0.5 * a + k * (a + 2 * c + b)
        bends.append({"s_start": round(start, 4), "s_arc_start": round(start + c, 4),
                      "s_arc_end": round(start + c + b, 4), "s_end": round(start + 2 * c + b, 4)})
    return {
        "version": VENUE_VERSION,
        "kind": "velodrome",
        "track_id": spec.id,
        "indoor": spec.indoor,
        "track_width_m": spec.track_width_m,
        "apron_width_m": spec.apron_width_m,
        "safety_width_m": spec.safety_width_m,
        "route_line": "measure",
        "lines": [
            {"id": "measure", "color": "black", "offset_m": spec.measure_line_m},
            {"id": "sprinters", "color": "red", "offset_m": spec.sprinters_line_m},
            {"id": "stayers", "color": "blue", "offset_m": spec.stayers_line_m},
        ],
        "marks": [
            {"id": "finish", "s": 0.0},
            {"id": "pursuit_a", "s": 0.0},
            {"id": "pursuit_b", "s": round(half, 4)},
            {"id": "line_200m", "s": round(spec.length_m - 200.0, 4)},
        ],
        "geometry": {
            "length_m": spec.length_m, "radius_m": spec.radius_m, "transition_m": spec.transition_m,
            "straight_m": round(a, 4), "arc_m": round(b, 4),
            "bank_straight_deg": spec.bank_straight_deg, "bank_bend_deg": spec.bank_bend_deg,
            "turn": "left",
            "bends": bends,
        },
        # Vitesse sans force de côté au sommet du virage (§3.2) : √(g · R · tan θ)
        "equilibrium_speed_kmh": round(3.6 * math.sqrt(9.81 * spec.radius_m * math.tan(
            math.radians(geo.bank_deg(bends[0]["s_arc_start"] + 0.5 * b)))), 1),
    }


def build_manifest(spec: TrackSpec, route: dict) -> dict:
    stats_route = {k: route[k] for k in ("n", "ds_m", "length_m", "alt_m", "surface")}
    return {
        "format": "openride-world",
        "format_version": FORMAT_VERSION,
        "name": spec.name,
        "created": CREATED,
        "compiler": {"name": "openride-velodrome", "version": "1.0.0"},
        "source": {"gpx": None, "gpx_sha256": None},
        "origin": {"lat": route["lat"][0], "lon": route["lon"][0], "alt_m": route["alt_m"][0], "utm_zone": "31T"},
        "projection": "local_equirectangular",
        "route": {"present": True, "version": "1.0", "file": "route.json",
                  "length_m": route["length_m"], "ds_m": route["ds_m"], "n": route["n"],
                  "type": route["type"], "grade_clamped_points": 0, "alt_source": "synthetic",
                  "surface_source": "venue"},
        "layers": {
            "terrain": {"present": False},
            "buildings": {"present": False},
            "vegetation": {"present": False, "source": "none"},
            "poi": {"present": False},
            "water": {"present": False},
            "segments": {"present": False},
            "venue": {"present": True, "version": VENUE_VERSION, "file": "venue.json", "kind": "velodrome"},
        },
        "stats": compute_stats(stats_route),
        "library": {
            "name": spec.name,
            "description": (f"Piste couverte de {spec.length_m:.0f} m en bois, virages relevés à "
                            f"{spec.bank_bend_deg:.0f}° et lignes droites à {spec.bank_straight_deg:.0f}°."),
            "tags": ["velodrome"],
        },
    }


def _dump(data: dict, compact: bool = False) -> str:
    if compact:
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_velodrome(out_dir: Path, track_id: str = TRACK_ID) -> Path:
    """Écrit `<out_dir>/<track_id>.world` de façon atomique (dossier temporaire voisin, puis renommage)."""
    try:
        spec = TRACKS[track_id]
    except KeyError as exc:
        raise VelodromeError(f"piste inconnue : {track_id}") from exc
    check_spec(spec)
    route = build_route(spec)
    files = {"route.json": _dump(route, compact=True), "venue.json": _dump(build_venue(spec)),
             "manifest.json": _dump(build_manifest(spec, route))}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    world = out_dir / f"{spec.id}.world"
    tmp = Path(tempfile.mkdtemp(dir=out_dir, prefix=f".{spec.id}-"))
    try:
        for name, text in files.items():
            (tmp / name).write_text(text, encoding="utf-8")
        if world.exists():
            old = Path(tempfile.mkdtemp(dir=out_dir, prefix=f".{spec.id}-ancien-"))
            os.replace(world, old / world.name)
            os.replace(tmp, world)
            shutil.rmtree(old, ignore_errors=True)
        else:
            os.replace(tmp, world)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return world


def write_all(out_dir: Path) -> list[Path]:
    """Toutes les pistes de la table (une seule aujourd'hui)."""
    return [write_velodrome(out_dir, track_id) for track_id in TRACKS]


# --- physique en piste (lot VD3) -------------------------------------------------------------------

STANDARD_AIR_K = 288.15      # 15 °C : la densité de `physics.air_density` est celle de l'air standard


def hall_altitude_m(alt_m: float, temperature_c: float) -> float:
    """Altitude équivalente de l'air de la salle : même densité que `physics.air_density` à `alt_m` corrigée
    de la température (gaz parfait, pression inchangée) ; la physique reçoit cette altitude, sans autre calcul."""
    from .physics import H_SCALE_M

    return alt_m + H_SCALE_M * math.log((273.15 + temperature_c) / STANDARD_AIR_K)


def height_on_track(lane_m: float | None) -> float:
    """Hauteur sur la piste (m, mesurée sur la pente depuis la ligne de mesure) d'un coureur à `lane_m` de l'axe :
    l'axe de la route est la ligne de mesure, la droite est le haut de la piste (virages à gauche)."""
    return max(0.0, float(lane_m or 0.0))
