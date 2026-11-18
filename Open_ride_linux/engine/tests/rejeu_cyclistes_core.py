#!/usr/bin/env python3
"""Rejeu core → engine des cyclistes du décor à vitesse tenue (lot AS9, banc r879b du 14/11 sur le volcan).

Pour chaque vitesse et chaque graine : le vrai core (`openride_core.road_cyclists`, pas de 50 Hz comme la séance)
roule le cycliste à vitesse constante sur une route droite et plate de 40 km et écrit sa liste `riders` toutes les
5 trames (10 Hz, `state_list`) ; puis `rejeu_cyclistes_core.gd` la rejoue dans `road_cyclists_model.gd` pour chaque
budget de préréglage (low 4, medium 8, high 16) et compte les contacts comme `living_decor._count_contacts`.
Les contacts du core seul (mêmes critères, à 10 Hz) sont comptés à part. Aucun écran ni matériel.

    python3 engine/tests/rejeu_cyclistes_core.py --godot ~/Applications/godot/Godot_v4.7.2-stable_linux.x86_64
    python3 engine/tests/rejeu_cyclistes_core.py --kmh 55,65 --seeds 0,1 --duration 600 --budgets 8

Code de sortie : 0 sans contact, 1 sinon.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
sys.path.insert(0, str(ENGINE.parent / "core" / "src"))

from openride_core.road_cyclists import RIDER_LATERAL_M, RoadCyclists  # noqa: E402
from openride_core.route import Route  # noqa: E402

LENGTH_M = 40000.0
DS_M = 10.0
CORE_HZ = 50
LIST_EVERY = 5            # une liste `riders` toutes les 3 trames `state` à 30 Hz : 10 Hz
CONTACT_LEN_M = 1.7       # living_decor.gd : 2 × CONTACT_BIKE_HALF_M
CONTACT_WIDTH_M = 0.6     # 2 × RIDER_HALF_WIDTH_M


def route_dict() -> dict:
    n = int(LENGTH_M / DS_M) + 1
    cols: dict[str, list[float]] = {k: [] for k in ("lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg")}
    for i in range(n):
        for k, v in (("lat", 48.9), ("lon", 7.1), ("alt_m", 200.0), ("x", i * DS_M), ("z", 0.0),
                     ("grade_pct", 0.0), ("heading_deg", 90.0)):
            cols[k].append(v)
    return {"version": "1.0", "ds_m": DS_M, "n": n, "length_m": (n - 1) * DS_M, "type": "open", **cols}


def trace(kmh: float, seed: int, duration_s: float) -> tuple[dict, int]:
    """Listes `riders` du core et contacts du core seul."""
    m = RoadCyclists(Route(route_dict()), (), (), seed=seed)
    dt = 1.0 / CORE_HZ
    v = kmh / 3.6
    s, t, k = 300.0, 0.0, 0
    frames = []
    contacts = 0
    while t < duration_s:
        m.update(s, v, dt)
        if k % LIST_EVERY == 0:
            frames.append([round(t, 4), round(s, 3), [[r["id"], r["s"], r["dir"], r["v"], r["lane_m"], r["look"]]
                                                      for r in m.state_list(s)]])
            items = [(r.group, r.s, r.lane_m) for r in m.riders()] + [("cycliste", s, RIDER_LATERAL_M)]
            for i, a in enumerate(items):
                for b in items[i + 1:]:
                    if a[0] != b[0] and abs(a[1] - b[1]) < CONTACT_LEN_M and abs(a[2] - b[2]) < CONTACT_WIDTH_M:
                        contacts += 1
        s += v * dt
        t += dt
        k += 1
    return {"kmh": kmh, "seed": seed, "length_m": LENGTH_M, "frames": frames}, contacts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--godot", default=os.environ.get("GODOT", "godot"))
    ap.add_argument("--kmh", default="30,45,55,65,75")
    ap.add_argument("--seeds", default="0,1,2,3")
    ap.add_argument("--budgets", default="4,8,16")
    ap.add_argument("--duration", type=float, default=900.0)
    args = ap.parse_args()
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        for kmh in [float(x) for x in args.kmh.split(",")]:
            for seed in [int(x) for x in args.seeds.split(",")]:
                data, core_hits = trace(kmh, seed, args.duration)
                path = Path(tmp) / f"trace_{kmh:.0f}_{seed}.json"
                path.write_text(json.dumps(data, separators=(",", ":")))
                total += core_hits
                for budget in [int(x) for x in args.budgets.split(",")]:
                    out = subprocess.run([args.godot, "--headless", "--path", str(ENGINE), "--script",
                                          "res://tests/rejeu_cyclistes_core.gd", "--", str(path), str(budget)],
                                         capture_output=True, text=True, timeout=600)
                    line = next((ln for ln in out.stdout.splitlines() if ln.startswith("contacts=")), "")
                    n = int(line.split()[0].split("=")[1]) if line else -1
                    total += max(n, 0) if n >= 0 else 1
                    print(f"{kmh:3.0f} km/h graine {seed} budget {budget:2d} : core seul {core_hits}, engine {line or out.stderr[-300:]}")
    print("RÉSULTAT :", "aucun contact" if total == 0 else f"{total} contacts (images × paires)")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
