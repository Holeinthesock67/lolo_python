"""Campagne de courses simulées pour la cote Elo (lot BOT-elo) : la cote suit-elle la force du cycliste ?

    python -m openride_core.tools.elo_campagne [--courses 30] [--forces 0.92,1.0,1.08] [--adversaires 4]
        [--tours 1] [--tour-m 2000] [--ftp 250] [--mode grandprix|race] [--json]

Un essai vélo de 10 min ne fait qu'une ou deux courses : il ne dit rien de la cote, qui ne bouge qu'au fil des
courses. Ce banc joue des campagnes entières sans vélo ni engine, avec la vraie séance (`CoreSession`) : Grand
Prix des objets (ou Course, `--mode race`, lot CR1) sur un anneau synthétique, bots à profil, cote lue et écrite dans `elo.json` d'un dossier
temporaire (rien n'est écrit dans le profil réel). Pour chaque force, le cycliste roule à puissance constante :
force × la puissance que visent les bots à la cote de départ (1 500), 1,08 = 8 % plus fort que le peloton. Au
Grand Prix, il joue ses objets comme un bot (`brain.wants`, sans délai de réaction) : depuis le lot GPO1, un
cycliste qui ne s'en sert jamais perd trop contre des objets qui durent pour que sa cote suive sa force.

Contrôles (code 1 si l'un échoue, code 2 pour un appel invalide) :
- la cote finale suit l'ordre des forces (plus fort : cote plus haute) ;
- un cycliste plus fort voit sa cote monter (au-dessus de 1 500), un plus faible la voit descendre (d'au moins
  40 points, 25 au Grand Prix des objets, où la chance des objets compte plus depuis le lot GPO1) ;
- sur le dernier tiers de la campagne, la place moyenne revient vers le milieu du peloton (juste part, entre
  la 2e et l'avant-dernière place) et la cote est stable (écart type sous 60 points) ;
- les écarts propres des bots restent dans leurs bornes (± 100 points).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest import mock

from .. import bot_elo, fit_export, profile
from ..config import Config
from ..demo_world import write_world
from ..grandprix import brain as gp_brain
from ..input_providers import NullProvider
from ..mock_driver import MockDriver
from ..session import CoreSession
from .route_vectors import _route

DT = 0.05                      # pas de la séance : la cote ne dépend que du classement
MAX_RACE_S = 3 * 3600.0
T0_WALL = 1_790_000_000.0
STABLE_STD = 60.0
MIN_DELTA = 40.0               # une force à ± 8 % doit déplacer la cote d'au moins 40 points
# Grand Prix : depuis le lot GPO1 (objets qui durent, coup ≈ 7 s), la chance des objets pèse autant qu'une force
# de ± 8 % sur une course de 2 km : la cote suit la force deux fois moins vite (20 courses : + 32 au lieu de + 93).
MIN_DELTA_BY_MODE = {"grandprix": 25.0}


class CampaignError(Exception):
    pass


def ring_route(lap_m: float) -> dict:
    """Anneau fermé de `lap_m` (pas de 10 m), une bosse douce de 6 m (celui des tests du Grand Prix)."""
    n = int(lap_m / 10.0) + 1
    headings = [i * 360.0 / (n - 1) for i in range(n)]
    alts = [100.0 + 6.0 * (1.0 - abs(2.0 * i / (n - 1) - 1.0)) for i in range(n)]
    return _route(headings, alts, ds=10.0, last=10.0, kind="loop")


def _session(tmp: Path, cfg: Config, power_w: float) -> CoreSession:
    s = CoreSession(cfg, driver=MockDriver(base_power_w=power_w, ramp_amplitude_w=0.0),
                    inputs=[NullProvider()], journal_dir=tmp / "journal", routes_root=tmp / "routes",
                    workouts_dir=tmp / "workouts", records_path=tmp / "profil" / "records.json",
                    powerups_path=tmp / "powerups.toml", wtf_path=tmp / "wtf.toml",
                    grandprix_path=tmp / "grandprix.toml", profile_path=tmp / "profile.json")
    s.server.send_raw = lambda m, max_size=None: None
    s.server.send_error = lambda code, msg: None
    s.server.send_input_event = lambda ev: None
    return s


def _play_item(s: CoreSession) -> None:
    """Objet en réserve du cycliste joué quand un bot le jouerait (Z au bon moment), Grand Prix seulement."""
    gp = s.grandprix
    me = gp.racers.get("me") if gp is not None and gp.table.items else None
    if me is not None and me.held is not None and me.finished is None:
        if gp_brain.wants(gp, me, gp.table.items[me.held]):
            gp.use("me")


def campaign(force: float, races: int, opponents: int = 4, laps: int = 1, lap_m: float = 2000.0,
             ftp_w: float = 250.0, mode: str = "grandprix") -> dict[str, Any]:
    """Une campagne de `races` courses du mode `mode` (Grand Prix ou Course) pour un cycliste de force `force` ;
    rend les lignes de cote."""
    wall = [T0_WALL]
    with tempfile.TemporaryDirectory(prefix="openride-elo-campagne-") as tmp_s, \
            mock.patch.object(fit_export, "ACTIVITIES_DIR", Path(tmp_s) / "Activities"), \
            mock.patch.object(profile, "PROFILE_PATH", Path(tmp_s) / "profile.json"), \
            mock.patch.object(time, "time", lambda: wall[0]):
        tmp = Path(tmp_s)
        (tmp / "workouts").mkdir()
        world = write_world(tmp / "routes", "anneau", lap_m)
        (world / "route.json").write_text(json.dumps(ring_route(lap_m)), encoding="utf-8")
        cfg = Config()
        cfg.depart.mode = "immediat"
        cfg.rider.ftp_w = ftp_w
        cfg.grandprix.opponents, cfg.grandprix.laps = opponents, laps
        cfg.race.opponents, cfg.race.laps = opponents, laps
        cfg.ride.vehicle_draft = "off"
        cfg.bots.elo = "on"
        target_w: float | None = None
        lines: list[dict] = []
        for n in range(races):
            s = _session(tmp, cfg, power_w=ftp_w)
            s._on_command("select_route", {"route_id": "anneau"}, 1)
            if s.route is None:
                raise CampaignError("anneau refusé par la séance")
            s._on_command("start", {"mode": mode}, 2)
            if s.grandprix is None:
                raise CampaignError(f"{mode} refusé par la séance")
            if target_w is None:
                # Puissance visée par les bots à la cote de départ : la référence de la force du cycliste.
                bots = list(s._effort_bots)
                target_w = ftp_w * sum(b.effort_target[0] for b in bots) / len(bots) / 100.0 if bots else 0.0
                if target_w <= 0:
                    raise CampaignError("effort des bots inconnu")
            s.driver.base_power_w = force * target_w
            t = 0.0
            while s.state.session_state == "RUNNING" and t < MAX_RACE_S:
                wall[0] += DT
                s._step(DT, wall[0])
                t += DT
                _play_item(s)
            if s.state.session_state == "RUNNING":
                s._finish(save=True)
            elo = (s.state.summary or {}).get("elo")
            if not elo:
                raise CampaignError(f"course {n + 1} : pas de cote au bilan")
            if elo.get("mode") != mode:
                raise CampaignError(f"course {n + 1} : cote du mode {elo.get('mode')!r} au lieu de {mode!r}")
            lines.append({k: elo[k] for k in ("place", "of", "before", "after", "delta")})
            wall[0] += 600.0
        book = bot_elo.load(bot_elo.path_for(tmp / "profil"))
    tail = lines[-max(races // 3, 1):]
    return {"mode": mode, "force": force, "rider_w": round(force * (target_w or 0.0), 1), "target_w_1500": round(target_w or 0.0, 1),
            "races": races, "of": opponents + 1, "final": round(book.rating), "lines": lines,
            "tail_place": round(statistics.mean(r["place"] for r in tail), 2),
            "tail_std": round(statistics.pstdev([r["after"] for r in tail]), 1),
            "offset_max": round(max((abs(v) for v in book.offsets.values()), default=0.0), 1)}


def checks(runs: list[dict]) -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []
    by = sorted(runs, key=lambda r: r["force"])
    finals = [r["final"] for r in by]
    out.append((all(a < b for a, b in zip(finals, finals[1:])),
                "cote finale dans l'ordre des forces : " + ", ".join(f"{r['force']:g} → {r['final']}" for r in by)))
    for r in by:
        tag = f"force {r['force']:g}"
        min_delta = MIN_DELTA_BY_MODE.get(str(r.get("mode", "")), MIN_DELTA)
        if r["force"] > 1.0:
            out.append((r["final"] >= bot_elo.START + min_delta, f"{tag} : la cote monte ({r['final']})"))
        elif r["force"] < 1.0:
            out.append((r["final"] <= bot_elo.START - min_delta, f"{tag} : la cote descend ({r['final']})"))
        of = r["of"]
        out.append((2.0 <= r["tail_place"] <= of - 1.0,
                    f"{tag} : place moyenne du dernier tiers {r['tail_place']} sur {of} (juste part : 2 à {of - 1})"))
        out.append((r["tail_std"] <= STABLE_STD, f"{tag} : cote stable sur le dernier tiers (écart type {r['tail_std']})"))
        out.append((r["offset_max"] <= bot_elo.OFFSET_MAX, f"{tag} : écarts des bots bornés ({r['offset_max']})"))
    return out


def format_text(runs: list[dict], result: list[tuple[bool, str]]) -> str:
    rows = []
    for r in runs:
        rows.append(f"Force {r['force']:g} : cycliste {r['rider_w']} W (bots à 1 500 : {r['target_w_1500']} W), "
                    f"{r['races']} courses à {r['of']}")
        rows.append("  cote : " + " ".join(str(x["after"]) for x in r["lines"]))
        rows.append("  places : " + " ".join(str(x["place"]) for x in r["lines"]))
    rows += [("[OK] " if ok else "[ÉCHEC] ") + txt for ok, txt in result]
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--courses", type=int, default=30)
    ap.add_argument("--forces", default="0.92,1.0,1.08", help="forces du cycliste, séparées par des virgules")
    ap.add_argument("--adversaires", type=int, default=4)
    ap.add_argument("--tours", type=int, default=1)
    ap.add_argument("--tour-m", type=float, default=2000.0)
    ap.add_argument("--ftp", type=float, default=250.0)
    ap.add_argument("--mode", choices=("grandprix", "race"), default="grandprix")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        forces = [float(x) for x in a.forces.split(",") if x.strip()]
    except ValueError:
        print("forces invalides", file=sys.stderr)
        return 2
    if a.courses < 3 or not forces or not 2 <= a.adversaires <= 11 or a.tours < 1 or a.tour_m < 500:
        print("appel invalide (au moins 3 courses, 2 à 11 adversaires, tour d'au moins 500 m)", file=sys.stderr)
        return 2
    t0 = time.perf_counter()
    try:
        runs = [campaign(f, a.courses, a.adversaires, a.tours, a.tour_m, a.ftp, a.mode) for f in forces]
    except CampaignError as e:
        print(f"échec : {e}", file=sys.stderr)
        return 2
    result = checks(runs)
    if a.json:
        print(json.dumps({"runs": runs, "checks": [{"ok": ok, "text": t} for ok, t in result],
                          "wall_s": round(time.perf_counter() - t0, 1)}, ensure_ascii=False, indent=1))
    else:
        print(format_text(runs, result))
        print(f"durée : {time.perf_counter() - t0:.0f} s")
    return 0 if all(ok for ok, _ in result) else 1


if __name__ == "__main__":
    sys.exit(main())
