"""Banc de l'abri derrière les bots (lot X50) : gain par position et abri dans un groupe libre, sans vélo.

    python -m openride_core.tools.draft_bench [--puissance 250] [--groupe 230,240,250] \\
        [--cycliste 240] [--duree 600] [--json]

La vraie séance (`CoreSession`, abri P3 et AS1, lissage de 1 s) tourne au pas fixe de 20 ms sur un plat de
20 km, sans trainer ni engine, en deux parties :

1. **Gain par position.** Une file de 1, 2 ou 3 bots roule à vitesse imposée, celle d'un cycliste seul à
   `--puissance` W, roue dans la roue (0,5 m entre les bots). Le cycliste garde un écart fixe derrière le
   dernier bot : un régulateur PI règle la puissance du trainer simulé sans rien savoir de l'abri. La
   puissance moyenne des 60 dernières secondes (sur 120 s), comparée à celle de l'air libre, donne le gain en W et en %
   pour chaque écart (0,5 à 15 m).
2. **Groupe libre.** Des bots à puissance constante (`--groupe`) et le cycliste (`--cycliste` W), départ
   groupé, `--duree` s : part du temps passé à l'abri (> 0,01) pour chacun, abri moyen et maximal, distance
   gagnée sur le même coureur seul et watts gagnés (puissance qu'il faudrait seul pour la vitesse moyenne
   du groupe, moins la sienne). Les bots s'abritent entre eux et derrière le cycliste (lot AS1).

Échec (code 1) si : l'abri ou le gain n'est pas décroissant avec l'écart, s'il ne croît pas avec le nombre de
bots devant, s'il dépasse le plafond de la SRS (0,45), s'il reste au-delà de 15 m, ou si un coureur du groupe
libre ne reçoit jamais d'abri ou ne va pas plus loin que seul.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest import mock

from .. import draft as draft_mod
from .. import fit_export
from ..bots import ConstantPowerBot
from ..config import Config
from ..demo_world import write_world
from ..input_providers import NullProvider
from ..mock_driver import MockDriver
from ..physics import PhysicsParams, resistive_force, steady_speed
from ..session import CoreSession

DT = 0.02
ROUTE_M = 20000.0
GAPS_M = (0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0)
FILE_GAP_M = 0.5               # écart entre les bots de la file imposée
HOLD_S = 120.0                  # durée d'une position
MEASURE_S = 60.0               # moyenne sur les dernières secondes
KP_W_PER_M = 60.0              # régulateur de l'écart (W par m d'écart, W par m/s, W par m·s)
KD_W_PER_MPS = 1500.0
KI_W_PER_MS = 15.0
SHELTER_MIN = 0.01             # abri compté dans la part du temps à l'abri
TOL = 1e-3


class PacedBot:
    """Bot `constant` à vitesse imposée : la file reste figée, seul l'abri du cycliste varie."""

    kind = "constant"

    def __init__(self, bot_id: str, s: float, v: float) -> None:
        self.id, self.name = bot_id, f"File {bot_id}"
        self._s, self._v = s, v
        self.draft, self.wheel, self.push = 0.0, None, 0.0

    @property
    def s(self) -> float:
        return self._s

    @property
    def v(self) -> float:
        return self._v

    def step(self, dt: float, route: Any = None) -> None:
        self._s += self._v * dt

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "s": round(self._s, 2), "v": round(self._v, 3), "kind": self.kind}


def free_power(v: float, p: PhysicsParams, alt_m: float) -> float:
    """Puissance qu'il faut seul, sur le plat à l'altitude `alt_m`, pour rouler à `v`."""
    return resistive_force(v, 0.0, alt_m, p) * v / p.efficiency


