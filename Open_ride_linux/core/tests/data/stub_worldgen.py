"""Doublure du générateur du monde ouvert pour les essais du core (lot W9).

Bibliothèque standard seulement : parle le dialogue de `docs/contracts/worldgen_v1.md` et écrit un monde
vivant minimal (route droite vers l'est, pente sinusoïdale, deux carrefours). Pannes sur demande :

    --horizon M          route engagée devant le cycliste (défaut 2 000 m)
    --crash-after-m M    `os._exit(3)` quand `progress` atteint M (autant de fois que --crash-times)
    --crash-times N      nombre de plantages successifs (marqueurs `crash.<k>` à côté du dossier de séance)
    --stall-m M          à partir de M, plus de prolongation (`data` = `missing`) tant que `resume.flag`
                         (à côté du dossier de séance) n'existe pas
    --late-m M           à partir de M, plus de prolongation tant que `resume.flag` n'existe pas, mais
                         `data` reste `cached` : générateur en retard sur le cycliste (machine lente)
    --no-ready           ne répond jamais à `open` (préparation interminable)
    --unavailable        répond `world_unavailable` à `open`

Avec `--stall-m` ou `--late-m`, `held.flag` (à côté du dossier de séance) donne, dès l'arrêt de la
prolongation, la dernière révision publiée : un essai sait quand le core a chargé la route figée.
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--session", type=Path, required=True)
ap.add_argument("--config", type=Path)
ap.add_argument("--horizon", type=float, default=2000.0)
ap.add_argument("--crash-after-m", type=float)
ap.add_argument("--crash-times", type=int, default=1)
ap.add_argument("--stall-m", type=float)
ap.add_argument("--late-m", type=float)
ap.add_argument("--no-ready", action="store_true")
ap.add_argument("--unavailable", action="store_true")
args = ap.parse_args()

SESSION: Path = args.session
SIDE = SESSION.parent
LAT0, LON0 = 45.0, 6.0
M_PER_DEG = 111_320.0

state = {"length": 0.0, "rev": 0, "s": 0.0, "data": "cached", "opened": False, "base_s": 0.0}
JUNCTIONS = [
    {"id": "jA", "s_m": 500.0, "default": 1, "chosen": 1, "branches": [(-90.0, "m", 3.0), (0.0, "t", -1.0), (90.0, "s", 6.0)]},
    {"id": "jB", "s_m": 1500.0, "default": 0, "chosen": 0, "branches": [(-30.0, "c", 0.5), (30.0, "k", 1.5)]},
]


def send(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    os.replace(tmp, path)


def grade(s: float) -> float:
    return round(2.0 * math.sin(s / 400.0), 3)


def part(k: int, length: float) -> dict:
    lo, hi = 1000.0 * k, min(1000.0 * (k + 1), length)
    ss = [lo + 10.0 * i for i in range(int(round((hi - lo) / 10.0)) + 1)]

    def altitude(s: float) -> float:   # intégrale de la pente : cohérente d'une partie à l'autre
        return round(600.0 + 2.0 * 400.0 * (1.0 - math.cos(s / 400.0)) / 100.0, 3)

    return {"version": "1.0", "ds_m": 10.0, "n": len(ss), "length_m": hi - lo, "type": "open", "s0_m": lo,
            "lat": [round(LAT0, 7)] * len(ss), "lon": [round(LON0 + s / (M_PER_DEG * math.cos(math.radians(LAT0))), 7) for s in ss],
            "alt_m": [altitude(s) for s in ss], "x": [float(s) for s in ss], "z": [0.0] * len(ss),
            "grade_pct": [grade(s) for s in ss], "heading_deg": [90.0] * len(ss)}


def junctions_payload() -> dict:
    out = []
    for j in JUNCTIONS:
        if j["s_m"] < state["s"] - 100.0 or j["s_m"] > state["length"]:
            continue
        out.append({"id": j["id"], "s_m": j["s_m"], "x": j["s_m"], "z": 0.0, "lock_s_m": j["s_m"] - 30.0,
                    "default": j["default"], "chosen": j["chosen"], "locked": state["s"] >= j["s_m"] - 30.0,
                    "branches": [{"index": i, "heading_deg": (90.0 + a) % 360.0, "angle_deg": a, "road_class": c,
                                  "grade_pct_500m": g, "dead_end": False,
                                  "preview": {"x": [j["s_m"], j["s_m"] + 10.0], "y": [600.0, 600.0], "z": [0.0, 10.0]}}
                                 for i, (a, c, g) in enumerate(j["branches"])]})
    return {"version": "1.0", "revision": state["rev"], "junctions": out}


def publish(changed_from: int) -> None:
    state["rev"] += 1
    n_parts = int(math.ceil(state["length"] / 1000.0))
    for k in range(changed_from, n_parts):
        write(SESSION / "route" / f"part_{k}.json", part(k, state["length"]))
    for stale in (SESSION / "route").glob("part_*.json"):
        if int(stale.stem.split("_")[1]) >= n_parts:
            stale.unlink()
    write(SESSION / "junctions.json", junctions_payload())
    write(SESSION / "live.json", {"version": "1.0", "revision": state["rev"],
                                  "route": {"parts": n_parts, "length_m": state["length"], "changed_from_part": changed_from},
                                  "tiles": {"near": [], "far": []}, "layer_tiles": [],
                                  "status": "ok" if state["data"] != "missing" else "missing"})
    send({"type": "revision", "rev": state["rev"], "length_m": state["length"], "changed_from_part": changed_from,
          "junctions": len(junctions_payload()["junctions"])})


def status(phase: str, message: str = "") -> None:
    send({"type": "status", "phase": phase, "done_bytes": 0, "total_bytes": None, "squares_ready": 0,
          "squares_needed": 0, "message": message, "data": state["data"]})


def extend(s: float) -> None:
    target = math.ceil((s + args.horizon) / 10.0) * 10.0
    if target > state["length"]:
        old = state["length"]
        state["length"] = target
        publish(max(0, int(old // 1000.0) - 1) if old else 0)


def hold() -> None:
    """Prolongation arrêtée : `held.flag` porte la dernière révision publiée (écriture atomique)."""
    if not (SIDE / "held.flag").exists():
        (SIDE / "held.flag.tmp").write_text(str(state["rev"]))
        os.replace(SIDE / "held.flag.tmp", SIDE / "held.flag")


def handle(msg: dict) -> bool:
    kind = msg.get("type")
    if kind == "open":
        if args.unavailable:
            send({"type": "error", "code": "world_unavailable", "message": "aucune route à moins de 200 m (doublure)"})
            return True
        if args.no_ready:
            status("osm", "doublure : préparation interminable")
            return True
        status("osm", "recherche de la région")
        status("generate", "carrés")
        state["opened"] = True
        status("ready")
        state["length"] = 0.0
        extend(0.0)
    elif kind == "progress" and state["opened"]:
        s = float(msg["s_m"])
        state["s"] = s
        if args.crash_after_m is not None and s >= args.crash_after_m:
            k = len(list(SIDE.glob("crash.*")))
            if k < args.crash_times:
                (SIDE / f"crash.{k}").write_text("x")
                sys.stderr.write("doublure : plantage simulé\n")
                sys.stderr.flush()
                os._exit(3)
        stalled = args.stall_m is not None and s >= args.stall_m and not (SIDE / "resume.flag").exists()
        if stalled:
            hold()
            if state["data"] != "missing":
                state["data"] = "missing"
                status("ready", "plus de route connue (doublure)")
            return True
        if state["data"] == "missing":
            state["data"] = "cached"
            status("ready")
        if args.late_m is not None and s >= args.late_m and not (SIDE / "resume.flag").exists():
            hold()
            return True
        extend(s)
    elif kind == "choose" and state["opened"]:
        j = next((x for x in JUNCTIONS if x["id"] == msg["junction_id"]), None)
        if j is None:
            send({"type": "error", "code": "unknown_junction", "message": "carrefour inconnu"})
        elif state["s"] >= j["s_m"] - 30.0:
            send({"type": "error", "code": "branch_locked", "message": "verrouillé"})
        else:
            j["chosen"] = int(msg["branch"])
            publish(int(j["s_m"] // 1000.0))
    elif kind == "close":
        send({"type": "closed"})
        return False
    return True


sys.stderr.write("doublure du générateur prête\n")
sys.stderr.flush()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    if not handle(msg):
        break
