"""Ponts dessinés (lot EA4, série EA, Format .world v1 §8 septies, depuis 1.9).

Une seule règle pour les parcours compilés et le monde ouvert :

- **Portions en pont.** Monde ouvert : les `spans` « bridge » des arêtes (lot W4). Parcours compilé : les points
  de la route accrochés à une voie OSM `bridge=*` (hors `bridge=no`) par la règle de la surface (lot U20,
  `surface.match_ways` : voie concordante à moins de 15 m, cap à moins de 30°) ; une suite de points en pont
  donne la portion `[s_premier − 5 m, s_dernier + 5 m]` ; deux portions à moins de 20 m l'une de l'autre se
  rejoignent ; une portion de moins de `MIN_BRIDGE_M` est ignorée.
- **Profil.** Sur une portion, la route va en ligne droite (en altitude) d'une culée à l'autre, prolongée de
  `SPAN_MARGIN_M` de chaque côté, avant le lissage, comme le profil d'arête du monde ouvert (`edge_profile`,
  étapes 3 et 4 ; parcours compilé : sur `alt_raw_m`) ; la pente est recalculée. Le terrain n'est pas fondu avec la route sous un pont (il garde le MNT).
- **Objet dessiné.** Axe du tablier `points` [[x, z, y], …] (y : altitude de la chaussée), aux points du
  profil, bouts compris ; demi-largeur de la chaussée `half_width_m` ; piles `piers` [[x, z, y_tablier,
  y_pied], …] pour un pont de plus de `PIER_SPAN_MIN_M`, également espacées d'au plus `PIER_SPACING_M`,
  gardées là où le tablier est à plus de `PIER_MIN_CLEAR_M` au-dessus du sol (pied enterré de `PIER_EMBED_M`).
  L'engine dessine le tablier, les garde-corps et les piles (`engine/scripts/bridge_mesh.gd`).

Tout en numpy, sans entrée-sortie hors `write_bridges_dir`.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from . import constants as C
from .pipeline import _grade

BRIDGES_VERSION = "1.0"
SPAN_MARGIN_M = 10.0        # même valeur que worldgen.edge_profile.SPAN_MARGIN_M
POINT_PAD_M = 5.0           # moitié du pas de la route : la portion couvre les points accrochés
MERGE_GAP_M = 20.0
MIN_BRIDGE_M = 8.0
PIER_SPAN_MIN_M = 30.0
PIER_SPACING_M = 30.0
PIER_MIN_CLEAR_M = 4.0
PIER_EMBED_M = 1.5

GroundFn = Callable[[np.ndarray, np.ndarray], np.ndarray]


def is_bridge(tags: dict[str, Any]) -> bool:
    """Voie OSM en pont : `bridge` présent et différent de `no`."""
    v = str(tags.get("bridge", "no") or "no")
    return v != "no"


# --- portions en pont d'un parcours compilé -----------------------------------------------------

def route_s(route: dict[str, Any]) -> np.ndarray:
    n, ds = int(route["n"]), float(route["ds_m"])
    s = np.arange(n, dtype=float) * ds
    s[-1] = float(route["length_m"])
    return s


def spans_from_flags(s: np.ndarray, flags: Sequence[bool], length: float) -> list[list[float]]:
    """Portions [s0, s1] des suites de points en pont, élargies de POINT_PAD_M, rapprochées puis filtrées."""
    runs: list[list[float]] = []
    i, n = 0, len(flags)
    while i < n:
        if not flags[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and flags[j + 1]:
            j += 1
        a, b = max(0.0, float(s[i]) - POINT_PAD_M), min(length, float(s[j]) + POINT_PAD_M)
        if runs and a - runs[-1][1] < MERGE_GAP_M:
            runs[-1][1] = b
        else:
            runs.append([a, b])
        i = j + 1
    return [[round(a, 2), round(b, 2)] for a, b in runs if b - a >= MIN_BRIDGE_M]


def route_bridge_spans(route: dict[str, Any], ways: list[dict[str, Any]], frame) -> list[list[float]]:
    """Portions en pont du parcours d'après les voies OSM du couloir (règle d'accrochage de la surface)."""
    from .surface import match_ways

    bridge_way = [is_bridge(w.get("tags") or {}) for w in ways]
    flags = [j is not None and bridge_way[j] for j in match_ways(route, ways, frame)]
    return spans_from_flags(route_s(route), flags, float(route["length_m"]))


def flatten_spans(s: np.ndarray, alt: np.ndarray, spans: Iterable[Sequence[float]],
                  margin: float = SPAN_MARGIN_M) -> np.ndarray:
    """Altitude en ligne droite sur chaque portion prolongée de `margin` (règle de `edge_profile`, étape 3)."""
    out = np.array(alt, dtype=float, copy=True)
    length = float(s[-1])
    for sp in spans:
        a, b = max(0.0, float(sp[0]) - margin), min(length, float(sp[1]) + margin)
        if b <= a:
            continue
        # bouts ramenés aux points du profil qui encadrent la portion : ils ne bougent pas, la règle rejouée
        # donne le même profil (`add-layer bridges` deux fois)
        a = float(s[max(int(np.searchsorted(s, a, side="right")) - 1, 0)])
        b = float(s[min(int(np.searchsorted(s, b, side="left")), len(s) - 1)])
        ya, yb = np.interp([a, b], s, out)
        inside = (s >= a) & (s <= b)
        out[inside] = ya + (yb - ya) * (s[inside] - a) / (b - a)
    return out


def apply_bridge_profile(route: dict[str, Any], spans: list[list[float]]) -> int:
    """Profil de la route en ligne droite sur les ponts, pente recalculée (bornée). Rend le nombre de points changés.

    Comme le profil d'arête du monde ouvert : la ligne droite est posée sur l'altitude brute (`alt_raw_m`, qui
    reste telle quelle), puis lissée (Savitzky-Golay de `pipeline.py`) ; sans `alt_raw_m` (parcours ancien),
    sur l'altitude lissée. Rejouée, la règle donne le même profil.
    """
    if not spans:
        return 0
    from .pipeline import _smooth_altitude

    s = route_s(route)
    alt = np.asarray(route["alt_m"], dtype=float)
    raw = route.get("alt_raw_m")
    if raw is not None and len(raw) == len(s) and len(s) >= C.SAVGOL_WINDOW:
        new = _smooth_altitude(flatten_spans(s, np.asarray(raw, dtype=float), spans), s)
    else:
        new = flatten_spans(s, alt, spans)
    loop = route.get("type") == "loop"
    if loop:
        new[-1] = new[0]
    new = np.round(new, 2)
    changed = int(np.count_nonzero(np.abs(new - alt) > 1e-6))
    grade = np.clip(_grade(new, s, loop), -C.GRADE_LIMIT_PCT, C.GRADE_LIMIT_PCT)
    route["alt_m"] = [float(v) for v in new]
    route["grade_pct"] = [round(float(v), 2) for v in grade]
    return changed


def outside_spans(s: np.ndarray, spans: Iterable[Sequence[float]]) -> np.ndarray:
    """Masque des points hors des portions en pont (bornes exclues, comme `axis_pieces` du monde ouvert)."""
    keep = np.ones(len(s), dtype=bool)
    for sp in spans:
        keep &= ~((s > float(sp[0])) & (s < float(sp[1])))
    return keep


# --- objets dessinés ------------------------------------------------------------------------------

def bridge_item(bid: str, s: np.ndarray, x: np.ndarray, z: np.ndarray, y: np.ndarray, s0: float, s1: float,
                ground: GroundFn, half_width: float = C.ROAD_HALF_WIDTH_M) -> dict[str, Any] | None:
    """Tablier et piles d'une portion [s0, s1] d'un profil (s, x, z, y) ; None si trop courte."""
    s0, s1 = max(float(s[0]), float(s0)), min(float(s[-1]), float(s1))
    if s1 - s0 < MIN_BRIDGE_M:
        return None
    inner = s[(s > s0) & (s < s1)]
    sv = np.concatenate(([s0], inner, [s1]))
    px, pz, py = np.interp(sv, s, x), np.interp(sv, s, z), np.interp(sv, s, y)
    piers: list[list[float]] = []
    span = s1 - s0
    if span >= PIER_SPAN_MIN_M:
        count = int(math.ceil(span / PIER_SPACING_M)) - 1
        ps = s0 + span * np.arange(1, count + 1) / (count + 1)
        qx, qz, qy = np.interp(ps, s, x), np.interp(ps, s, z), np.interp(ps, s, y)
        g = np.asarray(ground(qx, qz), dtype=float)
        for a, b, top, gy in zip(qx, qz, qy, g):
            if math.isfinite(gy) and top - gy >= PIER_MIN_CLEAR_M:
                piers.append([round(float(a), 2), round(float(b), 2), round(float(top), 2),
                              round(float(gy) - PIER_EMBED_M, 2)])
    return {"id": bid, "kind": "bridge", "length_m": round(span, 2), "half_width_m": half_width,
            "points": [[round(float(a), 2), round(float(b), 2), round(float(c), 2)] for a, b, c in zip(px, pz, py)],
            "piers": piers}


def route_bridges(route: dict[str, Any], spans: list[list[float]], ground: GroundFn) -> dict[int, list[dict[str, Any]]]:
    """Ponts d'un parcours compilé rangés par tronçon de 1 km (celui du milieu du pont)."""
    s = route_s(route)
    x, z, y = (np.asarray(route[k], dtype=float) for k in ("x", "z", "alt_m"))
    last_k = int(math.floor(float(route["length_m"]) / C.CHUNK_LENGTH_M))
    out: dict[int, list[dict[str, Any]]] = {}
    for n, (s0, s1) in enumerate(spans):
        item = bridge_item(f"b{n}", s, x, z, y, s0, s1, ground)
        if item is None:
            continue
        item["s0_m"], item["s1_m"] = round(float(s0), 2), round(float(s1), 2)
        k = min(int(math.floor(0.5 * (s0 + s1) / C.CHUNK_LENGTH_M)), last_k)
        out.setdefault(k, []).append(item)
    return out