class Bench:
    """Séances jetables : journal, FIT et records dans un dossier temporaire."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.routes = tmp / "routes"
        self.routes.mkdir()
        write_world(self.routes, "plat", ROUTE_M, created="2026-10-30T00:00:00+01:00", grade=lambda s: 0.0)
        self.n = 0

    def session(self, power_w: float, bots: list[Any]) -> CoreSession:
        self.n += 1
        run = self.tmp / f"run{self.n}"
        cfg = Config()
        cfg.depart.mode = "immediat"   # banc sans engine ni cycliste : départ à la commande start (lot O36)
        cfg.powerups.mode = "off"
        s = CoreSession(cfg, driver=MockDriver(base_power_w=power_w, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=run / "journal", routes_root=self.routes,
                        workouts_dir=run / "workouts", bots=bots, records_path=run / "records.json",
                        powerups_path=run / "powerups.toml", profile_path=run / "profile.json")
        s.server.send_raw = lambda m, max_size=None: None
        s.server.send_input_event = lambda ev: None
        s._on_command("select_route", {"route_id": "plat"}, 1)
        s._on_command("start", {}, 2)
        return s

    def hold(self, n_bots: int, gap_m: float, power_w: float) -> dict[str, Any]:
        """Le cycliste garde `gap_m` (roue à roue) derrière une file de `n_bots` bots à vitesse imposée."""
        probe = self.session(power_w, [])
        p, route = probe.physics.p, probe.route
        probe._finish(save=False)
        alt = route.sample(0.0).alt_m
        v0 = steady_speed(power_w, 0.0, p, alt)
        p_free = free_power(v0, p, alt)
        pitch = draft_mod.BIKE_LENGTH_M + FILE_GAP_M
        head = 50.0 + draft_mod.BIKE_LENGTH_M + gap_m + pitch * (n_bots - 1)
        bots = [PacedBot(f"f{i + 1}", head - pitch * i, v0) for i in range(n_bots)]
        s = self.session(p_free, bots)
        s.physics.s, s.physics.v = 50.0, v0
        last = bots[-1]
        integral, powers, drafts, gaps = 0.0, [], [], []
        t = 0.0
        while t < HOLD_S - 1e-9:
            err = (last.s - draft_mod.BIKE_LENGTH_M - gap_m) - s.physics.s   # > 0 : trop loin derrière
            integral += err * DT
            s.driver.base_power_w = max(0.0, p_free + KP_W_PER_M * err + KD_W_PER_MPS * (last.v - s.physics.v)
                                        + KI_W_PER_MS * integral)
            s._step(DT, time.monotonic())
            t += DT
            if t > HOLD_S - MEASURE_S:
                powers.append(s.driver.base_power_w)
                drafts.append(s._draft)
                gaps.append(last.s - draft_mod.BIKE_LENGTH_M - s.physics.s)
        s._finish(save=False)
        mean_p = sum(powers) / len(powers)
        return {"bots": n_bots, "gap_m": gap_m, "speed_kmh": round(v0 * 3.6, 2), "free_w": round(p_free, 1),
                "power_w": round(mean_p, 1), "gain_w": round(p_free - mean_p, 1) + 0.0,   # + 0.0 : pas de « -0.0 »
                "gain_pct": round((p_free - mean_p) / p_free * 100.0, 1) + 0.0,
                "draft": round(sum(drafts) / len(drafts), 3), "gap_mean_m": round(sum(gaps) / len(gaps), 2)}

    def group(self, powers: list[float], rider_w: float, seconds: float) -> dict[str, Any]:
        """Départ groupé (1,5 m entre les roues), le cycliste derrière le dernier bot."""
        pitch = draft_mod.BIKE_LENGTH_M + 1.5
        bots = [ConstantPowerBot(w, bot_id=f"b{i + 1}", s=100.0 + pitch * (len(powers) - i), v=9.0)
                for i, w in enumerate(powers)]
        s = self.session(rider_w, bots)
        s.physics.s, s.physics.v = 100.0, 9.0
        racers: list[tuple[str, float, Any]] = [(f"bot {w:g} W", w, b) for w, b in zip(powers, bots)]
        stats = {name: {"on": 0, "sum": 0.0, "max": 0.0, "start": 0.0} for name, _, _ in racers + [("cycliste", 0, None)]}
        for name, _, b in racers:
            stats[name]["start"] = b.s
        stats["cycliste"]["start"] = s.physics.s
        steps = int(round(seconds / DT))
        for _ in range(steps):
            s._step(DT, time.monotonic())
            for name, _, b in racers + [("cycliste", rider_w, None)]:
                a = s._draft if b is None else b.draft
                st = stats[name]
                st["on"] += a > SHELTER_MIN
                st["sum"] += a
                st["max"] = max(st["max"], a)
        p_rider, route = s.physics.p, s.route
        ends = {name: b.s for name, _, b in racers}
        ends["cycliste"] = s.physics.s
        s._finish(save=False)
        rows = []
        for name, w, b in racers + [("cycliste", rider_w, None)]:
            params = b.params if b is not None else p_rider
            solo = self.solo(w, params, seconds, route)
            dist = ends[name] - stats[name]["start"]
            v_mean = dist / seconds
            st = stats[name]
            rows.append({"name": name, "power_w": w, "shelter_pct": round(st["on"] / steps * 100.0, 1),
                         "draft_mean": round(st["sum"] / steps, 3), "draft_max": round(st["max"], 3),
                         "dist_m": round(dist, 1), "solo_m": round(solo, 1), "ahead_m": round(dist - solo, 1),
                         "speed_kmh": round(v_mean * 3.6, 2),
                         "gain_w": round(free_power(v_mean, params, route.sample(ends[name]).alt_m) - w, 1)})
        return {"seconds": seconds, "rows": rows}

    def solo(self, power_w: float, params: PhysicsParams, seconds: float, route: Any) -> float:
        """Distance d'un bot seul à la même puissance, même départ à 9 m/s, même physique et même parcours."""
        b = ConstantPowerBot(power_w, bot_id="solo", params=params, s=100.0, v=9.0)
        for _ in range(int(round(seconds / DT))):
            b.step(DT, route)
        return b.s - 100.0


