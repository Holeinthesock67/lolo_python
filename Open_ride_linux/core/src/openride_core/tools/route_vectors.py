"""Vecteurs de test de l'interpolation de route, partagés entre le core (Python) et l'engine (GDScript).

L'implémentation Python (`openride_core.route`) est la référence : ce script calcule les valeurs
attendues sur deux petits parcours et les écrit dans `docs/contracts/world/route_test_vectors.json`.

    python -m openride_core.tools.route_vectors            # régénère le fichier du dépôt
    python -m openride_core.tools.route_vectors --check    # code 1 si le fichier n'est plus à jour
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

from ..route import Route

DEFAULT_OUT = Path(__file__).resolve().parents[4] / "docs" / "contracts" / "world" / "route_test_vectors.json"
TOLERANCES = {"position_m": 0.01, "grade_pct": 1e-4, "heading_deg": 1e-3, "latlon_deg": 1e-9,
              "alt_m": 1e-6}


def _grades(alt: list[float], s: list[float]) -> list[float]:
    n = len(alt)
    out = []
    for i in range(n):
        a, b = max(i - 1, 0), min(i + 1, n - 1)
        out.append(100.0 * (alt[b] - alt[a]) / (s[b] - s[a]))
    return out


def _route(headings: list[float], alts: list[float], ds: float, last: float, kind: str) -> dict:
    """Parcours dont les points suivent les caps donnés (pas ds, dernier segment `last`)."""
    n = len(headings)
    s = [i * ds for i in range(n - 1)] + [(n - 2) * ds + last]
    xs, zs = [0.0], [0.0]
    for i in range(1, n):
        step = s[i] - s[i - 1]
        h = math.radians(headings[i - 1])
        xs.append(xs[-1] + step * math.sin(h))
        zs.append(zs[-1] - step * math.cos(h))
    if kind == "loop":   # fermeture exacte : le dernier point est le premier
        xs[-1], zs[-1], alts = 0.0, 0.0, alts[:-1] + [alts[0]]
    lat0, lon0 = 45.0, 6.0
    return {
        "version": "1.0", "ds_m": ds, "n": n, "length_m": s[-1], "type": kind,
        "lat": [lat0 - z / 111_195.0 for z in zs],
        "lon": [lon0 + x / (111_195.0 * math.cos(math.radians(lat0))) for x in xs],
        "alt_m": alts, "x": xs, "z": zs, "grade_pct": _grades(alts, s),
        "heading_deg": [h % 360.0 for h in headings],
    }


def build_cases() -> list[dict]:
    open_route = _route(
        headings=[340.0, 345.0, 352.0, 358.0, 4.0, 12.0, 20.0, 40.0, 70.0, 95.0, 100.0, 100.0],
        alts=[1000.0, 1000.4, 1001.1, 1001.9, 1002.4, 1002.6, 1002.3, 1001.5, 1000.9, 1000.7,
              1000.8, 1000.9],
        ds=10.0, last=6.0, kind="open")
    loop_headings = [i * 30.0 for i in range(12)] + [0.0]
    loop_route = _route(headings=loop_headings,
                        alts=[500.0 + 2.0 * math.sin(i * math.pi / 6) for i in range(13)],
                        ds=10.0, last=10.0, kind="loop")
    cases = []
    for name, data, extra_s in (
        ("open", open_route, [0.0, 3.7, 12.5, 29.99, 33.3, 50.0, 71.25, 99.0, 103.0, 106.0, -5.0, 200.0]),
        ("loop", loop_route, [0.0, 4.2, 55.5, 109.9, 115.0, 119.999, 120.0, 125.0, 250.0, -10.0]),
    ):
        route = Route(data)
        s_values = sorted(set(route.s) | set(extra_s))
        samples = []
        for s in s_values:
            smp = asdict(route.sample(s))
            samples.append({"s": s, "wrapped_s": route.wrap(s), **smp})
        cases.append({"name": name, "route": data, "samples": samples})
    return cases


def build_document() -> dict:
    return {
        "version": "1.0",
        "description": "Vecteurs de test de l'interpolation de la couche route (Format .world v1, §4.5). "
                       "Référence : openride_core.route ; à vérifier aussi par engine/scripts/route_data.gd.",
        "generated_by": "python -m openride_core.tools.route_vectors",
        "tolerances": TOLERANCES,
        "cases": build_cases(),
    }


def render() -> str:
    return json.dumps(build_document(), indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--check", action="store_true", help="vérifie que le fichier est à jour")
    args = p.parse_args(argv)
    text = render()
    if args.check:
        ok = args.out.is_file() and args.out.read_text(encoding="utf-8") == text
        print("à jour" if ok else f"périmé : relancer sans --check ({args.out})")
        return 0 if ok else 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"Écrit : {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
