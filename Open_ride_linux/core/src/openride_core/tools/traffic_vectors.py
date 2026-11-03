"""Vecteurs de test de la circulation (lot AS6), partagés entre le core (Python) et l'engine (GDScript).

`openride_core.traffic` est la référence : ce script tire les cases d'un parcours d'essai de 20 km
(virages, montée de plus de 8 %, passage enneigé, trois villages) avec deux graines, et écrit les
véhicules attendus (case, sorte, couleur, sens) dans `engine/tests/data/traffic_slots_vectors.json`.
Vérifiés par `core/tests/test_traffic.py` et `engine/tests/unit/test_traffic_model.gd`.

    python -m openride_core.tools.traffic_vectors            # régénère le fichier du dépôt
    python -m openride_core.tools.traffic_vectors --check    # code 1 si le fichier n'est plus à jour
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from ..route import Route
from ..traffic import SLOT_M, Traffic

DEFAULT_OUT = Path(__file__).resolve().parents[4] / "engine" / "tests" / "data" / "traffic_slots_vectors.json"
LENGTH_M = 20000.0
DS_M = 50.0
SEEDS = (0, 1, 2, 3, 12345, 0x7FFFFFFF)
VILLAGE_S = (3000.0, 9500.0, 16000.0)   # villages à 300 m de la route, au nord
SNOW_LINE_M = 2200.0


def route_dict() -> dict:
    """Parcours d'essai : cap qui ondule, montée raide de 6 à 7 km, col enneigé de 12 à 13 km."""
    n = int(LENGTH_M / DS_M) + 1
    xs, zs, alts, grades, heads = [0.0], [0.0], [400.0], [], []
    for i in range(n):
        s = i * DS_M
        heads.append(round((90.0 + 25.0 * math.sin(s / 1800.0)) % 360.0, 3))
        g = 10.0 if 6000.0 <= s < 7000.0 else 3.0 * math.sin(s / 900.0)
        grades.append(round(g, 3))
    for i in range(1, n):
        h = math.radians(heads[i - 1])
        xs.append(round(xs[-1] + DS_M * math.sin(h), 3))
        zs.append(round(zs[-1] - DS_M * math.cos(h), 3))
        alts.append(round(alts[-1] + DS_M * grades[i - 1] / 100.0, 3))
    alts = [a + 1900.0 if 12000.0 <= i * DS_M < 13000.0 else a for i, a in enumerate(alts)]
    return {"version": "1.0", "n": n, "ds_m": DS_M, "length_m": (n - 1) * DS_M, "type": "open",
            "lat": [48.9] * n, "lon": [7.1] * n, "alt_m": alts, "x": xs, "z": zs,
            "grade_pct": grades, "heading_deg": heads}


def build() -> dict:
    data = route_dict()
    route = Route(data)
    villages = [(round(route.sample(s).x, 3), round(route.sample(s).z - 300.0, 3)) for s in VILLAGE_S]
    cases = []
    for seed in SEEDS:
        t = Traffic(route=route, seed=seed, villages=villages, snow_line_m=SNOW_LINE_M)
        events = []
        for k in range(int(route.length_m // SLOT_M) + 1):
            ev = t.slot_event(k)
            if ev is not None:
                events.append({"slot": ev["slot"], "kind": ev["kind"], "color": ev["color"], "dir": ev["dir"],
                               "cruise_mps": round(ev["cruise_mps"], 6)})
        cases.append({"seed": seed, "events": events})
    return {
        "description": "Circulation (lot AS6) : véhicules tirés case par case (SLOT_M) sur un parcours d'essai "
                       "de 20 km, par traffic.py (core) et traffic_model.gd (engine), mêmes graine, villages "
                       "et limite de neige. Régénérer : python -m openride_core.tools.traffic_vectors.",
        "snow_line_m": SNOW_LINE_M,
        "villages": [{"x": x, "z": z} for x, z in villages],
        "route": data,
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    text = json.dumps(build(), ensure_ascii=False, separators=(",", ":")) + "\n"
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if current != text:
            print(f"{args.out} n'est plus à jour", file=sys.stderr)
            return 1
        return 0
    args.out.write_text(text, encoding="utf-8")
    print(f"écrit {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
