"""Tunnels dessinés (lot EA5, série EA, Format .world v1 §8 octies, depuis 1.11).

Même règle pour les parcours compilés et le monde ouvert, sur le modèle des ponts (lot EA4, `bridges.py`) :

- **Portions en tunnel.** Monde ouvert : les `spans` « tunnel » des arêtes (lot W4, balise `tunnel` d'OSM ou
  `brunnel=tunnel` des tuiles vectorielles). Parcours compilé : les points de la route accrochés à une voie OSM
  `tunnel=*` (hors `tunnel=no`) par la règle d'accrochage de la surface (`surface.match_ways`, lot U20), portions
  formées comme celles des ponts (`bridges.spans_from_flags`).
- **Profil.** Ligne droite d'une entrée à l'autre (étapes 3 et 4 du profil d'arête du monde ouvert ;
  `bridges.apply_bridge_profile` pour un parcours compilé, sur les portions en pont et en tunnel réunies).
- **Terrain.** La colline est gardée (choix du propriétaire du 20 novembre) : pas de fondu de la route et pas
  de garde-fou de la chaussée sur une portion en tunnel. L'engine ne dessine pas le terrain à l'intérieur du
  tube (`engine/scripts/tunnel_cut.gd`, test du shader du terrain).
- **Objet dessiné.** Axe du tube `points` [[x, z, y], …] (y : altitude de la chaussée), aux points du profil,
  bouts compris (les deux bouts sont les portails) ; demi-largeur de la chaussée `half_width_m`. L'engine dessine
  piédroits, voûte, trottoirs, têtes de portail et lampes (`engine/scripts/tunnel_mesh.gd`).

Tout en numpy, sans entrée-sortie hors `write_tunnels_dir`.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from . import constants as C
from .bridges import MIN_BRIDGE_M, route_s, spans_from_flags

TUNNELS_VERSION = "1.0"
MIN_TUNNEL_M = MIN_BRIDGE_M


def is_tunnel(tags: dict[str, Any]) -> bool:
    """Voie OSM en tunnel : `tunnel` présent et différent de `no` (`building_passage` et `avalanche_protector`
    compris : ils couvrent aussi la route)."""
    v = str(tags.get("tunnel", "no") or "no")
    return v != "no"


def route_tunnel_spans(route: dict[str, Any], ways: list[dict[str, Any]], frame) -> list[list[float]]:
    """Portions en tunnel du parcours d'après les voies OSM du couloir (règle d'accrochage de la surface)."""
    from .surface import match_ways

    tunnel_way = [is_tunnel(w.get("tags") or {}) for w in ways]
    flags = [j is not None and tunnel_way[j] for j in match_ways(route, ways, frame)]
    return spans_from_flags(route_s(route), flags, float(route["length_m"]))


def merge_spans(*groups: Sequence[Sequence[float]]) -> list[list[float]]:
    """Portions réunies (ponts et tunnels), triées, chevauchements fondus."""
    items = sorted([float(a), float(b)] for g in groups for a, b in (sp[:2] for sp in g))
    out: list[list[float]] = []
    for a, b in items:
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def tunnel_item(tid: str, s: np.ndarray, x: np.ndarray, z: np.ndarray, y: np.ndarray, s0: float, s1: float,
                half_width: float = C.ROAD_HALF_WIDTH_M) -> dict[str, Any] | None:
    """Axe du tube d'une portion [s0, s1] d'un profil (s, x, z, y) ; None si trop courte."""
    s0, s1 = max(float(s[0]), float(s0)), min(float(s[-1]), float(s1))
    if s1 - s0 < MIN_TUNNEL_M:
        return None
    inner = s[(s > s0) & (s < s1)]
    sv = np.concatenate(([s0], inner, [s1]))
    px, pz, py = np.interp(sv, s, x), np.interp(sv, s, z), np.interp(sv, s, y)
    return {"id": tid, "kind": "tunnel", "length_m": round(s1 - s0, 2), "half_width_m": half_width,
            "points": [[round(float(a), 2), round(float(b), 2), round(float(c), 2)] for a, b, c in zip(px, pz, py)]}


def route_tunnels(route: dict[str, Any], spans: list[list[float]]) -> dict[int, list[dict[str, Any]]]:
    """Tunnels d'un parcours compilé rangés par tronçon de 1 km (celui du milieu du tunnel)."""
    s = route_s(route)
    x, z, y = (np.asarray(route[k], dtype=float) for k in ("x", "z", "alt_m"))
    last_k = int(math.floor(float(route["length_m"]) / C.CHUNK_LENGTH_M))
    out: dict[int, list[dict[str, Any]]] = {}
    for n, (s0, s1) in enumerate(spans):
        item = tunnel_item(f"t{n}", s, x, z, y, s0, s1)
        if item is None:
            continue
        item["s0_m"], item["s1_m"] = round(float(s0), 2), round(float(s1), 2)
        k = min(int(math.floor(0.5 * (s0 + s1) / C.CHUNK_LENGTH_M)), last_k)
        out.setdefault(k, []).append(item)
    return out


def tunnels_manifest(chunks: dict[int, list[dict[str, Any]]], spans: list[list[float]],
                     osm_date: str | None = None) -> dict[str, Any]:
    return {"present": True, "version": TUNNELS_VERSION, "count": sum(len(v) for v in chunks.values()),
            "spans": [[float(a), float(b)] for a, b in spans], "osm_date": osm_date}


def manifest_spans(manifest: dict[str, Any]) -> list[list[float]]:
    """Portions en tunnel notées au manifeste (couche `tunnels`), [] sans couche."""
    info = ((manifest or {}).get("layers") or {}).get("tunnels") or {}
    if not info.get("present"):
        return []
    return [[float(a), float(b)] for a, b in info.get("spans") or []]


def write_tunnels_dir(folder: Path, chunks: dict[int, list[dict[str, Any]]]) -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for k in sorted(chunks):
        payload = {"version": TUNNELS_VERSION, "tunnels": chunks[k]}
        (folder / f"chunk_{k}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def tunnels_summary(chunks: dict[int, list[dict[str, Any]]]) -> str:
    items = [t for v in chunks.values() for t in v]
    if not items:
        return "tunnels : aucun"
    longest = max(t["length_m"] for t in items)
    return f"tunnels : {len(items)} (le plus long {longest:.0f} m)"


__all__ = ["TUNNELS_VERSION", "MIN_TUNNEL_M", "is_tunnel", "route_tunnel_spans", "merge_spans", "tunnel_item",
           "route_tunnels", "tunnels_manifest", "manifest_spans", "write_tunnels_dir", "tunnels_summary"]
