"""Banc de l'abri derrière les bots (lots X50 et AS2) : gain par position, abri dans un groupe libre,
placement dans la roue et dépassement, sans vélo.

    python -m openride_core.tools.draft_bench [--puissance 250] [--groupe 230,240,250] \\
        [--cycliste 240] [--duree 600] [--json]

La vraie séance (`CoreSession`, abri P3, AS1 et AS2, lissage de 1 s) tourne au pas fixe de 20 ms sur un plat de
20 km, sans trainer ni engine, en trois parties :

1. **Gain par position.** Une file de 1, 2 ou 3 bots roule à vitesse imposée, celle d'un cycliste seul à
   `--puissance` W, roue dans la roue (0,5 m entre les bots). Le cycliste garde un écart fixe derrière le
   dernier bot : un régulateur PI règle la puissance du trainer simulé sans rien savoir de l'abri. La
   puissance moyenne des 60 dernières secondes (sur 120 s), comparée à celle de l'air libre, donne le gain en W et en %
   pour chaque écart (0,5 à 15 m).
2. **Groupe libre.** Des bots à puissance constante (`--groupe`) et le cycliste (`--cycliste` W), départ
   groupé, `--duree` s, moyenne de trois départs (1,5, 2,5 et 3,5 m entre les roues) : part du temps passé à l'abri (> 0,01) pour chacun, abri moyen et maximal, distance
   gagnée sur le même coureur seul et watts gagnés (puissance qu'il faudrait seul pour la vitesse moyenne
   du groupe, moins la sienne). Les bots s'abritent entre eux et derrière le cycliste (lot AS1). Deux
   passages : placement dans la roue du cycliste activé (`ride.auto_draft = on`, défaut) puis coupé ; nombre
   de dépassements de chacun et contacts (deux coureurs qui se chevauchent à moins d'une largeur de coureur,
   0,6 m, sur le côté ; au plus 1 % du temps : les bots à puissance constante ne freinent pas).
3. **Placement et dépassement (lot AS2).** Mise en roue : un bot à vitesse imposée 2 m devant, 0,9 m à
   droite ; temps pour que le cycliste soit à 0,1 m de sa ligne et abri obtenu, comparés à l'abri dans la
   roue et à l'abri placement coupé. Dépassement : le cycliste roule 1 m/s plus vite que le bot ; écart
   latéral minimal pendant le chevauchement, écart à l'axe le plus à gauche, retour à 1,2 m.

Échec (code 1) si : l'abri ou le gain n'est pas décroissant avec l'écart, s'il ne croît pas avec le nombre de
bots devant, s'il dépasse le plafond de la SRS (0,45), s'il reste au-delà de 15 m, ou si un coureur du groupe
libre ne reçoit jamais d'abri ou ne va pas plus loin que seul ; (AS2) si la mise en roue prend plus de 3 s ou
ne donne pas l'abri plein, si l'abri placement coupé dépasse 15 % de l'abri dans la roue, si le dépassement
laisse moins de 0,9 m sur le côté, passe à gauche de l'axe hors dépassement, sort de la route ou ne revient
pas à 1,2 m, ou si le groupe libre a des contacts plus de 1 % du temps.
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
WHEEL_GAP_M = 2.0              # lot AS2 : mise en roue derrière un bot à 2 m...
WHEEL_S = 10.0                 # ... pendant 10 s
PASS_DV_MPS = 1.0              # dépassement : 1 m/s plus vite que le bot
PASS_S = 60.0
START_GAPS_M = (1.5, 2.5, 3.5)   # départs du groupe libre (m entre les roues), moyennés
CONTACT_MAX_SHARE = 0.01       # groupe libre : contacts passagers tolérés (bots à puissance constante, sans frein)
TOL = 1e-3


class PacedBot:
    """Bot `constant` à vitesse imposée : la file reste figée, seul l'abri du cycliste varie."""

    kind = "constant"

    def __init__(self, bot_id: str, s: float, v: float, lane_m: float = draft_mod.RIDER_LANE_M) -> None:
        self.id, self.name = bot_id, f"File {bot_id}"
        self._s, self._v = s, v
        self.draft, self.wheel, self.push = 0.0, None, 0.0
        self.lane = draft_mod.Lane(lane_m, lane_m, auto=False)   # ligne figée (lot AS2)

    @property
    def s(self) -> float:
        return self._s

    @property
    def v(self) -> float:
        return self._v

    def step(self, dt: float, route: Any = None) -> None:
        self._s += self._v * dt

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "s": round(self._s, 2), "v": round(self._v, 3), "kind": self.kind,
                "lane_m": round(self.lane.m, 2)}


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

    def session(self, power_w: float, bots: list[Any], auto_draft: str = "on") -> CoreSession:
        self.n += 1
        run = self.tmp / f"run{self.n}"
        cfg = Config()
        cfg.powerups.mode = "off"
        cfg.ride.auto_draft = auto_draft
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

    def groups(self, powers: list[float], rider_w: float, seconds: float, auto_draft: str = "on") -> dict[str, Any]:
        """Groupe libre moyenné sur les départs de `START_GAPS_M` : la course d'un groupe est chaotique, un
        seul départ ne dit pas grand-chose de la part du temps à l'abri (lot AS2)."""
        runs = [self.group(powers, rider_w, seconds, auto_draft, g) for g in START_GAPS_M]
        rows = []
        for i, r0 in enumerate(runs[0]["rows"]):
            each = [run["rows"][i] for run in runs]
            row = {k: round(sum(r[k] for r in each) / len(each), 3 if k.startswith("draft") else 1)
                   for k in r0 if isinstance(r0[k], float)}
            row.update(name=r0["name"], power_w=r0["power_w"], passes=sum(r["passes"] for r in each),
                       shelter_each=[r["shelter_pct"] for r in each])
            rows.append(row)
        return {"seconds": seconds, "auto_draft": auto_draft, "starts_m": list(START_GAPS_M), "rows": rows,
                "contacts_s": round(sum(run["contacts_s"] for run in runs), 2)}

    def group(self, powers: list[float], rider_w: float, seconds: float, auto_draft: str = "on",
              start_gap_m: float = 1.5) -> dict[str, Any]:
        """Départ groupé (`start_gap_m` entre les roues), le cycliste derrière le dernier bot."""
        pitch = draft_mod.BIKE_LENGTH_M + start_gap_m
        bots = [ConstantPowerBot(w, bot_id=f"b{i + 1}", s=100.0 + pitch * (len(powers) - i), v=9.0)
                for i, w in enumerate(powers)]
        s = self.session(rider_w, bots, auto_draft)
        s.physics.s, s.physics.v = 100.0, 9.0
        racers: list[tuple[str, float, Any]] = [(f"bot {w:g} W", w, b) for w, b in zip(powers, bots)]
        stats = {name: {"on": 0, "sum": 0.0, "max": 0.0, "start": 0.0, "passes": 0}
                 for name, _, _ in racers + [("cycliste", 0, None)]}
        for name, _, b in racers:
            stats[name]["start"] = b.s
        stats["cycliste"]["start"] = s.physics.s
        steps = int(round(seconds / DT))
        contacts = 0
        for _ in range(steps):
            was = {name: (s._lane if b is None else b.lane).passing for name, _, b in racers + [("cycliste", 0, None)]}
            s._step(DT, time.monotonic())
            lanes = [(s.physics.s, s._lane.m)] + [(b.s, b.lane.m) for b in bots]
            contacts += any(abs(a[0] - b[0]) < draft_mod.BIKE_LENGTH_M and abs(a[1] - b[1]) < draft_mod.RIDER_WIDTH_M
                            for i, a in enumerate(lanes) for b in lanes[i + 1:])
            for name, _, b in racers + [("cycliste", rider_w, None)]:
                a = s._draft if b is None else b.draft
                st = stats[name]
                st["on"] += a > SHELTER_MIN
                st["sum"] += a
                st["max"] = max(st["max"], a)
                lane = s._lane if b is None else b.lane
                st["passes"] += lane.passing and not was[name]
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
                         "speed_kmh": round(v_mean * 3.6, 2), "passes": st["passes"],
                         "gain_w": round(free_power(v_mean, params, route.sample(ends[name]).alt_m) - w, 1)})
        return {"seconds": seconds, "auto_draft": auto_draft, "rows": rows, "contacts_s": round(contacts * DT, 2)}

    def wheel(self, power_w: float) -> dict[str, Any]:
        """Mise en roue (lot AS2) : bot à vitesse imposée 2 m devant et 0,9 m à droite du cycliste, qui garde
        l'écart au régulateur ; placement activé puis coupé."""
        probe = self.session(power_w, [])
        p, route = probe.physics.p, probe.route
        probe._finish(save=False)
        alt = route.sample(0.0).alt_m
        v0 = steady_speed(power_w, 0.0, p, alt)
        out: dict[str, Any] = {"speed_kmh": round(v0 * 3.6, 2), "gap_m": WHEEL_GAP_M,
                               "full": round(draft_mod.draft_coefficient(WHEEL_GAP_M), 3)}
        for auto in ("on", "off"):
            lead = PacedBot("w1", 50.0 + draft_mod.BIKE_LENGTH_M + WHEEL_GAP_M, v0, draft_mod.BOT_LANE_M)
            s = self.session(free_power(v0, p, alt), [lead], auto)
            s.physics.s, s.physics.v = 50.0, v0
            settle, t, integral = None, 0.0, 0.0
            while t < WHEEL_S - 1e-9:
                err = (lead.s - draft_mod.BIKE_LENGTH_M - WHEEL_GAP_M) - s.physics.s
                integral += err * DT
                s.driver.base_power_w = max(0.0, free_power(v0, p, alt) + KP_W_PER_M * err
                                            + KD_W_PER_MPS * (lead.v - s.physics.v) + KI_W_PER_MS * integral)
                s._step(DT, time.monotonic())
                t += DT
                if settle is None and abs(s._lane.m - lead.lane.m) < 0.1:
                    settle = t
            out[auto] = {"settle_s": None if settle is None else round(settle, 2), "lane_m": round(s._lane.m, 2),
                         "draft": round(s._draft, 3)}
            s._finish(save=False)
        return out

    def overtake(self, power_w: float) -> dict[str, Any]:
        """Dépassement (lot AS2) : le cycliste, 1 m/s plus vite, rattrape un bot à vitesse imposée sur sa ligne."""
        probe = self.session(power_w, [])
        p, route = probe.physics.p, probe.route
        probe._finish(save=False)
        alt = route.sample(0.0).alt_m
        v0 = steady_speed(power_w, 0.0, p, alt)
        lead = PacedBot("o1", 50.0 + draft_mod.BIKE_LENGTH_M + 8.0, v0, draft_mod.RIDER_LANE_M)
        s = self.session(free_power(v0 + PASS_DV_MPS, p, alt), [lead])
        s.physics.s, s.physics.v = 50.0, v0 + PASS_DV_MPS
        side, leftmost, off_axis, passes, was = [], 9.0, 0.0, 0, False
        for _ in range(int(round(PASS_S / DT))):
            s.driver.base_power_w = free_power(v0 + PASS_DV_MPS, p, alt) + KD_W_PER_MPS * (v0 + PASS_DV_MPS - s.physics.v)
            s._step(DT, time.monotonic())
            lane = s._lane
            if abs(lead.s - s.physics.s) < draft_mod.BIKE_LENGTH_M:
                side.append(abs(lane.m - lead.lane.m))
            leftmost = min(leftmost, lane.m)
            if not lane.passing:
                off_axis = min(off_axis, lane.m)
            passes += lane.passing and not was
            was = lane.passing
        out = {"dv_mps": PASS_DV_MPS, "side_min_m": round(min(side), 2) if side else None,
               "leftmost_m": round(leftmost, 2), "left_of_axis_m": round(off_axis, 2), "passes": passes,
               "end_lane_m": round(s._lane.m, 2), "ahead_m": round(s.physics.s - lead.s, 1)}
        s._finish(save=False)
        return out

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
        group = bench.groups(group_w, rider_w, seconds)
        group_off = bench.groups(group_w, rider_w, seconds, "off")
        wheel = bench.wheel(power_w)
        passing = bench.overtake(power_w)
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
    for grp in (group, group_off):
        checks.append((grp["contacts_s"] <= CONTACT_MAX_SHARE * grp["seconds"] * len(grp["starts_m"]),
                       f"groupe libre, placement {grp['auto_draft']} : "
                       f"{grp['contacts_s']:g} s de contact (chevauchement à moins de {draft_mod.RIDER_WIDTH_M:g} m sur le côté ; "
                       f"au plus {CONTACT_MAX_SHARE:.0%} du temps)"))
    on, off = wheel["on"], wheel["off"]
    checks.append((on["settle_s"] is not None and on["settle_s"] < 3.0,
                   f"mise en roue : à 0,1 m de la ligne du bot en {on['settle_s']} s (moins de 3 s)"))
    checks.append((on["draft"] >= 0.95 * wheel["full"], f"mise en roue : abri {on['draft']:.3f} (dans la roue {wheel['full']:.3f})"))
    checks.append((off["draft"] < 0.15 * wheel["full"],
                   f"placement coupé, bot 0,9 m à droite : abri {off['draft']:.3f}, moins de 15 % de l'abri dans la roue"))
    checks.append((passing["side_min_m"] is not None and passing["side_min_m"] >= draft_mod.SIDE_CLEAR_M - 0.01,
                   f"dépassement : {passing['side_min_m']} m sur le côté au plus près (au moins {draft_mod.SIDE_CLEAR_M:g} m)"))
    checks.append((passing["left_of_axis_m"] >= 0.0 and passing["leftmost_m"] > -3.0,
                   f"dépassement : jamais à gauche de l'axe hors dépassement, au plus à {passing['leftmost_m']} m"))
    checks.append((abs(passing["end_lane_m"] - draft_mod.RIDER_LANE_M) < 0.05 and passing["ahead_m"] > 0.0,
                   f"dépassement : revenu à {passing['end_lane_m']} m de l'axe, {passing['ahead_m']:g} m devant le bot"))
    return {"power_w": power_w, "positions": positions, "group": group, "group_off": group_off,
            "wheel": wheel, "overtake": passing,
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
    for grp in (out["group"], out["group_off"]):
        starts = ", ".join(f"{g:g}" for g in grp["starts_m"])
        lines += ["", f"2{'a' if grp['auto_draft'] == 'on' else 'b'}. Groupe libre, {grp['seconds']:g} s sur le plat, placement dans la roue {grp['auto_draft']} : "
                  f"moyenne de {len(grp['starts_m'])} départs ({starts} m entre les roues)", "",
                  f"  {'coureur':<12} {'à l’abri':>9} {'abri moy.':>9} {'max':>5} {'distance':>9} {'seul':>8} {'gagné':>7} "
                  f"{'vitesse':>10} {'gain':>7} {'dépass.':>7}"]
        for r in grp["rows"]:
            lines.append(f"  {r['name']:<12} {r['shelter_pct']:7.1f} % {r['draft_mean']:9.3f} {r['draft_max']:5.2f} "
                         f"{r['dist_m']:7.0f} m {r['solo_m']:6.0f} m {r['ahead_m']:+5.0f} m {r['speed_kmh']:6.1f} km/h "
                         f"{r['gain_w']:5.1f} W {r['passes']:7d}")
    w, o = out["wheel"], out["overtake"]
    lines += ["", f"3. Placement (lot AS2) : bot à {w['gap_m']:g} m devant, 0,9 m à droite, {w['speed_kmh']:.1f} km/h",
              f"  placement activé : ligne du bot en {w['on']['settle_s']} s, abri {w['on']['draft']:.3f} "
              f"(dans la roue {w['full']:.3f})",
              f"  placement coupé  : reste à {w['off']['lane_m']} m de l'axe, abri {w['off']['draft']:.3f}",
              f"  dépassement à +{o['dv_mps']:g} m/s : {o['side_min_m']} m sur le côté au plus près, au plus à "
              f"{o['leftmost_m']} m de l'axe, retour à {o['end_lane_m']} m", ""]
    lines += [f"[{'OK' if c['ok'] else 'ÉCHEC'}] {c['text']}" for c in out["checks"]]
    lines.append(f"Calcul en {out['wall_s']:.1f} s")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Banc de l'abri derrière les bots (lots X50 et AS2).")
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