def bridges_manifest(chunks: dict[int, list[dict[str, Any]]], spans: list[list[float]],
                     osm_date: str | None = None) -> dict[str, Any]:
    return {"present": True, "version": BRIDGES_VERSION, "count": sum(len(v) for v in chunks.values()),
            "piers": sum(len(b["piers"]) for v in chunks.values() for b in v),
            "spans": [[float(a), float(b)] for a, b in spans], "osm_date": osm_date}


def manifest_spans(manifest: dict[str, Any]) -> list[list[float]]:
    """Portions en pont notées au manifeste (couche `bridges`), [] sans couche."""
    info = ((manifest or {}).get("layers") or {}).get("bridges") or {}
    if not info.get("present"):
        return []
    return [[float(a), float(b)] for a, b in info.get("spans") or []]


def write_bridges_dir(folder: Path, chunks: dict[int, list[dict[str, Any]]]) -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for k in sorted(chunks):
        payload = {"version": BRIDGES_VERSION, "bridges": chunks[k]}
        (folder / f"chunk_{k}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def bridges_summary(chunks: dict[int, list[dict[str, Any]]]) -> str:
    items = [b for v in chunks.values() for b in v]
    if not items:
        return "ponts : aucun"
    piers = sum(len(b["piers"]) for b in items)
    longest = max(b["length_m"] for b in items)
    return f"ponts : {len(items)} (le plus long {longest:.0f} m), {piers} pile(s)"


__all__ = ["BRIDGES_VERSION", "SPAN_MARGIN_M", "MIN_BRIDGE_M", "PIER_SPAN_MIN_M", "PIER_SPACING_M",
           "PIER_MIN_CLEAR_M", "PIER_EMBED_M", "is_bridge", "route_s", "spans_from_flags", "route_bridge_spans",
           "flatten_spans", "apply_bridge_profile", "outside_spans", "bridge_item", "route_bridges",
           "bridges_manifest", "manifest_spans", "write_bridges_dir", "bridges_summary"]
