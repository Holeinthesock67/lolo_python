#!/usr/bin/env python3
"""Relevé de parité des cyclistes du décor (lot AS7) : `core/src/openride_core/road_cyclists.py` face à
`engine/scripts/road_cyclists_model.gd`.

Le portage du core roule la séance du test de l'engine `test_road_cyclists_model.gd` (20 km de plaine
puis 10 km de montée à 6 %, cycliste à 30 puis 14 km/h, un bot parti 200 m derrière à 32 puis 15 km/h,
15 images/s, budget 16, graine 7), sans le maintien de vitesse du lot AS7 (`hold_after_pass=False`)
pour suivre exactement le modèle de l'engine. Il écrit les groupes tirés dans l'ordre (`log`) et, toutes
les `EVERY_S` secondes, l'abscisse et l'écart latéral de chaque cycliste (`frames`).

`engine/tests/unit/test_road_cyclists_parity.gd` rejoue la même séance avec le modèle de l'engine et
compare ; `core/tests/test_road_cyclists.py` vérifie que le fichier est à jour.

    python3 engine/tests/make_road_cyclists_parity.py            # réécrit engine/tests/data/road_cyclists_parity.json
    python3 engine/tests/make_road_cyclists_parity.py --check    # code 1 si le fichier n'est plus à jour
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "core" / "src"))

from openride_core.road_cyclists import RoadCyclists  # noqa: E402
from openride_core.route import Route  # noqa: E402

OUT = HERE / "data" / "road_cyclists_parity.json"
FLAT_M = 20000.0
LENGTH_M = 31000.0
CLIMB_PCT = 6.0
DS_M = 10.0
CLIMBS = [(FLAT_M, FLAT_M + 10000.0)]
BUDGET = 16
SEED = 7
FPS = 15
EVERY_S = 20


def route_dict() -> dict:
    """Route droite vers l'est du test de l'engine (mêmes colonnes)."""
    n = int(LENGTH_M / DS_M) + 1
    cols: dict[str, list[float]] = {k: [] for k in ("lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg")}
    for i in range(n):
        s = i * DS_M
        climbing = FLAT_M <= s < FLAT_M + 10000.0
        cols["lat"].append(48.9)
        cols["lon"].append(7.1)
        cols["alt_m"].append(200.0 + min(max(s - FLAT_M, 0.0), 10000.0) * CLIMB_PCT / 100.0)
        cols["x"].append(s)
        cols["z"].append(0.0)
        cols["grade_pct"].append(CLIMB_PCT if climbing else 0.0)
        cols["heading_deg"].append(90.0)
    return {"version": "1.0", "ds_m": DS_M, "n": n, "length_m": (n - 1) * DS_M, "type": "open", **cols}


def trace() -> dict:
    """Séance du test de l'engine, avec le portage du core."""
    m = RoadCyclists(Route(route_dict()), CLIMBS, (), BUDGET, SEED, 6.0, hold_after_pass=False)
    dt = 1.0 / FPS
    s, bot = 300.0, 100.0
    seen: set[str] = set()
    log, frames = [], []
    frame = 0
    while s < FLAT_M + 10000.0:
        v = 30.0 / 3.6 if s < FLAT_M else 14.0 / 3.6
        bot += (32.0 if bot < FLAT_M else 15.0) / 3.6 * dt
        m.update(s, v, dt, False, [bot])
        for g in m.groups:
            if g.id not in seen:
                seen.add(g.id)
                log.append([g.id, g.case, g.size])
        if frame % (FPS * EVERY_S) == 0:
            frames.append({"frame": frame, "rider_s": round(s, 3),
                           "riders": [[r.id, round(r.s, 3), round(r.lane_m, 3)] for r in m.riders()]})
        s += v * dt
        frame += 1
    return {"route": {"flat_m": FLAT_M, "length_m": LENGTH_M, "climb_pct": CLIMB_PCT, "ds_m": DS_M},
            "budget": BUDGET, "seed": SEED, "fps": FPS, "every_s": EVERY_S,
            "spawned": m.spawned_total, "passed": m.passed_total, "overtook": m.overtook_total,
            "log": log, "frames": frames}


def render() -> str:
    return json.dumps(trace(), ensure_ascii=False, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="vérifie le fichier sans l'écrire")
    args = ap.parse_args(argv)
    text = render()
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("à jour" if ok else f"{OUT} n'est plus à jour : relancer sans --check")
        return 0 if ok else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"{OUT} écrit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