def run(power_w: float = 250.0, group_w: list[float] | None = None, rider_w: float = 240.0,
        seconds: float = 600.0, gaps: tuple[float, ...] = GAPS_M) -> dict[str, Any]:
    group_w = group_w or [230.0, 240.0, 250.0]
    t_wall = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="openride-draft-bench-") as tmp_s, \
            mock.patch.object(fit_export, "ACTIVITIES_DIR", Path(tmp_s) / "Activities"):
        bench = Bench(Path(tmp_s))
        positions = [bench.hold(n, g, power_w) for n in (1, 2, 3) for g in gaps]
        group = bench.group(group_w, rider_w, seconds)
    checks = []
    for n in (1, 2, 3):
        line = [r for r in positions if r["bots"] == n]
        dec = all(a["gain_w"] >= b["gain_w"] - 0.5 and a["draft"] >= b["draft"] - TOL for a, b in zip(line, line[1:]))
        checks.append((dec, f"derrière {n} bot(s) : gain décroissant avec l'écart"))
    for g in gaps:
        col = [r for r in positions if r["gap_m"] == g]
        if col[0]["draft"] > TOL:
            inc = all(b["draft"] >= a["draft"] - TOL for a, b in zip(col, col[1:]))
            checks.append((inc, f"à {g:g} m : abri qui croît avec le nombre de bots devant"))
    top = max(r["draft"] for r in positions)
    checks.append((top <= draft_mod.ALPHA_CAP + TOL, f"abri le plus fort {top:.3f} (plafond {draft_mod.ALPHA_CAP})"))
    far = [r for r in positions if r["gap_m"] > draft_mod.GAP_CUTOFF_M]
    if far:
        checks.append((all(r["draft"] <= TOL for r in far), f"aucun abri au-delà de {draft_mod.GAP_CUTOFF_M:g} m"))
    hold_ok = all(abs(r["gap_mean_m"] - r["gap_m"]) < 0.1 for r in positions)
    checks.append((hold_ok, "le régulateur garde l'écart moyen à 0,1 m près"))
    for r in group["rows"]:
        checks.append((r["draft_max"] > 0.05 and r["ahead_m"] > 0.0,
                       f"groupe libre, {r['name']} : à l'abri {r['shelter_pct']:g} % du temps, {r['ahead_m']:+.0f} m sur seul"))
    return {"power_w": power_w, "positions": positions, "group": group,
            "checks": [{"ok": ok, "text": txt} for ok, txt in checks], "wall_s": round(time.perf_counter() - t_wall, 1)}


def format_text(out: dict[str, Any]) -> str:
    pos = out["positions"]
    lines = [f"1. Gain par position : file à vitesse imposée ({pos[0]['speed_kmh']:.1f} km/h, {pos[0]['free_w']:.0f} W seul)",
             "", f"  {'écart':>6}  " + "  ".join(f"{f'derrière {n} bot' + ('s' if n > 1 else ''):>22}" for n in (1, 2, 3))]
    for g in sorted({r["gap_m"] for r in pos}):
        cells = []
        for n in (1, 2, 3):
            r = next(x for x in pos if x["bots"] == n and x["gap_m"] == g)
            cells.append(f"{r['draft']:.2f}  {r['gain_w']:5.1f} W {r['gain_pct']:4.1f} %")
        lines.append(f"  {g:5g} m  " + "  ".join(f"{c:>22}" for c in cells))
    grp = out["group"]
    lines += ["", f"2. Groupe libre, départ groupé, {grp['seconds']:g} s sur le plat", "",
              f"  {'coureur':<12} {'à l’abri':>9} {'abri moy.':>9} {'max':>5} {'distance':>9} {'seul':>8} {'gagné':>7} {'vitesse':>10} {'gain':>7}"]
    for r in grp["rows"]:
        lines.append(f"  {r['name']:<12} {r['shelter_pct']:7.1f} % {r['draft_mean']:9.3f} {r['draft_max']:5.2f} "
                     f"{r['dist_m']:7.0f} m {r['solo_m']:6.0f} m {r['ahead_m']:+5.0f} m {r['speed_kmh']:6.1f} km/h {r['gain_w']:5.1f} W")
    lines.append("")
    lines += [f"[{'OK' if c['ok'] else 'ÉCHEC'}] {c['text']}" for c in out["checks"]]
    lines.append(f"Calcul en {out['wall_s']:.1f} s")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Banc de l'abri derrière les bots (lot X50).")
    ap.add_argument("--puissance", type=float, default=250.0, help="puissance de la file imposée (W)")
    ap.add_argument("--groupe", default="230,240,250", help="puissances des bots du groupe libre (W)")
    ap.add_argument("--cycliste", type=float, default=240.0, help="puissance du cycliste du groupe libre (W)")
    ap.add_argument("--duree", type=float, default=600.0, help="durée du groupe libre (s)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        group = [float(x) for x in args.groupe.split(",") if x.strip()]
    except ValueError:
        print(f"puissances invalides : {args.groupe}", file=sys.stderr)
        return 2
    if not group or min(group) <= 0 or args.puissance <= 0 or args.cycliste <= 0 or args.duree <= 0:
        print("puissances et durée doivent être positives", file=sys.stderr)
        return 2
    out = run(args.puissance, group, args.cycliste, args.duree)
    print(json.dumps(out, ensure_ascii=False, indent=2) if args.json else format_text(out), end="" if not args.json else "\n")
    return 0 if all(c["ok"] for c in out["checks"]) else 1


if __name__ == "__main__":
    sys.exit(main())
