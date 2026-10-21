"""Démo FIT du sprint 0 : séance simulée de bout en bout, sans matériel.

Puissance factice (échauffement, blocs, récupération) -> physique à 50 Hz sur un parcours
factice -> journal JSONL à 1 Hz (avec une pause) -> fichier FIT à ouvrir dans GoldenCheetah
et Garmin Connect.

    python -m openride_core.tools.fit_demo --minutes 10 --out ./spike_reports
"""

from __future__ import annotations

import argparse
import bisect
import math
import time
from pathlib import Path

from ..config import Config
from ..fit_export import journal_to_fit
from ..journal import JournalWriter, Record
from ..physics import DT_DEFAULT, PhysicsParams, RiderPhysics
from .fake_world import build_route


class LinearRoute:
    """Lecture simplifiée de la couche route (interpolation linéaire).

    Provisoire : la règle officielle (Catmull-Rom centripète pour la position) arrivera
    avec le module route du sprint 1.
    """

    def __init__(self, route: dict) -> None:
        self.r = route
        self.length = route["length_m"]
        self.s = [min(i * route["ds_m"], self.length) for i in range(route["n"])]

    def sample(self, key: str, s: float) -> float:
        s = min(max(s, 0.0), self.length)
        i = min(bisect.bisect_right(self.s, s) - 1, len(self.s) - 2)
        s0, s1 = self.s[i], self.s[i + 1]
        u = (s - s0) / (s1 - s0) if s1 > s0 else 0.0
        a, b = self.r[key][i], self.r[key][i + 1]
        return a + (b - a) * u


def demo_power(t: float, total: float) -> float:
    """Profil de puissance factice : échauffement, 3 blocs à 280 W, récupération."""
    warm = 0.2 * total
    cool = 0.85 * total
    if t < warm:
        return 140 + 80 * t / warm
    if t > cool:
        return 150.0
    block = (t - warm) / ((cool - warm) / 6)
    base = 280.0 if int(block) % 2 == 0 else 180.0
    return base + 10 * math.sin(t / 7.0)


def run(minutes: float, out_dir: Path) -> Path:
    cfg = Config()
    route = LinearRoute(build_route(30_000.0))
    phys = RiderPhysics(PhysicsParams.from_config(cfg))
    total = minutes * 60.0
    start_wall = time.time() - total - 60.0   # séance « passée » pour des horodatages réalistes
    journal_path = out_dir / f"fit_demo_{int(start_wall)}.jsonl"
    pause_at, pause_len = total / 2, 30.0

    with JournalWriter(journal_path, route_id="fake-climb") as j:
        j.event("start", start_wall)
        t_session, wall, next_log = 0.0, start_wall, 0.0
        paused = False
        while t_session < total:
            if not paused and t_session >= pause_at:
                j.event("pause", wall)
                wall += pause_len
                j.event("resume", wall)
                paused = True
            p = demo_power(t_session, total)
            grade = route.sample("grade_pct", phys.s)
            alt = route.sample("alt_m", phys.s)
            phys.step(p, grade, alt, DT_DEFAULT)
            t_session += DT_DEFAULT
            wall += DT_DEFAULT
            if t_session >= next_log:
                next_log += 1.0
                j.record(Record(
                    ts=round(wall, 3), t=round(t_session, 2),
                    lat=route.sample("lat", phys.s), lon=route.sample("lon", phys.s),
                    alt=round(alt, 2), distance=round(phys.s, 2), speed=round(phys.v, 3),
                    power=round(p), cadence=round(85 + 5 * math.sin(t_session / 11.0)),
                    hr=int(110 + 0.15 * p), grade=round(grade, 2), gear=12,
                ))
        j.event("stop", wall)

    fit_path, summary = journal_to_fit(journal_path, out_dir / journal_path.with_suffix(".fit").name)
    print(f"Journal : {journal_path}")
    print(f"FIT     : {fit_path}")
    print(f"Distance {summary.distance_m / 1000:.2f} km, chrono {summary.timer_s / 60:.1f} min, "
          f"écoulé {summary.elapsed_s / 60:.1f} min, P moy {summary.avg_power:.0f} W, "
          f"{summary.n_records} points")
    return fit_path


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--minutes", type=float, default=10.0)
    p.add_argument("--out", type=Path, default=Path("spike_reports"))
    args = p.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    run(args.minutes, args.out)


if __name__ == "__main__":
    main()
